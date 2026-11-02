"""Notes a person keeps about a repository, optionally tied to a file and line."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_owned_repository
from app.db.session import get_db
from app.models import RepositoryNote, SavedRepository
from app.schemas.library import NoteIn, NoteOut, NoteUpdate

router = APIRouter(prefix="/repositories/{repository_id}/notes", tags=["notes"])

MAX_NOTES_PER_REPOSITORY = 500


def _get_note(db: Session, repository: SavedRepository, note_id: uuid.UUID) -> RepositoryNote:
    note = db.get(RepositoryNote, note_id)
    if note is None or note.saved_repository_id != repository.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("", response_model=list[NoteOut])
def list_notes(
    path: str | None = Query(default=None, max_length=1000, description="Only notes on this file"),
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> list[RepositoryNote]:
    query = select(RepositoryNote).where(RepositoryNote.saved_repository_id == repository.id)
    if path is not None:
        query = query.where(RepositoryNote.path == path)
    return list(db.scalars(query.order_by(RepositoryNote.created_at.desc(), RepositoryNote.id)))


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(
    body: NoteIn,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryNote:
    count = db.scalar(
        select(func.count())
        .select_from(RepositoryNote)
        .where(RepositoryNote.saved_repository_id == repository.id)
    )
    if (count or 0) >= MAX_NOTES_PER_REPOSITORY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A repository can have at most {MAX_NOTES_PER_REPOSITORY} notes.",
        )
    note = RepositoryNote(
        saved_repository_id=repository.id,
        body=body.body,
        path=body.path,
        line=body.line if body.path else None,  # a line means nothing without a file
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/{note_id}", response_model=NoteOut)
def edit_note(
    note_id: uuid.UUID,
    body: NoteUpdate,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryNote:
    note = _get_note(db, repository, note_id)
    note.body = body.body
    note.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    repository: SavedRepository = Depends(get_owned_repository),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(_get_note(db, repository, note_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
