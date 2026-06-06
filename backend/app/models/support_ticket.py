from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SupportTicket(Base):
    __tablename__ = "support_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
