"""The grade of one answer: what the model returns (untrusted) and what is stored."""

from typing import Literal

from pydantic import BaseModel, Field

from app.services.ai.schemas import Citation, Finding, RawCitation

Verdict = Literal["supported", "contradicted", "not_found"]

SCORE_LABELS = {0: "No answer", 1: "Incorrect", 2: "Partial", 3: "Good", 4: "Excellent"}


class RawClaim(BaseModel):
    claim: str = Field(description="A specific statement the candidate made about the code.")
    verdict: Verdict
    citations: list[RawCitation] = Field(
        description="Evidence for 'supported' or 'contradicted'. Empty for 'not_found'."
    )


class RawGrade(BaseModel):
    score: int = Field(
        description="0 no real answer, 1 mostly wrong, 2 partial, 3 good, 4 excellent."
    )
    summary: str = Field(
        description="One or two sentences of feedback, addressed to the candidate."
    )
    strengths: list[str]
    gaps: list[str]
    claims: list[RawClaim]
    covered_points: list[int] = Field(
        description="Numbers of the reference points the answer covered, starting at 1."
    )
    follow_up: str = Field(
        description="One probing question about the most important gap, or an empty string."
    )


class ClaimCheck(BaseModel):
    claim: str
    # "unverified" when the model's evidence for supported/contradicted did not check out.
    verdict: Literal["supported", "contradicted", "not_found", "unverified"]
    citations: list[Citation]


class Grade(BaseModel):
    score: int
    label: str
    summary: str
    strengths: list[str]
    gaps: list[str]
    claims: list[ClaimCheck]
    # Reference points the answer did not cover, with their evidence from the code.
    missed_points: list[Finding]
    follow_up: str | None
    removed_citations: int = 0
