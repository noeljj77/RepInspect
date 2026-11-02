"""Chat with a repository: the search index it needs, conversations and questions."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_completed_analysis, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ChatMessage,
    ChatSession,
    IndexStatus,
    MessageStatus,
    RepositoryAnalysis,
    SearchIndex,
    User,
)
from app.schemas.chat import AskIn, ChatOut, ChatSummary, IndexOut, MessageOut
from app.services.ai import limits
from app.services.rag import indexer
from app.services.rag.chat_jobs import run_chat_job
from app.worker.runner import JobRunner, get_job_runner

router = APIRouter(prefix="/repositories/{repository_id}", tags=["chat"])

MAX_TITLE = 80
MAX_LISTED_CHATS = 50


# --- search index ------------------------------------------------------------------------------


def _index_out(record: SearchIndex | None) -> IndexOut:
    if record is None:
        return IndexOut(status="missing")
    return IndexOut(
        status=record.status,
        chunk_count=record.chunk_count,
        chunks_embedded=record.chunks_embedded,
        truncated=record.truncated,
        model=record.model,
        error_code=record.error_code,
        error_message=record.error_message,
        completed_at=record.completed_at,
    )


@router.get("/index", response_model=IndexOut)
def get_index(
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> IndexOut:
    return _index_out(db.get(SearchIndex, analysis.id))


@router.post("/index", response_model=IndexOut, status_code=status.HTTP_202_ACCEPTED)
def build_index(
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> IndexOut:
    """Build (or rebuild) the search index, for example for an import made before chat existed."""
    existing = db.get(SearchIndex, analysis.id)
    if existing is not None and existing.status in (IndexStatus.PENDING, IndexStatus.BUILDING):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="The search index is already being built"
        )
    record = indexer.request_index(db, analysis.id)
    runner.submit(indexer.run_index_job, analysis.id)
    db.refresh(record)
    return _index_out(record)


# --- conversations -------------------------------------------------------------------------------


def _chat_out(db: Session, session: ChatSession) -> ChatOut:
    # Reload from the database: a job may have just updated these rows in its own session.
    db.refresh(session)
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.position)
        .execution_options(populate_existing=True)
    )
    return ChatOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[MessageOut.model_validate(m, from_attributes=True) for m in messages],
    )


def _get_chat(db: Session, analysis: RepositoryAnalysis, chat_id: uuid.UUID) -> ChatSession:
    session = db.get(ChatSession, chat_id)
    if session is None or session.analysis_id != analysis.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return session


def _title(question: str) -> str:
    line = " ".join(question.split())
    if len(line) <= MAX_TITLE:
        return line
    cut = line[: MAX_TITLE - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _check_can_ask(db: Session, analysis: RepositoryAnalysis, user: User) -> None:
    if not get_settings().llm_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI chat is not set up on this server."
        )
    index = db.get(SearchIndex, analysis.id)
    if index is None or index.status != IndexStatus.READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Chat is not ready yet: the repository's search index has not been built.",
        )
    try:
        limits.check_allowance(db, user)
    except limits.AiLimitReached as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=error.message) from None


def _add_turn(db: Session, session: ChatSession, question: str, user: User) -> ChatMessage:
    """The question and a pending answer, committed together with the usage record."""
    last = db.scalar(
        select(func.max(ChatMessage.position)).where(ChatMessage.session_id == session.id)
    )
    position = (last or 0) + 1
    db.add(ChatMessage(session_id=session.id, position=position, role="user", content=question))
    answer = ChatMessage(
        session_id=session.id,
        position=position + 1,
        role="assistant",
        status=MessageStatus.PENDING,
    )
    db.add(answer)
    limits.record_request(db, user)
    session.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # two questions sent to the same conversation at once
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Wait for the current answer before asking again"
        ) from None
    return answer


@router.get("/chats", response_model=list[ChatSummary])
def list_chats(
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> list[ChatSession]:
    return list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.analysis_id == analysis.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(MAX_LISTED_CHATS)
        )
    )


@router.post("/chats", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
def start_chat(
    body: AskIn,
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> ChatOut:
    """Start a conversation with its first question."""
    _check_can_ask(db, analysis, user)
    session = ChatSession(analysis_id=analysis.id, title=_title(body.question))
    db.add(session)
    db.flush()
    answer = _add_turn(db, session, body.question, user)
    runner.submit(run_chat_job, answer.id)
    return _chat_out(db, session)


@router.get("/chats/{chat_id}", response_model=ChatOut)
def get_chat(
    chat_id: uuid.UUID,
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> ChatOut:
    return _chat_out(db, _get_chat(db, analysis, chat_id))


@router.post(
    "/chats/{chat_id}/messages", response_model=ChatOut, status_code=status.HTTP_202_ACCEPTED
)
def ask(
    chat_id: uuid.UUID,
    body: AskIn,
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> ChatOut:
    session = _get_chat(db, analysis, chat_id)
    pending = db.scalar(
        select(ChatMessage.id).where(
            ChatMessage.session_id == session.id, ChatMessage.status == MessageStatus.PENDING
        )
    )
    if pending is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Wait for the current answer before asking again"
        )
    _check_can_ask(db, analysis, user)
    answer = _add_turn(db, session, body.question, user)
    runner.submit(run_chat_job, answer.id)
    return _chat_out(db, session)


@router.post(
    "/chats/{chat_id}/messages/{message_id}/retry",
    response_model=ChatOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_answer(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> ChatOut:
    """Try a failed answer again. Only the latest answer of a conversation can be retried."""
    session = _get_chat(db, analysis, chat_id)
    answer = db.get(ChatMessage, message_id)
    last = db.scalar(
        select(func.max(ChatMessage.position)).where(ChatMessage.session_id == session.id)
    )
    if answer is None or answer.session_id != session.id or answer.role != "assistant":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Answer not found")
    if answer.status != MessageStatus.FAILED or answer.position != last:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Only the latest failed answer can be retried"
        )
    _check_can_ask(db, analysis, user)

    answer.status = MessageStatus.PENDING
    answer.error_code = None
    answer.error_message = None
    answer.completed_at = None
    limits.record_request(db, user)
    db.commit()
    runner.submit(run_chat_job, answer.id)
    return _chat_out(db, session)


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: uuid.UUID,
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(_get_chat(db, analysis, chat_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
