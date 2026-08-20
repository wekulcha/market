from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.b2b import SystemSetting


T = TypeVar("T", str, int, bool)


async def runtime_setting(
    db: AsyncSession,
    key: str,
    default: T,
) -> T:
    row = (
        await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    ).scalars().first()
    if not row or not isinstance(row.value, dict):
        return default
    value = row.value.get("value")
    # bool is a subclass of int, so reject it for integer settings.
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        return value if isinstance(value, int) and not isinstance(value, bool) else default
    return value if isinstance(value, str) else default
