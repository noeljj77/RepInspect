"""Failures during ingestion.

Each error has a stable `code` (stored on the analysis, used by the frontend) and a
`message` written for end users. Messages never include internal details.
"""


class IngestionError(Exception):
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidRepositoryUrl(IngestionError):
    code = "invalid_url"


class RepositoryNotFound(IngestionError):
    code = "repository_not_found"


class RateLimited(IngestionError):
    code = "rate_limited"


class RepositoryEmpty(IngestionError):
    code = "repository_empty"


class RepositoryTooLarge(IngestionError):
    code = "repository_too_large"


class GitHubUnavailable(IngestionError):
    code = "github_unavailable"


class UnsafeArchive(IngestionError):
    code = "unsafe_archive"
