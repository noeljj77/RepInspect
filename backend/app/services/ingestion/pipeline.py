"""The background job that imports one GitHub repository.

    queued → fetching (GitHub API + download) → extracting (unpack, filter, store) → completed

Any failure ends in `failed` with a user-readable message. Repository code is only
ever read as text; nothing from it is executed.
"""

import logging
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisFile, AnalysisStatus, RepositoryAnalysis, SavedRepository
from app.services.ingestion.archive import ExtractionLimits, ExtractionResult, extract_tar_gz
from app.services.ingestion.errors import IngestionError, RepositoryEmpty
from app.services.ingestion.github_client import GitHubClient
from app.storage import artifacts

logger = logging.getLogger(__name__)

README_NAME = re.compile(r"readme(\.(md|markdown|rst|txt))?", re.IGNORECASE)
MAX_README_CHARS = 200_000
GENERIC_FAILURE = "Something went wrong while analyzing this repository. Try again in a moment."


def create_github_client() -> GitHubClient:
    """Separate function so tests can substitute a client with a fake network."""
    return GitHubClient.from_settings()


def run_github_analysis(analysis_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        analysis = db.get(RepositoryAnalysis, analysis_id)
        if analysis is None or analysis.status != AnalysisStatus.QUEUED:
            return  # already handled, or deleted in the meantime
        repository = db.get(SavedRepository, analysis.saved_repository_id)
        try:
            _import_repository(db, analysis, repository)
        except IngestionError as error:
            _mark_failed(db, analysis_id, error.code, error.message)
        except Exception:
            logger.exception("Analysis %s failed unexpectedly", analysis_id)
            _mark_failed(db, analysis_id, "internal_error", GENERIC_FAILURE)


def _import_repository(
    db: Session, analysis: RepositoryAnalysis, repository: SavedRepository
) -> None:
    settings = get_settings()
    owner, name = repository.owner, repository.name

    analysis.status = AnalysisStatus.FETCHING
    analysis.started_at = datetime.now(UTC)
    db.commit()

    with create_github_client() as github, tempfile.TemporaryDirectory(prefix="repinspect-") as tmp:
        metadata = github.get_repository(owner, name)
        sha = github.get_head_commit(owner, name, metadata["default_branch"])
        try:
            languages = github.get_languages(owner, name)
        except IngestionError:
            languages = {}  # nice to have, not worth failing the analysis for

        analysis.github_metadata = metadata
        analysis.languages = languages
        analysis.commit_sha = sha
        # Show GitHub's capitalization (e.g. "Pallets/Flask") in the library.
        canonical_owner, _, canonical_name = metadata["full_name"].partition("/")
        repository.owner, repository.name = canonical_owner, canonical_name
        analysis.status = AnalysisStatus.EXTRACTING
        db.commit()

        archive_path = Path(tmp) / "repository.tar.gz"
        github.download_tarball(owner, name, sha, archive_path)

        staging = artifacts.staging_dir(analysis.id)
        artifacts.remove_analysis(analysis.id)  # clear leftovers from a crashed earlier run
        result = extract_tar_gz(archive_path, staging, ExtractionLimits.from_settings(settings))

    if result.kept_count == 0:
        raise RepositoryEmpty("This repository has no readable source files to analyze.")

    readme_path, readme_text = _read_readme(staging, result)
    artifacts.publish_staging(analysis.id)
    _store_results(db, analysis, result, readme_path, readme_text)


def _read_readme(directory: Path, result: ExtractionResult) -> tuple[str | None, str | None]:
    candidates = [f for f in result.kept if "/" not in f.path and README_NAME.fullmatch(f.path)]
    if not candidates:
        return None, None
    # Prefer Markdown over reStructuredText or plain text.
    candidates.sort(key=lambda f: (not f.path.lower().endswith((".md", ".markdown")), f.path))
    chosen = candidates[0].path
    text = (directory / chosen).read_text(encoding="utf-8")
    return chosen, text[:MAX_README_CHARS]


def _store_results(
    db: Session,
    analysis: RepositoryAnalysis,
    result: ExtractionResult,
    readme_path: str | None,
    readme_text: str | None,
) -> None:
    db.execute(delete(AnalysisFile).where(AnalysisFile.analysis_id == analysis.id))
    db.execute(
        insert(AnalysisFile),
        [
            {
                "id": uuid.uuid4(),
                "analysis_id": analysis.id,
                "path": f.path,
                "language": f.language,
                "size_bytes": f.size_bytes,
                "line_count": f.line_count,
                "skipped_reason": f.skipped_reason,
            }
            for f in result.files
        ],
    )
    analysis.file_count = result.kept_count
    analysis.total_bytes = result.total_bytes
    analysis.skipped_summary = result.skipped_counts
    analysis.redaction_count = result.redaction_count
    analysis.truncated = result.truncated
    analysis.readme_path = readme_path
    analysis.readme_text = readme_text
    analysis.status = AnalysisStatus.COMPLETED
    analysis.completed_at = datetime.now(UTC)
    db.commit()


def _mark_failed(db: Session, analysis_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    analysis = db.get(RepositoryAnalysis, analysis_id)
    if analysis is not None:
        analysis.status = AnalysisStatus.FAILED
        analysis.error_code = code
        analysis.error_message = message
        analysis.completed_at = datetime.now(UTC)
        db.commit()
    artifacts.remove_analysis(analysis_id)
