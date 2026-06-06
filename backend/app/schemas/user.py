from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserDto(BaseModel):
    id: int | None = Field(None, alias="telegramId")
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    registeredAt: datetime | None = None

    model_config = {"populate_by_name": True}


class UserRestaurantDto(BaseModel):
    id: int
    name: str
    address: str
    permissions: list[str]
