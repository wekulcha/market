from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, Numeric, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import OrderStatus, OrderType


class OrderStatusColumn(TypeDecorator[OrderStatus]):
    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, OrderStatus):
            return value.value
        return str(value)

    def process_result_value(self, value: object | None, dialect: object) -> OrderStatus:
        if value is None:
            raise ValueError("order status is required")
        return OrderStatus(value)


class OrderTypeColumn(TypeDecorator[OrderType]):
    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, OrderType):
            return value.value
        return str(value)

    def process_result_value(self, value: object | None, dialect: object) -> OrderType:
        if value is None:
            raise ValueError("order type is required")
        return OrderType(value)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[OrderStatus] = mapped_column(OrderStatusColumn(), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    delivery_address: Mapped[str | None] = mapped_column(String, nullable=True)
    restaurant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("restaurant.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    courier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("courier.id"), nullable=True)
    order_type: Mapped[OrderType] = mapped_column(OrderTypeColumn(), nullable=False)
    items_total: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    service_fee: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    user_telegram_notify_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    table_number: Mapped[str | None] = mapped_column(String, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    review_rating: Mapped[int | None] = mapped_column(nullable=True)
    review_text: Mapped[str | None] = mapped_column(String, nullable=True)
    review_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    admin_order_messages: Mapped[list[dict[str, int]] | None] = mapped_column(
        JSON, nullable=True
    )
    review_admin_messages: Mapped[list[dict[str, int]] | None] = mapped_column(
        JSON, nullable=True
    )

    user = relationship("User", lazy="joined")
    restaurant = relationship("Restaurant", lazy="joined")
    courier = relationship("Courier", lazy="joined")
