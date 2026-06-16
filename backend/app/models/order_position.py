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
    final_weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)

    meal = relationship("Meal", lazy="joined")
    order = relationship("Order", lazy="joined")
    unit_weights: Mapped[list["OrderPositionUnitWeight"]] = relationship(
        "OrderPositionUnitWeight",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderPositionUnitWeight.unit_index",
    )


class OrderPositionUnitWeight(Base):
    __tablename__ = "order_position_unit_weight"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_position_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_position.id", ondelete="CASCADE"), nullable=False
    )
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_grams: Mapped[int] = mapped_column(Integer, nullable=False)
