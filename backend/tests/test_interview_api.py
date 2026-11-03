import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import QuestionBatch
from app.services.ai.schemas import RawCitation, RawDecision, RawImprovement, RawReport
from app.services.interview import questions as interview_questions
from app.services.interview.schemas import RawQuestion, RawQuestions
from app.services.llm.errors import LLMUnavailable
from app.worker.runner import get_job_runner
from tests.test_ai_api import FILES, MAIN_PATH, cite, finding
from tests.test_repositories_api import NoopRunner, add, sign_up

GOOD = cite()  # "app = FastAPI()" on line 4 of app/main.py
INVENTED = RawCitation(path="app/payments.py", start_line=1, end_line=1, quote="charge(card)")


def question(text="How is the app created?", category="architecture", difficulty="basic", *points):
    return RawQuestion(
        question=text,
        category=category,
        difficulty=difficulty,
        why_asked="Checks that you know the entry point.",
        answer_points=list(points) or [finding("The app is a FastAPI instance.", GOOD)],
        follow_ups=["Why FastAPI?", "  ", "How is it started?"],
    )


@pytest.fixture
def repo(github, client, llm):
    sign_up(client)
    github.files = FILES
    llm.respond(RawQuestions, RawQuestions(questions=[question()]))
    return add(client).json()


def url(repo, suffix=""):
    return f"/api/repositories/{repo['id']}/questions{suffix}"


def generate(client, repo, **body):
    return client.post(url(repo), json=body)


# --- the interview report ------------------------------------------------------------------------


def test_the_report_is_generated_and_checked_like_other_explanations(client, repo, llm):
    llm.respond(
        RawReport,
        RawReport(
            pitch="I built a small web API with FastAPI.",
            problem="Shops need a health check.",
            walkthrough=[finding("A FastAPI app is created.", GOOD)],
            decisions=[
                RawDecision(
                    decision="FastAPI was chosen for the API.",
                    citations=[GOOD, INVENTED],
                    alternatives=["Flask", ""],
                    trade_offs=["Younger ecosystem"],
                )
            ],
            highlights=[finding("Payments are charged.", INVENTED)],
            improvements=[
                RawImprovement(idea="Add tests", reason="There are none."),
                RawImprovement(idea=" ", reason="x"),
            ],
        ),
    )

    assert client.post(f"/api/repositories/{repo['id']}/ai/report").status_code == 202
    report = client.get(f"/api/repositories/{repo['id']}/ai/report").json()

    assert report["status"] == "completed"
    content = report["content"]
    assert content["pitch"] == "I built a small web API with FastAPI."
    assert content["walkthrough"][0]["verified"] is True
    decision = content["decisions"][0]
    assert decision["finding"]["verified"] is True and len(decision["finding"]["citations"]) == 1
    assert decision["alternatives"] == ["Flask"]
    assert content["highlights"][0]["verified"] is False  # its only citation was invented
    assert [i["idea"] for i in content["improvements"]] == ["Add tests"]
    assert content["removed_citations"] == 2
    assert "job interview" in llm.calls[-1].system and "untrusted" in llm.calls[-1].system


# --- generating questions -------------------------------------------------------------------------


def test_questions_are_generated_with_checked_answer_points(client, repo):
    response = generate(client, repo, count=5)

    assert response.status_code == 202
    data = client.get(url(repo)).json()
    assert (
        data["latest_batch"]["status"] == "completed"
        and data["latest_batch"]["question_count"] == 1
    )
    [q] = data["questions"]
    assert q["question"] == "How is the app created?"
    assert (q["category"], q["difficulty"], q["grounded"]) == ("architecture", "basic", True)
    assert q["answer_points"][0]["citations"][0]["path"] == MAIN_PATH
    assert q["follow_ups"] == ["Why FastAPI?", "How is it started?"]
    assert q["status"] == "new" and q["analysis_version"] == 1
    assert data["progress"] == {"new": 1, "practicing": 0, "confident": 0}


def test_answers_that_cannot_be_confirmed_are_marked(client, repo, llm):
    llm.respond(
        RawQuestions,
        RawQuestions(
            questions=[
                question(
                    "How are payments charged?",
                    "implementation",
                    "advanced",
                    finding("Cards are charged.", INVENTED),
                )
            ]
        ),
    )

    generate(client, repo)

    [q] = client.get(url(repo)).json()["questions"]
    assert q["grounded"] is False and q["removed_citations"] == 1


def test_the_request_shapes_the_prompt(client, repo, llm):
    generate(client, repo, count=4, categories=["security", "data"], difficulty="advanced")

    prompt = llm.calls[-1].prompt
    assert "write 4 interview questions" in prompt
    assert "Categories (use these exact keys): data, security." in prompt
    assert "Difficulty: advanced." in prompt
    assert "hunter2" not in prompt  # the .env file is never stored, so never sent


def test_only_the_requested_categories_and_count_are_kept(client, repo, llm):
    llm.respond(
        RawQuestions,
        RawQuestions(
            questions=[
                question("Q1 about data?", "data"),
                question("Q2 about security?", "security"),
                question("Q3 about data?", "data"),
                question("Q4 about data?", "data"),
            ]
        ),
    )

    generate(client, repo, count=3, categories=["data"])

    assert [q["question"] for q in client.get(url(repo)).json()["questions"]] == [
        "Q1 about data?",
        "Q3 about data?",
        "Q4 about data?",
    ]


def test_more_questions_are_added_without_repeating_earlier_ones(client, repo, llm):
    generate(client, repo)
    llm.respond(
        RawQuestions,
        RawQuestions(
            questions=[question("How is the app created?!"), question("Where is the health check?")]
        ),
    )

    generate(client, repo)

    assert "- How is the app created?" in llm.calls[-1].prompt  # told what was already asked
    assert [q["question"] for q in client.get(url(repo)).json()["questions"]] == [
        "How is the app created?",
        "Where is the health check?",
    ]


@pytest.mark.parametrize(
    "body", [{"count": 2}, {"count": 13}, {"categories": ["gossip"]}, {"difficulty": "extreme"}]
)
def test_invalid_requests_are_refused(client, repo, body):
    assert generate(client, repo, **body).status_code == 422


def test_failures_are_shown_on_the_latest_batch(client, repo, llm):
    llm.respond(RawQuestions, LLMUnavailable("The AI service is busy."))

    generate(client, repo)

    batch = client.get(url(repo)).json()["latest_batch"]
    assert batch["status"] == "failed" and batch["error_message"] == "The AI service is busy."


def test_one_batch_at_a_time(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()

    assert generate(client, repo).json()["latest_batch"]["status"] == "pending"
    assert generate(client, repo).status_code == 409


def test_questions_need_ai_to_be_set_up(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "none")

    assert generate(client, repo).status_code == 503


def test_questions_share_the_daily_ai_allowance(client, repo, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ai_requests_per_user_per_day", 1)

    assert generate(client, repo).status_code == 202
    assert client.post(f"/api/repositories/{repo['id']}/ai/overview").status_code == 429


def test_batches_interrupted_by_a_restart_are_marked_failed(app, client, repo):
    app.dependency_overrides[get_job_runner] = lambda: NoopRunner()
    generate(client, repo)

    with SessionLocal() as db:
        assert interview_questions.mark_interrupted(db) == 1
        assert db.query(QuestionBatch).one().error_code == "interrupted"


# --- progress ---------------------------------------------------------------------------------


def test_progress_and_draft_answers_are_saved(client, repo):
    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]

    updated = client.patch(
        url(repo, f"/{q['id']}"),
        json={"status": "practicing", "user_answer": "  It uses FastAPI. "},
    ).json()

    assert updated["status"] == "practicing" and updated["user_answer"] == "It uses FastAPI."
    assert updated["practiced_at"] is not None
    assert client.get(url(repo)).json()["progress"] == {"new": 0, "practicing": 1, "confident": 0}
    cleared = client.patch(url(repo, f"/{q['id']}"), json={"user_answer": None}).json()
    assert cleared["user_answer"] is None and cleared["status"] == "practicing"


def test_an_unknown_status_is_refused(client, repo):
    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]

    assert client.patch(url(repo, f"/{q['id']}"), json={"status": "mastered"}).status_code == 422


def test_questions_can_be_deleted(client, repo):
    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]

    assert client.delete(url(repo, f"/{q['id']}")).status_code == 204
    assert client.get(url(repo)).json()["questions"] == []


def test_questions_and_progress_survive_a_refresh(client, repo):
    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]
    client.patch(url(repo, f"/{q['id']}"), json={"status": "confident"})

    client.post(f"/api/repositories/{repo['id']}/analyses")

    [kept] = client.get(url(repo)).json()["questions"]
    assert kept["status"] == "confident" and kept["analysis_version"] == 1


def test_other_people_cannot_see_or_change_questions(client, other_client, repo):
    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]
    sign_up(other_client, "grace@example.com")

    assert other_client.get(url(repo)).status_code == 404
    assert generate(other_client, repo).status_code == 404
    assert (
        other_client.patch(url(repo, f"/{q['id']}"), json={"status": "confident"}).status_code
        == 404
    )
    assert other_client.delete(url(repo, f"/{q['id']}")).status_code == 404


def test_login_is_required(client, other_client, repo):
    assert other_client.get(url(repo)).status_code == 401


def test_the_library_list_shows_practice_progress(client, repo):
    [before] = client.get("/api/repositories").json()
    assert before["practice"] == {"total": 0, "practicing": 0, "confident": 0}

    generate(client, repo)
    q = client.get(url(repo)).json()["questions"][0]
    client.patch(url(repo, f"/{q['id']}"), json={"status": "confident"})

    [after] = client.get("/api/repositories").json()
    assert after["practice"] == {"total": 1, "practicing": 0, "confident": 1}


def test_practice_progress_is_counted_per_repository(client, repo, github, llm):
    generate(client, repo)
    llm.respond(RawQuestions, RawQuestions(questions=[question("Second?"), question("Third?")]))
    github.files = FILES
    other = add(client, "https://github.com/acme/other").json()
    generate(client, other)

    summaries = {s["id"]: s["practice"]["total"] for s in client.get("/api/repositories").json()}

    assert summaries == {repo["id"]: 1, other["id"]: 2}
