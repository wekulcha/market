from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_activity_log import UserActivityLog


SENSITIVE_KEYS = {"phone", "token", "secret", "password", "initData", "initDataRaw"}


def _clean_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key in SENSITIVE_KEYS:
            cleaned[key] = "***"
        elif isinstance(item, (str, int, float, bool)) or item is None:
            cleaned[key] = item
        else:
            cleaned[key] = str(item)
    return cleaned


async def log_user_activity(
    db: AsyncSession,
    *,
    user_id: int,
    event: str,
    source: str = "backend",
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        UserActivityLog(
            user_id=user_id,
            event=event[:64],
            source=source[:32],
            metadata_json=_clean_metadata(metadata),
            created_at=datetime.now(),
        )
    )
    await db.flush()
