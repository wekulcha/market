from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SubscriptionLogDto(BaseModel):
    id: int | None = None
    restaurantId: int | None = None
    price: Decimal | None = None
    startDttm: datetime | None = None
    endDttm: datetime | None = None
