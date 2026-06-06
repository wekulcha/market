from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Courier(Base):
    __tablename__ = "courier"
    __table_args__ = (
        UniqueConstraint("user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    user = relationship("User", lazy="joined")
