from __future__ import annotations

from pydantic import BaseModel

from app.schemas.order import OrderDto


class CourierDto(BaseModel):
    id: int | None = None
    userId: int | None = None


class CourierPanelOverviewDto(BaseModel):
    courierId: int | None = None
    userId: int
    deliveryOrders: list[OrderDto] = []
    deliveryHistory: list[OrderDto] = []
    createdOrders: list[OrderDto] = []
