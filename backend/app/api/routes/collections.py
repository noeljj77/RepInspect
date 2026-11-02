"""Collections: named groups of repositories in one person's library."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Collection, CollectionRepository, User
from app.schemas.library import CollectionIn, CollectionOut, CollectionUpdate
from app.services import repositories

router = APIRouter(prefix="/collections", tags=["collections"])

MAX_COLLECTIONS = 100
DUPLICATE_NAME = "You already have a collection with this name."


def _get(db: Session, user: User, collection_id: uuid.UUID) -> Collection:
    collection = db.get(Collection, collection_id)
    if collection is None or collection.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


def _out(db: Session, collection: Collection) -> CollectionOut:
    members = db.scalars(
        select(CollectionRepository.saved_repository_id)
        .where(CollectionRepository.collection_id == collection.id)
        .order_by(CollectionRepository.added_at)
    )
    return CollectionOut(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        repository_ids=list(members),
    )


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_NAME) from None


@router.get("", response_model=list[CollectionOut])
def list_collections(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CollectionOut]:
    collections = db.scalars(
        select(Collection)
        .where(Collection.user_id == user.id)
        .order_by(func.lower(Collection.name))
    )
    return [_out(db, c) for c in collections]


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    body: CollectionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CollectionOut:
    count = db.scalar(
        select(func.count()).select_from(Collection).where(Collection.user_id == user.id)
    )
    if (count or 0) >= MAX_COLLECTIONS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"You can have at most {MAX_COLLECTIONS} collections."
        )
    collection = Collection(user_id=user.id, name=body.name, description=body.description or None)
    db.add(collection)
    _commit_or_conflict(db)
    return _out(db, collection)


@router.patch("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CollectionOut:
    collection = _get(db, user, collection_id)
    if body.name is not None:
        collection.name = body.name
    if "description" in body.model_fields_set:
        collection.description = body.description or None
    _commit_or_conflict(db)
    return _out(db, collection)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Delete the collection. The repositories in it stay in the library."""
    db.delete(_get(db, user, collection_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _owned_repository_id(db: Session, user: User, repository_id: uuid.UUID) -> uuid.UUID:
    if repositories.get_owned(db, user.id, repository_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repository_id


@router.put("/{collection_id}/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_to_collection(
    collection_id: uuid.UUID,
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Put a repository in the collection. Doing it twice changes nothing."""
    collection = _get(db, user, collection_id)
    _owned_repository_id(db, user, repository_id)
    db.execute(
        insert(CollectionRepository)
        .values(collection_id=collection.id, saved_repository_id=repository_id)
        .on_conflict_do_nothing()
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{collection_id}/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_from_collection(
    collection_id: uuid.UUID,
    repository_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    collection = _get(db, user, collection_id)
    membership = db.get(CollectionRepository, (collection.id, repository_id))
    if membership is not None:
        db.delete(membership)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
