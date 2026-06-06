from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StaffPermission


class StaffPermissionColumn(TypeDecorator[StaffPermission]):
    """Хранит права как VARCHAR — без PostgreSQL ENUM (на проде нет типа staffpermission)."""

    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, StaffPermission):
            return value.value
        return str(value)

    def process_result_value(self, value: object | None, dialect: object) -> StaffPermission | None:
        if value is None:
            return None
        return StaffPermission(value)


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = (
        UniqueConstraint("user_id", "restaurant_id", "permission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("restaurant.id"), nullable=False)
    permission: Mapped[StaffPermission] = mapped_column(StaffPermissionColumn(), nullable=False)

    user = relationship("User", lazy="joined")
    restaurant = relationship("Restaurant", lazy="joined")
