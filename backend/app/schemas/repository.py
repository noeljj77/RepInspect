import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    url: str = Field(max_length=500)


class RepositoryUpdate(BaseModel):
    labels: list[str] = Field(max_length=50)


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
    # Its stored files were removed after a newer version replaced it (see refresh history).
    source_removed: bool = False
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


class LanguageShare(BaseModel):
    name: str
    share: float  # of the lines of code, 0 to 1


class RepositorySummary(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str | None
    owner: str | None
    name: str
    labels: list[str]
    collection_ids: list[uuid.UUID]
    description: str | None
    created_at: datetime
    latest_analysis: AnalysisSummary | None
    # From the latest analysis, for the library list: the main languages and the size.
    languages: list[LanguageShare] = []
    code_lines: int | None = None


class RepositoryDetail(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str | None
    owner: str | None
    name: str
    labels: list[str]
    collection_ids: list[uuid.UUID]
    created_at: datetime
    # The newest version, whatever its status (it may be a refresh still running).
    latest_analysis: AnalysisDetail | None
    # The newest version that finished: what the page shows. Equal to latest_analysis
    # unless a refresh is running or failed.
    current_analysis: AnalysisDetail | None = None
    important_files: list[ImportantFile] = []


class PathChangesOut(BaseModel):
    count: int
    paths: list[str]  # at most the first 100, sorted


class ChangesOut(BaseModel):
    added: PathChangesOut
    removed: PathChangesOut
    modified: PathChangesOut
    unchanged: int
    exact: bool
    technologies_added: list[str]
    technologies_removed: list[str]
    dependencies_added: list[str]
    dependencies_removed: list[str]
    dependencies_changed: list[str]


class VersionChanges(BaseModel):
    """What changed in one version compared with the version before it."""

    version: int
    previous_version: int | None
    previous_commit_sha: str | None
    changes: ChangesOut | None


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
