"""The static analysis results as seen through the API."""

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import IN_PROGRESS_STATUSES, CodeImport, CodeSymbol, ProjectDependency
from app.services.ingestion import pipeline
from app.worker.runner import get_job_runner
from tests.test_repositories_api import NoopRunner, add, sign_up  # noqa: F401

FILES = {
    "README.md": "# Shop\n",
    "pyproject.toml": '[project]\ndependencies = ["fastapi>=0.100", "sqlalchemy"]\n'
    '[project.optional-dependencies]\ndev = ["pytest"]\n',
    "app/__init__.py": "",
    "app/main.py": (
        "from fastapi import FastAPI\nfrom app import util\nfrom app.models import User\n\n"
        "app = FastAPI()\n\n\ndef create():\n    return util.helper()\n\n\n"
        'if __name__ == "__main__":\n    create()\n'
    ),
    "app/util.py": "def helper():\n    '''Helps.'''\n    return 1\n\n\ndef helper_two():\n    return 2\n",
    "app/models.py": "class User:\n    def save(self): ...\n\n    def load(self): ...\n",
    "web/package.json": '{"dependencies": {"react": "^19"}}\n',
    "web/src/App.tsx": "import React from 'react';\nexport default function App() { return 1; }\n",
    "broken.py": "def oops(:\n",
}


@pytest.fixture
def repo(github, client):
    sign_up(client)
    github.files = FILES
    return add(client).json()


def url(repo, suffix=""):
    return f"/api/repositories/{repo['id']}{suffix}"


# --- repository detail ------------------------------------------------------------------


def test_detail_includes_technologies_with_evidence(client, repo):
    detail = client.get(url(repo)).json()["latest_analysis"]

    techs = {t["name"]: t for t in detail["technologies"]}
    assert {"FastAPI", "SQLAlchemy", "React", "pytest"} <= set(techs)
    fastapi = techs["FastAPI"]
    assert fastapi["category"] == "Backend framework"
    evidence = {(e["kind"], e["path"], e["line"]) for e in fastapi["evidence"]}
    assert ("dependency", "pyproject.toml", 2) in evidence
    assert ("import", "app/main.py", 1) in evidence


def test_detail_includes_code_statistics(client, repo):
    stats = client.get(url(repo)).json()["latest_analysis"]["code_stats"]

    languages = {row["name"]: row for row in stats["languages"]}
    assert languages["Python"]["files"] == 5
    assert languages["TypeScript"]["files"] == 1
    totals = stats["totals"]
    assert totals["symbols_by_kind"] == {"function": 4, "class": 1, "method": 2}
    assert totals["parse_errors"] == 1
    assert totals["dependencies"] == 4


def test_important_files_are_listed_with_reasons(client, repo):
    important = client.get(url(repo)).json()["important_files"]

    by_path = {f["path"]: f for f in important}
    assert by_path["README.md"]["reasons"] == ["Project README"]
    assert "Dependency manifest" in by_path["pyproject.toml"]["reasons"]
    assert "Application entry point" in by_path["app/main.py"]["reasons"]
    assert "app/util.py" not in by_path  # an ordinary module
    scores = [f["score"] for f in important]
    assert scores == sorted(scores, reverse=True)


def test_important_files_only_appear_once_the_analysis_is_complete(app, github, client):
    sign_up(client)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    body = add(client).json()

    assert body["important_files"] == []
    assert body["latest_analysis"]["technologies"] is None


def test_the_analyzing_step_counts_as_in_progress():
    assert "analyzing" in {s.value for s in IN_PROGRESS_STATUSES}


# --- files ----------------------------------------------------------------------------------


def test_file_list_carries_importance_and_symbol_counts(client, repo):
    files = {f["path"]: f for f in client.get(url(repo, "/files")).json()}

    assert files["app/main.py"]["importance_score"] >= 30
    assert files["app/util.py"]["symbol_count"] == 2
    assert files["README.md"]["symbol_count"] == 0
    assert files["broken.py"]["parse_error"] is True
    assert files["app/util.py"]["parse_error"] is False


def test_file_content_includes_symbols_imports_and_importers(client, repo):
    util = client.get(url(repo, "/files/content"), params={"path": "app/util.py"}).json()

    helper = next(s for s in util["symbols"] if s["name"] == "helper")
    assert (helper["kind"], helper["start_line"], helper["end_line"]) == ("function", 1, 3)
    assert helper["signature"] == "def helper()"
    assert helper["doc"] == "Helps."
    assert util["imported_by"] == ["app/main.py"]
    assert util["imports"] == []

    main = client.get(url(repo, "/files/content"), params={"path": "app/main.py"}).json()
    imports = {i["module"]: i for i in main["imports"]}
    assert imports["fastapi"]["resolved_path"] is None  # a library
    assert imports["app"]["names"] == ["util"]
    assert imports["app"]["resolved_path"] in {"app/__init__.py", "app/util.py"}
    assert imports["app.models"]["resolved_path"] == "app/models.py"
    assert main["importance_reasons"] == ["Application entry point"]


def test_a_file_that_failed_to_parse_still_opens(client, repo):
    body = client.get(url(repo, "/files/content"), params={"path": "broken.py"}).json()

    assert body["parse_error"] is True and body["symbols"] == []
    assert body["content"] == "def oops(:\n"


# --- dependencies -------------------------------------------------------------------------------


def test_dependencies_are_listed_with_source_file_and_line(client, repo):
    rows = client.get(url(repo, "/dependencies")).json()

    summary = [
        (r["name"], r["version_spec"], r["scope"], r["source_file"], r["line"]) for r in rows
    ]
    assert summary == [
        ("fastapi", ">=0.100", "runtime", "pyproject.toml", 2),
        ("sqlalchemy", None, "runtime", "pyproject.toml", 2),
        ("pytest", None, "dev", "pyproject.toml", 4),
        ("react", "^19", "runtime", "web/package.json", 1),
    ]
    assert rows[0]["ecosystem"] == "pypi" and rows[-1]["ecosystem"] == "npm"


# --- symbol search --------------------------------------------------------------------------------


def names(response):
    return [(s["qualified_name"], s["path"]) for s in response.json()]


def test_symbol_search_matches_names_case_insensitively(client, repo):
    result = client.get(url(repo, "/symbols"), params={"q": "HELPER"})

    assert names(result) == [("helper", "app/util.py"), ("helper_two", "app/util.py")]
    assert result.json()[0]["start_line"] == 1


def test_symbol_search_by_kind_and_qualified_name(client, repo):
    assert names(client.get(url(repo, "/symbols"), params={"kind": "class"})) == [
        ("User", "app/models.py")
    ]
    assert names(client.get(url(repo, "/symbols"), params={"q": "User.sa"})) == [
        ("User.save", "app/models.py")
    ]
    assert client.get(url(repo, "/symbols"), params={"q": "nothing-like-this"}).json() == []


def test_symbol_search_treats_wildcards_literally(client, repo):
    assert client.get(url(repo, "/symbols"), params={"q": "%"}).json() == []
    # "_" is a literal underscore here, not "any one character".
    assert client.get(url(repo, "/symbols"), params={"q": "h_lper"}).json() == []
    assert names(client.get(url(repo, "/symbols"), params={"q": "helper_t"})) == [
        ("helper_two", "app/util.py")
    ]


def test_symbol_search_limit(client, repo):
    assert len(client.get(url(repo, "/symbols"), params={"limit": 2}).json()) == 2
    assert client.get(url(repo, "/symbols"), params={"limit": 0}).status_code == 422
    assert client.get(url(repo, "/symbols"), params={"limit": 1000}).status_code == 422


# --- access control and edge cases ----------------------------------------------------------------------


@pytest.mark.parametrize("suffix", ["/dependencies", "/symbols", "/files", "/files/content?path=a"])
def test_other_users_cannot_read_code_insight(client, other_client, repo, suffix):
    sign_up(other_client, "grace@example.com")

    response = other_client.get(url(repo, suffix))

    assert response.status_code == 404
    assert response.json() == {"detail": "Repository not found"}


@pytest.mark.parametrize("suffix", ["/dependencies", "/symbols"])
def test_login_is_required(client, other_client, repo, suffix):
    assert other_client.get(url(repo, suffix)).status_code == 401


@pytest.mark.parametrize("suffix", ["/dependencies", "/symbols"])
def test_nothing_is_available_before_the_analysis_finishes(app, github, client, suffix):
    sign_up(client)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    queued = add(client).json()

    assert client.get(url(queued, suffix)).status_code == 409


def test_a_static_analysis_failure_does_not_fail_the_import(github, client, monkeypatch, caplog):
    sign_up(client)

    def explode(*args, **kwargs):
        raise RuntimeError("analysis bug")

    monkeypatch.setattr(pipeline, "analyze_directory", explode)
    body = add(client).json()
    analysis = body["latest_analysis"]

    assert analysis["status"] == "completed"  # files were still imported
    assert analysis["technologies"] is None and analysis["code_stats"] is None
    assert analysis["file_count"] == 2
    assert client.get(url(body, "/dependencies")).json() == []
    assert "Static analysis failed" in caplog.text


def test_a_new_analysis_replaces_what_the_old_one_found(github, client, repo):
    github.files = {"only.py": "def only(): ...\n", "README.md": "# x"}

    client.post(url(repo, "/analyses"))

    assert names(client.get(url(repo, "/symbols"))) == [("only", "only.py")]
    assert client.get(url(repo, "/dependencies")).json() == []


def test_deleting_a_user_removes_every_analysis_row(github, client, repo):
    from sqlalchemy import text

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CodeSymbol)) > 0
        db.execute(text("DELETE FROM users"))
        db.commit()
        for model in (CodeSymbol, CodeImport, ProjectDependency):
            assert db.scalar(select(func.count()).select_from(model)) == 0
