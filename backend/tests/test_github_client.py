import random

import httpx
import pytest

from app.services.ingestion.errors import (
    GitHubUnavailable,
    RateLimited,
    RepositoryEmpty,
    RepositoryNotFound,
    RepositoryTooLarge,
)
from app.services.ingestion.github_client import GitHubClient
from tests.fakes import SHA, FakeGitHub


@pytest.fixture
def fake() -> FakeGitHub:
    return FakeGitHub()


def client_for(fake: FakeGitHub, **kwargs) -> GitHubClient:
    return GitHubClient(transport=fake.transport(), **kwargs)


def client_with(handler, **kwargs) -> GitHubClient:
    return GitHubClient(transport=httpx.MockTransport(handler), **kwargs)


# --- repository details ---


def test_get_repository_returns_the_fields_we_keep(fake):
    with client_for(fake) as github:
        data = github.get_repository("Owner", "Repo")

    assert data["full_name"] == "Owner/Repo"
    assert data["default_branch"] == "main"
    assert (data["stars"], data["forks"], data["open_issues"]) == (42, 7, 3)
    assert data["license"] == "MIT"
    assert data["homepage"] is None  # empty string becomes None
    assert "private" not in data


def test_missing_repository(fake):
    fake.metadata_status = 404

    with client_for(fake) as github, pytest.raises(RepositoryNotFound):
        github.get_repository("o", "r")


def test_private_repositories_are_refused_even_with_a_token(fake):
    fake.private = True

    with client_for(fake, token="secret") as github, pytest.raises(RepositoryNotFound):
        github.get_repository("o", "r")


def test_rate_limit_message_says_when_to_retry(fake):
    fake.metadata_status = 403
    fake.rate_limit_reset = 1_800_000_000  # 2027-01-15 08:00:00 UTC

    with client_for(fake) as github, pytest.raises(RateLimited, match=r"after 08:00 UTC"):
        github.get_repository("o", "r")


def test_429_is_a_rate_limit(fake):
    fake.metadata_status = 429

    with client_for(fake) as github, pytest.raises(RateLimited):
        github.get_repository("o", "r")


def test_other_403_is_not_reported_as_a_rate_limit():
    def handler(request):
        return httpx.Response(403, json={"message": "Repository access blocked"})

    with client_with(handler) as github, pytest.raises(GitHubUnavailable):
        github.get_repository("o", "r")


@pytest.mark.parametrize("status", [500, 502, 503, 418])
def test_server_errors_are_reported_as_unavailable(fake, status):
    fake.metadata_status = status

    with client_for(fake) as github, pytest.raises(GitHubUnavailable):
        github.get_repository("o", "r")


def test_timeouts_are_reported_to_the_user():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with client_with(handler) as github, pytest.raises(GitHubUnavailable, match="too long"):
        github.get_repository("o", "r")


def test_network_failures_are_reported_to_the_user():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with client_with(handler) as github, pytest.raises(GitHubUnavailable, match="Could not reach"):
        github.get_repository("o", "r")


def test_renamed_repositories_follow_the_api_redirect(fake):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/repos/old/name":
            return httpx.Response(
                301, headers={"location": "https://api.github.com/repositories/99"}
            )
        return fake._handle(request.__class__("GET", "https://api.github.com/repos/new/name"))

    with client_with(handler) as github:
        assert github.get_repository("old", "name")["full_name"] == "new/name"
    assert seen[0].endswith("/repos/old/name") and seen[1].endswith("/repositories/99")


# --- commits and empty repositories ---


def test_head_commit_returns_the_full_sha(fake):
    with client_for(fake) as github:
        assert github.get_head_commit("o", "r", "main") == SHA


def test_branch_names_with_slashes_are_supported_and_encoded(fake):
    with client_for(fake) as github:
        github.get_head_commit("o", "r", "feature/new thing")

    assert fake.requests[0].url.raw_path.endswith(b"/commits/feature/new%20thing")


def test_a_repository_without_commits_is_reported_as_empty(fake):
    fake.commit_status = 409

    with client_for(fake) as github, pytest.raises(RepositoryEmpty):
        github.get_head_commit("o", "r", "main")


def test_unexpected_commit_responses_are_rejected():
    def handler(request):
        return httpx.Response(200, text="<html>not a sha</html>")

    with client_with(handler) as github, pytest.raises(GitHubUnavailable):
        github.get_head_commit("o", "r", "main")


# --- downloads ---


def test_download_follows_the_redirect_to_codeload_and_saves_the_file(fake, tmp_path):
    destination = tmp_path / "repo.tar.gz"

    with client_for(fake) as github:
        written = github.download_tarball("o", "r", SHA, destination)

    assert written == destination.stat().st_size > 0
    assert [r.url.host for r in fake.requests] == ["api.github.com", "codeload.github.com"]
    assert f"/tarball/{SHA}" in fake.requests[0].url.path


def test_the_token_is_only_sent_to_the_api_host(fake, tmp_path):
    with client_for(fake, token="super-secret-token") as github:
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    api, codeload = fake.requests
    assert api.headers["authorization"] == "Bearer super-secret-token"
    assert "authorization" not in codeload.headers


def test_no_authorization_header_without_a_token(fake):
    with client_for(fake) as github:
        github.get_repository("o", "r")

    assert "authorization" not in fake.requests[0].headers


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example.com/steal",
        "https://api.github.com.evil.com/x",
        "http://codeload.github.com/o/r/legacy.tar.gz/abc",  # downgrade to http
        "https://169.254.169.254/latest/meta-data/",
        "https://localhost/internal",
        "https://127.0.0.1/",
        "https://codeload.github.com:8443/o/r",
        "file:///etc/passwd",
    ],
)
def test_redirects_to_other_destinations_are_blocked_and_never_requested(fake, tmp_path, target):
    fake.tarball_redirect_to = target

    with client_for(fake, token="t") as github, pytest.raises(GitHubUnavailable):
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    assert [r.url.host for r in fake.requests] == ["api.github.com"]  # nothing else was contacted


def test_redirect_loops_are_stopped():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://api.github.com/loop"})

    with client_with(handler) as github, pytest.raises(GitHubUnavailable, match="too many times"):
        github.get_repository("o", "r")


def test_downloads_over_the_limit_are_aborted_while_streaming(tmp_path):
    # No Content-Length header (chunked), so the size is only known by counting bytes.
    def chunks():
        for _ in range(100):
            yield random.Random(1).randbytes(500)

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"location": "https://codeload.github.com/x"})
        return httpx.Response(200, content=chunks())

    with (
        client_with(handler, max_download_bytes=1_000) as github,
        pytest.raises(RepositoryTooLarge),
    ):
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    assert (tmp_path / "x.tar.gz").stat().st_size <= 1_000  # stopped well before 50 KB


def test_a_declared_size_over_the_limit_is_rejected_before_downloading(tmp_path):
    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"location": "https://codeload.github.com/x"})
        return httpx.Response(200, headers={"content-length": "999999999"}, content=b"tiny")

    with (
        client_with(handler, max_download_bytes=1_000) as github,
        pytest.raises(RepositoryTooLarge),
    ):
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    assert (tmp_path / "x.tar.gz").exists() is False


def test_download_requires_a_full_commit_sha(fake, tmp_path):
    with client_for(fake) as github, pytest.raises(ValueError):
        github.download_tarball("o", "r", "main", tmp_path / "x.tar.gz")
    assert fake.requests == []


def test_a_missing_tarball_is_reported(fake, tmp_path):
    fake.tarball_status = 404

    with client_for(fake) as github, pytest.raises(RepositoryNotFound):
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")


# --- retries ---


def test_a_temporary_server_error_is_retried(fake):
    calls = []
    inner = fake.transport()

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return inner.handle_request(request)

    with client_with(handler) as github:
        data = github.get_repository("o", "r")

    assert data["default_branch"] == "main" and len(calls) == 2


def test_a_dropped_connection_is_retried():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("reset", request=request)
        return httpx.Response(200, text="a" * 40)

    with client_with(handler) as github:
        sha = github.get_head_commit("o", "r", "main")

    assert sha == "a" * 40 and len(calls) == 3


def test_retrying_gives_up_after_a_few_attempts():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with client_with(handler) as github, pytest.raises(GitHubUnavailable):
        github.get_repository("o", "r")

    assert len(calls) == 3  # the first try and two retries


def test_a_missing_repository_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with client_with(handler) as github, pytest.raises(RepositoryNotFound):
        github.get_repository("o", "r")

    assert len(calls) == 1


def test_a_404_after_the_repository_was_found_is_retried(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(404)
        return httpx.Response(200, content=b"tarball bytes")

    with client_with(handler) as github:
        written = github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    assert written == len(b"tarball bytes") and len(calls) == 2


def test_a_persistent_404_after_the_repository_was_found_still_ends_as_not_found(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with client_with(handler) as github, pytest.raises(RepositoryNotFound):
        github.download_tarball("o", "r", SHA, tmp_path / "x.tar.gz")

    assert len(calls) == 3


def test_rate_limits_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429)

    with client_with(handler) as github, pytest.raises(RateLimited):
        github.get_repository("o", "r")

    assert len(calls) == 1
