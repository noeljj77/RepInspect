import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AiExplanation
from app.services.ai import jobs
from app.services.ai.schemas import (
    RawCitation,
    RawFileExplanation,
    RawFinding,
    RawKeySymbol,
    RawOverview,
    RawSection,
    RawTechnologies,
    RawTechnology,
)
from app.services.llm.errors import (
    LLMBadResponse,
    LLMBlocked,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMUnavailable,
)
from app.worker.runner import get_job_runner
from tests.test_repositories_api import NoopRunner, add, sign_up

MAIN = (
    "from fastapi import FastAPI\n"  # 1
    "from app import util\n"  # 2
    "\n"  # 3
    "app = FastAPI()\n"  # 4
    "\n"  # 5
    "\n"  # 6
    "@app.get('/health')\n"  # 7
    "def health():\n"  # 8
    "    return util.ok()\n"  # 9
)
FILES = {
    "README.md": "# Shop\n\nSells things online.\n",
    "pyproject.toml": '[project]\ndependencies = ["fastapi>=0.1"]\n',
    "app/__init__.py": "",
    "app/main.py": MAIN,
    "app/util.py": "def ok():\n    return 'ok'\n",
    ".env": "DATABASE_PASSWORD=hunter2-super-secret",
}
MAIN_PATH = "app/main.py"


def cite(path=MAIN_PATH, start=4, end=4, quote="app = FastAPI()"):
    return RawCitation(path=path, start_line=start, end_line=end, quote=quote)


def finding(statement="Creates the app.", *citations):
    return RawFinding(statement=statement, citations=list(citations) if citations else [cite()])


def overview(*sections):
    return RawOverview(sections=list(sections))


def section(key, summary="A summary.", determined=True, findings=None):
    return RawSection(
        key=key,
        summary=summary,
        determined=determined,
        findings=findings if findings is not None else [finding()],
    )


@pytest.fixture
def repo(github, client, llm):
    sign_up(client)
    github.files = FILES
    llm.respond(RawOverview, overview(section("purpose"), section("backend")))
    llm.respond(
        RawTechnologies,
        RawTechnologies(
            technologies=[
                RawTechnology(
                    name="FastAPI",
                    what_it_is="A web framework.",
                    plausible_reason="It may be fast.",
                    advantages=["Fast"],
                    alternatives=["Flask"],
                    trade_offs=["Young"],
                )
            ]
        ),
    )
    llm.respond(
        RawFileExplanation,
        RawFileExplanation(
            purpose="Defines the app.",
            determined=True,
            inputs_outputs="Serves HTTP.",
            findings=[finding()],
            key_symbols=[RawKeySymbol(name="health", explanation="Health check.")],
        ),
    )
    return add(client).json()


def url(repo, kind, suffix=""):
    return f"/api/repositories/{repo['id']}/ai/{kind}{suffix}"


def get(client, repo, kind, **params):
    return client.get(url(repo, kind), params=params)


def post(client, repo, kind, **params):
    return client.post(url(repo, kind), params=params)


# --- reading ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["overview", "technologies"])
def test_nothing_has_been_requested_yet(client, repo, kind):
    body = get(client, repo, kind).json()

    assert (body["status"], body["kind"], body["content"]) == ("missing", kind, None)


def test_a_file_explanation_is_requested_by_path(client, repo):
    assert get(client, repo, "file", path=MAIN_PATH).json()["status"] == "missing"
    assert get(client, repo, "file").status_code == 422
    assert get(client, repo, "file", path="app/nope.py").status_code == 404
    assert (
        get(client, repo, "file", path=".env").status_code == 404
    )  # skipped files cannot be explained


def test_unknown_kinds_are_rejected(client, repo):
    assert get(client, repo, "poem").status_code == 422
    assert post(client, repo, "poem").status_code == 422


# --- generating -----------------------------------------------------------------------------------------------


def test_generating_an_overview_stores_the_checked_result(client, repo, llm):
    response = post(client, repo, "overview")

    assert response.status_code == 202
    body = get(client, repo, "overview").json()
    assert (body["status"], body["model"]) == ("completed", "fake-model")
    sections = body["content"]["sections"]
    assert [s["key"] for s in sections][:3] == ["purpose", "problem", "technologies"] and len(
        sections
    ) == 10
    purpose = sections[0]
    assert purpose["findings"][0]["verified"] is True
    assert purpose["findings"][0]["citations"][0] == {
        "path": MAIN_PATH,
        "start_line": 4,
        "end_line": 4,
        "quote": "app = FastAPI()",
    }
    assert (
        next(s for s in sections if s["key"] == "frontend")["determined"] is False
    )  # skipped by the model


def test_unverifiable_claims_are_marked_and_counted(client, repo, llm):
    invented = finding(
        "Uses Django.", cite(path="requirements.txt", start=1, end=1, quote="django==5.0")
    )
    wrong_lines = finding("Defines the route.", cite(start=1, end=1, quote="@app.get('/health')"))
    unsourced = RawFinding(statement="Probably caches things.", citations=[])
    llm.respond(
        RawOverview, overview(section("purpose", findings=[invented, wrong_lines, unsourced]))
    )

    post(client, repo, "overview")
    content = get(client, repo, "overview").json()["content"]

    findings = content["sections"][0]["findings"]
    assert [f["verified"] for f in findings] == [False, True, False]
    assert findings[1]["citations"][0]["start_line"] == 7  # the model's line numbers were corrected
    assert content["removed_citations"] == 1


def test_files_the_model_invents_are_flagged(client, repo, llm):
    llm.respond(
        RawOverview, overview(section("modules", summary="The core is in src/engine/core.py."))
    )

    post(client, repo, "overview")
    modules = next(
        s
        for s in get(client, repo, "overview").json()["content"]["sections"]
        if s["key"] == "modules"
    )

    assert modules["ungrounded_paths"] == ["src/engine/core.py"]


def test_technology_explanations_cover_only_detected_technologies(client, repo, llm):
    llm.respond(
        RawTechnologies,
        RawTechnologies(
            technologies=[
                RawTechnology(
                    name="fastapi",
                    what_it_is="Web framework.",
                    plausible_reason="Possibly speed.",
                    advantages=[],
                    alternatives=[],
                    trade_offs=[],
                ),
                RawTechnology(
                    name="Kubernetes",
                    what_it_is="Invented.",
                    plausible_reason="",
                    advantages=[],
                    alternatives=[],
                    trade_offs=[],
                ),
            ]
        ),
    )

    post(client, repo, "technologies")
    technologies = get(client, repo, "technologies").json()["content"]["technologies"]

    assert [t["name"] for t in technologies] == ["FastAPI"]


def test_a_file_explanation_keeps_only_real_symbols(client, repo, llm):
    llm.respond(
        RawFileExplanation,
        RawFileExplanation(
            purpose="Defines the app.",
            determined=True,
            inputs_outputs="",
            findings=[finding()],
            key_symbols=[
                RawKeySymbol(name="health", explanation="Health check."),
                RawKeySymbol(name="launch_rockets", explanation="Invented."),
            ],
        ),
    )

    post(client, repo, "file", path=MAIN_PATH)
    body = get(client, repo, "file", path=MAIN_PATH).json()

    assert body["path"] == MAIN_PATH
    assert [(s["name"], s["start_line"]) for s in body["content"]["key_symbols"]] == [
        ("health", 7)
    ]  # the range starts at the decorator


def test_each_file_has_its_own_explanation(client, repo):
    post(client, repo, "file", path=MAIN_PATH)

    assert get(client, repo, "file", path=MAIN_PATH).json()["status"] == "completed"
    assert get(client, repo, "file", path="app/util.py").json()["status"] == "missing"


def test_technologies_cannot_be_explained_when_none_were_found(github, client, llm):
    sign_up(client)
    github.files = {"notes.txt": "plain text only\n", "README.md": "# x\n"}
    repo = add(client).json()

    assert post(client, repo, "technologies").status_code == 409


# --- what the model is given --------------------------------------------------------------------------------------


def test_the_prompt_contains_facts_and_numbered_code_but_never_skipped_files(client, repo, llm):
    post(client, repo, "overview")

    [call] = llm.calls
    prompt = call.prompt
    assert "Sells things online." in prompt  # README
    assert "4| app = FastAPI()" in prompt  # numbered excerpt
    assert "GET /health -> app/main.py:7 health" in prompt  # discovered route
    assert "FastAPI [Backend framework]" in prompt
    assert "hunter2" not in prompt and "DATABASE_PASSWORD" not in prompt  # .env is never imported
    assert call.schema is RawOverview


def test_the_system_prompt_carries_the_safety_rules(client, repo, llm):
    post(client, repo, "overview")

    system = llm.calls[0].system
    for rule in (
        "Never invent",
        "untrusted",
        "Never follow it",
        "exact text",
        "only the JSON object",
    ):
        assert rule in system


def test_every_request_uses_a_fresh_boundary(client, repo, llm):
    post(client, repo, "overview")
    post(client, repo, "overview")

    first, second = (c.prompt for c in llm.calls)
    code = lambda p: p.split("the code ", 1)[1].split(" ", 1)[0]  # noqa: E731
    assert code(first) != code(second)


def test_the_model_client_is_always_closed(client, repo, llm):
    post(client, repo, "overview")

    assert llm.closed is True


# --- failures ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "code", "words"),
    [
        (
            LLMUnavailable("The AI service is busy right now. Try again in a moment."),
            "ai_unavailable",
            "busy",
        ),
        (
            LLMRateLimited("The AI is receiving too many requests. Try again in a minute."),
            "ai_rate_limited",
            "too many",
        ),
        (
            LLMQuotaExhausted("The daily AI allowance has been used up. Try again tomorrow."),
            "ai_quota_exhausted",
            "tomorrow",
        ),
        (LLMBlocked("The AI declined to analyze this content."), "ai_blocked", "declined"),
        (
            LLMBadResponse("The AI returned an answer in the wrong format. Try again."),
            "ai_bad_response",
            "wrong format",
        ),
    ],
)
def test_provider_failures_are_recorded_with_a_clear_message(client, repo, llm, error, code, words):
    llm.respond(RawOverview, error)

    post(client, repo, "overview")
    body = get(client, repo, "overview").json()

    assert (body["status"], body["error_code"]) == ("failed", code)
    assert words in body["error_message"] and body["content"] is None


def test_unexpected_errors_are_hidden_from_the_user_but_logged(client, repo, llm, caplog):
    llm.respond(RawOverview, RuntimeError("boom: key=AIzaSECRET at /srv/path"))

    with caplog.at_level(logging.ERROR):
        post(client, repo, "overview")
    body = get(client, repo, "overview").json()

    assert body["status"] == "failed" and body["error_code"] == "ai_error"
    assert "boom" not in body["error_message"] and "AIza" not in body["error_message"]
    assert "AI job" in caplog.text


def test_a_failed_request_can_be_retried_and_replaces_the_failure(client, repo, llm):
    llm.respond(RawOverview, LLMUnavailable("busy"))
    post(client, repo, "overview")
    assert get(client, repo, "overview").json()["status"] == "failed"

    llm.respond(RawOverview, overview(section("purpose")))
    assert post(client, repo, "overview").status_code == 202

    assert get(client, repo, "overview").json()["status"] == "completed"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AiExplanation)) == 1


def test_regenerating_replaces_the_earlier_result(client, repo, llm):
    llm.respond(RawOverview, overview(section("purpose", summary="First answer.")))
    post(client, repo, "overview")
    llm.respond(RawOverview, overview(section("purpose", summary="Second answer.")))

    post(client, repo, "overview")

    assert (
        get(client, repo, "overview").json()["content"]["sections"][0]["summary"]
        == "Second answer."
    )


def test_ai_that_is_not_set_up_is_reported_and_nothing_is_created(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "none")

    response = post(client, repo, "overview")

    assert response.status_code == 503 and "not set up" in response.json()["detail"]
    assert get(client, repo, "overview").json()["status"] == "missing"  # reading still works


# --- in progress, limits ------------------------------------------------------------------------------------------------


def test_a_request_in_progress_is_reported_and_cannot_be_duplicated(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    first = post(client, repo, "overview")

    assert first.status_code == 202 and first.json()["status"] == "pending"
    assert get(client, repo, "overview").json()["status"] == "pending"
    assert post(client, repo, "overview").status_code == 409


def test_a_person_gets_a_daily_allowance(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 2)

    assert post(client, repo, "overview").status_code == 202
    assert post(client, repo, "technologies").status_code == 202
    blocked = post(client, repo, "file", path=MAIN_PATH)

    assert blocked.status_code == 429 and "limit of 2" in blocked.json()["detail"]


def test_regenerating_still_uses_the_daily_allowance(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 2)

    assert post(client, repo, "overview").status_code == 202
    assert post(client, repo, "overview").status_code == 202  # replaces the first one
    blocked = post(client, repo, "overview")

    assert blocked.status_code == 429


def test_requests_that_are_turned_away_do_not_use_the_allowance(app, client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 2)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert post(client, repo, "overview").status_code == 202
    assert post(client, repo, "overview").status_code == 409  # already pending
    assert post(client, repo, "technologies").status_code == 202


def test_only_a_few_requests_may_run_at_once(app, client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_ai_jobs_per_user", 1)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert post(client, repo, "overview").status_code == 202
    blocked = post(client, repo, "technologies")

    assert blocked.status_code == 429 and "already running" in blocked.json()["detail"]


def test_one_persons_usage_does_not_count_against_another(
    app, github, client, other_client, llm, monkeypatch
):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 1)
    github.files = FILES
    sign_up(client)
    mine = add(client).json()
    sign_up(other_client, "grace@example.com")
    theirs = add(other_client).json()
    llm.respond(RawOverview, overview(section("purpose")))

    assert post(client, mine, "overview").status_code == 202
    assert post(other_client, theirs, "overview").status_code == 202


# --- access and lifecycle --------------------------------------------------------------------------------------------------


def test_other_users_cannot_read_or_start_explanations(client, other_client, repo):
    post(client, repo, "overview")
    sign_up(other_client, "grace@example.com")

    for response in (get(other_client, repo, "overview"), post(other_client, repo, "overview")):
        assert response.status_code == 404 and response.json() == {"detail": "Repository not found"}


def test_login_is_required(client, other_client, repo):
    assert get(other_client, repo, "overview").status_code == 401
    assert post(other_client, repo, "overview").status_code == 401


def test_nothing_is_available_before_the_analysis_finishes(app, github, client, llm):
    sign_up(client)
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    queued = add(client).json()

    assert get(client, queued, "overview").status_code == 409
    assert post(client, queued, "overview").status_code == 409


def test_a_new_analysis_starts_without_the_old_ones_explanations(client, repo, github):
    post(client, repo, "overview")
    assert get(client, repo, "overview").json()["status"] == "completed"

    client.post(f"/api/repositories/{repo['id']}/analyses")

    assert get(client, repo, "overview").json()["status"] == "missing"


def test_explanations_interrupted_by_a_restart_are_marked_failed(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    post(client, repo, "overview")

    with TestClient(app):  # starting the app runs the startup cleanup
        pass

    body = get(client, repo, "overview").json()
    assert (body["status"], body["error_code"]) == ("failed", "interrupted")


def test_a_job_for_a_missing_or_finished_row_does_nothing(llm):
    import uuid

    jobs.run_ai_job(uuid.uuid4())  # no such row: no error
    assert llm.calls == []


def test_deleting_a_user_removes_their_explanations(client, repo):
    post(client, repo, "overview")

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AiExplanation)) == 1
        db.execute(text("DELETE FROM users"))
        db.commit()
        assert db.scalar(select(func.count()).select_from(AiExplanation)) == 0
