from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityLogCreateDto(BaseModel):
    userId: int | None = None
    event: str = Field(..., min_length=1, max_length=64)
    source: str | None = Field(None, max_length=32)
    metadata: dict[str, Any] | None = None


class ActivityLogDto(BaseModel):
    id: int
    userId: int
    event: str
    source: str
    metadata: dict[str, Any] | None = None
    createdAt: datetime
