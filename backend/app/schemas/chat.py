import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class IndexOut(BaseModel):
    # "missing" (never built), "pending", "building", "ready" or "failed"
    status: str
    chunk_count: int = 0
    chunks_embedded: int = 0
    truncated: bool = False
    model: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class AskIn(BaseModel):
    question: Question


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    # "pending", "completed" or "failed" (questions are always "completed")
    status: str
    content: str
    # For answers: answerable, citations, sources, removed_citations, ungrounded_paths.
    details: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    model: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ChatSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatOut(ChatSummary):
    messages: list[MessageOut]
