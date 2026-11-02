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


class AnalysisDetail(AnalysisSummary):
    github_metadata: dict[str, Any] | None
    languages: dict[str, int] | None
    readme_path: str | None
    readme_text: str | None


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


class FileEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    language: str | None
    size_bytes: int
    line_count: int | None
    skipped_reason: str | None


class FileContent(BaseModel):
    path: str
    language: str | None
    size_bytes: int
    line_count: int | None
    content: str
