from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.b2b import BuyerProfile, Subscription, SubscriptionPayment, SubscriptionPlan
from app.services.b2b_common import utcnow
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_settings import runtime_setting


async def activate_paid_subscription(
    db: AsyncSession,
    payment: SubscriptionPayment,
) -> Subscription:
    """Idempotently activate/extend a subscription after provider confirmation."""
    payment = await db.get(SubscriptionPayment, payment.id, with_for_update=True)
    if not payment:
        raise HTTPException(404, "Платёж не найден")
    if payment.status == "PAID" and payment.subscription_id:
        subscription = await db.get(Subscription, payment.subscription_id)
        if subscription:
            return subscription
    if payment.status not in {"PENDING", "PAID"}:
        raise HTTPException(409, "Платёж нельзя подтвердить из текущего статуса")
    plan = await db.get(SubscriptionPlan, payment.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(409, "Тариф недоступен")
    now = utcnow()
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.buyer_profile_id == payment.buyer_profile_id,
            Subscription.status.in_(("TRIAL", "ACTIVE", "PAST_DUE")),
        )
        .order_by(Subscription.ends_at.desc())
        .limit(1)
        .with_for_update()
    )
    subscription = result.scalars().first()
    starts_at = max(now, subscription.ends_at) if subscription else now
    ends_at = starts_at + timedelta(days=plan.duration_days)
    grace_days = await runtime_setting(
        db,
        "subscriptionGracePeriodDays",
        get_settings().subscription_grace_period_days,
    )
    grace_until = ends_at + timedelta(days=grace_days)
    if subscription:
        subscription.plan_id = plan.id
        subscription.status = "ACTIVE"
        subscription.ends_at = ends_at
        subscription.grace_until = grace_until if grace_until > ends_at else None
        subscription.canceled_at = None
        subscription.source = "PAYMENT"
    else:
        subscription = Subscription(
            buyer_profile_id=payment.buyer_profile_id,
            plan_id=plan.id,
            status="ACTIVE",
            starts_at=starts_at,
            ends_at=ends_at,
            grace_until=grace_until if grace_until > ends_at else None,
            source="PAYMENT",
        )
        db.add(subscription)
        await db.flush()
    payment.status = "PAID"
    payment.paid_at = now
    payment.subscription_id = subscription.id
    profile = await db.get(BuyerProfile, payment.buyer_profile_id)
    if profile and profile.status != "BLOCKED":
        profile.status = "ACTIVE"
    await db.flush()
    return subscription


async def expire_subscriptions(db: AsyncSession) -> int:
    """Advance ended subscriptions and keep the denormalized buyer status honest."""
    now = utcnow()
    rows = list(
        (
            await db.execute(
                select(Subscription)
                .where(
                    Subscription.status.in_(("TRIAL", "ACTIVE", "PAST_DUE")),
                    Subscription.ends_at <= now,
                )
                .order_by(Subscription.buyer_profile_id, Subscription.ends_at)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
    )
    changed = 0
    settings = get_settings()
    for subscription in rows:
        profile = await db.get(BuyerProfile, subscription.buyer_profile_id)
        if subscription.grace_until and subscription.grace_until > now:
            if subscription.status != "PAST_DUE":
                subscription.status = "PAST_DUE"
                changed += 1
                if profile:
                    if profile.status != "BLOCKED":
                        profile.status = "PAST_DUE"
                    await enqueue_notification(
                        db,
                        user_id=profile.user_id,
                        recipient=profile.user_id,
                        event_type="SUBSCRIPTION_PAST_DUE",
                        idempotency_key=f"subscription-past-due:{subscription.id}",
                        text="Подписка требует продления; действует льготный период.",
                        bot_scope="BUYER",
                        deep_link=(
                            f"{settings.public_base_url.rstrip('/')}"
                            f"{settings.buyer_app_path}/subscription"
                        ),
                    )
            continue
        if subscription.status != "EXPIRED":
            subscription.status = "EXPIRED"
            changed += 1
            if profile:
                await enqueue_notification(
                    db,
                    user_id=profile.user_id,
                    recipient=profile.user_id,
                    event_type="SUBSCRIPTION_EXPIRED",
                    idempotency_key=f"subscription-expired:{subscription.id}",
                    text="Подписка завершилась. Оформление новых заказов временно недоступно.",
                    bot_scope="BUYER",
                    deep_link=(
                        f"{settings.public_base_url.rstrip('/')}"
                        f"{settings.buyer_app_path}/subscription"
                    ),
                )
        await db.flush()
        remaining_access = int(
            (
                await db.execute(
                    select(func.count(Subscription.id)).where(
                        Subscription.buyer_profile_id == subscription.buyer_profile_id,
                        Subscription.id != subscription.id,
                        or_(
                            (
                                Subscription.status.in_(("TRIAL", "ACTIVE", "PAST_DUE"))
                                & (Subscription.ends_at > now)
                            ),
                            (
                                (Subscription.status == "PAST_DUE")
                                & Subscription.grace_until.is_not(None)
                                & (Subscription.grace_until > now)
                            ),
                        ),
                    )
                )
            ).scalar_one()
        )
        if profile and profile.status != "BLOCKED" and remaining_access == 0:
            profile.status = "EXPIRED"
    await db.flush()
    return changed
