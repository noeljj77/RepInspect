"""What the model is asked to produce for interview questions (untrusted until checked)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.services.ai.schemas import RawFinding

# In display order, with the name people see.
CATEGORIES: dict[str, str] = {
    "architecture": "Architecture",
    "implementation": "Implementation",
    "technologies": "Technology choices",
    "data": "Data and storage",
    "testing": "Testing and quality",
    "security": "Security",
    "performance": "Performance and scaling",
    "trade_offs": "Trade-offs and improvements",
}
Category = Literal[
    "architecture", "implementation", "technologies", "data",
    "testing", "security", "performance", "trade_offs",
]  # fmt: skip
Difficulty = Literal["basic", "intermediate", "advanced"]


class RawQuestion(BaseModel):
    question: str
    category: Category
    difficulty: Difficulty
    why_asked: str = Field(description="What the interviewer wants to find out, in one sentence.")
    answer_points: list[RawFinding] = Field(
        description="The points a strong answer covers, each backed by citations from the code."
    )
    follow_ups: list[str] = Field(description="Up to three likely follow-up questions.")


class RawQuestions(BaseModel):
    questions: list[RawQuestion]
