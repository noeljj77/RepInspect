"""Background job that writes one pending chat answer.

Like the AI explanations, answering takes seconds and can fail in many ways, so it runs
outside the request. The page polls the conversation until the answer is no longer pending.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisFile, ChatMessage, ChatSession, MessageStatus
from app.services.ai import jobs as ai_jobs
from app.services.ai.grounding import Grounding
from app.services.llm.errors import LLMError
from app.services.rag import retrieval, vector_store
from app.services.rag.answering import answer_question, file_reader, strip_markers

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "Something went wrong while answering. Try again in a moment."
INDEX_MISSING = (
    "The search index for this repository is missing or outdated. Rebuild it and ask again."
)
HISTORY_ANSWER_CHARS = 1500
# Short questions are usually follow-ups ("and where is it called?") that make no sense
# on their own, so the previous question is searched along with them.
FOLLOW_UP_WORDS = 8


def history_and_question(
    messages: list[ChatMessage], answer: ChatMessage, turns: int
) -> tuple[list[tuple[str, str]], str]:
    """Earlier completed turns (oldest first) and the question this answer belongs to."""
    before = [m for m in messages if m.position < answer.position]
    question = before[-1].content if before and before[-1].role == "user" else ""
    pairs: list[tuple[str, str]] = []
    for asked, replied in zip(before, before[1:], strict=False):
        if (
            asked.role == "user"
            and replied.role == "assistant"
            and replied.status == MessageStatus.COMPLETED
        ):
            pairs.append((asked.content, strip_markers(replied.content)[:HISTORY_ANSWER_CHARS]))
    return (pairs[-turns:] if turns else []), question


def search_text(question: str, history: list[tuple[str, str]]) -> str:
    if history and len(question.split()) < FOLLOW_UP_WORDS:
        return f"{history[-1][0]} {question}"
    return question


def run_chat_job(message_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        answer = db.get(ChatMessage, message_id)
        if answer is None or answer.role != "assistant" or answer.status != MessageStatus.PENDING:
            return
        try:
            _answer(db, answer)
        except LLMError as error:
            _fail(db, message_id, error.code, error.message)
        except vector_store.IndexMissing:
            _fail(db, message_id, "index_missing", INDEX_MISSING)
        except Exception:
            logger.exception("Chat answer %s failed unexpectedly", message_id)
            _fail(db, message_id, "chat_error", GENERIC_FAILURE)


def _answer(db: Session, answer: ChatMessage) -> None:
    settings = get_settings()
    session = db.get(ChatSession, answer.session_id)
    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.position)
        )
    )
    history, question = history_and_question(messages, answer, settings.chat_history_turns)

    excerpts = retrieval.retrieve(
        db,
        session.analysis_id,
        search_text(question, history),
        settings.rag_top_k,
        settings.rag_context_chars,
    )
    paths = db.scalars(
        select(AnalysisFile.path).where(
            AnalysisFile.analysis_id == session.analysis_id, AnalysisFile.skipped_reason.is_(None)
        )
    )
    grounding = Grounding(paths, file_reader(session.analysis_id))

    provider = ai_jobs.create_provider()
    try:
        answered = answer_question(provider, question, history, excerpts, grounding)
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    details = answered.content.model_dump()
    answer.content = details.pop("answer")
    answer.details = details
    answer.model = answered.model
    answer.input_tokens = answered.input_tokens
    answer.output_tokens = answered.output_tokens
    answer.status = MessageStatus.COMPLETED
    answer.completed_at = datetime.now(UTC)
    session.updated_at = answer.completed_at
    db.commit()
    logger.info(
        "Chat answer with %s: %d excerpts, %s tokens in, %s out",
        answered.model,
        len(excerpts),
        answered.input_tokens,
        answered.output_tokens,
    )


def _fail(db: Session, message_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    record = db.get(ChatMessage, message_id)
    if record is not None:
        record.status = MessageStatus.FAILED
        record.error_code = code
        record.error_message = message
        record.completed_at = datetime.now(UTC)
        db.commit()


def mark_interrupted(db: Session) -> int:
    """Fail answers whose job died with a previous server process."""
    result = db.execute(
        update(ChatMessage)
        .where(ChatMessage.status == MessageStatus.PENDING)
        .values(
            status=MessageStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while this answer was being written. Try again.",
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return result.rowcount or 0
