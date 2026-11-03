import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisFile, RepositoryAnalysis, SavedRepository
from app.services.ingestion import pipeline
from app.storage import artifacts
from app.worker.runner import get_job_runner
from tests.fakes import SHA, make_tarball, raw_file

URL = "https://github.com/Owner/Repo"


class NoopRunner:
    """Accepts jobs but never runs them, leaving analyses in the `queued` state."""

    def submit(self, job, *args) -> None:
        pass

    def shutdown(self) -> None:
        pass


def sign_up(client: TestClient, email: str = "ada@example.com") -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "Ada", "password": "analytical-engine"},
    )
    assert response.status_code == 201


def add(client: TestClient, url: str = URL):
    return client.post("/api/repositories", json={"url": url})


@pytest.fixture
def user(client):
    sign_up(client)
    return client


# --- access control ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/repositories"),
        ("GET", "/api/repositories"),
        ("GET", "/api/repositories/11111111-1111-1111-1111-111111111111"),
        ("POST", "/api/repositories/11111111-1111-1111-1111-111111111111/analyses"),
        ("GET", "/api/repositories/11111111-1111-1111-1111-111111111111/files"),
        ("GET", "/api/repositories/11111111-1111-1111-1111-111111111111/files/content?path=a"),
    ],
)
def test_every_endpoint_requires_login(client, method, path):
    response = client.request(method, path, json={"url": URL} if method == "POST" else None)

    assert response.status_code == 401


def test_users_cannot_see_or_touch_each_others_repositories(github, user, other_client):
    repo_id = add(user).json()["id"]
    sign_up(other_client, "grace@example.com")

    assert other_client.get("/api/repositories").json() == []
    for response in (
        other_client.get(f"/api/repositories/{repo_id}"),
        other_client.post(f"/api/repositories/{repo_id}/analyses"),
        other_client.get(f"/api/repositories/{repo_id}/files"),
        other_client.get(f"/api/repositories/{repo_id}/files/content?path=app.py"),
    ):
        # Same answer as for an id that does not exist, so ids cannot be probed.
        assert response.status_code == 404
        assert response.json() == {"detail": "Repository not found"}

    # The owner is unaffected, and the other user can save the same repository separately.
    assert user.get(f"/api/repositories/{repo_id}").status_code == 200
    other_id = add(other_client).json()["id"]
    assert other_id != repo_id
    assert len(user.get("/api/repositories").json()) == 1


def test_unknown_repository_ids_are_404(github, user):
    assert user.get("/api/repositories/11111111-1111-1111-1111-111111111111").status_code == 404
    assert user.get("/api/repositories/not-a-uuid").status_code == 422


# --- adding a repository ---


def test_adding_a_repository_imports_it(github, user):
    response = add(user)

    assert response.status_code == 202
    body = response.json()
    assert (body["owner"], body["name"], body["source_type"]) == ("Owner", "Repo", "github")
    assert body["source_url"] == "https://github.com/Owner/Repo"

    analysis = body["latest_analysis"]
    assert analysis["status"] == "completed"
    assert analysis["version"] == 1
    assert analysis["commit_sha"] == SHA
    assert analysis["file_count"] == 2
    assert analysis["error_message"] is None
    assert analysis["github_metadata"]["stars"] == 42
    assert analysis["github_metadata"]["default_branch"] == "main"
    assert analysis["languages"] == {"Python": 1000, "JavaScript": 200}
    assert analysis["readme_path"] == "README.md"
    assert "A small demo project." in analysis["readme_text"]


def test_download_is_pinned_to_the_resolved_commit(github, user):
    add(user)

    assert github.count(rf"/tarball/{SHA}$") == 1
    assert github.count(r"/commits/main$") == 1


def test_files_are_recorded_and_stored_on_disk(github, user):
    body = add(user).json()
    analysis_id = body["latest_analysis"]["id"]

    files = user.get(f"/api/repositories/{body['id']}/files").json()

    assert {f["path"] for f in files} == {"README.md", "app.py"}
    app = next(f for f in files if f["path"] == "app.py")
    assert (app["language"], app["line_count"], app["skipped_reason"]) == ("Python", 2, None)
    assert (
        artifacts.source_dir(analysis_id) / "app.py"
    ).read_text() == "def main():\n    return 1\n"
    assert not artifacts.staging_dir(analysis_id).exists()


def test_sensitive_binary_and_ignored_files_never_reach_disk(github, user):
    github.files = {
        "app.py": "x = 1",
        ".env": "DATABASE_URL=postgres://user:pw@host/db",
        "certs/server.key": "-----BEGIN PRIVATE KEY-----",
        "logo.png": b"\x89PNG",
        "node_modules/lib/index.js": "module.exports = 1",
    }
    body = add(user).json()
    analysis = body["latest_analysis"]

    listed = {
        f["path"]: f["skipped_reason"]
        for f in user.get(f"/api/repositories/{body['id']}/files").json()
    }

    assert listed == {
        "app.py": None,
        ".env": "sensitive",
        "certs/server.key": "sensitive",
        "logo.png": "binary",
    }
    assert analysis["skipped_summary"] == {"sensitive": 2, "binary": 1, "ignored_directory": 1}
    on_disk = {p.name for p in artifacts.source_dir(analysis["id"]).rglob("*") if p.is_file()}
    assert on_disk == {"app.py"}


def test_secrets_in_source_are_redacted_everywhere(github, user):
    github.files = {
        "settings.py": 'API_KEY = "sk-' + "a" * 40 + '"\nDEBUG = True\n',
        "README.md": "# x",
    }
    body = add(user).json()

    content = user.get(
        f"/api/repositories/{body['id']}/files/content", params={"path": "settings.py"}
    ).json()

    assert "a" * 40 not in content["content"]
    assert "[REDACTED]" in content["content"]
    assert content["line_count"] == 2
    assert body["latest_analysis"]["redaction_count"] == 1


def test_the_readme_is_optional(github, user):
    github.files = {"app.py": "x = 1"}

    analysis = add(user).json()["latest_analysis"]

    assert analysis["status"] == "completed"
    assert analysis["readme_text"] is None and analysis["readme_path"] is None


def test_markdown_readme_is_preferred_and_subfolder_readmes_ignored(github, user):
    github.files = {
        "README.rst": "rst",
        "readme.md": "# md",
        "docs/README.md": "# docs",
        "a.py": "x",
    }

    analysis = add(user).json()["latest_analysis"]

    assert analysis["readme_path"] == "readme.md"


def test_repository_names_use_githubs_capitalisation(github, user):
    body = add(user, "https://github.com/OWNER/repo").json()

    assert (body["owner"], body["name"]) == ("OWNER", "repo")  # fake echoes what it was asked


def test_repository_list_shows_description_and_status(github, user):
    add(user)

    [item] = user.get("/api/repositories").json()

    assert item["description"] == "A demo repository"
    assert item["latest_analysis"]["status"] == "completed"
    assert "readme_text" not in item["latest_analysis"]  # summaries stay small


# --- duplicates ---


def test_adding_the_same_repository_twice_returns_the_existing_entry(github, user):
    first = add(user)
    requests_after_first = len(github.requests)
    second = add(user, "https://github.com/owner/REPO.git")

    assert first.status_code == 202 and second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(user.get("/api/repositories").json()) == 1
    assert len(github.requests) == requests_after_first  # no second analysis
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RepositoryAnalysis)) == 1


def test_the_database_itself_rejects_duplicate_entries(github, user):
    add(user)
    with SessionLocal() as db:
        existing = db.scalar(select(SavedRepository))
        duplicate = SavedRepository(
            user_id=existing.user_id,
            source_type="github",
            source_key=existing.source_key,
            name="x",
        )
        db.add(duplicate)
        with pytest.raises(Exception, match="uq_saved_repositories_user_id_source_key"):
            db.commit()


# --- validation and failures ---


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "https://evil.com/owner/repo",
        "http://169.254.169.254/",
        "https://github.com/owner",
    ],
)
def test_invalid_urls_are_rejected_without_creating_anything(github, user, url):
    response = add(user, url)

    assert response.status_code == 422
    assert "public GitHub repository URL" in response.json()["detail"]
    assert user.get("/api/repositories").json() == []
    assert github.requests == []


def test_a_very_long_url_is_rejected(github, user):
    assert add(user, "https://github.com/o/r/" + "x" * 600).status_code == 422


@pytest.mark.parametrize(
    ("setup", "code", "message"),
    [
        (lambda g: setattr(g, "metadata_status", 404), "repository_not_found", "not found"),
        (
            lambda g: setattr(g, "private", True),
            "repository_not_found",
            "private repositories are not supported",
        ),
        (lambda g: setattr(g, "metadata_status", 403), "rate_limited", "Try again after"),
        (lambda g: setattr(g, "metadata_status", 503), "github_unavailable", "problems"),
        (lambda g: setattr(g, "commit_status", 409), "repository_empty", "empty"),
        (lambda g: setattr(g, "tarball_status", 404), "repository_not_found", "not found"),
        (
            lambda g: setattr(g, "files", {"logo.png": b"x", ".env": "A=1"}),
            "repository_empty",
            "no readable source",
        ),
        (
            lambda g: setattr(g, "tarball_override", b"definitely not a tarball"),
            "unsafe_archive",
            "could not be read",
        ),
    ],
)
def test_failures_are_recorded_with_a_clear_message(github, user, setup, code, message):
    setup(github)

    body = add(user).json()
    analysis = body["latest_analysis"]

    assert analysis["status"] == "failed"
    assert analysis["error_code"] == code
    assert message.lower() in analysis["error_message"].lower()
    assert analysis["completed_at"] is not None
    # Nothing half-finished is left behind.
    assert not artifacts.source_dir(analysis["id"]).exists()
    assert not artifacts.staging_dir(analysis["id"]).exists()
    assert user.get(f"/api/repositories/{body['id']}/files").status_code == 409


def test_a_malicious_archive_fails_the_import_and_writes_nothing_outside_storage(
    github, user, tmp_path
):
    github.tarball_override = make_tarball(
        {"ok.py": "x"}, extra=(raw_file("../../escaped.txt", b"x"),)
    )

    analysis = add(user).json()["latest_analysis"]

    assert analysis["error_code"] == "unsafe_archive"
    assert not (get_settings().artifact_dir.parent / "escaped.txt").exists()
    assert not (get_settings().artifact_dir / "escaped.txt").exists()


def test_a_download_over_the_limit_fails_cleanly(github, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_download_bytes", 100)

    analysis = add(user).json()["latest_analysis"]

    assert analysis["error_code"] == "repository_too_large"
    assert "100" not in analysis["error_message"] or "MB" in analysis["error_message"]


def test_unexpected_errors_are_hidden_from_the_user(github, user, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise RuntimeError("boom: /srv/secret/path password=hunter2")

    monkeypatch.setattr(pipeline, "extract_tar_gz", explode)

    analysis = add(user).json()["latest_analysis"]

    assert analysis["status"] == "failed"
    assert analysis["error_code"] == "internal_error"
    assert "boom" not in analysis["error_message"] and "hunter2" not in analysis["error_message"]
    assert "Analysis" in caplog.text  # the real cause is logged for developers


def test_the_token_is_sent_to_github_but_never_stored_or_returned(github, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "github_token", SecretStr("ghp_" + "t" * 36))

    response = add(user)

    assert github.requests[0].headers["authorization"] == "Bearer ghp_" + "t" * 36
    assert "ghp_" not in response.text


def test_large_repositories_are_cut_off_and_flagged(github, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_files", 3)
    github.files = {f"f{i}.py": "x" for i in range(10)}

    analysis = add(user).json()["latest_analysis"]

    assert analysis["status"] == "completed"
    assert analysis["truncated"] is True
    assert analysis["file_count"] == 3


# --- retrying and re-analysing ---


def test_adding_a_failed_repository_again_retries_it(github, user):
    github.metadata_status = 503
    first = add(user).json()
    assert first["latest_analysis"]["status"] == "failed"

    github.metadata_status = 200
    retry = add(user)

    assert retry.status_code == 202
    assert retry.json()["id"] == first["id"]
    assert retry.json()["latest_analysis"]["version"] == 2
    assert retry.json()["latest_analysis"]["status"] == "completed"
    assert len(user.get("/api/repositories").json()) == 1


def test_a_new_analysis_can_be_started_for_a_saved_repository(github, user):
    repo = add(user).json()
    github.files = {"app.py": "changed = True\n", "new.py": "x"}

    response = user.post(f"/api/repositories/{repo['id']}/analyses")

    assert response.status_code == 202
    assert response.json()["latest_analysis"]["version"] == 2
    assert response.json()["latest_analysis"]["file_count"] == 2
    assert {f["path"] for f in user.get(f"/api/repositories/{repo['id']}/files").json()} == {
        "app.py",
        "new.py",
    }
    with SessionLocal() as db:  # the first version's files are kept
        assert db.scalar(select(func.count()).select_from(RepositoryAnalysis)) == 2


# --- in-progress work and limits ---


def test_a_queued_analysis_blocks_a_second_one(app, github, user):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    repo = add(user).json()
    assert repo["latest_analysis"]["status"] == "queued"

    response = user.post(f"/api/repositories/{repo['id']}/analyses")

    assert response.status_code == 409
    assert "already being analyzed" in response.json()["detail"]
    # Same URL again does not start a second one either.
    assert add(user).status_code == 200
    assert user.get(f"/api/repositories/{repo['id']}/files").status_code == 409


def test_each_user_may_only_run_a_few_analyses_at_once(app, github, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_analyses_per_user", 2)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert add(user, "https://github.com/o/one").status_code == 202
    assert add(user, "https://github.com/o/two").status_code == 202
    blocked = add(user, "https://github.com/o/three")

    assert blocked.status_code == 429
    assert "2 analyses running" in blocked.json()["detail"]


def test_one_users_running_analyses_do_not_count_against_another(
    app, github, user, other_client, monkeypatch
):
    monkeypatch.setattr(get_settings(), "max_active_analyses_per_user", 1)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    add(user)
    sign_up(other_client, "grace@example.com")

    assert add(other_client).status_code == 202


def test_analyses_interrupted_by_a_restart_are_marked_failed(app, github, user):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    repo = add(user).json()

    with TestClient(app):  # starting the app runs the startup cleanup
        pass

    analysis = user.get(f"/api/repositories/{repo['id']}").json()["latest_analysis"]
    assert analysis["status"] == "failed"
    assert analysis["error_code"] == "interrupted"
    assert "restarted" in analysis["error_message"]


# --- reading stored files ---


def test_file_content_is_served_from_storage(github, user):
    repo = add(user).json()

    response = user.get(f"/api/repositories/{repo['id']}/files/content", params={"path": "app.py"})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "app.py"
    assert body["language"] == "Python"
    assert body["size_bytes"] == 25
    assert body["line_count"] == 2
    assert body["content"] == "def main():\n    return 1\n"
    assert [(s["qualified_name"], s["kind"]) for s in body["symbols"]] == [("main", "function")]


@pytest.mark.parametrize(
    "path",
    [
        "../../../etc/passwd",
        "..\\..\\secret",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "missing.py",
        "",
        ".",
        "app.py/../../x",
    ],
)
def test_file_content_rejects_paths_that_are_not_stored_files(github, user, path):
    repo = add(user).json()

    response = user.get(f"/api/repositories/{repo['id']}/files/content", params={"path": path})

    assert response.status_code in (404, 422)


def test_skipped_files_cannot_be_read_even_if_something_is_on_disk(github, user):
    github.files = {"app.py": "x", ".env": "SECRET=1"}
    repo = add(user).json()
    analysis_id = repo["latest_analysis"]["id"]
    # Even if a file by that name somehow existed in storage, it is not served.
    stray = Path(artifacts.source_dir(analysis_id)) / ".env"
    stray.write_text("SECRET=1")

    response = user.get(f"/api/repositories/{repo['id']}/files/content", params={"path": ".env"})

    assert response.status_code == 404


def test_a_file_swapped_for_a_link_cannot_escape_storage(github, user, tmp_path):
    repo = add(user).json()
    analysis_id = repo["latest_analysis"]["id"]
    outside = tmp_path / "outside.txt"
    outside.write_text("outside storage")
    target = artifacts.source_dir(analysis_id) / "app.py"
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need extra privileges on this machine")

    response = user.get(f"/api/repositories/{repo['id']}/files/content", params={"path": "app.py"})

    assert response.status_code == 404


# --- cleanup ---


def test_deleting_a_user_removes_their_library_rows(github, user):
    add(user)

    with SessionLocal() as db:
        db.execute(__import__("sqlalchemy").text("DELETE FROM users"))
        db.commit()
        for model in (SavedRepository, RepositoryAnalysis, AnalysisFile):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_artifact_helpers_clean_up(github, user):
    analysis_id = add(user).json()["latest_analysis"]["id"]
    assert artifacts.source_dir(analysis_id).exists()

    artifacts.remove_analysis(analysis_id)

    assert not artifacts.source_dir(analysis_id).exists()
    shutil.rmtree(get_settings().artifact_dir, ignore_errors=True)
    get_settings().artifact_dir.mkdir(parents=True, exist_ok=True)


def test_the_library_list_shows_the_main_languages_and_size(github, user):
    github.files = {
        "app.py": "x = 1\ny = 2\n",
        "web/app.js": "let a = 1\n",
        "README.md": "# Demo\n",
    }
    add(user)

    [summary] = user.get("/api/repositories").json()

    assert [lang["name"] for lang in summary["languages"]] == ["Python", "JavaScript"]
    assert summary["languages"][0]["share"] == 0.667
    assert summary["code_lines"] == 3
