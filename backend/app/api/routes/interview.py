"""Interview practice questions: generate them, and track progress on each."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_completed_analysis, get_current_user, get_owned_repository
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    BatchStatus,
    InterviewQuestion,
    Progress,
    QuestionBatch,
    RepositoryAnalysis,
    SavedRepository,
    User,
)
from app.schemas.interview import (
    BatchOut,
    GenerateQuestions,
    QuestionOut,
    QuestionsOut,
    QuestionUpdate,
)
from app.services.ai import limits
from app.services.interview.questions import run_question_job
from app.worker.runner import JobRunner, get_job_runner

router = APIRouter(prefix="/repositories/{repository_id}/questions", tags=["interview"])

MAX_QUESTIONS_PER_REPOSITORY = 200


def _out(db: Session, repository: SavedRepository) -> QuestionsOut:
    # Reload: a job may have just written these rows in its own session.
    questions = list(
        db.scalars(
            select(InterviewQuestion)
            .where(InterviewQuestion.saved_repository_id == repository.id)
            .order_by(InterviewQuestion.position)
            .execution_options(populate_existing=True)
        )
    )
    latest = db.scalar(
        select(QuestionBatch)
        .where(QuestionBatch.saved_repository_id == repository.id)
        .order_by(QuestionBatch.created_at.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    progress = {state.value: 0 for state in Progress}
    for question in questions:
        progress[question.status] = progress.get(question.status, 0) + 1
    return QuestionsOut(
        questions=[QuestionOut.model_validate(q) for q in questions],
        latest_batch=BatchOut.model_validate(latest) if latest else None,
        progress=progress,
    )


def _get_question(
    db: Session, repository: SavedRepository, question_id: uuid.UUID
) -> InterviewQuestion:
    question = db.get(InterviewQuestion, question_id)
    if question is None or question.saved_repository_id != repository.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


@router.get("", response_model=QuestionsOut)
def list_questions(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> QuestionsOut:
    return _out(db, repository)


@router.post("", response_model=QuestionsOut, status_code=status.HTTP_202_ACCEPTED)
def generate_questions(
    body: GenerateQuestions,
    repository: SavedRepository = Depends(get_owned_repository),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> QuestionsOut:
    """Write more questions from the version on screen. They are added to the existing ones."""
    if not get_settings().llm_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI features are not set up on this server."
        )
    pending = db.scalar(
        select(QuestionBatch.id).where(
            QuestionBatch.saved_repository_id == repository.id,
            QuestionBatch.status == BatchStatus.PENDING,
        )
    )
    if pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Questions are already being written")
    existing = len(_out(db, repository).questions)
    if existing + body.count > MAX_QUESTIONS_PER_REPOSITORY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A repository can have at most {MAX_QUESTIONS_PER_REPOSITORY} questions. "
            "Delete some you no longer need.",
        )
    try:
        limits.check_allowance(db, user)
    except limits.AiLimitReached as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=error.message) from None

    batch = QuestionBatch(
        saved_repository_id=repository.id,
        analysis_id=analysis.id,
        requested_count=body.count,
        categories=sorted(set(body.categories)) if body.categories else None,
        difficulty=body.difficulty,
    )
    db.add(batch)
    limits.record_request(db, user)
    db.commit()
    runner.submit(run_question_job, batch.id)
    return _out(db, repository)


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdate,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> InterviewQuestion:
    """Record progress: a status, a draft answer, or both."""
    question = _get_question(db, repository, question_id)
    if body.status is not None:
        question.status = body.status
    if "user_answer" in body.model_fields_set:
        question.user_answer = (body.user_answer or "").strip() or None
    question.practiced_at = datetime.now(UTC)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(_get_question(db, repository, question_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
