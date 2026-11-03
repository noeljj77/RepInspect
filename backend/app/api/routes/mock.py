"""Mock interviews: start one, answer (or skip) each question, and get a report."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_completed_analysis, get_current_user, get_owned_repository
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    InterviewStatus,
    MockInterview,
    MockTurn,
    QuestionBatch,
    RepositoryAnalysis,
    SavedRepository,
    TurnStatus,
    User,
)
from app.schemas.mock import AnswerIn, InterviewOut, InterviewSummary, StartInterview, TurnOut
from app.services.ai import limits
from app.services.mock import flow
from app.worker.runner import JobRunner, get_job_runner

router = APIRouter(prefix="/repositories/{repository_id}/mock-interviews", tags=["mock interviews"])

EXTRA_QUESTIONS = 2  # written beyond what is missing, so later interviews have some variety
OPEN = (InterviewStatus.PREPARING, InterviewStatus.ACTIVE)


def _out(db: Session, interview: MockInterview) -> InterviewOut:
    db.refresh(interview)  # a job may have changed it in its own session
    turns = flow.turns_of(db, interview.id)
    return InterviewOut(
        id=interview.id,
        status=interview.status,
        question_count=interview.question_count,
        asked=sum(1 for t in turns if t.kind == "question"),
        categories=interview.categories,
        difficulty=interview.difficulty,
        report=interview.report,
        error_message=interview.error_message,
        created_at=interview.created_at,
        completed_at=interview.completed_at,
        turns=[TurnOut.model_validate(t) for t in turns],
    )


def _get(db: Session, repository: SavedRepository, interview_id: uuid.UUID) -> MockInterview:
    interview = db.get(MockInterview, interview_id)
    if interview is None or interview.saved_repository_id != repository.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview


def _require_ai(db: Session, user: User) -> None:
    if not get_settings().llm_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI features are not set up on this server."
        )
    try:
        limits.check_allowance(db, user)
    except limits.AiLimitReached as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=error.message) from None


def _waiting_turn(db: Session, interview: MockInterview) -> MockTurn:
    turn = db.scalar(
        select(MockTurn).where(
            MockTurn.interview_id == interview.id, MockTurn.status == TurnStatus.WAITING
        )
    )
    if interview.status != InterviewStatus.ACTIVE or turn is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="There is no question waiting for an answer"
        )
    return turn


@router.get("", response_model=list[InterviewSummary])
def list_interviews(
    repository: SavedRepository = Depends(get_owned_repository), db: Session = Depends(get_db)
) -> list[InterviewSummary]:
    interviews = db.scalars(
        select(MockInterview)
        .where(MockInterview.saved_repository_id == repository.id)
        .order_by(MockInterview.created_at.desc())
    )
    return [
        InterviewSummary(
            id=i.id,
            status=i.status,
            question_count=i.question_count,
            percent=(i.report or {}).get("percent"),
            created_at=i.created_at,
            completed_at=i.completed_at,
        )
        for i in interviews
    ]


@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
def start_interview(
    body: StartInterview,
    repository: SavedRepository = Depends(get_owned_repository),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> InterviewOut:
    """Start an interview. It uses practice questions, writing more first if needed."""
    if not get_settings().llm_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI features are not set up on this server."
        )
    already = db.scalar(
        select(MockInterview.id).where(
            MockInterview.saved_repository_id == repository.id, MockInterview.status.in_(OPEN)
        )
    )
    if already is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Finish or end the interview you already started first.",
        )

    interview = MockInterview(
        saved_repository_id=repository.id,
        analysis_id=analysis.id,
        question_count=body.question_count,
        categories=sorted(set(body.categories)) if body.categories else None,
        difficulty=body.difficulty,
    )
    db.add(interview)
    db.flush()
    available = flow.candidates(db, interview)
    if len(available) >= body.question_count:
        flow.activate(db, interview, flow.choose(db, interview))  # no AI call needed yet
        db.commit()
        return _out(db, interview)

    pending_batch = db.scalar(
        select(QuestionBatch.id).where(
            QuestionBatch.saved_repository_id == repository.id, QuestionBatch.status == "pending"
        )
    )
    if pending_batch is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Practice questions are being written. Try again shortly.",
        )
    _require_ai(db, user)
    missing = body.question_count - len(available)
    batch = QuestionBatch(
        saved_repository_id=repository.id,
        analysis_id=analysis.id,
        requested_count=min(max(missing + EXTRA_QUESTIONS, 3), 12),
        categories=interview.categories,
        difficulty=interview.difficulty,
    )
    db.add(batch)
    limits.record_request(db, user)
    db.commit()
    runner.submit(flow.run_prepare_job, interview.id, batch.id)
    return _out(db, interview)


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(
    interview_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> InterviewOut:
    return _out(db, _get(db, repository, interview_id))


@router.post(
    "/{interview_id}/answer", response_model=InterviewOut, status_code=status.HTTP_202_ACCEPTED
)
def answer(
    interview_id: uuid.UUID,
    body: AnswerIn,
    repository: SavedRepository = Depends(get_owned_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> InterviewOut:
    """Answer the waiting question. It is graded in the background."""
    interview = _get(db, repository, interview_id)
    turn = _waiting_turn(db, interview)
    _require_ai(db, user)
    turn.answer = body.answer
    turn.answered_at = flow.now()
    turn.status = TurnStatus.GRADING
    limits.record_request(db, user)
    db.commit()
    runner.submit(flow.run_grade_job, turn.id)
    return _out(db, interview)


@router.post("/{interview_id}/skip", response_model=InterviewOut)
def skip(
    interview_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> InterviewOut:
    """Skip the waiting question. It counts as a score of 0."""
    interview = _get(db, repository, interview_id)
    flow.skip(db, interview, _waiting_turn(db, interview))
    db.commit()
    return _out(db, interview)


@router.post(
    "/{interview_id}/turns/{turn_id}/retry",
    response_model=InterviewOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_grading(
    interview_id: uuid.UUID,
    turn_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_job_runner),
) -> InterviewOut:
    interview = _get(db, repository, interview_id)
    turn = db.get(MockTurn, turn_id)
    if turn is None or turn.interview_id != interview.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Question not found")
    if turn.status != TurnStatus.FAILED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Only an answer whose grading failed can be retried"
        )
    _require_ai(db, user)
    turn.status = TurnStatus.GRADING
    turn.error_code = turn.error_message = None
    limits.record_request(db, user)
    db.commit()
    runner.submit(flow.run_grade_job, turn.id)
    return _out(db, interview)


@router.post("/{interview_id}/finish", response_model=InterviewOut)
def finish(
    interview_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> InterviewOut:
    """End the interview now and write the report from what was answered."""
    interview = _get(db, repository, interview_id)
    if interview.status != InterviewStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This interview is not running")
    if any(t.status == TurnStatus.GRADING for t in flow.turns_of(db, interview.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Wait for the last answer to be graded"
        )
    flow.finish(db, interview)
    db.commit()
    return _out(db, interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(
    interview_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> Response:
    interview = _get(db, repository, interview_id)
    if any(t.status == TurnStatus.GRADING for t in flow.turns_of(db, interview.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Wait for the last answer to be graded"
        )
    db.delete(interview)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
