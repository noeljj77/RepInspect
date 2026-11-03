"""Minimal GitHub REST client for public repositories.

Security properties:
- Only https requests to the hosts in ALLOWED_HOSTS are ever made. Redirects are
  followed by hand so every hop is checked, which stops a redirect to an internal address.
- The API token (if configured) is only sent to api.github.com.
- Every request has a timeout, and downloads stop at a hard size limit.
- Private repositories are refused even if the configured token could read them.
"""

import re
import time
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.core.config import Settings, get_settings
from app.services.ingestion.errors import (
    GitHubUnavailable,
    RateLimited,
    RepositoryEmpty,
    RepositoryNotFound,
    RepositoryTooLarge,
)

API_HOST = "api.github.com"
ALLOWED_HOSTS = frozenset({API_HOST, "codeload.github.com"})
MAX_REDIRECTS = 5
_SHA = re.compile(r"[0-9a-f]{40}")

# Pauses before each retry of a request that failed for a temporary reason.
RETRY_DELAYS = (0.5, 1.5)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class _TemporaryFailure(GitHubUnavailable):
    """A timeout or dropped connection: worth trying again."""


_NOT_FOUND = (
    "Repository not found. Check the URL, and note that private repositories are not supported."
)


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        timeout: float = 10.0,
        max_download_bytes: int = 50 * 1024 * 1024,
        transport: httpx.BaseTransport | None = None,
    ):
        self._token = token
        self._max_download_bytes = max_download_bytes
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=5.0),
            follow_redirects=False,
            transport=transport,
        )

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None
    ) -> "GitHubClient":
        settings = settings or get_settings()
        return cls(
            token=settings.github_token.get_secret_value() if settings.github_token else None,
            timeout=settings.github_timeout_seconds,
            max_download_bytes=settings.max_download_bytes,
            transport=transport,
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- public API ------------------------------------------------------------

    def get_repository(self, owner: str, name: str) -> dict[str, Any]:
        """Return the repository details we keep. Raises for missing, private or empty repos."""
        response = self._get(f"https://{API_HOST}/repos/{quote(owner)}/{quote(name)}")
        try:
            self._raise_for_status(response)
            data = response.json()
        finally:
            response.close()

        # A token that can see private repositories must not become a way to read
        # other people's private code through this service.
        if data.get("private") or data.get("visibility", "public") != "public":
            raise RepositoryNotFound(_NOT_FOUND)

        return {
            "full_name": data["full_name"],
            "description": data.get("description"),
            "html_url": data["html_url"],
            "homepage": data.get("homepage") or None,
            "default_branch": data["default_branch"],
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            # GitHub counts open pull requests in this number as well.
            "open_issues": data.get("open_issues_count", 0),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "pushed_at": data.get("pushed_at"),
            "license": (data.get("license") or {}).get("spdx_id"),
            "topics": data.get("topics", []),
            "size_kb": data.get("size", 0),
            "archived": bool(data.get("archived")),
            "fork": bool(data.get("fork")),
        }

    def get_languages(self, owner: str, name: str) -> dict[str, int]:
        """Bytes of code per language, as classified by GitHub."""
        response = self._get(
            f"https://{API_HOST}/repos/{quote(owner)}/{quote(name)}/languages", retry_not_found=True
        )
        try:
            self._raise_for_status(response)
            return {str(k): int(v) for k, v in response.json().items()}
        finally:
            response.close()

    def get_head_commit(self, owner: str, name: str, branch: str) -> str:
        """Full SHA of the branch tip, so the download is pinned to one exact commit.

        GitHub answers 409 here for a repository with no commits, which is how an
        empty repository is detected (the `size` field is rounded to whole KB and
        can be 0 for tiny repositories that do have code).
        """
        repo_path = f"/repos/{quote(owner)}/{quote(name)}"
        url = f"https://{API_HOST}{repo_path}/commits/{quote(branch, safe='/')}"
        response = self._get(
            url, headers={"Accept": "application/vnd.github.sha"}, retry_not_found=True
        )
        try:
            self._raise_for_status(response)
            sha = response.text.strip()
        finally:
            response.close()
        if not _SHA.fullmatch(sha):
            raise GitHubUnavailable(
                "GitHub returned an unexpected response. Try again in a moment."
            )
        return sha

    def download_tarball(self, owner: str, name: str, sha: str, destination: Path) -> int:
        """Stream the repository at `sha` to `destination`. Returns the bytes written."""
        if not _SHA.fullmatch(sha):
            raise ValueError("sha must be a full commit hash")
        response = self._get(
            f"https://{API_HOST}/repos/{quote(owner)}/{quote(name)}/tarball/{sha}",
            stream=True,
            retry_not_found=True,
        )
        written = 0
        try:
            self._raise_for_status(response)
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self._max_download_bytes:
                raise self._too_large()
            with destination.open("wb") as out:
                for chunk in response.iter_bytes(64 * 1024):
                    written += len(chunk)
                    if written > self._max_download_bytes:
                        raise self._too_large()
                    out.write(chunk)
        except httpx.HTTPError:
            raise GitHubUnavailable(
                "The download from GitHub was interrupted. Try again."
            ) from None
        finally:
            response.close()
        return written

    # --- internals -------------------------------------------------------------

    def _too_large(self) -> RepositoryTooLarge:
        limit_mb = self._max_download_bytes // (1024 * 1024)
        return RepositoryTooLarge(
            f"This repository is larger than the {limit_mb} MB download limit."
        )

    def _headers_for(self, url: str, extra: dict[str, str] | None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepInspect",
        }
        # Never forward the token to any host other than the API itself.
        if self._token and urlsplit(url).hostname == API_HOST:
            headers["Authorization"] = f"Bearer {self._token}"
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _check_url(url: str) -> None:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname not in ALLOWED_HOSTS
            or parts.port not in (None, 443)
        ):
            raise GitHubUnavailable(
                "GitHub sent an unexpected redirect, so the request was stopped."
            )

    def _get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        stream: bool = False,
        retry_not_found: bool = False,
    ) -> httpx.Response:
        """GET with a couple of retries for problems that usually pass in a second or two.

        Timeouts, dropped connections and 502/503/504 are retried. So is a 404, but only
        when the caller already knows the repository exists (`retry_not_found`): GitHub
        sometimes answers 404 for a moment on a repository that is there. A first 404 on
        the repository itself is final.
        """
        for delay in (*RETRY_DELAYS, None):
            try:
                response = self._get_once(url, headers=headers, stream=stream)
            except _TemporaryFailure:
                if delay is None:
                    raise
                _sleep(delay)
                continue
            retryable = response.status_code in (502, 503, 504) or (
                retry_not_found and response.status_code == 404
            )
            if retryable and delay is not None:
                response.close()
                _sleep(delay)
                continue
            return response
        raise AssertionError("unreachable")  # the last pass returns or raises

    def _get_once(
        self, url: str, *, headers: dict[str, str] | None = None, stream: bool = False
    ) -> httpx.Response:
        for _ in range(MAX_REDIRECTS + 1):
            self._check_url(url)
            request = self._http.build_request("GET", url, headers=self._headers_for(url, headers))
            try:
                response = self._http.send(request, stream=stream)
            except httpx.TimeoutException:
                raise _TemporaryFailure(
                    "GitHub took too long to respond. Try again in a moment."
                ) from None
            except httpx.HTTPError:
                raise _TemporaryFailure("Could not reach GitHub. Try again in a moment.") from None

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise GitHubUnavailable(
                        "GitHub sent an unexpected response. Try again in a moment."
                    )
                url = str(httpx.URL(url).join(location))
                continue
            return response
        raise GitHubUnavailable("GitHub redirected too many times, so the request was stopped.")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == 404:
            raise RepositoryNotFound(_NOT_FOUND)
        if status == 409:
            raise RepositoryEmpty("This repository is empty. There is no code to analyze yet.")
        if status in (403, 429) and _is_rate_limited(response):
            raise RateLimited(_rate_limit_message(response))
        if status == 451:
            raise GitHubUnavailable("GitHub has blocked access to this repository.")
        if status >= 500:
            raise GitHubUnavailable("GitHub is having problems right now. Try again in a moment.")
        raise GitHubUnavailable("GitHub refused the request. Try again later.")


def _is_rate_limited(response: httpx.Response) -> bool:
    return (
        response.status_code == 429
        or response.headers.get("x-ratelimit-remaining") == "0"
        or "retry-after" in response.headers
    )


def _rate_limit_message(response: httpx.Response) -> str:
    reset = response.headers.get("x-ratelimit-reset", "")
    if reset.isdigit():
        when = datetime.fromtimestamp(int(reset), UTC).strftime("%H:%M UTC")
        return f"GitHub's rate limit was reached. Try again after {when}."
    return "GitHub's rate limit was reached. Try again in a few minutes."
