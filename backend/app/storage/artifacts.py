"""Where large analysis outputs live on disk: source snapshots and search indexes.

Layout:  <artifact_dir>/<analysis id>/source/<repo files...>
         <artifact_dir>/<analysis id>/index/vectors.faiss
         <artifact_dir>/uploads/<analysis id>.zip     (an uploaded ZIP until it is extracted)

Postgres stores the records; the bytes live here, behind this small interface so the
storage backend can change (for example to S3) without touching callers.
"""

import os
import shutil
import uuid
from pathlib import Path

from app.core.config import get_settings


def _analysis_dir(analysis_id: uuid.UUID) -> Path:
    return get_settings().artifact_dir / str(analysis_id)


def staging_dir(analysis_id: uuid.UUID) -> Path:
    """Where files are written while an import is running."""
    return _analysis_dir(analysis_id) / "source.partial"


def source_dir(analysis_id: uuid.UUID) -> Path:
    return _analysis_dir(analysis_id) / "source"


def index_dir(analysis_id: uuid.UUID) -> Path:
    return _analysis_dir(analysis_id) / "index"


def publish_staging(analysis_id: uuid.UUID) -> None:
    """Make a finished import visible. The rename is atomic: no half-written snapshots."""
    os.replace(staging_dir(analysis_id), source_dir(analysis_id))


def upload_dir() -> Path:
    return get_settings().artifact_dir / "uploads"


def upload_path(analysis_id: uuid.UUID) -> Path:
    return upload_dir() / f"{analysis_id}.zip"


def remove_upload(analysis_id: uuid.UUID) -> None:
    upload_path(analysis_id).unlink(missing_ok=True)


def remove_staging(analysis_id: uuid.UUID) -> None:
    shutil.rmtree(staging_dir(analysis_id), ignore_errors=True)


def remove_analysis(analysis_id: uuid.UUID) -> None:
    shutil.rmtree(_analysis_dir(analysis_id), ignore_errors=True)


def read_source_file(analysis_id: uuid.UUID, relative_path: str) -> bytes | None:
    """Read one stored file, or None if it does not exist or the path escapes the snapshot."""
    root = source_dir(analysis_id).resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target.read_bytes()
