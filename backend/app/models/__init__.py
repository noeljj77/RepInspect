"""ORM models. Import every model module here so Alembic autogenerate can see it."""

from app.db.base import Base
from app.models.ai_explanation import AiExplanation, AiKind, AiStatus
from app.models.ai_request import AiRequest
from app.models.analysis_file import AnalysisFile
from app.models.chat import ChatMessage, ChatSession, MessageStatus
from app.models.code_analysis import CodeImport, CodeSymbol, ProjectDependency
from app.models.interview import BatchStatus, InterviewQuestion, Progress, QuestionBatch
from app.models.library import Collection, CollectionRepository, RepositoryNote
from app.models.mock_interview import InterviewStatus, MockInterview, MockTurn, TurnStatus
from app.models.repository_analysis import (
    IN_PROGRESS_STATUSES,
    AnalysisStatus,
    RepositoryAnalysis,
)
from app.models.saved_repository import SavedRepository
from app.models.search import CodeChunk, IndexStatus, SearchIndex
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
    "BatchStatus",
    "ChatMessage",
    "ChatSession",
    "CodeChunk",
    "CodeImport",
    "CodeSymbol",
    "Collection",
    "CollectionRepository",
    "IndexStatus",
    "InterviewQuestion",
    "InterviewStatus",
    "MessageStatus",
    "MockInterview",
    "MockTurn",
    "Progress",
    "ProjectDependency",
    "QuestionBatch",
    "RepositoryAnalysis",
    "RepositoryNote",
    "SavedRepository",
    "SearchIndex",
    "TurnStatus",
    "User",
]
