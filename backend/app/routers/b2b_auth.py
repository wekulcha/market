from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps.b2b import roles_for_user
from app.models.b2b import AuditLog, B2BRole, B2BUserRole, TelegramAccount
from app.models.user import User
from app.services.b2b_common import utcnow
from app.services.b2b_rate_limit import rate_limit
from app.services.session_auth import (
    create_access_token,
    create_refresh_session,
    ensure_customer,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.services.telegram_auth import verify_telegram_init_data


router = APIRouter(prefix="/api/auth", tags=["b2b-auth"])
B2B_REFRESH_COOKIE = "kulcha_b2b_refresh_token"


class TelegramAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initDataRaw: str = Field(min_length=1, max_length=16_384)
    role: Literal["BUYER", "SELLER", "ADMIN", "SUPERADMIN"]


class AuthUserResponse(BaseModel):
    id: int
    telegramId: int
    username: str | None
    displayName: str
    roles: list[str]


class AuthSessionResponse(BaseModel):
    accessToken: str
    accessTokenExpiresAt: datetime
    user: AuthUserResponse


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    settings = get_settings()
    now = utcnow().replace(tzinfo=None)
    response.set_cookie(
        key=B2B_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        domain=settings.auth_cookie_domain or None,
        path="/api/auth",
        max_age=max(0, int((expires_at - now).total_seconds())),
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=B2B_REFRESH_COOKIE,
        domain=settings.auth_cookie_domain or None,
        path="/api/auth",
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


async def _role(db: AsyncSession, code: str) -> B2BRole:
    result = await db.execute(select(B2BRole).where(B2BRole.code == code))
    role = result.scalars().first()
    if role:
        return role
    role = B2BRole(code=code, name=code.title())
    db.add(role)
    await db.flush()
    return role


async def _grant_role(
    db: AsyncSession,
    user_id: int,
    code: str,
    *,
    granted_by_user_id: int | None = None,
) -> None:
    role = await _role(db, code)
    result = await db.execute(
        select(B2BUserRole).where(
            B2BUserRole.user_id == user_id,
            B2BUserRole.role_id == role.id,
        )
    )
    if not result.scalars().first():
        db.add(
            B2BUserRole(
                user_id=user_id,
                role_id=role.id,
                granted_by_user_id=granted_by_user_id,
            )
        )
        await db.flush()


def _token_for_role(role: str) -> tuple[str, str]:
    settings = get_settings()
    if role == "BUYER":
        return settings.b2b_buyer_bot_token, "BUYER"
    if role == "SELLER":
        return settings.b2b_seller_bot_token, "SELLER"
    return settings.b2b_admin_bot_token, "ADMIN"


async def _upsert_telegram_account(
    db: AsyncSession,
    user: User,
    scope: str,
    tg_user: dict,
) -> None:
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.telegram_user_id == user.id,
            TelegramAccount.bot_scope == scope,
        )
    )
    account = result.scalars().first()
    if not account:
        account = TelegramAccount(
            user_id=user.id,
            telegram_user_id=user.id,
            bot_scope=scope,
        )
        db.add(account)
    account.username = tg_user.get("username")
    account.first_name = tg_user.get("first_name")
    account.last_name = tg_user.get("last_name")
    account.language_code = tg_user.get("language_code")
    account.last_authenticated_at = utcnow()
    await db.flush()


async def _response_for(db: AsyncSession, response: Response, user: User) -> AuthSessionResponse:
    access_token, access_expires_at = create_access_token(user.id)
    refresh_token, refresh_expires_at = await create_refresh_session(db, user.id)
    _set_refresh_cookie(response, refresh_token, refresh_expires_at)
    roles = sorted(await roles_for_user(db, user.id))
    return AuthSessionResponse(
        accessToken=access_token,
        accessTokenExpiresAt=access_expires_at,
        user=AuthUserResponse(
            id=user.id,
            telegramId=user.id,
            username=user.username or None,
            displayName=user.username or f"Telegram {user.id}",
            roles=roles,
        ),
    )


@router.post(
    "/telegram",
    response_model=AuthSessionResponse,
    dependencies=[Depends(rate_limit("b2b-auth", requests=20, seconds=60))],
)
async def telegram_login(
    body: TelegramAuthRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    settings = get_settings()
    bot_token, scope = _token_for_role(body.role)
    if not bot_token:
        raise HTTPException(503, "Telegram-бот для этой роли не настроен")
    tg_user = verify_telegram_init_data(
        body.initDataRaw.strip(),
        bot_token,
        max_age_seconds=settings.telegram_init_data_max_age_seconds,
    )
    if not tg_user or tg_user.get("id") is None:
        raise HTTPException(401, "Некорректные или устаревшие данные Telegram")
    telegram_id = int(tg_user["id"])

    result = await db.execute(select(User).where(User.id == telegram_id))
    user = result.scalars().first()
    existing_roles = await roles_for_user(db, telegram_id) if user else frozenset()

    if body.role in {"ADMIN", "SUPERADMIN"}:
        is_existing_admin = bool(existing_roles.intersection({"ADMIN", "SUPERADMIN"}))
        bootstrap_allowed = bool(settings.b2b_admin_telegram_ids) and (
            telegram_id in settings.b2b_admin_telegram_ids
        )
        if not is_existing_admin and not bootstrap_allowed:
            raise HTTPException(403, "Нет доступа к административному контуру")
        if not user:
            user = await ensure_customer(db, telegram_id, tg_user.get("username"))
        if not is_existing_admin:
            await _grant_role(db, user.id, "SUPERADMIN", granted_by_user_id=user.id)
            db.add(
                AuditLog(
                    actor_user_id=user.id,
                    action="SUPERADMIN_BOOTSTRAPPED",
                    entity_type="user",
                    entity_id=str(user.id),
                    reason="Configured Telegram bootstrap allowlist",
                    request_id=getattr(request.state, "request_id", None),
                    ip_address=request.client.host if request.client else None,
                )
            )
    else:
        if not user or body.role not in existing_roles:
            if body.role == "BUYER":
                raise HTTPException(403, "Откройте персональную ссылку-приглашение в buyer-боте")
            raise HTTPException(403, "Завершите регистрацию в seller-боте")

    if not user.is_active:
        raise HTTPException(403, "Аккаунт отключён")
    await _upsert_telegram_account(db, user, scope, tg_user)
    return await _response_for(db, response, user)


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(None, alias=B2B_REFRESH_COOKIE),
) -> AuthSessionResponse:
    if not refresh_cookie:
        raise HTTPException(401, "Refresh cookie отсутствует")
    rotated = await rotate_refresh_session(db, refresh_cookie)
    if not rotated:
        _clear_refresh_cookie(response)
        raise HTTPException(401, "Сессия истекла")
    user, token, expires_at = rotated
    roles = await roles_for_user(db, user.id)
    if not roles:
        _clear_refresh_cookie(response)
        raise HTTPException(403, "B2B-роли отозваны")
    _set_refresh_cookie(response, token, expires_at)
    access_token, access_expires_at = create_access_token(user.id)
    return AuthSessionResponse(
        accessToken=access_token,
        accessTokenExpiresAt=access_expires_at,
        user=AuthUserResponse(
            id=user.id,
            telegramId=user.id,
            username=user.username or None,
            displayName=user.username or f"Telegram {user.id}",
            roles=sorted(roles),
        ),
    )


@router.post("/logout", status_code=204, response_class=Response)
async def logout(
    db: AsyncSession = Depends(get_db),
    refresh_cookie: str | None = Cookie(None, alias=B2B_REFRESH_COOKIE),
) -> Response:
    await revoke_refresh_session(db, refresh_cookie)
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response
