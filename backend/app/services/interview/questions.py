"""Generate interview questions about a repository, and check their answer points.

    evidence pack (as for the overview) + questions already asked ─► model ─► grounding
    ─► interview_questions rows (appended to the repository's list)

Each answer point goes through the same citation checks as the AI explanations. A question
whose points could not be confirmed is still kept (it may be a fair question) but marked
as not grounded, so the page can say its suggested answer is only a guess.
"""

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    BatchStatus,
    InterviewQuestion,
    QuestionBatch,
    RepositoryAnalysis,
    SavedRepository,
)
from app.services.ai import context
from app.services.ai import jobs as ai_jobs
from app.services.ai.generators import source_reader
from app.services.ai.grounding import Grounding
from app.services.ai.prompts import CITATIONS_RULE, UNTRUSTED_RULE, frame
from app.services.interview.schemas import CATEGORIES, RawQuestions
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMError

logger = logging.getLogger(__name__)

QUESTIONS_MAX_TOKENS = 8000
MAX_EARLIER_LISTED = 80  # earlier questions shown to the model so it does not repeat them
MAX_POINTS = 5
MAX_FOLLOW_UPS = 3
MAX_TEXT = 600
GENERIC_FAILURE = "Something went wrong while writing questions. Try again in a moment."

SYSTEM_QUESTIONS = f"""\
You are an experienced technical interviewer preparing questions for a candidate about a \
project the candidate built. Good questions are specific to this code: they name its parts \
and probe whether the candidate understands why it works the way it does.

Rules you must always follow:
1. Use only the material in the data blocks. Never invent files, functions, endpoints, tables \
or behaviour. Ask only about things the material shows.
2. {UNTRUSTED_RULE}
3. Answer points are what a strong answer would cover. Each is a finding. {CITATIONS_RULE}
4. Mix difficulties as requested. Basic questions check what something does; intermediate \
ones ask how and why; advanced ones probe trade-offs, failure cases and alternatives.
5. Do not repeat or rephrase any question listed as already asked.
6. Reply with only the JSON object that the schema describes."""


def _task(
    count: int, categories: list[str] | None, difficulty: str | None, earlier: list[str]
) -> str:
    wanted = ", ".join(categories) if categories else "a mix of " + ", ".join(CATEGORIES)
    level = difficulty or "a mix of basic, intermediate and advanced"
    lines = [
        f"Task: write {count} interview questions about this project.",
        f"Categories (use these exact keys): {wanted}.",
        f"Difficulty: {level}.",
        "For each: why_asked (one sentence), two to five answer_points with citations, and up "
        "to three follow_ups.",
    ]
    if earlier:
        lines.append("Already asked (do not repeat):")
        lines += [f"- {q}" for q in earlier]
    return "\n".join(lines)


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def write_questions(
    db: Session, provider: LLMProvider, batch: QuestionBatch, analysis: RepositoryAnalysis
) -> list[InterviewQuestion]:
    repository = db.get(SavedRepository, batch.saved_repository_id)
    facts = context.load_facts(db, repository, analysis)
    reader = source_reader(analysis.id)
    boundary = context.new_boundary()
    pack = context.build_overview_pack(facts, reader, boundary, get_settings().ai_context_chars)

    earlier = list(
        db.scalars(
            select(InterviewQuestion.question)
            .where(InterviewQuestion.saved_repository_id == repository.id)
            .order_by(InterviewQuestion.position.desc())
            .limit(MAX_EARLIER_LISTED)
        )
    )
    result = provider.generate_structured(
        system=SYSTEM_QUESTIONS,
        prompt=frame(
            boundary,
            pack.text(),
            _task(batch.requested_count, batch.categories, batch.difficulty, earlier),
        ),
        schema=RawQuestions,
        max_output_tokens=QUESTIONS_MAX_TOKENS,
    )
    batch.model = result.model
    batch.input_tokens = result.input_tokens
    batch.output_tokens = result.output_tokens

    grounding = Grounding(facts.files, reader)
    seen = {_normalized(q) for q in earlier}
    position = (
        db.scalar(
            select(func.max(InterviewQuestion.position)).where(
                InterviewQuestion.saved_repository_id == repository.id
            )
        )
        or 0
    )
    questions: list[InterviewQuestion] = []
    for raw in result.data.questions:
        key = _normalized(raw.question)
        if not key or key in seen or len(questions) >= batch.requested_count:
            continue  # empty, a repeat, or more than was asked for
        if batch.categories and raw.category not in batch.categories:
            continue
        seen.add(key)
        points, removed = [], 0
        for raw_point in raw.answer_points[:MAX_POINTS]:
            finding, dropped = grounding.ground_finding(raw_point)
            removed += dropped
            if finding.statement:
                points.append(finding)
        position += 1
        questions.append(
            InterviewQuestion(
                saved_repository_id=repository.id,
                batch_id=batch.id,
                analysis_version=analysis.version,
                position=position,
                category=raw.category,
                difficulty=raw.difficulty,
                question=_clip(raw.question),
                why_asked=_clip(raw.why_asked),
                answer_points=[p.model_dump() for p in points],
                follow_ups=[_clip(f, 300) for f in raw.follow_ups if f.strip()][:MAX_FOLLOW_UPS],
                grounded=any(p.verified for p in points),
                removed_citations=removed,
            )
        )
    return questions


def run_question_job(batch_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        batch = db.get(QuestionBatch, batch_id)
        if batch is None or batch.status != BatchStatus.PENDING:
            return
        analysis = db.get(RepositoryAnalysis, batch.analysis_id) if batch.analysis_id else None
        if analysis is None:
            _fail(
                db, batch_id, "analysis_missing", "This version is no longer available. Try again."
            )
            return
        provider = ai_jobs.create_provider()
        try:
            questions = write_questions(db, provider, batch, analysis)
            db.add_all(questions)
            batch.question_count = len(questions)
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.now(UTC)
            db.commit()
        except LLMError as error:
            _fail(db, batch_id, error.code, error.message)
        except Exception:
            logger.exception("Question batch %s failed unexpectedly", batch_id)
            _fail(db, batch_id, "ai_error", GENERIC_FAILURE)
        finally:
            close = getattr(provider, "close", None)
            if close:
                close()


def _fail(db: Session, batch_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    batch = db.get(QuestionBatch, batch_id)
    if batch is not None:
        batch.status = BatchStatus.FAILED
        batch.error_code = code
        batch.error_message = message
        batch.completed_at = datetime.now(UTC)
        db.commit()


def mark_interrupted(db: Session) -> int:
    """Fail batches whose job died with a previous server process."""
    result = db.execute(
        update(QuestionBatch)
        .where(QuestionBatch.status == BatchStatus.PENDING)
        .values(
            status=BatchStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while questions were being written. Try again.",
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return result.rowcount or 0


def progress_counts(
    db: Session, repository_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """How many practice questions each repository has, by progress, in one query."""
    counts = {rid: {"total": 0, "practicing": 0, "confident": 0} for rid in repository_ids}
    if repository_ids:
        rows = db.execute(
            select(
                InterviewQuestion.saved_repository_id,
                InterviewQuestion.status,
                func.count(),
            )
            .where(InterviewQuestion.saved_repository_id.in_(repository_ids))
            .group_by(InterviewQuestion.saved_repository_id, InterviewQuestion.status)
        )
        for repository_id, status, count in rows:
            counts[repository_id]["total"] += count
            if status in ("practicing", "confident"):
                counts[repository_id][status] = count
    return counts
