from __future__ import annotations

from pydantic import BaseModel


class RestaurantDto(BaseModel):
    id: int | None = None
    name: str | None = None
    address: str | None = None
    imageLink: str | None = None
    workingHoursFrom: str | None = None
    workingHoursTo: str | None = None
    ordersAcceptFrom: str | None = None
    ordersAcceptTo: str | None = None
    telegramGroupChatId: int | None = None


class RestaurantPatchDto(BaseModel):
    name: str | None = None
    address: str | None = None
    imageLink: str | None = None
    workingHoursFrom: str | None = None
    workingHoursTo: str | None = None
    ordersAcceptFrom: str | None = None
    ordersAcceptTo: str | None = None
    telegramGroupChatId: int | None = None
