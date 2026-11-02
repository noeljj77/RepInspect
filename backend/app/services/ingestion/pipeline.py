"""The background job that imports one GitHub repository.

    queued → fetching (GitHub API + download) → extracting (unpack, filter, store)
           → analyzing (parse code, dependencies, frameworks) → completed

Any failure ends in `failed` with a user-readable message. Repository code is only
ever read as text; nothing from it is executed.
"""

import logging
import re
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models import (
    AnalysisFile,
    AnalysisStatus,
    CodeImport,
    CodeSymbol,
    ProjectDependency,
    RepositoryAnalysis,
    SavedRepository,
)
from app.services.analysis.runner import AnalysisOutput, SourceFile, analyze_directory
from app.services.ingestion.archive import ExtractionLimits, ExtractionResult, extract_tar_gz
from app.services.ingestion.errors import IngestionError, RepositoryEmpty
from app.services.ingestion.github_client import GitHubClient
from app.storage import artifacts

logger = logging.getLogger(__name__)

README_NAME = re.compile(r"readme(\.(md|markdown|rst|txt))?", re.IGNORECASE)
MAX_README_CHARS = 200_000
GENERIC_FAILURE = "Something went wrong while analyzing this repository. Try again in a moment."


@contextmanager
def _timed(timings: dict[str, float], stage: str) -> Iterator[None]:
    """Record how long a stage took, so a slow import can be traced from the logs."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] = timings.get(stage, 0.0) + time.perf_counter() - start


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
    timings: dict[str, float] = {}

    analysis.status = AnalysisStatus.FETCHING
    analysis.started_at = datetime.now(UTC)
    db.commit()

    with create_github_client() as github, tempfile.TemporaryDirectory(prefix="repinspect-") as tmp:
        with _timed(timings, "github_api"):
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
        with _timed(timings, "download"):
            github.download_tarball(owner, name, sha, archive_path)

        staging = artifacts.staging_dir(analysis.id)
        artifacts.remove_analysis(analysis.id)  # clear leftovers from a crashed earlier run
        with _timed(timings, "extract"):
            result = extract_tar_gz(archive_path, staging, ExtractionLimits.from_settings(settings))

    if result.kept_count == 0:
        raise RepositoryEmpty("This repository has no readable source files to analyze.")

    analysis.status = AnalysisStatus.ANALYZING
    db.commit()
    readme_path, readme_text = _read_readme(staging, result)
    with _timed(timings, "analyze"):
        output = _run_static_analysis(staging, result)
    artifacts.publish_staging(analysis.id)
    with _timed(timings, "store"):
        _store_results(db, analysis, result, output, readme_path, readme_text)

    logger.info(
        "Analysis %s done: %d files, %s",
        analysis.id,
        result.kept_count,
        ", ".join(f"{stage} {seconds:.1f}s" for stage, seconds in timings.items()),
    )


def _run_static_analysis(directory: Path, result: ExtractionResult) -> AnalysisOutput | None:
    """Parse the stored files. If this fails the import still succeeds, without code insight."""
    files = [
        SourceFile(f.path, f.language, f.size_bytes, f.line_count or 0)
        for f in result.files
        if f.skipped_reason is None
    ]
    try:
        return analyze_directory(directory, files)
    except Exception:
        logger.exception("Static analysis failed")
        return None


def _read_readme(directory: Path, result: ExtractionResult) -> tuple[str | None, str | None]:
    candidates = [f for f in result.kept if "/" not in f.path and README_NAME.fullmatch(f.path)]
    if not candidates:
        return None, None
    # Prefer Markdown over reStructuredText or plain text.
    candidates.sort(key=lambda f: (not f.path.lower().endswith((".md", ".markdown")), f.path))
    chosen = candidates[0].path
    text = (directory / chosen).read_text(encoding="utf-8")
    return chosen, text[:MAX_README_CHARS]


def _insert_all(db: Session, model: type[Base], rows: list[dict]) -> None:
    """Insert many rows quickly.

    The RETURNING clause is there on purpose: it makes SQLAlchemy send many rows per
    INSERT statement. Without it the driver sends rows one by one, and when a nullable
    column is sometimes NULL and sometimes text (like a docstring) it re-prepares the
    statement every time the type flips. That took 11 s for 1,400 rows; this takes 0.2 s.
    """
    for start in range(0, len(rows), 2000):
        db.execute(insert(model).returning(model.id), rows[start : start + 2000])


def _store_results(
    db: Session,
    analysis: RepositoryAnalysis,
    result: ExtractionResult,
    output: AnalysisOutput | None,
    readme_path: str | None,
    readme_text: str | None,
) -> None:
    db.execute(delete(AnalysisFile).where(AnalysisFile.analysis_id == analysis.id))
    file_ids = {f.path: uuid.uuid4() for f in result.files}

    file_rows = []
    for f in result.files:
        found = output.files.get(f.path) if output else None
        parsed = found.analysis if found else None
        file_rows.append(
            {
                "id": file_ids[f.path],
                "analysis_id": analysis.id,
                "path": f.path,
                "language": f.language,
                "size_bytes": f.size_bytes,
                "line_count": f.line_count,
                "skipped_reason": f.skipped_reason,
                "importance_score": found.importance_score if found else 0,
                "importance_reasons": (found.importance_reasons or None) if found else None,
                "symbol_count": len(parsed.symbols) if parsed else 0,
                "parse_error": parsed.parse_error if parsed else False,
            }
        )
    _insert_all(db, AnalysisFile, file_rows)  # files first: later rows point at them

    if output is not None:
        _store_analysis_rows(db, analysis, output, file_ids)
        analysis.technologies = [asdict(tech) for tech in output.technologies]
        analysis.code_stats = output.stats

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


def _store_analysis_rows(
    db: Session,
    analysis: RepositoryAnalysis,
    output: AnalysisOutput,
    file_ids: dict[str, uuid.UUID],
) -> None:
    symbols, imports = [], []
    for path, found in output.files.items():
        for symbol in found.analysis.symbols if found.analysis else []:
            symbols.append(
                {
                    "id": uuid.uuid4(),
                    "analysis_id": analysis.id,
                    "file_id": file_ids[path],
                    "kind": symbol.kind,
                    "name": symbol.name,
                    "qualified_name": symbol.qualified_name,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "signature": symbol.signature,
                    "doc": symbol.doc,
                    "decorators": symbol.decorators or None,
                }
            )

    for item in output.imports:
        # An import of several names can reach several files; each gets its own row.
        for target in item.targets or [None]:
            imports.append(
                {
                    "id": uuid.uuid4(),
                    "analysis_id": analysis.id,
                    "file_id": file_ids[item.path],
                    "module": item.ref.module,
                    "names": item.ref.names or None,
                    "line": item.ref.line,
                    "resolved_file_id": file_ids[target] if target else None,
                }
            )

    dependencies = [
        {
            "id": uuid.uuid4(),
            "analysis_id": analysis.id,
            "ecosystem": dep.ecosystem,
            "name": dep.name,
            "version_spec": dep.version_spec,
            "scope": dep.scope,
            "source_file": dep.source_file,
            "line": dep.line,
        }
        for dep in output.dependencies
    ]
    _insert_all(db, CodeSymbol, symbols)
    _insert_all(db, CodeImport, imports)
    _insert_all(db, ProjectDependency, dependencies)


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
