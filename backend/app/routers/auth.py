from __future__ import annotations

import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.staff import Staff
from app.models.user import User
from app.schemas.admin import AdminWebAppSessionDto
from app.schemas.auth import AuthSessionDto, AuthUserDto, BotTokenRequest, TelegramLoginRequest
from app.schemas.user import UserDto, UserRestaurantDto
from app.services.session_auth import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    create_access_token,
    create_refresh_session,
    ensure_customer,
    get_user_from_bearer,
    revoke_refresh_session,
    rotate_refresh_session,
    set_refresh_cookie,
)
from app.services.telegram_auth import verify_telegram_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_user_dto(u: User) -> UserDto:
    return UserDto(
        id=u.id,
        username=u.username,
        phone=u.phone,
        email=u.email,
        address=u.address,
        registeredAt=u.registered_at,
    )


def _to_legacy_user_payload(u: User) -> dict[str, object]:
    return {
        "id": u.id,
        "telegramId": u.id,
        "username": u.username,
        "phone": u.phone,
        "email": u.email,
        "address": u.address,
        "registeredAt": u.registered_at,
    }


def _to_auth_user_dto(u: User) -> AuthUserDto:
    return AuthUserDto(
        id=u.id,
        username=u.username,
        phone=u.phone,
        email=u.email,
        address=u.address,
        registeredAt=u.registered_at,
    )


async def _issue_auth_session(
    db: AsyncSession,
    response: Response,
    user: User,
) -> AuthSessionDto:
    access_token, access_token_expires_at = create_access_token(user.id)
    refresh_token, refresh_expires_at = await create_refresh_session(db, user.id)
    set_refresh_cookie(response, refresh_token, refresh_expires_at)
    return AuthSessionDto(
        accessToken=access_token,
        accessTokenExpiresAt=access_token_expires_at,
        user=_to_auth_user_dto(user),
    )


async def _list_restaurants_for_staff(db: AsyncSession, user_id: int) -> list[UserRestaurantDto]:
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(Staff)
        .options(joinedload(Staff.restaurant))
        .where(Staff.user_id == user_id)
    )
    staff_list = result.unique().scalars().all()

    grouped: dict[int, list[Staff]] = {}
    for staff in staff_list:
        grouped.setdefault(staff.restaurant_id, []).append(staff)

    restaurants = []
    for assignments in grouped.values():
        first = assignments[0]
        if not first.restaurant.is_active:
            continue
        restaurants.append(
            UserRestaurantDto(
                id=first.restaurant.id,
                name=first.restaurant.name,
                address=first.restaurant.address,
                permissions=list({staff.permission.value for staff in assignments}),
            )
        )
    restaurants.sort(key=lambda restaurant: restaurant.name)
    return restaurants


def _verify_bot_token(token: str, bot_token: str) -> int:
    """Verify bot-generated HMAC token: {telegramId}_{expiry}_{hmac}."""
    if not token:
        raise HTTPException(401, "Missing bot auth token")
    if not bot_token:
        raise HTTPException(503, "Bot token not configured")

    parts = token.split("_", 2)
    if len(parts) != 3:
        raise HTTPException(401, "Malformed bot auth token")

    try:
        telegram_id = int(parts[0])
        expiry = int(parts[1])
    except ValueError as exc:
        raise HTTPException(401, "Malformed bot auth token") from exc

    if int(time.time()) > expiry:
        raise HTTPException(401, "Bot auth token expired")

    data = f"{parts[0]}_{parts[1]}"
    expected = hmac.new(
        bot_token.encode(),
        data.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected.lower(), parts[2].lower()):
        raise HTTPException(401, "Invalid bot auth token signature")

    return telegram_id


@router.post("/telegram/user", response_model=AuthSessionDto)
async def login_telegram_user(
    body: TelegramLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    init_data = body.initDataRaw.strip()
    if not init_data:
        raise HTTPException(400, "initDataRaw is required")

    from app.config import get_settings

    settings = get_settings()
    if not settings.user_bot_token:
        raise HTTPException(503, "MARKET_USER_BOT_TOKEN is not configured")

    tg_user = verify_telegram_init_data(init_data, settings.user_bot_token)
    if not tg_user:
        raise HTTPException(401, "Invalid Telegram init data")

    tid = tg_user.get("id")
    if tid is None:
        raise HTTPException(401, "No user id in init data")

    user = await ensure_customer(db, int(tid), tg_user.get("username"))
    return await _issue_auth_session(db, response, user)


@router.post("/telegram/superadmin", response_model=AuthSessionDto)
async def login_telegram_superadmin(
    body: TelegramLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    init_data = body.initDataRaw.strip()
    if not init_data:
        raise HTTPException(400, "initDataRaw is required")

    from app.config import get_settings

    settings = get_settings()
    if not settings.superadmin_bot_token:
        raise HTTPException(503, "MARKET_SUPERADMIN_BOT_TOKEN is not configured")

    tg_user = verify_telegram_init_data(init_data, settings.superadmin_bot_token)
    if not tg_user:
        raise HTTPException(401, "Invalid Telegram init data")

    tid = tg_user.get("id")
    if tid is None:
        raise HTTPException(401, "No user id in init data")

    telegram_id = int(tid)
    if settings.superadmin_allowed_ids and telegram_id not in settings.superadmin_allowed_ids:
        logger.warning("telegram/superadmin: access denied for telegram_id=%s", telegram_id)
        raise HTTPException(403, "Нет доступа. Ваш Telegram ID не в списке разработчиков.")

    logger.info("telegram/superadmin: authenticated telegram_id=%s", telegram_id)
    user = await ensure_customer(db, telegram_id, tg_user.get("username"))
    return await _issue_auth_session(db, response, user)


@router.post("/refresh", response_model=AuthSessionDto)
async def refresh_user_session(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    if not refresh_cookie:
        raise HTTPException(401, "Refresh cookie is missing")

    rotated = await rotate_refresh_session(db, refresh_cookie)
    if not rotated:
        clear_refresh_cookie(response)
        raise HTTPException(401, "Refresh session is invalid or expired")

    user, refresh_token, refresh_expires_at = rotated
    set_refresh_cookie(response, refresh_token, refresh_expires_at)
    access_token, access_token_expires_at = create_access_token(user.id)
    return AuthSessionDto(
        accessToken=access_token,
        accessTokenExpiresAt=access_token_expires_at,
        user=_to_auth_user_dto(user),
    )


@router.post("/logout", status_code=204)
async def logout_user_session(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    await revoke_refresh_session(db, refresh_cookie)
    clear_refresh_cookie(response)


@router.get("/me", response_model=AuthUserDto)
async def me(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
):
    user = await get_user_from_bearer(db, authorization)
    if not user:
        raise HTTPException(401, "Authorization bearer token is required")
    return _to_auth_user_dto(user)


@router.post("/webapp-user")
async def webapp_user(
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
):
    from app.config import get_settings

    init_data = (x_telegram_init_data or x_init_data or "").strip()
    if not init_data:
        logger.warning("webapp-user: no init data header received")
        raise HTTPException(401, "Missing Telegram WebApp data")

    settings = get_settings()
    if not settings.user_bot_token:
        logger.error("webapp-user: MARKET_USER_BOT_TOKEN is not configured")
        raise HTTPException(503, "MARKET_USER_BOT_TOKEN is not configured")

    tg_user = verify_telegram_init_data(init_data, settings.user_bot_token)
    if not tg_user:
        logger.warning("webapp-user: initData validation failed (len=%d)", len(init_data))
        raise HTTPException(401, "Invalid Telegram init data")

    tid = tg_user.get("id")
    if tid is None:
        raise HTTPException(401, "No user id in init data")

    logger.info("webapp-user: authenticated telegram_id=%s", tid)
    user = await ensure_customer(db, int(tid), tg_user.get("username"))
    return _to_legacy_user_payload(user)


@router.post("/webapp-admin")
async def webapp_admin(
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
):
    from app.config import get_settings

    init_data = (x_telegram_init_data or x_init_data or "").strip()
    if not init_data:
        logger.warning("webapp-admin: no init data header received")
        raise HTTPException(401, "Missing Telegram WebApp data")

    settings = get_settings()
    if not settings.admin_bot_token:
        logger.error("webapp-admin: MARKET_ADMIN_BOT_TOKEN is not configured")
        raise HTTPException(503, "MARKET_ADMIN_BOT_TOKEN is not configured")

    tg_user = verify_telegram_init_data(init_data, settings.admin_bot_token)
    if not tg_user:
        logger.warning("webapp-admin: initData validation failed (len=%d)", len(init_data))
        raise HTTPException(401, "Invalid Telegram init data")

    tid = tg_user.get("id")
    if tid is None:
        raise HTTPException(401, "No user id in init data")

    logger.info("webapp-admin: authenticated telegram_id=%s", tid)

    result = await db.execute(select(User).where(User.id == int(tid)))
    user = result.scalars().first()
    if not user:
        user = await ensure_customer(db, int(tid), tg_user.get("username"))
    elif not user.is_active:
        raise HTTPException(403, "Аккаунт отключён")

    restaurants = await _list_restaurants_for_staff(db, user.id)
    if not restaurants:
        raise HTTPException(403, "Нет доступа к магазину")

    return AdminWebAppSessionDto(user=_to_user_dto(user), restaurants=restaurants)


@router.post("/verify-user-bot-token")
async def verify_user_bot_token(
    body: BotTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.config import get_settings

    settings = get_settings()
    telegram_id = _verify_bot_token(body.token, settings.user_bot_token)
    user = await ensure_customer(db, telegram_id, None)
    return _to_legacy_user_payload(user)


@router.post("/verify-admin-bot-token")
async def verify_admin_bot_token(
    body: BotTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.config import get_settings

    settings = get_settings()
    telegram_id = _verify_bot_token(body.token, settings.admin_bot_token)

    result = await db.execute(select(User).where(User.id == telegram_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(403, "Пользователь не найден. Добавьте сотрудника в магазине.")

    restaurants = await _list_restaurants_for_staff(db, user.id)
    if not restaurants:
        raise HTTPException(403, "Нет доступа к магазину")

    return AdminWebAppSessionDto(user=_to_user_dto(user), restaurants=restaurants)
