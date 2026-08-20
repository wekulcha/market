from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.b2b import (
    B2BRole,
    B2BUserRole,
    BuyerProfile,
    SellerProfile,
    Subscription,
)
from app.models.user import User
from app.services.b2b_common import utcnow
from app.services.b2b_settings import runtime_setting
from app.services.session_auth import get_user_from_bearer


@dataclass(frozen=True)
class B2BPrincipal:
    user: User
    roles: frozenset[str]


async def roles_for_user(db: AsyncSession, user_id: int) -> frozenset[str]:
    result = await db.execute(
        select(B2BRole.code)
        .join(B2BUserRole, B2BUserRole.role_id == B2BRole.id)
        .where(B2BUserRole.user_id == user_id)
    )
    return frozenset(str(code) for code in result.scalars().all())


async def require_principal(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
) -> B2BPrincipal:
    user = await get_user_from_bearer(db, authorization)
    if not user:
        raise HTTPException(401, "Требуется авторизация")
    roles = await roles_for_user(db, user.id)
    if not roles:
        raise HTTPException(403, "Для аккаунта не назначена роль KULCHA B2B")
    return B2BPrincipal(user=user, roles=roles)


def _assert_any_role(principal: B2BPrincipal, allowed: set[str]) -> B2BPrincipal:
    if principal.roles.isdisjoint(allowed):
        raise HTTPException(403, "Недостаточно прав")
    return principal


async def require_buyer(principal: B2BPrincipal = Depends(require_principal)) -> B2BPrincipal:
    return _assert_any_role(principal, {"BUYER"})


async def require_seller(principal: B2BPrincipal = Depends(require_principal)) -> B2BPrincipal:
    return _assert_any_role(principal, {"SELLER"})


async def require_admin(principal: B2BPrincipal = Depends(require_principal)) -> B2BPrincipal:
    return _assert_any_role(principal, {"ADMIN", "SUPERADMIN"})


async def require_superadmin(principal: B2BPrincipal = Depends(require_principal)) -> B2BPrincipal:
    return _assert_any_role(principal, {"SUPERADMIN"})


async def buyer_profile_for(db: AsyncSession, user_id: int) -> BuyerProfile:
    result = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == user_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(403, "Профиль покупателя не создан")
    if profile.status == "BLOCKED":
        raise HTTPException(403, "Профиль покупателя заблокирован")
    return profile


async def seller_profile_for(db: AsyncSession, user_id: int) -> SellerProfile:
    result = await db.execute(select(SellerProfile).where(SellerProfile.user_id == user_id))
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(403, "Профиль поставщика не создан")
    if profile.status in {"SUSPENDED", "BLOCKED"}:
        raise HTTPException(403, "Профиль поставщика приостановлен")
    return profile


async def active_subscription_for(db: AsyncSession, buyer_profile_id: object) -> Subscription | None:
    now = utcnow()
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.buyer_profile_id == buyer_profile_id,
            Subscription.status.in_(("TRIAL", "ACTIVE", "PAST_DUE")),
            Subscription.ends_at > now,
        )
        .order_by(Subscription.ends_at.desc())
        .limit(1)
    )
    subscription = result.scalars().first()
    if subscription:
        return subscription

    # Grace is stored explicitly so access decisions are deterministic even if
    # configuration changes after a payment.
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.buyer_profile_id == buyer_profile_id,
            Subscription.status == "PAST_DUE",
            Subscription.grace_until.is_not(None),
            Subscription.grace_until > now,
        )
        .order_by(Subscription.grace_until.desc())
        .limit(1)
    )
    return result.scalars().first()


async def require_active_subscription(
    db: AsyncSession,
    buyer_profile_id: object,
) -> Subscription:
    subscription = await active_subscription_for(db, buyer_profile_id)
    if not subscription:
        raise HTTPException(402, "Для оформления заказа нужна активная подписка")
    return subscription


async def catalog_access(db: AsyncSession, buyer_profile_id: object) -> str:
    if await active_subscription_for(db, buyer_profile_id):
        return "FULL"
    return await runtime_setting(
        db,
        "catalogAccessPolicy",
        get_settings().catalog_access_policy,
    )
