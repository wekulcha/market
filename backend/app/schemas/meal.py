from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class MealDto(BaseModel):
    id: int | None = None
    restaurantId: int | None = None
    name: str | None = None
    description: str | None = None
    weight: int | None = None
    calorie: int | None = None
    imageLink: str | None = None
    category: str | None = None
    price: Decimal | None = None
    available: bool | None = None


class MealCategoryAvailabilityPatchDto(BaseModel):
    restaurantId: int
    category: str
    available: bool
