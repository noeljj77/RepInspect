import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NoteBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
NotePath = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
CollectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class NoteIn(BaseModel):
    body: NoteBody
    # Optional: the file (and line) the note is about.
    path: NotePath | None = None
    line: int | None = Field(default=None, ge=1)


class NoteUpdate(BaseModel):
    body: NoteBody


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    path: str | None
    line: int | None
    created_at: datetime
    updated_at: datetime


class CollectionIn(BaseModel):
    name: CollectionName
    description: Description | None = None


class CollectionUpdate(BaseModel):
    name: CollectionName | None = None
    description: Description | None = None


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    repository_ids: list[uuid.UUID]
