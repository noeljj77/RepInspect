"""The user's repository library: saving repositories and starting analyses.

Every function here takes the owning user's id and filters by it. Callers never pass
a bare repository id without one, which is what keeps users' data separate.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    IN_PROGRESS_STATUSES,
    AnalysisStatus,
    RepositoryAnalysis,
    SavedRepository,
)
from app.services.ingestion.github_url import RepoRef

_IN_PROGRESS = [status.value for status in IN_PROGRESS_STATUSES]


def get_owned(db: Session, user_id: uuid.UUID, repository_id: uuid.UUID) -> SavedRepository | None:
    return db.scalar(
        select(SavedRepository).where(
            SavedRepository.id == repository_id, SavedRepository.user_id == user_id
        )
    )


def get_or_create_github(db: Session, user_id: uuid.UUID, ref: RepoRef) -> SavedRepository:
    """Return the user's library entry for this repository, creating it if needed."""
    existing = _find_github(db, user_id, ref)
    if existing is not None:
        return existing

    repository = SavedRepository(
        user_id=user_id,
        source_type="github",
        source_key=ref.key,
        source_url=ref.url,
        owner=ref.owner,
        name=ref.name,
    )
    db.add(repository)
    try:
        db.commit()
    except IntegrityError:
        # Two requests saved the same repository at once; the constraint kept one.
        db.rollback()
        existing = _find_github(db, user_id, ref)
        if existing is None:
            raise
        return existing
    return repository


def _find_github(db: Session, user_id: uuid.UUID, ref: RepoRef) -> SavedRepository | None:
    return db.scalar(
        select(SavedRepository).where(
            SavedRepository.user_id == user_id, SavedRepository.source_key == ref.key
        )
    )


def latest_analysis(db: Session, repository_id: uuid.UUID) -> RepositoryAnalysis | None:
    return db.scalar(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.saved_repository_id == repository_id)
        .order_by(RepositoryAnalysis.version.desc())
        .limit(1)
    )


def latest_analyses(
    db: Session, repository_ids: list[uuid.UUID]
) -> dict[uuid.UUID, RepositoryAnalysis]:
    """Newest analysis for each repository, in one query."""
    if not repository_ids:
        return {}
    # PostgreSQL's DISTINCT ON keeps the first row per repository in the ORDER BY,
    # which is the highest version.
    rows = db.scalars(
        select(RepositoryAnalysis)
        .ext(distinct_on(RepositoryAnalysis.saved_repository_id))
        .where(RepositoryAnalysis.saved_repository_id.in_(repository_ids))
        .order_by(RepositoryAnalysis.saved_repository_id, RepositoryAnalysis.version.desc())
    )
    return {row.saved_repository_id: row for row in rows}


def list_for_user(db: Session, user_id: uuid.UUID) -> list[SavedRepository]:
    return list(
        db.scalars(
            select(SavedRepository)
            .where(SavedRepository.user_id == user_id)
            .order_by(SavedRepository.created_at.desc())
        )
    )


def active_analysis_count(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(RepositoryAnalysis)
            .join(SavedRepository, SavedRepository.id == RepositoryAnalysis.saved_repository_id)
            .where(SavedRepository.user_id == user_id, RepositoryAnalysis.status.in_(_IN_PROGRESS))
        )
        or 0
    )


def create_analysis(db: Session, repository: SavedRepository) -> RepositoryAnalysis:
    """Add the next version of this repository's analysis in the `queued` state."""
    for _ in range(2):
        previous = latest_analysis(db, repository.id)
        analysis = RepositoryAnalysis(
            saved_repository_id=repository.id,
            version=(previous.version + 1) if previous else 1,
            status=AnalysisStatus.QUEUED.value,
        )
        db.add(analysis)
        try:
            db.commit()
            return analysis
        except IntegrityError:
            db.rollback()  # another request took this version number; try the next one
    raise RuntimeError("Could not allocate an analysis version")


def mark_interrupted(db: Session) -> int:
    """Fail analyses left in progress by a previous server process.

    Their background threads died with the old process, so nothing will ever finish
    them. (This assumes a single API process; a multi-process deployment would need a
    heartbeat instead.)
    """
    result = db.execute(
        update(RepositoryAnalysis)
        .where(RepositoryAnalysis.status.in_(_IN_PROGRESS))
        .values(
            status=AnalysisStatus.FAILED.value,
            error_code="interrupted",
            error_message=(
                "The server restarted while this repository was being analyzed. Try again."
            ),
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return result.rowcount or 0
