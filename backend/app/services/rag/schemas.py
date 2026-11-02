"""What the model is asked for (untrusted) and what is stored after checking."""

from pydantic import BaseModel, Field

from app.services.ai.schemas import Citation, RawCitation


class RawChatAnswer(BaseModel):
    # The descriptions are part of the schema the model receives.
    answerable: bool = Field(description="False when the excerpts do not contain the answer.")
    answer: str = Field(
        description="Plain text. Every statement about the code ends with a marker such as [1] "
        "or [2] that refers to the citations list (1 is the first citation)."
    )
    citations: list[RawCitation] = Field(
        description="Evidence for the answer, in the order the markers refer to it."
    )


class Source(BaseModel):
    """An excerpt that was found by search and given to the model."""

    path: str
    start_line: int
    end_line: int
    symbol: str | None
    matched_by: list[str]


class ChatAnswer(BaseModel):
    answerable: bool
    # Markers are renumbered to match `citations`; markers for dropped citations are removed.
    answer: str
    citations: list[Citation]
    # Citations the model gave that could not be confirmed in the code.
    removed_citations: int = 0
    # Files the answer names that are not in this repository.
    ungrounded_paths: list[str] = []
    sources: list[Source] = []
