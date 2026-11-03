"""How a mock interview moves along.

    start ──► choose questions from the practice list (write more first if there are too few)
          ──► ask the first one
    answer ──► grade in the background ──► follow-up on the biggest gap (once per question)
                                       └─► otherwise the next question, or the report

Each answer is graded in its own background job, because a model call takes seconds.
"""

import logging
import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    AnalysisFile,
    BatchStatus,
    InterviewQuestion,
    InterviewStatus,
    MockInterview,
    MockTurn,
    Progress,
    QuestionBatch,
    RepositoryAnalysis,
    TurnStatus,
)
from app.services import library
from app.services.ai import jobs as ai_jobs
from app.services.ai.generators import source_reader
from app.services.ai.grounding import Grounding
from app.services.interview.questions import write_questions
from app.services.llm.errors import LLMError
from app.services.mock.grading import grade_answer
from app.services.mock.report import build_report

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "Something went wrong while grading this answer. Try again in a moment."
# Questions you are least sure about come first.
_PREFERENCE = {Progress.NEW: 0, Progress.PRACTICING: 1, Progress.CONFIDENT: 2}


def now() -> datetime:
    return datetime.now(UTC)


# --- choosing questions ------------------------------------------------------------------------


def candidates(db: Session, interview: MockInterview) -> list[InterviewQuestion]:
    query = select(InterviewQuestion).where(
        InterviewQuestion.saved_repository_id == interview.saved_repository_id
    )
    if interview.categories:
        query = query.where(InterviewQuestion.category.in_(interview.categories))
    if interview.difficulty:
        query = query.where(InterviewQuestion.difficulty == interview.difficulty)
    return [q for q in db.scalars(query) if q.answer_points]


def choose(db: Session, interview: MockInterview) -> list[InterviewQuestion]:
    """Questions for this interview, least practised first, shuffled within each group."""
    pool = candidates(db, interview)
    random.shuffle(pool)
    pool.sort(key=lambda q: _PREFERENCE.get(q.status, 3))
    picked = pool[: interview.question_count]
    random.shuffle(picked)  # do not always start with the easiest kind
    return picked


def plan_from(questions: list[InterviewQuestion]) -> list[dict]:
    return [
        {
            "question_id": str(q.id),
            "prompt": q.question,
            "category": q.category,
            "difficulty": q.difficulty,
            "reference_points": q.answer_points,
        }
        for q in questions
    ]


def activate(db: Session, interview: MockInterview, questions: list[InterviewQuestion]) -> None:
    interview.plan = plan_from(questions)
    interview.question_count = len(questions)
    interview.status = InterviewStatus.ACTIVE
    _ask_next(db, interview)


def run_prepare_job(interview_id: uuid.UUID, batch_id: uuid.UUID) -> None:
    """Write the missing questions (they also join the practice list), then begin."""
    with SessionLocal() as db:
        interview = db.get(MockInterview, interview_id)
        batch = db.get(QuestionBatch, batch_id)
        if interview is None or interview.status != InterviewStatus.PREPARING or batch is None:
            return
        analysis = (
            db.get(RepositoryAnalysis, interview.analysis_id) if interview.analysis_id else None
        )
        provider = ai_jobs.create_provider()
        try:
            if analysis is None:
                raise LLMError("This version is no longer available. Start a new interview.")
            new = write_questions(db, provider, batch, analysis)
            db.add_all(new)
            batch.question_count = len(new)
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = now()
            db.flush()
            questions = choose(db, interview)
            if not questions:
                raise LLMError(
                    "No questions could be written for this interview. Try other topics."
                )
            activate(db, interview, questions)
            db.commit()
        except LLMError as error:
            _fail_preparation(db, interview_id, batch_id, error.code, error.message)
        except Exception:
            logger.exception("Preparing mock interview %s failed", interview_id)
            _fail_preparation(
                db,
                interview_id,
                batch_id,
                "ai_error",
                "The interview could not be prepared. Try again.",
            )
        finally:
            close = getattr(provider, "close", None)
            if close:
                close()


def _fail_preparation(
    db: Session, interview_id: uuid.UUID, batch_id: uuid.UUID, code: str, message: str
) -> None:
    db.rollback()
    for record in (db.get(MockInterview, interview_id), db.get(QuestionBatch, batch_id)):
        if record is not None:
            record.status = "failed"
            record.error_code = code
            record.error_message = message
            record.completed_at = now()
    db.commit()


# --- asking ----------------------------------------------------------------------------------


def turns_of(db: Session, interview_id: uuid.UUID) -> list[MockTurn]:
    return list(
        db.scalars(
            select(MockTurn)
            .where(MockTurn.interview_id == interview_id)
            .order_by(MockTurn.position)
            .execution_options(populate_existing=True)
        )
    )


def _add_turn(db: Session, interview: MockInterview, **fields) -> MockTurn:
    position = (
        db.scalar(select(func.max(MockTurn.position)).where(MockTurn.interview_id == interview.id))
        or 0
    ) + 1
    turn = MockTurn(interview_id=interview.id, position=position, asked_at=now(), **fields)
    db.add(turn)
    db.flush()
    return turn


def _ask_next(db: Session, interview: MockInterview) -> None:
    """Ask a follow-up to the last answer if it called for one, else the next question,
    else finish."""
    turns = turns_of(db, interview.id)
    last = turns[-1] if turns else None
    if (
        last is not None
        and last.kind == "question"
        and last.status == TurnStatus.GRADED
        and (last.grade or {}).get("follow_up")
    ):
        _add_turn(
            db,
            interview,
            kind="follow_up",
            question_id=last.question_id,
            prompt=last.grade["follow_up"],
            category=last.category,
            difficulty=last.difficulty,
            reference_points=last.reference_points,
        )
        return

    asked = sum(1 for t in turns if t.kind == "question")
    if asked < len(interview.plan):
        item = interview.plan[asked]
        _add_turn(
            db,
            interview,
            kind="question",
            question_id=uuid.UUID(item["question_id"]),
            prompt=item["prompt"],
            category=item["category"],
            difficulty=item["difficulty"],
            reference_points=item["reference_points"],
        )
        return
    finish(db, interview)


def finish(db: Session, interview: MockInterview) -> None:
    for turn in turns_of(db, interview.id):
        if turn.status == TurnStatus.WAITING:
            turn.status = TurnStatus.CANCELLED
    db.flush()
    interview.report = build_report(turns_of(db, interview.id))
    interview.status = InterviewStatus.COMPLETED
    interview.completed_at = now()


def skip(db: Session, interview: MockInterview, turn: MockTurn) -> None:
    turn.status = TurnStatus.SKIPPED
    turn.score = 0
    turn.answered_at = now()
    db.flush()
    _ask_next(db, interview)


# --- grading ------------------------------------------------------------------------------------


def run_grade_job(turn_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        turn = db.get(MockTurn, turn_id)
        if turn is None or turn.status != TurnStatus.GRADING:
            return
        interview = db.get(MockInterview, turn.interview_id)
        provider = ai_jobs.create_provider()
        try:
            _grade(db, provider, interview, turn)
            _ask_next(db, interview)
            db.commit()
        except LLMError as error:
            _fail_grading(db, turn_id, error.code, error.message)
        except Exception:
            logger.exception("Grading turn %s failed unexpectedly", turn_id)
            _fail_grading(db, turn_id, "ai_error", GENERIC_FAILURE)
        finally:
            close = getattr(provider, "close", None)
            if close:
                close()


def _grade(db: Session, provider, interview: MockInterview, turn: MockTurn) -> None:
    # Check quotes against the newest finished version: the code the person sees now.
    analysis = library.latest_completed(db, interview.saved_repository_id)
    analysis_id = analysis.id if analysis else None
    paths = (
        db.scalars(
            select(AnalysisFile.path).where(
                AnalysisFile.analysis_id == analysis_id, AnalysisFile.skipped_reason.is_(None)
            )
        )
        if analysis_id
        else []
    )
    grounding = Grounding(paths, source_reader(analysis_id) if analysis_id else (lambda _: None))
    asked_after = None
    if turn.kind == "follow_up":
        parent = db.scalar(
            select(MockTurn).where(
                MockTurn.interview_id == interview.id,
                MockTurn.position == turn.position - 1,
            )
        )
        asked_after = parent.prompt if parent else ""
    grade, result = grade_answer(
        db,
        provider,
        analysis_id,
        grounding,
        turn.prompt,
        turn.reference_points,
        turn.answer or "",
        asked_after,
    )
    turn.grade = grade.model_dump()
    turn.score = grade.score
    turn.model = result.model
    turn.status = TurnStatus.GRADED
    turn.graded_at = now()
    db.flush()


def _fail_grading(db: Session, turn_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    turn = db.get(MockTurn, turn_id)
    if turn is not None:
        turn.status = TurnStatus.FAILED
        turn.error_code = code
        turn.error_message = message
        db.commit()


def mark_interrupted(db: Session) -> int:
    """Grading and preparation that died with a previous server process."""
    turns = db.execute(
        update(MockTurn)
        .where(MockTurn.status == TurnStatus.GRADING)
        .values(
            status=TurnStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while this answer was being graded. Try again.",
        )
    )
    interviews = db.execute(
        update(MockInterview)
        .where(MockInterview.status == InterviewStatus.PREPARING)
        .values(
            status=InterviewStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while the interview was being prepared.",
            completed_at=now(),
        )
    )
    db.commit()
    return (turns.rowcount or 0) + (interviews.rowcount or 0)
