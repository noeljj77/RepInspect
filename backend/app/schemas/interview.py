import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.interview.schemas import Category, Difficulty

ProgressStatus = Literal["new", "practicing", "confident"]
Answer = Annotated[str, StringConstraints(max_length=10_000)]


class GenerateQuestions(BaseModel):
    count: int = Field(default=8, ge=3, le=12)
    # None or empty means any category.
    categories: list[Category] | None = Field(default=None, max_length=8)
    difficulty: Difficulty | None = None


class QuestionUpdate(BaseModel):
    status: ProgressStatus | None = None
    user_answer: Answer | None = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_version: int
    category: str
    difficulty: str
    question: str
    why_asked: str
    # Checked findings: statement, citations, verified, ungrounded_paths.
    answer_points: list[dict[str, Any]]
    follow_ups: list[str]
    grounded: bool
    removed_citations: int
    status: str
    user_answer: str | None
    practiced_at: datetime | None
    created_at: datetime


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    requested_count: int
    question_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class QuestionsOut(BaseModel):
    questions: list[QuestionOut]
    # The newest request, so the page can show "writing questions" or why it failed.
    latest_batch: BatchOut | None
    # How many questions are in each progress status.
    progress: dict[str, int]
