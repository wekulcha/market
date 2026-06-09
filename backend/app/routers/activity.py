from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.activity import ActivityLogCreateDto
from app.services.activity_log import log_user_activity
from app.services.session_auth import get_user_from_bearer

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


@router.post("", status_code=204)
async def create_activity_log(
    body: ActivityLogCreateDto,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
    x_kulcha_bot_secret: str | None = Header(None, alias="X-Market-Bot-Secret"),
):
    settings = get_settings()
    bot_authorized = bool(
        x_kulcha_bot_secret
        and settings.bot_api_secret
        and x_kulcha_bot_secret == settings.bot_api_secret
    )

    user: User | None = None
    if not bot_authorized:
        user = await get_user_from_bearer(db, authorization)
        if not user:
            raise HTTPException(401, "Authorization bearer token is required")
    elif body.userId is None:
        raise HTTPException(400, "userId is required for bot activity logs")

    user_id = int(body.userId if bot_authorized else user.id)
    await log_user_activity(
        db,
        user_id=user_id,
        event=body.event,
        source=body.source or ("bot" if bot_authorized else "webapp"),
        metadata=body.metadata,
    )
