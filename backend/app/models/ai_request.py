import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiRequest(Base):
    """One accepted AI request, kept for the daily allowance.

    Explanations are replaced when regenerated and removed with their repository, so
    counting them would let people reset their usage. This log only grows.
    """

    __tablename__ = "ai_requests"
    __table_args__ = (Index("ix_ai_requests_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
