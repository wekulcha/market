from __future__ import annotations

import hmac
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps.b2b import roles_for_user
from app.deps.b2b import active_subscription_for
from app.models.b2b import (
    AuditLog,
    BuyerProfile,
    InviteLink,
    Offer,
    SellerProfile,
    Subscription,
    SubscriptionPlan,
    TelegramAccount,
)
from app.models.user import User
from app.routers.b2b_auth import _grant_role
from app.services.b2b_common import hash_secret, utcnow
from app.services.b2b_rate_limit import rate_limit
from app.services.phone_norm import normalize_phone_to_storage
from app.services.session_auth import ensure_customer


router = APIRouter(prefix="/api/internal/bots", tags=["b2b-internal-bots"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuyerRegistrationRequest(StrictBody):
    telegramId: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=200)
    phone: str = Field(min_length=6, max_length=32)
    inviteToken: str = Field(min_length=20, max_length=256)


class SellerRegistrationRequest(StrictBody):
    telegramId: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=200)
    phone: str = Field(min_length=6, max_length=32)
    companyName: str | None = Field(default=None, max_length=250)


class AdminQuickActionRequest(StrictBody):
    action: Literal["approve", "reject", "request_changes"]
    reason: str | None = Field(default=None, max_length=2000)


def _assert_internal_secret(value: str | None) -> None:
    expected = get_settings().b2b_internal_api_secret
    if not expected or not value or not hmac.compare_digest(value, expected):
        raise HTTPException(403, "Некорректный внутренний секрет")


async def _upsert_account(
    db: AsyncSession,
    user_id: int,
    telegram_id: int,
    username: str | None,
    scope: str,
) -> None:
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.telegram_user_id == telegram_id,
            TelegramAccount.bot_scope == scope,
        )
    )
    account = result.scalars().first()
    if not account:
        account = TelegramAccount(
            user_id=user_id,
            telegram_user_id=telegram_id,
            bot_scope=scope,
        )
        db.add(account)
    account.username = username
    account.last_authenticated_at = utcnow()


async def _register_user(
    db: AsyncSession,
    telegram_id: int,
    username: str | None,
    phone: str,
) -> User:
    normalized = normalize_phone_to_storage(phone)
    if not normalized:
        raise HTTPException(422, "Некорректный номер телефона")
    result = await db.execute(select(User).where(User.phone == normalized, User.id != telegram_id))
    if result.scalars().first():
        raise HTTPException(409, "Этот номер уже связан с другим аккаунтом")
    result = await db.execute(select(User).where(User.id == telegram_id))
    user = result.scalars().first()
    if not user:
        user = await ensure_customer(db, telegram_id, username)
    user.username = username or user.username or f"tg_{telegram_id}"
    user.phone = normalized
    user.is_active = True
    await db.flush()
    return user


@router.post(
    "/buyer/register",
    status_code=201,
    dependencies=[Depends(rate_limit("buyer-invite-activation", requests=20, seconds=60))],
)
async def register_buyer(
    body: BuyerRegistrationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    internal_secret: str | None = Header(None, alias="X-B2B-Internal-Secret"),
):
    _assert_internal_secret(internal_secret)
    now = utcnow()
    result = await db.execute(
        select(InviteLink)
        .where(InviteLink.token_hash == hash_secret(body.inviteToken))
        .with_for_update()
    )
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(404, "Приглашение не найдено")
    if invite.status not in {"ACTIVE", "EXHAUSTED"}:
        raise HTTPException(410, "Приглашение отозвано или недоступно")
    if invite.expires_at <= now:
        invite.status = "EXPIRED"
        raise HTTPException(410, "Срок приглашения истёк")
    if invite.bound_telegram_user_id not in {None, body.telegramId}:
        raise HTTPException(409, "Приглашение уже привязано к другому Telegram-аккаунту")

    user = await _register_user(db, body.telegramId, body.username, body.phone)
    result = await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == user.id))
    profile = result.scalars().first()
    repeated_activation = invite.activated_by_user_id == user.id
    if not profile:
        profile = BuyerProfile(
            user_id=user.id,
            status="REGISTERED",
            contact_name=body.username or f"Telegram {user.id}",
            phone=user.phone,
        )
        db.add(profile)
        await db.flush()
    else:
        profile.phone = user.phone
        if profile.status == "INVITED":
            profile.status = "REGISTERED"

    await _grant_role(db, user.id, "BUYER")
    await _upsert_account(db, user.id, body.telegramId, body.username, "BUYER")

    trial_days = invite.trial_days
    plan: SubscriptionPlan | None = None
    if invite.plan_id:
        plan = await db.get(SubscriptionPlan, invite.plan_id)
        if plan:
            trial_days = trial_days or plan.trial_days
    if trial_days > 0 and plan:
        existing = await db.execute(
            select(Subscription).where(
                Subscription.buyer_profile_id == profile.id,
                Subscription.status.in_(("TRIAL", "ACTIVE")),
                Subscription.ends_at > now,
            )
        )
        if not existing.scalars().first():
            db.add(
                Subscription(
                    buyer_profile_id=profile.id,
                    plan_id=plan.id,
                    status="TRIAL",
                    starts_at=now,
                    ends_at=now + timedelta(days=trial_days),
                    source="INVITE",
                )
            )
        profile.status = "TRIAL"

    if not repeated_activation:
        if invite.use_count >= invite.max_uses:
            raise HTTPException(410, "Лимит использований приглашения исчерпан")
        invite.use_count += 1
    invite.bound_telegram_user_id = body.telegramId
    invite.activated_by_user_id = user.id
    invite.last_used_at = now
    if invite.use_count >= invite.max_uses:
        invite.status = "EXHAUSTED"

    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="BUYER_INVITE_ACTIVATED",
            entity_type="invite_link",
            entity_id=str(invite.id),
            reason="Buyer bot contact registration",
            request_id=getattr(request.state, "request_id", None),
        )
    )
    return {
        "userId": user.id,
        "buyerProfileId": str(profile.id),
        "status": profile.status,
        "repeated": repeated_activation,
    }


@router.post(
    "/seller/register",
    status_code=201,
    dependencies=[Depends(rate_limit("seller-registration", requests=20, seconds=60))],
)
async def register_seller(
    body: SellerRegistrationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    internal_secret: str | None = Header(None, alias="X-B2B-Internal-Secret"),
):
    _assert_internal_secret(internal_secret)
    user = await _register_user(db, body.telegramId, body.username, body.phone)
    result = await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
    profile = result.scalars().first()
    if not profile:
        profile = SellerProfile(
            user_id=user.id,
            status="PENDING",
            company_name=body.companyName or body.username or f"Поставщик {user.id}",
            contact_name=body.username or f"Telegram {user.id}",
            phone=user.phone,
        )
        db.add(profile)
        await db.flush()
    else:
        profile.phone = user.phone
        if body.companyName:
            profile.company_name = body.companyName
    await _grant_role(db, user.id, "SELLER")
    await _upsert_account(db, user.id, body.telegramId, body.username, "SELLER")
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="SELLER_REGISTERED",
            entity_type="seller_profile",
            entity_id=str(profile.id),
            reason="Seller bot contact registration",
            request_id=getattr(request.state, "request_id", None),
        )
    )
    return {"userId": user.id, "sellerProfileId": str(profile.id), "status": profile.status}


@router.get("/status/{telegram_id}")
async def bot_status(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
    internal_secret: str | None = Header(None, alias="X-B2B-Internal-Secret"),
):
    _assert_internal_secret(internal_secret)
    result = await db.execute(select(User).where(User.id == telegram_id))
    user = result.scalars().first()
    if not user:
        return {"registered": False, "roles": []}
    buyer = (
        await db.execute(select(BuyerProfile).where(BuyerProfile.user_id == user.id))
    ).scalars().first()
    seller = (
        await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
    ).scalars().first()
    subscription = await active_subscription_for(db, buyer.id) if buyer else None
    return {
        "registered": True,
        "roles": sorted(await roles_for_user(db, user.id)),
        "buyerStatus": buyer.status if buyer else None,
        "sellerStatus": seller.status if seller else None,
        "subscriptionStatus": subscription.status if subscription else "NONE",
        "subscriptionExpiresAt": subscription.ends_at if subscription else None,
    }


@router.post("/admin/offers/{offer_id}/{action}")
async def admin_offer_quick_action(
    offer_id: str,
    action: Literal["approve", "reject", "request_changes"],
    body: AdminQuickActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    internal_secret: str | None = Header(None, alias="X-B2B-Internal-Secret"),
    actor_id: int | None = Header(None, alias="X-Telegram-User-ID"),
):
    _assert_internal_secret(internal_secret)
    settings = get_settings()
    if actor_id is None or actor_id not in settings.b2b_admin_telegram_ids:
        raise HTTPException(403, "Telegram ID не входит в admin allowlist")
    roles = await roles_for_user(db, actor_id)
    if roles.isdisjoint({"ADMIN", "SUPERADMIN"}):
        raise HTTPException(403, "Административная роль не назначена")
    if body.action != action:
        raise HTTPException(422, "Action в URL и body не совпадает")
    if action in {"reject", "request_changes"} and not (body.reason or "").strip():
        raise HTTPException(422, "Для отклонения или запроса изменений нужна причина")
    try:
        from uuid import UUID

        parsed_id = UUID(offer_id)
    except ValueError as exc:
        raise HTTPException(404, "Предложение не найдено") from exc
    result = await db.execute(select(Offer).where(Offer.id == parsed_id).with_for_update())
    offer = result.scalars().first()
    if not offer:
        raise HTTPException(404, "Предложение не найдено")
    before = offer.status
    if action == "approve":
        if offer.status not in {"SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED"}:
            raise HTTPException(409, "Предложение нельзя одобрить из текущего статуса")
        offer.status = "APPROVED"
        offer.rejection_reason = None
    elif action == "reject":
        offer.status = "REJECTED"
        offer.rejection_reason = body.reason
    else:
        offer.status = "CHANGES_REQUESTED"
        offer.rejection_reason = body.reason
    offer.reviewed_at = utcnow()
    offer.reviewed_by_user_id = actor_id
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=f"OFFER_{action.upper()}",
            entity_type="offer",
            entity_id=str(offer.id),
            reason=body.reason,
            before_data={"status": before},
            after_data={"status": offer.status},
            request_id=getattr(request.state, "request_id", None),
        )
    )
    return {"id": str(offer.id), "status": offer.status}
