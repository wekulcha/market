from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class OrderPositionDto(BaseModel):
    id: int | None = None
    mealId: int | None = None
    mealName: str | None = None
    mealWeight: int | None = None
    orderId: int | None = None
    quantity: int | None = None
    unitPrice: Decimal | None = None
    totalPrice: Decimal | None = None
