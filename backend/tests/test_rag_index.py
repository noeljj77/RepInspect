import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import CodeChunk, IndexStatus, SearchIndex
from app.services.rag import indexer, retrieval, vector_store
from app.services.rag.retrieval import _rrf, keyword_query
from app.storage import artifacts
from app.worker.runner import get_job_runner
from tests.test_repositories_api import NoopRunner, add, sign_up

AUTH = (
    "import argon2\n"  # 1
    "\n"  # 2
    "\n"  # 3
    "def verify_password(plain, stored_hash):\n"  # 4
    '    """Check a login attempt against the stored hash."""\n'  # 5
    "    return argon2.verify(stored_hash, plain)\n"  # 6
    "\n"  # 7
    "\n"  # 8
    "def create_session(user):\n"  # 9
    "    return {'user': user.id, 'expires': 3600}\n"  # 10
)
ORDERS = (
    "class OrderService:\n"  # 1
    "    def create_order(self, cart):\n"  # 2
    "        total = sum(item.price for item in cart)\n"  # 3
    "        return Order(total=total)\n"  # 4
    "\n"  # 5
    "    def cancel_order(self, order):\n"  # 6
    "        if order.shipped:\n"  # 7
    "            raise ValueError('Order already shipped, refund instead')\n"  # 8
    "        order.status = 'cancelled'\n"  # 9
)
README = "# Shop\n\nAn online shop that sells handmade lamps.\n\n## Payments\n\nCards are charged through the payment provider.\n"
FILES = {
    "README.md": README,
    "pyproject.toml": '[project]\nname = "shop"\ndependencies = ["argon2-cffi>=23"]\n',
    "app/__init__.py": "",
    "app/auth.py": AUTH,
    "app/orders.py": ORDERS,
    ".env": "DATABASE_PASSWORD=hunter2-super-secret",
}


@pytest.fixture
def repo(github, client):
    sign_up(client)
    github.files = FILES
    return add(client).json()


def analysis_id(repo) -> uuid.UUID:
    return uuid.UUID(repo["latest_analysis"]["id"])


def search(repo, question, k=3, budget=20_000):
    with SessionLocal() as db:
        return retrieval.retrieve(db, analysis_id(repo), question, k, budget)


def places(results):
    return [(r.path, r.symbol) for r in results]


# --- building the index -----------------------------------------------------------------------


def test_an_import_builds_a_ready_index(client, repo, embedder):
    index = client.get(f"/api/repositories/{repo['id']}/index").json()

    assert index["status"] == "ready" and index["model"] == "fake-embedder"
    assert index["chunk_count"] == index["chunks_embedded"] > 0
    assert embedder.documents_embedded == index["chunk_count"]
    with SessionLocal() as db:
        stored = db.scalar(
            select(func.count())
            .select_from(CodeChunk)
            .where(CodeChunk.analysis_id == analysis_id(repo))
        )
    assert stored == index["chunk_count"]
    assert vector_store.load(analysis_id(repo)).index.ntotal == stored


def test_chunks_follow_functions_and_never_include_secret_files(repo):
    with SessionLocal() as db:
        chunks = db.execute(
            select(
                CodeChunk.path, CodeChunk.symbol, CodeChunk.start_line, CodeChunk.end_line
            ).where(CodeChunk.analysis_id == analysis_id(repo))
        ).all()

    assert ("app/auth.py", "verify_password", 4, 6) in chunks
    assert ("app/orders.py", "OrderService", 1, 9) in chunks
    assert not any(path == ".env" for path, *_ in chunks)


def test_an_index_can_be_rebuilt(client, repo):
    response = client.post(f"/api/repositories/{repo['id']}/index")

    assert response.status_code == 202
    assert client.get(f"/api/repositories/{repo['id']}/index").json()["status"] == "ready"


def test_an_index_that_is_being_built_is_not_started_twice(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert client.post(f"/api/repositories/{repo['id']}/index").json()["status"] == "pending"
    assert client.post(f"/api/repositories/{repo['id']}/index").status_code == 409


def test_older_imports_have_no_index_until_one_is_requested(client, repo):
    with SessionLocal() as db:
        db.delete(db.get(SearchIndex, analysis_id(repo)))
        db.commit()

    assert client.get(f"/api/repositories/{repo['id']}/index").json()["status"] == "missing"


def test_a_failure_while_indexing_leaves_the_analysis_usable(github, client, monkeypatch):
    def broken(*_):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(indexer.vector_store, "save", broken)
    sign_up(client)
    github.files = FILES
    repo = add(client).json()

    assert repo["latest_analysis"]["status"] == "completed"
    index = client.get(f"/api/repositories/{repo['id']}/index").json()
    assert index["status"] == "failed" and "could not be built" in index["error_message"]


def test_a_repository_with_nothing_searchable_says_so(github, client):
    sign_up(client)
    github.files = {"logo.png": b"\x89PNG\x00\x00binary", "empty.py": ""}
    repo = add(client).json()

    index = client.get(f"/api/repositories/{repo['id']}/index").json()
    assert index["status"] == "failed" and index["error_code"] == "nothing_to_index"


def test_the_chunk_limit_keeps_the_most_important_files(github, client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_chunks_per_analysis", 2)
    sign_up(client)
    github.files = FILES
    repo = add(client).json()

    index = client.get(f"/api/repositories/{repo['id']}/index").json()
    assert index["status"] == "ready" and index["chunk_count"] == 2 and index["truncated"]


def test_indexes_interrupted_by_a_restart_are_marked_failed(repo):
    with SessionLocal() as db:
        db.get(SearchIndex, analysis_id(repo)).status = IndexStatus.BUILDING
        db.commit()
        assert indexer.mark_interrupted(db) == 1
        assert db.get(SearchIndex, analysis_id(repo)).error_code == "interrupted"


# --- searching ----------------------------------------------------------------------------------


def test_search_finds_the_function_that_answers_the_question(repo):
    assert places(search(repo, "how is the password verified at login?"))[0] == (
        "app/auth.py",
        "verify_password",
    )


def test_keyword_search_finds_exact_rare_words(repo):
    results = search(repo, "Why do I get 'already shipped'?")

    assert results[0].path == "app/orders.py"
    assert "keywords" in results[0].matched_by


def test_keyword_search_matches_parts_of_camel_case_names(repo):
    results = search(repo, "order service")

    assert results[0].symbol == "OrderService"


def test_files_and_functions_named_in_the_question_come_first(repo):
    assert search(repo, "explain orders.py")[0].path == "app/orders.py"
    named = search(repo, "what does create_session return?")[0]
    assert named.symbol == "create_session" and "name" in named.matched_by


def test_results_respect_the_count_and_the_text_budget(repo):
    assert len(search(repo, "shop orders password payments", k=2)) == 2
    tight = search(repo, "shop orders password payments", k=10, budget=200)
    assert sum(len(r.content) for r in tight) <= 200


def test_an_index_made_with_another_model_is_not_used(repo, monkeypatch):
    monkeypatch.setattr(retrieval.embeddings.get_embedder(), "model_name", "another-model")

    with pytest.raises(vector_store.IndexMissing):
        search(repo, "password")


def test_a_missing_index_file_is_reported(repo):
    artifacts.remove_analysis(analysis_id(repo))
    vector_store.forget(analysis_id(repo))

    with pytest.raises(vector_store.IndexMissing):
        search(repo, "password")


def test_keyword_queries_accept_any_word_and_split_names():
    assert (
        keyword_query("How does getUserById work?")
        == "how | does | getuserbyid | get | user | by | id | work"
    )
    assert keyword_query("?!") is None


def test_rank_fusion_rewards_chunks_found_by_several_searches():
    fused = _rrf([("meaning", [1, 2, 3], 1.0), ("keywords", [3, 4], 1.0)])

    assert max(fused, key=lambda o: fused[o][0]) == 3
    assert fused[3][1] == ["meaning", "keywords"]
