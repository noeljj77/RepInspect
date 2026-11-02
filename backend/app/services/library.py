"""Managing a library: labels, deleting repositories, uploads and the history of versions."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    IN_PROGRESS_STATUSES,
    AnalysisFile,
    AnalysisStatus,
    CollectionRepository,
    ProjectDependency,
    RepositoryAnalysis,
    SavedRepository,
)
from app.services.rag import vector_store
from app.storage import artifacts

MAX_LABELS = 10
MAX_LABEL_CHARS = 40
MAX_LISTED_CHANGES = 100  # paths listed per kind of change; the counts are always complete


class InvalidLabels(ValueError):
    pass


def normalize_labels(labels: list[str]) -> list[str]:
    """Trimmed, single-spaced and without duplicates (ignoring case), in the given order."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in labels:
        label = " ".join(raw.split())
        if not label:
            continue
        if len(label) > MAX_LABEL_CHARS:
            raise InvalidLabels(f"Labels can be at most {MAX_LABEL_CHARS} characters long.")
        if label.casefold() not in seen:
            seen.add(label.casefold())
            cleaned.append(label)
    if len(cleaned) > MAX_LABELS:
        raise InvalidLabels(f"A repository can have at most {MAX_LABELS} labels.")
    return cleaned


def collection_ids(
    db: Session, repository_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """The collections each repository is in, in one query."""
    found: dict[uuid.UUID, list[uuid.UUID]] = {rid: [] for rid in repository_ids}
    if repository_ids:
        rows = db.execute(
            select(CollectionRepository.saved_repository_id, CollectionRepository.collection_id)
            .where(CollectionRepository.saved_repository_id.in_(repository_ids))
            .order_by(CollectionRepository.added_at)
        )
        for repository_id, collection_id in rows:
            found[repository_id].append(collection_id)
    return found


def latest_completed(db: Session, repository_id: uuid.UUID) -> RepositoryAnalysis | None:
    """The newest version that finished. A refresh in progress (or one that failed) does
    not replace it until the new version is complete."""
    return db.scalar(
        select(RepositoryAnalysis)
        .where(
            RepositoryAnalysis.saved_repository_id == repository_id,
            RepositoryAnalysis.status == AnalysisStatus.COMPLETED,
        )
        .order_by(RepositoryAnalysis.version.desc())
        .limit(1)
    )


def is_busy(db: Session, repository_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(RepositoryAnalysis.id).where(
                RepositoryAnalysis.saved_repository_id == repository_id,
                RepositoryAnalysis.status.in_([s.value for s in IN_PROGRESS_STATUSES]),
            )
        )
        is not None
    )


def delete_repository(db: Session, repository: SavedRepository) -> None:
    """Remove a repository with everything that belongs to it, on disk too.

    The database removes the dependent rows itself (ON DELETE CASCADE): analyses, files,
    symbols, chunks, explanations, conversations, notes and collection memberships. The
    AI usage log is kept, so deleting does not give the daily allowance back.
    """
    analysis_ids = list(
        db.scalars(
            select(RepositoryAnalysis.id).where(
                RepositoryAnalysis.saved_repository_id == repository.id
            )
        )
    )
    db.delete(repository)
    db.commit()
    for analysis_id in analysis_ids:
        artifacts.remove_analysis(analysis_id)
        artifacts.remove_upload(analysis_id)
        vector_store.forget(analysis_id)


def history(db: Session, repository_id: uuid.UUID) -> list[RepositoryAnalysis]:
    return list(
        db.scalars(
            select(RepositoryAnalysis)
            .where(RepositoryAnalysis.saved_repository_id == repository_id)
            .order_by(RepositoryAnalysis.version.desc())
        )
    )


# --- comparing two versions -------------------------------------------------------------------


@dataclass
class PathChanges:
    count: int = 0
    paths: list[str] = field(default_factory=list)

    def add(self, path: str) -> None:
        self.count += 1
        if len(self.paths) < MAX_LISTED_CHANGES:
            self.paths.append(path)


@dataclass
class Changes:
    added: PathChanges = field(default_factory=PathChanges)
    removed: PathChanges = field(default_factory=PathChanges)
    modified: PathChanges = field(default_factory=PathChanges)
    unchanged: int = 0
    # False when one version predates content hashes, so "modified" is judged by size.
    exact: bool = True
    technologies_added: list[str] = field(default_factory=list)
    technologies_removed: list[str] = field(default_factory=list)
    dependencies_added: list[str] = field(default_factory=list)
    dependencies_removed: list[str] = field(default_factory=list)
    dependencies_changed: list[str] = field(default_factory=list)


def previous_completed(db: Session, analysis: RepositoryAnalysis) -> RepositoryAnalysis | None:
    return db.scalar(
        select(RepositoryAnalysis)
        .where(
            RepositoryAnalysis.saved_repository_id == analysis.saved_repository_id,
            RepositoryAnalysis.status == AnalysisStatus.COMPLETED,
            RepositoryAnalysis.version < analysis.version,
        )
        .order_by(RepositoryAnalysis.version.desc())
        .limit(1)
    )


def _files(db: Session, analysis_id: uuid.UUID) -> dict[str, tuple[str | None, int]]:
    rows = db.execute(
        select(AnalysisFile.path, AnalysisFile.content_hash, AnalysisFile.size_bytes).where(
            AnalysisFile.analysis_id == analysis_id, AnalysisFile.skipped_reason.is_(None)
        )
    )
    return {path: (digest, size) for path, digest, size in rows}


def _dependencies(db: Session, analysis_id: uuid.UUID) -> dict[str, str | None]:
    rows = db.execute(
        select(
            ProjectDependency.ecosystem, ProjectDependency.name, ProjectDependency.version_spec
        ).where(ProjectDependency.analysis_id == analysis_id)
    )
    return {f"{name} ({ecosystem})": spec for ecosystem, name, spec in rows}


def compare(db: Session, older: RepositoryAnalysis, newer: RepositoryAnalysis) -> Changes:
    changes = Changes()
    before, after = _files(db, older.id), _files(db, newer.id)
    for path in sorted(after.keys() - before.keys()):
        changes.added.add(path)
    for path in sorted(before.keys() - after.keys()):
        changes.removed.add(path)
    for path in sorted(before.keys() & after.keys()):
        (old_hash, old_size), (new_hash, new_size) = before[path], after[path]
        if old_hash and new_hash:
            different = old_hash != new_hash
        else:
            changes.exact = False
            different = old_size != new_size
        if different:
            changes.modified.add(path)
        else:
            changes.unchanged += 1

    old_tech = {t["name"] for t in older.technologies or []}
    new_tech = {t["name"] for t in newer.technologies or []}
    changes.technologies_added = sorted(new_tech - old_tech)
    changes.technologies_removed = sorted(old_tech - new_tech)

    old_deps, new_deps = _dependencies(db, older.id), _dependencies(db, newer.id)
    changes.dependencies_added = sorted(new_deps.keys() - old_deps.keys())
    changes.dependencies_removed = sorted(old_deps.keys() - new_deps.keys())
    changes.dependencies_changed = sorted(
        f"{name}: {old_deps[name] or 'any'} → {new_deps[name] or 'any'}"
        for name in old_deps.keys() & new_deps.keys()
        if old_deps[name] != new_deps[name]
    )
    return changes
