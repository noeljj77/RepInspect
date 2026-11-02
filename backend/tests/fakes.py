"""Test doubles: a fake GitHub (no network) and a tarball builder for crafting archives."""

import io
import re
import tarfile
import time
from types import SimpleNamespace

import httpx

from app.services.llm.base import LLMResult

SHA = "1234567890abcdef1234567890abcdef12345678"


def make_tarball(
    files: dict[str, str | bytes] | None = None,
    *,
    wrapper: str = "owner-repo-1234567",
    extra: tuple[tuple[tarfile.TarInfo, bytes | None], ...] = (),
) -> bytes:
    """Build a .tar.gz laid out like GitHub's: everything inside one wrapper folder."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        folder = tarfile.TarInfo(wrapper)
        folder.type = tarfile.DIRTYPE
        tar.addfile(folder)
        for path, content in (files or {}).items():
            data = content.encode() if isinstance(content, str) else content
            info = tarfile.TarInfo(f"{wrapper}/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return buffer.getvalue()


def raw_file(name: str, data: bytes = b"x") -> tuple[tarfile.TarInfo, bytes]:
    """A regular file with exactly this member name (no wrapper added)."""
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, data


def raw_symlink(name: str, target: str) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    return info, None


class FakeGitHub:
    """Answers the handful of GitHub endpoints RepInspect uses. Tweak attributes per test."""

    def __init__(self) -> None:
        self.files: dict[str, str | bytes] = {
            "README.md": "# Demo\n\nA small demo project.\n",
            "app.py": "def main():\n    return 1\n",
        }
        self.private = False
        self.metadata_status = 200
        self.commit_status = 200
        self.tarball_status = 200
        self.tarball_override: bytes | None = None
        self.tarball_redirect_to: str | None = None
        self.rate_limit_reset: int | None = None
        self.default_branch = "main"
        self.requests: list[httpx.Request] = []

    # --- wiring ---------------------------------------------------------------

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def count(self, pattern: str) -> int:
        return sum(1 for r in self.requests if re.search(pattern, str(r.url)))

    # --- endpoints ------------------------------------------------------------

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path = request.url.host, request.url.path

        if host == "codeload.github.com":
            return httpx.Response(200, content=self._tarball())

        match = re.fullmatch(r"/repos/([^/]+)/([^/]+)(/.*)?", path)
        if host != "api.github.com" or not match:
            return httpx.Response(404, json={"message": "Not Found"})
        owner, name, rest = match.group(1), match.group(2), match.group(3) or ""

        if rest == "":
            return self._metadata(owner, name)
        if rest == "/languages":
            return httpx.Response(200, json={"Python": 1000, "JavaScript": 200})
        if rest.startswith("/commits/"):
            if self.commit_status != 200:
                return httpx.Response(
                    self.commit_status, json={"message": "Git Repository is empty."}
                )
            return httpx.Response(200, text=SHA)
        if rest.startswith("/tarball/"):
            if self.tarball_status != 200:
                return httpx.Response(self.tarball_status, json={"message": "error"})
            target = (
                self.tarball_redirect_to
                or f"https://codeload.github.com/{owner}/{name}/legacy.tar.gz/{SHA}"
            )
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(404, json={"message": "Not Found"})

    def _metadata(self, owner: str, name: str) -> httpx.Response:
        if self.metadata_status == 403:
            reset = self.rate_limit_reset or int(time.time()) + 600
            return httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
                json={"message": "API rate limit exceeded"},
            )
        if self.metadata_status != 200:
            return httpx.Response(self.metadata_status, json={"message": "error"})
        return httpx.Response(
            200,
            json={
                "full_name": f"{owner}/{name}",
                "description": "A demo repository",
                "html_url": f"https://github.com/{owner}/{name}",
                "homepage": "",
                "default_branch": self.default_branch,
                "stargazers_count": 42,
                "forks_count": 7,
                "open_issues_count": 3,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
                "pushed_at": "2026-10-01T00:00:00Z",
                "license": {"spdx_id": "MIT"},
                "topics": ["demo"],
                "size": 120,
                "archived": False,
                "fork": False,
                "private": self.private,
                "visibility": "private" if self.private else "public",
            },
        )

    def _tarball(self) -> bytes:
        return (
            self.tarball_override if self.tarball_override is not None else make_tarball(self.files)
        )


class InlineRunner:
    """Runs jobs immediately, in the calling thread, so tests need no waiting."""

    def submit(self, job, *args) -> None:
        job(*args)

    def shutdown(self) -> None:
        pass


class FakeLLM:
    """A language model that answers from a script, and records every prompt it was given.

    `respond(schema, value)` sets what to return for a schema: a model instance, an
    exception to raise, or a function taking (system, prompt) and returning either.
    """

    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[SimpleNamespace] = []
        self._answers: dict[type, object] = {}
        self.closed = False

    def respond(self, schema: type, value: object) -> None:
        self._answers[schema] = value

    def generate_structured(
        self, *, system, prompt, schema, max_output_tokens=4096, temperature=0.2
    ):
        self.calls.append(SimpleNamespace(system=system, prompt=prompt, schema=schema))
        value = self._answers[schema]
        if callable(value):
            value = value(system, prompt)
        if isinstance(value, Exception):
            raise value
        return LLMResult(value, self.model, 120, 60)

    def close(self) -> None:
        self.closed = True
