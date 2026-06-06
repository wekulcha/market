from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Restaurant(Base):
    __tablename__ = "restaurant"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    image_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    working_hours_from: Mapped[str | None] = mapped_column(String(8), nullable=True)
    working_hours_to: Mapped[str | None] = mapped_column(String(8), nullable=True)
    orders_accept_from: Mapped[str | None] = mapped_column(String(8), nullable=True)
    orders_accept_to: Mapped[str | None] = mapped_column(String(8), nullable=True)
    telegram_group_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
