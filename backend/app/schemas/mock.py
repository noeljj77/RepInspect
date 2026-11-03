import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.interview.schemas import Category, Difficulty

AnswerText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]


class StartInterview(BaseModel):
    question_count: int = Field(default=5, ge=3, le=8)
    categories: list[Category] | None = Field(default=None, max_length=8)
    difficulty: Difficulty | None = None


class AnswerIn(BaseModel):
    answer: AnswerText


class TurnOut(BaseModel):
    """A question and its result. The expected answer is never sent before grading:
    it only appears as the missed points of the grade."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    kind: str
    prompt: str
    category: str
    difficulty: str
    status: str
    answer: str | None
    score: int | None
    grade: dict[str, Any] | None
    error_message: str | None
    asked_at: datetime | None
    answered_at: datetime | None
    graded_at: datetime | None


class InterviewSummary(BaseModel):
    id: uuid.UUID
    status: str
    question_count: int
    percent: int | None
    created_at: datetime
    completed_at: datetime | None


class InterviewOut(BaseModel):
    id: uuid.UUID
    status: str
    question_count: int
    # Main questions asked so far (follow-ups not counted).
    asked: int
    categories: list[str] | None
    difficulty: str | None
    report: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    turns: list[TurnOut]
