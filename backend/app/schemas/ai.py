import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExplanationOut(BaseModel):
    kind: str
    path: str | None
    # "missing" (never requested), "pending", "completed" or "failed"
    status: str
    error_code: str | None = None
    error_message: str | None = None
    # The checked result. Its shape depends on `kind` (see services/ai/schemas.py).
    content: dict[str, Any] | None = None
    model: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    id: uuid.UUID | None = None
