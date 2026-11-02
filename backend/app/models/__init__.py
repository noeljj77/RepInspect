"""ORM models. Import every model module here so Alembic autogenerate can see it."""

from app.db.base import Base
from app.models.ai_explanation import AiExplanation, AiKind, AiStatus
from app.models.ai_request import AiRequest
from app.models.analysis_file import AnalysisFile
from app.models.code_analysis import CodeImport, CodeSymbol, ProjectDependency
from app.models.repository_analysis import (
    IN_PROGRESS_STATUSES,
    AnalysisStatus,
    RepositoryAnalysis,
)
from app.models.saved_repository import SavedRepository
from app.models.user import User

__all__ = [
    "IN_PROGRESS_STATUSES",
    "AiExplanation",
    "AiKind",
    "AiRequest",
    "AiStatus",
    "AnalysisFile",
    "AnalysisStatus",
    "Base",
    "CodeImport",
    "CodeSymbol",
    "ProjectDependency",
    "RepositoryAnalysis",
    "SavedRepository",
    "User",
]
