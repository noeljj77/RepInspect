import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    url: str = Field(max_length=500)


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    status: str
    error_code: str | None
    error_message: str | None
    commit_sha: str | None
    file_count: int
    total_bytes: int
    skipped_summary: dict[str, int] | None
    redaction_count: int
    truncated: bool
    created_at: datetime
    completed_at: datetime | None


class EvidenceOut(BaseModel):
    kind: str  # dependency, import or file
    path: str
    line: int | None
    detail: str
    scope: str | None = None  # for dependencies: runtime, dev, optional...


class TechnologyOut(BaseModel):
    name: str
    category: str
    evidence: list[EvidenceOut]
    # Only a development dependency, used only from tests. Absent in older analyses.
    dev_only: bool = False


class AnalysisDetail(AnalysisSummary):
    github_metadata: dict[str, Any] | None
    languages: dict[str, int] | None
    technologies: list[TechnologyOut] | None
    code_stats: dict[str, Any] | None
    readme_path: str | None
    readme_text: str | None


class ImportantFile(BaseModel):
    path: str
    language: str | None
    score: int
    reasons: list[str]


class RepositorySummary(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str | None
    owner: str | None
    name: str
    label: str | None
    description: str | None
    created_at: datetime
    latest_analysis: AnalysisSummary | None


class RepositoryDetail(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str | None
    owner: str | None
    name: str
    label: str | None
    created_at: datetime
    latest_analysis: AnalysisDetail | None
    important_files: list[ImportantFile] = []


class FileEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    language: str | None
    size_bytes: int
    line_count: int | None
    skipped_reason: str | None
    importance_score: int
    symbol_count: int
    parse_error: bool


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    signature: str
    doc: str | None
    decorators: list[str] | None


class SymbolMatch(SymbolOut):
    path: str


class ImportOut(BaseModel):
    module: str
    names: list[str]
    line: int
    # Set when the import points at another file in this repository.
    resolved_path: str | None


class FileContent(BaseModel):
    path: str
    language: str | None
    size_bytes: int
    line_count: int | None
    content: str
    parse_error: bool
    importance_reasons: list[str]
    symbols: list[SymbolOut]
    imports: list[ImportOut]
    imported_by: list[str]


class DependencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ecosystem: str
    name: str
    version_spec: str | None
    scope: str
    source_file: str
    line: int | None
