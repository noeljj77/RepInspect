"""Background job that fills in one pending AI explanation.

Calls to a language model take seconds and can fail in many ways, so they run outside
the HTTP request, like repository analysis. The row's status tells the page what to show.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AiExplanation, AiKind, AiStatus, RepositoryAnalysis, SavedRepository
from app.services.ai import context, generators
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMError
from app.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "Something went wrong while generating this. Try again in a moment."


def create_provider() -> LLMProvider:
    """Separate function so tests can substitute a fake model."""
    return create_llm_provider()


def run_ai_job(explanation_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        record = db.get(AiExplanation, explanation_id)
        if record is None or record.status != AiStatus.PENDING:
            return
        try:
            _generate(db, record)
        except LLMError as error:
            _fail(db, explanation_id, error.code, error.message)
        except Exception:
            logger.exception("AI job %s failed unexpectedly", explanation_id)
            _fail(db, explanation_id, "ai_error", GENERIC_FAILURE)


def _generate(db: Session, record: AiExplanation) -> None:
    analysis = db.get(RepositoryAnalysis, record.analysis_id)
    repository = db.get(SavedRepository, analysis.saved_repository_id)
    provider = create_provider()
    try:
        facts = context.load_facts(db, repository, analysis)
        if record.kind == AiKind.OVERVIEW:
            generated = generators.generate_overview(provider, facts, analysis.id)
        elif record.kind == AiKind.TECHNOLOGIES:
            generated = generators.generate_technologies(provider, facts)
        else:
            generated = generators.generate_file_explanation(
                provider, facts, analysis.id, record.target_path
            )
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    record.content = generated.content.model_dump()
    record.model = generated.model
    record.input_tokens = generated.input_tokens
    record.output_tokens = generated.output_tokens
    record.status = AiStatus.COMPLETED
    record.completed_at = datetime.now(UTC)
    db.commit()
    logger.info(
        "AI %s done with %s: %s tokens in, %s out",
        record.kind,
        generated.model,
        generated.input_tokens,
        generated.output_tokens,
    )


def _fail(db: Session, explanation_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    record = db.get(AiExplanation, explanation_id)
    if record is not None:
        record.status = AiStatus.FAILED
        record.error_code = code
        record.error_message = message
        record.completed_at = datetime.now(UTC)
        db.commit()


def mark_interrupted(db: Session) -> int:
    """Fail explanations whose job died with a previous server process."""
    result = db.execute(
        update(AiExplanation)
        .where(AiExplanation.status == AiStatus.PENDING)
        .values(
            status=AiStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while this was being generated. Try again.",
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return result.rowcount or 0
