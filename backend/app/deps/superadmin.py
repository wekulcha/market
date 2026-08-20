from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services.session_auth import get_user_from_bearer


async def assert_superadmin(db: AsyncSession, authorization: str | None) -> User:
    """Same rules as require_superadmin, for use inside route bodies (e.g. conditional branches)."""
    user = await get_user_from_bearer(db, authorization)
    if not user:
        raise HTTPException(401, "Authorization bearer token is required")
    settings = get_settings()
    # Fail closed: an empty allowlist is a configuration error, not public
    # superadmin access.
    if not settings.superadmin_allowed_ids or user.id not in settings.superadmin_allowed_ids:
        raise HTTPException(403, "Нет доступа. Ваш ID не в списке разработчиков.")
    return user


async def require_superadmin(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
) -> User:
    return await assert_superadmin(db, authorization)
