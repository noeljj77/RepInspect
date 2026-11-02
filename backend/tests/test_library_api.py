import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisFile, CodeChunk, RepositoryNote, SearchIndex
from app.storage import artifacts
from app.worker.runner import get_job_runner
from tests.test_repositories_api import NoopRunner, add, sign_up
from tests.test_zip_archive import make_zip

PROJECT = {
    "shop-main/README.md": "# Shop\n\nSells lamps.\n",
    "shop-main/app/main.py": "def run():\n    return 'ok'\n",
    "shop-main/app/util.py": "def helper(value):\n    return value * 2\n",
}


def upload(client, data: bytes, name="shop.zip"):
    return client.post(
        "/api/repositories/upload",
        params={"name": name},
        content=data,
        headers={"Content-Type": "application/zip"},
    )


def upload_version(client, repo, data: bytes):
    return client.post(
        f"/api/repositories/{repo['id']}/upload",
        content=data,
        headers={"Content-Type": "application/zip"},
    )


def repo_url(repo, suffix=""):
    return f"/api/repositories/{repo['id']}{suffix}"


def analysis_dir(analysis_id) -> bool:
    return (get_settings().artifact_dir / str(analysis_id)).exists()


@pytest.fixture
def me(client):
    sign_up(client)
    return client


# --- ZIP upload ---------------------------------------------------------------------------------


def test_an_uploaded_zip_is_analyzed_like_a_repository(me):
    response = upload(me, make_zip(PROJECT))

    assert response.status_code == 202
    repo = response.json()
    assert repo["source_type"] == "zip" and repo["name"] == "shop" and repo["owner"] is None
    assert repo["latest_analysis"]["status"] == "completed"
    paths = {f["path"] for f in me.get(repo_url(repo, "/files")).json()}
    assert paths == {"README.md", "app/main.py", "app/util.py"}
    assert me.get(repo_url(repo, "/index")).json()["status"] == "ready"


def test_the_uploaded_file_is_deleted_once_it_is_extracted(me):
    upload(me, make_zip(PROJECT))

    assert list(artifacts.upload_dir().iterdir()) == []


def test_uploads_with_the_same_name_are_separate_projects(me):
    first = upload(me, make_zip(PROJECT)).json()
    second = upload(me, make_zip(PROJECT)).json()

    assert first["id"] != second["id"]
    assert len(me.get("/api/repositories").json()) == 2


def test_something_that_is_not_a_zip_is_refused(me):
    response = upload(me, b"just some text, not an archive")

    assert response.status_code == 422 and "not a ZIP" in response.json()["detail"]
    assert me.get("/api/repositories").json() == []


def test_uploads_over_the_size_limit_are_refused(me, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)

    response = upload(me, make_zip(PROJECT))

    assert response.status_code == 413 and "upload limit" in response.json()["detail"]
    assert me.get("/api/repositories").json() == []
    assert not any(artifacts.upload_dir().glob("*"))


def test_a_zip_that_cannot_be_unpacked_fails_with_a_clear_message(me):
    repo = upload(me, b"PK\x03\x04" + b"broken" * 20).json()

    assert repo["latest_analysis"]["status"] == "failed"
    assert "could not be read" in repo["latest_analysis"]["error_message"]


def test_an_upload_counts_towards_the_analysis_limit(app, me, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_analyses_per_user", 1)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    assert upload(me, make_zip(PROJECT)).status_code == 202

    assert upload(me, make_zip(PROJECT)).status_code == 429
    assert len(me.get("/api/repositories").json()) == 1  # no empty entry left behind


def test_an_uploaded_project_is_refreshed_with_a_new_zip(me):
    repo = upload(me, make_zip(PROJECT)).json()
    changed = {**PROJECT, "shop-main/app/util.py": "def helper(value):\n    return value * 3\n"}

    response = upload_version(me, repo, make_zip(changed))

    assert response.status_code == 202
    assert response.json()["latest_analysis"]["version"] == 2
    assert me.post(repo_url(repo, "/analyses")).status_code == 409  # needs a new ZIP


def test_a_github_repository_cannot_be_refreshed_with_a_zip(github, me):
    repo = add(me).json()

    assert upload_version(me, repo, make_zip(PROJECT)).status_code == 409


def test_uploading_requires_login(client):
    assert upload(client, make_zip(PROJECT)).status_code == 401


# --- refresh history -----------------------------------------------------------------------------


def test_refreshing_keeps_a_history_of_versions(github, me):
    repo = add(me).json()

    me.post(repo_url(repo, "/analyses"))

    versions = me.get(repo_url(repo, "/analyses")).json()
    assert [v["version"] for v in versions] == [2, 1]
    assert [v["source_removed"] for v in versions] == [False, True]


def test_older_versions_give_back_their_disk_space_but_keep_their_file_list(github, me):
    repo = add(me).json()
    first = uuid.UUID(repo["latest_analysis"]["id"])
    assert analysis_dir(first)

    me.post(repo_url(repo, "/analyses"))

    assert not analysis_dir(first)
    with SessionLocal() as db:
        count = lambda model: db.scalar(  # noqa: E731
            select(func.count()).select_from(model).where(model.analysis_id == first)
        )
        assert count(AnalysisFile) > 0
        assert count(CodeChunk) == 0 and count(SearchIndex) == 0


def test_the_changes_between_versions_are_listed(github, me):
    github.files = {"README.md": "# Demo\n", "app.py": "x = 1\n", "old.py": "gone = 1\n"}
    repo = add(me).json()
    github.files = {"README.md": "# Demo\n", "app.py": "x = 2\n", "new.py": "fresh = 1\n"}
    latest = me.post(repo_url(repo, "/analyses")).json()["latest_analysis"]

    result = me.get(repo_url(repo, f"/analyses/{latest['id']}/changes")).json()

    assert result["version"] == 2 and result["previous_version"] == 1
    changes = result["changes"]
    assert changes["added"] == {"count": 1, "paths": ["new.py"]}
    assert changes["removed"] == {"count": 1, "paths": ["old.py"]}
    assert changes["modified"] == {"count": 1, "paths": ["app.py"]}
    assert changes["unchanged"] == 1 and changes["exact"] is True


def test_dependency_and_technology_changes_are_listed(github, me):
    github.files = {"requirements.txt": "flask==2.0\nrequests\n", "app.py": "import flask\n"}
    repo = add(me).json()
    github.files = {"requirements.txt": "flask==3.0\nfastapi\n", "app.py": "import fastapi\n"}
    latest = me.post(repo_url(repo, "/analyses")).json()["latest_analysis"]

    changes = me.get(repo_url(repo, f"/analyses/{latest['id']}/changes")).json()["changes"]

    assert changes["dependencies_added"] == ["fastapi (pypi)"]
    assert changes["dependencies_removed"] == ["requests (pypi)"]
    assert changes["dependencies_changed"] == ["flask (pypi): ==2.0 → ==3.0"]
    assert "FastAPI" in changes["technologies_added"]
    assert "Requests" in changes["technologies_removed"]


def test_the_first_version_has_nothing_to_compare_with(github, me):
    repo = add(me).json()

    result = me.get(repo_url(repo, f"/analyses/{repo['latest_analysis']['id']}/changes")).json()

    assert result["previous_version"] is None and result["changes"] is None


def test_versions_of_other_repositories_are_not_found(github, me, other_client):
    repo = add(me).json()
    sign_up(other_client, "grace@example.com")
    theirs = add(other_client, "https://github.com/octo/other").json()

    response = me.get(repo_url(repo, f"/analyses/{theirs['latest_analysis']['id']}/changes"))

    assert response.status_code == 404


def test_the_previous_version_stays_usable_while_a_refresh_runs(app, github, me):
    repo = add(me).json()
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    detail = me.post(repo_url(repo, "/analyses")).json()

    assert detail["latest_analysis"]["status"] == "queued"
    assert detail["current_analysis"]["version"] == 1
    assert me.get(repo_url(repo, "/files")).status_code == 200


def test_a_failed_refresh_keeps_the_previous_version(github, me):
    repo = add(me).json()
    github.tarball_status = 500

    detail = me.post(repo_url(repo, "/analyses")).json()

    assert detail["latest_analysis"]["status"] == "failed"
    assert detail["current_analysis"]["version"] == 1
    assert analysis_dir(repo["latest_analysis"]["id"])  # nothing was pruned


# --- labels ------------------------------------------------------------------------------------------


def test_labels_are_cleaned_up_and_saved(github, me):
    repo = add(me).json()

    response = me.patch(repo_url(repo), json={"labels": [" Backend ", "to  review", "backend", ""]})

    assert response.status_code == 200 and response.json()["labels"] == ["Backend", "to review"]
    assert me.get("/api/repositories").json()[0]["labels"] == ["Backend", "to review"]


@pytest.mark.parametrize("labels", [["x" * 41], [f"label {n}" for n in range(11)]])
def test_too_many_or_too_long_labels_are_refused(github, me, labels):
    repo = add(me).json()

    assert me.patch(repo_url(repo), json={"labels": labels}).status_code == 422


# --- delete -------------------------------------------------------------------------------------------


def test_deleting_a_repository_removes_everything_stored_for_it(github, me):
    repo = add(me).json()
    analysis_id = repo["latest_analysis"]["id"]
    me.post(repo_url(repo, "/notes"), json={"body": "Remember the cache"})
    collection = me.post("/api/collections", json={"name": "Work"}).json()
    me.put(f"/api/collections/{collection['id']}/repositories/{repo['id']}")

    assert me.delete(repo_url(repo)).status_code == 204

    assert me.get(repo_url(repo)).status_code == 404
    assert me.get("/api/repositories").json() == []
    assert not analysis_dir(analysis_id)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RepositoryNote)) == 0
    assert me.get("/api/collections").json()[0]["repository_ids"] == []  # the collection stays


def test_a_repository_being_analyzed_cannot_be_deleted(app, github, me):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    repo = add(me).json()

    assert me.delete(repo_url(repo)).status_code == 409


def test_other_people_cannot_delete_or_label_a_repository(github, me, other_client):
    repo = add(me).json()
    sign_up(other_client, "grace@example.com")

    assert other_client.delete(repo_url(repo)).status_code == 404
    assert other_client.patch(repo_url(repo), json={"labels": ["mine"]}).status_code == 404
    assert me.get(repo_url(repo)).status_code == 200


# --- notes ---------------------------------------------------------------------------------------


def test_notes_can_be_added_edited_listed_and_deleted(github, me):
    repo = add(me).json()
    general = me.post(repo_url(repo, "/notes"), json={"body": "Ask about the cache"}).json()
    on_file = me.post(
        repo_url(repo, "/notes"), json={"body": "Entry point", "path": "app.py", "line": 1}
    ).json()

    assert [n["id"] for n in me.get(repo_url(repo, "/notes")).json()] == [
        on_file["id"],
        general["id"],
    ]
    assert [
        n["id"] for n in me.get(repo_url(repo, "/notes"), params={"path": "app.py"}).json()
    ] == [on_file["id"]]

    edited = me.patch(repo_url(repo, f"/notes/{general['id']}"), json={"body": "Ask about Redis"})
    assert edited.json()["body"] == "Ask about Redis"
    assert me.delete(repo_url(repo, f"/notes/{general['id']}")).status_code == 204
    assert [n["id"] for n in me.get(repo_url(repo, "/notes")).json()] == [on_file["id"]]


def test_a_line_without_a_file_is_ignored(github, me):
    repo = add(me).json()

    note = me.post(repo_url(repo, "/notes"), json={"body": "General", "line": 4}).json()

    assert note["line"] is None


@pytest.mark.parametrize("body", [{"body": ""}, {"body": "x" * 5001}, {"body": "ok", "line": 0}])
def test_invalid_notes_are_refused(github, me, body):
    repo = add(me).json()

    assert me.post(repo_url(repo, "/notes"), json=body).status_code == 422


def test_notes_survive_a_refresh(github, me):
    repo = add(me).json()
    me.post(repo_url(repo, "/notes"), json={"body": "Keep me"})

    me.post(repo_url(repo, "/analyses"))

    assert [n["body"] for n in me.get(repo_url(repo, "/notes")).json()] == ["Keep me"]


def test_other_people_cannot_read_or_change_notes(github, me, other_client):
    repo = add(me).json()
    note = me.post(repo_url(repo, "/notes"), json={"body": "Private"}).json()
    sign_up(other_client, "grace@example.com")

    assert other_client.get(repo_url(repo, "/notes")).status_code == 404
    assert (
        other_client.patch(repo_url(repo, f"/notes/{note['id']}"), json={"body": "x"}).status_code
        == 404
    )
    assert other_client.delete(repo_url(repo, f"/notes/{note['id']}")).status_code == 404


# --- collections ----------------------------------------------------------------------------------


def test_collections_group_repositories(github, me):
    repo = add(me).json()
    collection = me.post("/api/collections", json={"name": "Interview: Acme"}).json()
    url = f"/api/collections/{collection['id']}/repositories/{repo['id']}"

    assert me.put(url).status_code == 204
    assert me.put(url).status_code == 204  # adding twice changes nothing

    assert me.get("/api/collections").json()[0]["repository_ids"] == [repo["id"]]
    assert me.get("/api/repositories").json()[0]["collection_ids"] == [collection["id"]]
    assert me.delete(url).status_code == 204
    assert me.get(repo_url(repo)).json()["collection_ids"] == []


def test_collections_are_listed_by_name_and_can_be_renamed(me):
    me.post("/api/collections", json={"name": "zeta"})
    alpha = me.post("/api/collections", json={"name": "Alpha", "description": "First"}).json()

    renamed = me.patch(f"/api/collections/{alpha['id']}", json={"name": "Beta"}).json()

    assert renamed["name"] == "Beta" and renamed["description"] == "First"
    assert [c["name"] for c in me.get("/api/collections").json()] == ["Beta", "zeta"]
    cleared = me.patch(f"/api/collections/{alpha['id']}", json={"description": None}).json()
    assert cleared["description"] is None


def test_collection_names_are_unique_per_person(me, other_client):
    me.post("/api/collections", json={"name": "Work"})
    other = me.post("/api/collections", json={"name": "Other"}).json()

    assert me.post("/api/collections", json={"name": "Work"}).status_code == 409
    assert me.patch(f"/api/collections/{other['id']}", json={"name": "Work"}).status_code == 409
    sign_up(other_client, "grace@example.com")
    assert other_client.post("/api/collections", json={"name": "Work"}).status_code == 201


def test_deleting_a_collection_keeps_its_repositories(github, me):
    repo = add(me).json()
    collection = me.post("/api/collections", json={"name": "Work"}).json()
    me.put(f"/api/collections/{collection['id']}/repositories/{repo['id']}")

    assert me.delete(f"/api/collections/{collection['id']}").status_code == 204

    assert me.get("/api/collections").json() == []
    assert me.get(repo_url(repo)).status_code == 200


def test_collections_and_their_repositories_are_private(github, me, other_client):
    repo = add(me).json()
    mine = me.post("/api/collections", json={"name": "Mine"}).json()
    sign_up(other_client, "grace@example.com")
    theirs = other_client.post("/api/collections", json={"name": "Theirs"}).json()

    assert other_client.get("/api/collections").json()[0]["id"] == theirs["id"]
    assert (
        other_client.patch(f"/api/collections/{mine['id']}", json={"name": "x"}).status_code == 404
    )
    assert other_client.delete(f"/api/collections/{mine['id']}").status_code == 404
    # Someone else's repository cannot be put in your collection.
    assert (
        other_client.put(f"/api/collections/{theirs['id']}/repositories/{repo['id']}").status_code
        == 404
    )


def test_collections_require_login(client):
    assert client.get("/api/collections").status_code == 401
    assert client.post("/api/collections", json={"name": "x"}).status_code == 401
