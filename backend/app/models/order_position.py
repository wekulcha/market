from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderPosition(Base):
    __tablename__ = "order_position"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meal.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    meal = relationship("Meal", lazy="joined")
    order = relationship("Order", lazy="joined")
