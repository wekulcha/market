from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserActivityLog(Base):
    __tablename__ = "user_activity_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="backend")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    user = relationship("User", lazy="joined")
