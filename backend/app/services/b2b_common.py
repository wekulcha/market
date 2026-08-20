from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException


_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_invite_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_secret(raw)


def require_idempotency_key(value: str | None) -> str:
    key = (value or "").strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key должен содержать 8–128 безопасных символов",
        )
    return key


def page_offset(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(422, "page должен быть не меньше 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(422, "pageSize должен быть от 1 до 100")
    return (page - 1) * page_size, page_size


def available_quantity_label(value: object) -> str:
    """Avoid exposing exact high-volume stock while remaining useful to buyers."""
    try:
        numeric = float(value)  # quantities, unlike money, may be fractional
    except (TypeError, ValueError):
        return "Уточняется"
    if numeric <= 0:
        return "Нет в наличии"
    if numeric < 10:
        return "Осталось мало"
    if numeric < 100:
        return "В наличии"
    return "Большая партия"
