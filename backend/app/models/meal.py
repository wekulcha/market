from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
class MealCategoryColumn(TypeDecorator[str | None]):
    """Всегда работаем со строкой, даже если старая БД ещё хранит enum."""

    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: object | None, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)


class Meal(Base):
    __tablename__ = "meal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("restaurant.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calorie: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_link: Mapped[str] = mapped_column(String(2048), nullable=False)
    category: Mapped[str | None] = mapped_column(MealCategoryColumn(), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    restaurant = relationship("Restaurant", lazy="joined")
