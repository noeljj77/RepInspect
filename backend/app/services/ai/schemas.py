"""Two families of shapes.

`Raw*` is what the model is asked to produce. It is untrusted: the grounding step checks
it against the real repository before anything is stored.

The other classes are the verified result that is stored and shown to people. Anything
the checks could not confirm is marked, never silently kept.
"""

from typing import Literal

from pydantic import BaseModel, Field

# The ten parts of an overview, in display order.
OVERVIEW_SECTIONS: list[tuple[str, str]] = [
    ("purpose", "What the project does"),
    ("problem", "The problem it solves"),
    ("technologies", "Technologies used"),
    ("architecture", "Overall architecture"),
    ("frontend", "Frontend structure"),
    ("backend", "Backend structure"),
    ("data", "Database and data flow"),
    ("modules", "Important modules and files"),
    ("running", "How the application runs"),
    ("decisions", "Important implementation decisions"),
]
SectionKey = Literal[
    "purpose", "problem", "technologies", "architecture", "frontend",
    "backend", "data", "modules", "running", "decisions",
]  # fmt: skip


# --- what the model produces (untrusted) -------------------------------------------------


class RawCitation(BaseModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str  # exact text copied from the cited lines


class RawFinding(BaseModel):
    statement: str
    citations: list[RawCitation]


class RawSection(BaseModel):
    key: SectionKey
    summary: str
    determined: bool  # false when the provided material does not say
    findings: list[RawFinding]


class RawOverview(BaseModel):
    sections: list[RawSection]


class RawTechnology(BaseModel):
    name: str
    what_it_is: str
    plausible_reason: str
    advantages: list[str]
    alternatives: list[str]
    trade_offs: list[str]


class RawTechnologies(BaseModel):
    technologies: list[RawTechnology]


class RawKeySymbol(BaseModel):
    name: str
    explanation: str


class RawFileExplanation(BaseModel):
    purpose: str
    determined: bool
    inputs_outputs: str
    findings: list[RawFinding]
    key_symbols: list[RawKeySymbol]


# --- what is stored and shown (verified) ----------------------------------------------------


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int
    quote: str


class Finding(BaseModel):
    statement: str
    # Only citations whose file exists and whose quoted text really appears there.
    citations: list[Citation]
    # True when at least one citation was confirmed. False findings are shown as inference.
    verified: bool
    # Files named in the text that are not in this repository.
    ungrounded_paths: list[str] = []


class OverviewSection(BaseModel):
    key: str
    title: str
    summary: str
    determined: bool
    findings: list[Finding]
    ungrounded_paths: list[str] = []


class OverviewContent(BaseModel):
    sections: list[OverviewSection]
    removed_citations: int = 0  # citations that could not be confirmed and were dropped


class TechnologyExplanation(BaseModel):
    name: str
    what_it_is: str
    plausible_reason: str
    advantages: list[str]
    alternatives: list[str]
    trade_offs: list[str]


class TechnologiesContent(BaseModel):
    technologies: list[TechnologyExplanation]


class KeySymbol(BaseModel):
    name: str
    qualified_name: str
    kind: str
    start_line: int
    explanation: str


class FileExplanationContent(BaseModel):
    purpose: str
    determined: bool
    inputs_outputs: str
    findings: list[Finding]
    key_symbols: list[KeySymbol]
    ungrounded_paths: list[str] = []
    removed_citations: int = 0
