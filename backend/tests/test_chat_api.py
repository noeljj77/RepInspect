import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ChatMessage, MessageStatus
from app.services.ai.schemas import RawCitation
from app.services.llm.errors import LLMQuotaExhausted, LLMUnavailable
from app.services.rag import chat_jobs
from app.services.rag.schemas import RawChatAnswer
from app.storage import artifacts
from app.worker.runner import get_job_runner
from tests.test_rag_index import FILES, analysis_id
from tests.test_repositories_api import NoopRunner, add, sign_up

VERIFY_QUOTE = "return argon2.verify(stored_hash, plain)"


def answer(text="Passwords are checked with argon2 [1].", *citations, answerable=True):
    if not citations:
        citations = (RawCitation(path="app/auth.py", start_line=6, end_line=6, quote=VERIFY_QUOTE),)
    return RawChatAnswer(answerable=answerable, answer=text, citations=list(citations))


@pytest.fixture
def repo(github, client, llm):
    sign_up(client)
    github.files = FILES
    llm.respond(RawChatAnswer, answer())
    return add(client).json()


def chats(repo, suffix=""):
    return f"/api/repositories/{repo['id']}/chats{suffix}"


def start(client, repo, question="How are passwords checked?"):
    return client.post(chats(repo), json={"question": question})


def ask(client, repo, chat_id, question):
    return client.post(chats(repo, f"/{chat_id}/messages"), json={"question": question})


# --- asking -----------------------------------------------------------------------------------


def test_a_question_gets_an_answer_backed_by_the_code(client, repo):
    response = start(client, repo)

    assert response.status_code == 201
    chat = client.get(chats(repo, f"/{response.json()['id']}")).json()
    assert chat["title"] == "How are passwords checked?"
    question, reply = chat["messages"]
    assert (question["role"], question["content"]) == ("user", "How are passwords checked?")
    assert reply["role"] == "assistant" and reply["status"] == "completed"
    assert reply["content"] == "Passwords are checked with argon2 [1]."
    assert reply["model"] == "fake-model"
    details = reply["details"]
    assert details["answerable"] is True
    assert details["citations"] == [
        {"path": "app/auth.py", "start_line": 6, "end_line": 6, "quote": VERIFY_QUOTE}
    ]
    assert details["removed_citations"] == 0


def test_the_answer_lists_what_the_search_found(client, repo):
    chat = start(client, repo).json()

    sources = chat["messages"][1]["details"]["sources"]
    assert sources[0]["path"] == "app/auth.py" and sources[0]["symbol"] == "verify_password"
    assert set(sources[0]["matched_by"]) <= {"meaning", "keywords", "name"}


def test_the_model_sees_fenced_excerpts_and_never_secret_files(client, repo, llm):
    start(client, repo)

    call = llm.calls[-1]
    assert "Use only the excerpts" in call.system and "untrusted" in call.system
    boundary = call.prompt.split("contain the code ", 1)[1].split(".", 1)[0]
    assert f"<<<{boundary}:BEGIN excerpt" in call.prompt
    assert 'path="app/auth.py"' in call.prompt
    assert "6| " + "    " + VERIFY_QUOTE in call.prompt  # real line numbers
    assert call.prompt.rstrip().endswith("Question: How are passwords checked?")
    assert "hunter2" not in call.prompt


def test_invented_citations_are_removed_and_markers_renumbered(client, repo, llm):
    llm.respond(
        RawChatAnswer,
        answer(
            "It emails the admin [1]. It uses argon2 [2].",
            RawCitation(path="app/mail.py", start_line=1, end_line=1, quote="send_email(admin)"),
            RawCitation(path="app/auth.py", start_line=2, end_line=2, quote=VERIFY_QUOTE),
        ),
    )

    reply = start(client, repo).json()["messages"][1]

    assert reply["content"] == "It emails the admin. It uses argon2 [1]."
    assert reply["details"]["removed_citations"] == 1
    assert reply["details"]["citations"][0]["start_line"] == 6  # corrected


def test_questions_the_code_cannot_answer_are_marked(client, repo, llm):
    llm.respond(
        RawChatAnswer, RawChatAnswer(answerable=False, answer="No database is used.", citations=[])
    )

    reply = start(client, repo, "Which database does it use?").json()["messages"][1]

    assert reply["details"]["answerable"] is False and reply["details"]["citations"] == []


def test_follow_up_questions_carry_the_conversation(client, repo, llm):
    chat = start(client, repo).json()

    response = ask(client, repo, chat["id"], "And where is it called?")

    assert response.status_code == 202
    assert [m["role"] for m in response.json()["messages"]] == ["user", "assistant"] * 2
    prompt = llm.calls[-1].prompt
    assert "Earlier in this conversation:" in prompt
    assert (
        "Question: How are passwords checked?\nAnswer: Passwords are checked with argon2." in prompt
    )
    assert prompt.rstrip().endswith("Question: And where is it called?")


def test_conversations_are_listed_newest_first_and_can_be_deleted(client, repo):
    first = start(client, repo, "First?").json()
    second = start(client, repo, "Second?").json()

    assert [c["id"] for c in client.get(chats(repo)).json()] == [second["id"], first["id"]]
    assert client.delete(chats(repo, f"/{first['id']}")).status_code == 204
    assert client.get(chats(repo, f"/{first['id']}")).status_code == 404
    assert [c["id"] for c in client.get(chats(repo)).json()] == [second["id"]]


def test_long_questions_get_a_short_title(client, repo):
    chat = start(client, repo, "word " * 60).json()

    assert len(chat["title"]) <= 80 and chat["title"].endswith("…")


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
def test_empty_or_huge_questions_are_rejected(client, repo, question):
    assert start(client, repo, question).status_code == 422


# --- failures and limits -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LLMUnavailable("The AI service is busy."), "ai_unavailable"),
        (LLMQuotaExhausted("Today's AI quota is used up."), "ai_quota_exhausted"),
    ],
)
def test_provider_failures_are_shown_and_can_be_retried(client, repo, llm, error, code):
    llm.respond(RawChatAnswer, error)
    chat = start(client, repo).json()
    reply = chat["messages"][1]
    assert reply["status"] == "failed" and reply["error_code"] == code
    assert reply["error_message"] == error.message

    llm.respond(RawChatAnswer, answer())
    retried = client.post(chats(repo, f"/{chat['id']}/messages/{reply['id']}/retry"))

    assert retried.status_code == 202
    assert retried.json()["messages"][1]["status"] == "completed"


def test_only_the_latest_failed_answer_can_be_retried(client, repo):
    chat = start(client, repo).json()
    reply = chat["messages"][1]

    response = client.post(chats(repo, f"/{chat['id']}/messages/{reply['id']}/retry"))

    assert response.status_code == 409  # it did not fail


def test_unexpected_errors_are_hidden_but_logged(client, repo, llm, caplog):
    llm.respond(RawChatAnswer, RuntimeError("secret stack trace"))

    reply = start(client, repo).json()["messages"][1]

    assert reply["error_code"] == "chat_error" and "secret" not in reply["error_message"]
    assert "secret stack trace" in caplog.text


def test_a_missing_index_file_is_reported_with_a_fix(client, repo):
    artifacts.remove_analysis(analysis_id(repo))

    reply = start(client, repo).json()["messages"][1]

    assert reply["error_code"] == "index_missing" and "Rebuild" in reply["error_message"]


def test_chat_needs_a_ready_index(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    client.post(f"/api/repositories/{repo['id']}/index")  # now pending

    response = start(client, repo)

    assert response.status_code == 409 and "search index" in response.json()["detail"]


def test_chat_that_is_not_set_up_is_reported(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "none")

    response = start(client, repo)

    assert response.status_code == 503 and client.get(chats(repo)).json() == []


def test_one_question_at_a_time_per_conversation(app, client, repo):
    chat = start(client, repo).json()
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert ask(client, repo, chat["id"], "Next?").status_code == 202
    assert ask(client, repo, chat["id"], "And another?").status_code == 409


def test_chat_shares_the_daily_ai_allowance_with_explanations(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 2)

    assert start(client, repo).status_code == 201
    assert client.post(f"/api/repositories/{repo['id']}/ai/overview").status_code == 202
    blocked = start(client, repo)

    assert blocked.status_code == 429 and "limit of 2" in blocked.json()["detail"]


def test_running_answers_count_towards_the_limit_on_simultaneous_requests(
    app, client, repo, monkeypatch
):
    monkeypatch.setattr(get_settings(), "max_active_ai_jobs_per_user", 1)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert start(client, repo).status_code == 201
    blocked = client.post(f"/api/repositories/{repo['id']}/ai/overview")

    assert blocked.status_code == 429 and "already running" in blocked.json()["detail"]


def test_answers_interrupted_by_a_restart_are_marked_failed(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    start(client, repo)

    with SessionLocal() as db:
        assert chat_jobs.mark_interrupted(db) == 1
        failed = db.query(ChatMessage).filter_by(role="assistant").one()
        assert failed.status == MessageStatus.FAILED and failed.error_code == "interrupted"


def test_a_job_for_a_finished_answer_does_nothing(client, repo, llm):
    reply = start(client, repo).json()["messages"][1]
    calls = len(llm.calls)

    chat_jobs.run_chat_job(reply["id"])

    assert len(llm.calls) == calls


# --- access -------------------------------------------------------------------------------------------


def test_other_people_cannot_see_or_use_a_conversation(client, other_client, repo):
    chat = start(client, repo).json()
    sign_up(other_client, "grace@example.com")

    assert other_client.get(chats(repo)).status_code == 404
    assert other_client.get(chats(repo, f"/{chat['id']}")).status_code == 404
    assert ask(other_client, repo, chat["id"], "Hi?").status_code == 404
    assert other_client.delete(chats(repo, f"/{chat['id']}")).status_code == 404
    assert other_client.get(f"/api/repositories/{repo['id']}/index").status_code == 404


def test_a_conversation_belongs_to_one_repository(github, client, repo):
    chat = start(client, repo).json()
    github.files = FILES
    other = add(client, "https://github.com/octo/other").json()

    assert client.get(chats(other, f"/{chat['id']}")).status_code == 404


def test_login_is_required(client, other_client, repo):
    assert other_client.get(chats(repo)).status_code == 401
    assert other_client.post(chats(repo), json={"question": "Hi?"}).status_code == 401


def test_a_new_analysis_starts_with_no_conversations(client, repo):
    start(client, repo)

    client.post(f"/api/repositories/{repo['id']}/analyses")

    assert client.get(chats(repo)).json() == []
