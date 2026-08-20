#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models.b2b import (  # noqa: E402
    B2BCategory,
    B2BRole,
    B2BUserRole,
    InventoryBalance,
    InventoryMovement,
    InviteLink,
    Offer,
    OfferImage,
    OfferRevision,
    SellerProfile,
    SubscriptionPlan,
)
from app.models.user import User  # noqa: E402
from app.services.b2b_common import issue_invite_token, utcnow  # noqa: E402


ROLE_NAMES = {
    "BUYER": "Покупатель",
    "SELLER": "Поставщик",
    "ADMIN": "Администратор",
    "SUPERADMIN": "Владелец платформы",
    "DISPATCHER": "Диспетчер",
    "COURIER": "Курьер",
}
CATEGORIES = (
    ("vegetables", "Овощи и зелень"),
    ("fruits", "Фрукты и ягоды"),
    ("dairy", "Молочная продукция и яйца"),
    ("meat", "Мясо и птица"),
    ("fish", "Рыба и морепродукты"),
    ("grocery", "Бакалея"),
    ("beverages", "Напитки"),
)


async def ensure_user(db, telegram_id: int, username: str) -> User:
    user = await db.get(User, telegram_id)
    if not user:
        user = User(
            id=telegram_id,
            username=username,
            phone=f"tg-{telegram_id}",
            registered_at=utcnow().replace(tzinfo=None),
            is_active=True,
        )
        db.add(user)
        await db.flush()
    return user


async def ensure_role(db, code: str) -> B2BRole:
    role = (await db.execute(select(B2BRole).where(B2BRole.code == code))).scalars().first()
    if not role:
        role = B2BRole(code=code, name=ROLE_NAMES[code])
        db.add(role)
        await db.flush()
    return role


async def grant(db, user_id: int, role: B2BRole, actor_id: int) -> None:
    existing = (
        await db.execute(
            select(B2BUserRole).where(
                B2BUserRole.user_id == user_id,
                B2BUserRole.role_id == role.id,
            )
        )
    ).scalars().first()
    if not existing:
        db.add(
            B2BUserRole(
                user_id=user_id,
                role_id=role.id,
                granted_by_user_id=actor_id,
            )
        )


async def main() -> None:
    settings = get_settings()
    if settings.app_env.lower() not in {"development", "dev", "local", "test", "testing"}:
        raise SystemExit("Refusing to seed outside development/local/test")
    raw_admin_id = os.environ.get("B2B_BOOTSTRAP_SUPERADMIN_TELEGRAM_ID", "").strip()
    if not raw_admin_id.isdigit():
        raise SystemExit("Set B2B_BOOTSTRAP_SUPERADMIN_TELEGRAM_ID to your Telegram numeric ID")
    admin_id = int(raw_admin_id)
    seller_id = int(os.environ.get("B2B_DEMO_SELLER_TELEGRAM_ID", "900000001"))

    async with async_session() as db:
        async with db.begin():
            roles = {code: await ensure_role(db, code) for code in ROLE_NAMES}
            admin = await ensure_user(db, admin_id, "b2b_superadmin")
            await grant(db, admin.id, roles["SUPERADMIN"], admin.id)

            plan = (
                await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == "MONTHLY"))
            ).scalars().first()
            if not plan:
                plan = SubscriptionPlan(
                    code="MONTHLY",
                    name="Месячная подписка",
                    description="Полный доступ к B2B-каталогу и оформлению заказов",
                    price_kopecks=199_000,
                    currency="RUB",
                    duration_days=30,
                    trial_days=7,
                    is_active=True,
                )
                db.add(plan)
                await db.flush()

            categories: dict[str, B2BCategory] = {}
            for order, (slug, name) in enumerate(CATEGORIES):
                category = (
                    await db.execute(select(B2BCategory).where(B2BCategory.slug == slug))
                ).scalars().first()
                if not category:
                    category = B2BCategory(slug=slug, name=name, sort_order=order, is_active=True)
                    db.add(category)
                    await db.flush()
                categories[slug] = category

            seller_user = await ensure_user(db, seller_id, "demo_supplier")
            await grant(db, seller_user.id, roles["SELLER"], admin.id)
            seller = (
                await db.execute(select(SellerProfile).where(SellerProfile.user_id == seller_id))
            ).scalars().first()
            if not seller:
                seller = SellerProfile(
                    user_id=seller_id,
                    status="VERIFIED",
                    company_type="ООО",
                    company_name="Демо Поставщик",
                    inn="7700000000",
                    contact_name="Демо менеджер",
                    phone=f"tg-{seller_id}",
                    pickup_address="Москва, Демо-склад, 1",
                    pickup_hours="Пн–Пт 09:00–18:00",
                    verified_at=utcnow(),
                )
                db.add(seller)
                await db.flush()

            offer = (
                await db.execute(
                    select(Offer)
                    .join(OfferRevision, OfferRevision.offer_id == Offer.id)
                    .where(
                        Offer.seller_profile_id == seller.id,
                        OfferRevision.original_title == "Демо-партия томатов",
                    )
                )
            ).scalars().first()
            if not offer:
                offer = Offer(
                    seller_profile_id=seller.id,
                    status="PUBLISHED",
                    reviewed_by_user_id=admin.id,
                    reviewed_at=utcnow(),
                    published_at=utcnow(),
                    publication_starts_at=utcnow(),
                    expires_at=utcnow() + timedelta(days=14),
                )
                db.add(offer)
                await db.flush()
                revision = OfferRevision(
                    offer_id=offer.id,
                    revision_number=1,
                    category_id=categories["vegetables"].id,
                    original_title="Демо-партия томатов",
                    original_description="Свежие томаты, оптовая партия для локальной проверки.",
                    public_title="Томаты свежие, оптовая партия",
                    public_description="Свежие томаты. Минимальный заказ 10 кг.",
                    supplier_unit_price_kopecks=8_000,
                    markup_type="PERCENT",
                    markup_value=Decimal("20"),
                    buyer_unit_price_kopecks=9_600,
                    currency="RUB",
                    sale_unit="KG",
                    package_size=Decimal("1"),
                    proposed_total_quantity=Decimal("250"),
                    minimum_order_quantity=Decimal("10"),
                    quantity_step=Decimal("5"),
                    expiration_date=(utcnow() + timedelta(days=14)).date(),
                    storage_conditions="Хранить при +8…+12 °C",
                    pickup_address=seller.pickup_address,
                    pickup_hours=seller.pickup_hours,
                    created_by_user_id=seller_user.id,
                    is_published=True,
                    published_at=utcnow(),
                )
                db.add(revision)
                balance = InventoryBalance(
                    offer_id=offer.id,
                    total_quantity=Decimal("250"),
                    reserved_quantity=Decimal("0"),
                    sold_quantity=Decimal("0"),
                )
                db.add(balance)
                await db.flush()
                db.add(
                    InventoryMovement(
                        inventory_balance_id=balance.id,
                        movement_type="INITIAL",
                        quantity=Decimal("250"),
                        total_after=Decimal("250"),
                        reserved_after=Decimal("0"),
                        sold_after=Decimal("0"),
                        actor_user_id=admin.id,
                        reason="Local demo seed",
                    )
                )
                # A tiny local PNG is sufficient for deterministic UI/E2E smoke data.
                png = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
                )
                key = f"b2b/offers/{offer.id}/{revision.id}/seed.png"
                path = (Path(settings.uploads_dir).resolve() / key).resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
                db.add(
                    OfferImage(
                        revision_id=revision.id,
                        storage_key=key,
                        public_url=f"{settings.public_base_url.rstrip('/')}/api/assets/{key}",
                        mime_type="image/png",
                        size_bytes=len(png),
                        width=1,
                        height=1,
                        display_order=0,
                    )
                )

            old_invites = list(
                (
                    await db.execute(
                        select(InviteLink).where(
                            InviteLink.source == "local-seed",
                            InviteLink.status == "ACTIVE",
                        )
                    )
                ).scalars().all()
            )
            for invite in old_invites:
                invite.status = "REVOKED"
                invite.revoked_at = utcnow()
            raw_token, token_hash = issue_invite_token()
            invite = InviteLink(
                token_hash=token_hash,
                status="ACTIVE",
                created_by_user_id=admin.id,
                plan_id=plan.id,
                expires_at=utcnow() + timedelta(days=7),
                max_uses=1,
                use_count=0,
                trial_days=7,
                source="local-seed",
                manager_label="Local demo buyer",
            )
            db.add(invite)
        username = settings.b2b_buyer_bot_username.lstrip("@") or "<BUYER_BOT_USERNAME>"
        print("KULCHA B2B local seed complete")
        print(f"Superadmin Telegram ID: {admin_id}")
        print(f"Demo seller Telegram ID: {seller_id}")
        print(f"Buyer invite token (shown once): {raw_token}")
        print(f"Buyer deep link: https://t.me/{username}?start=invite_{raw_token}")


if __name__ == "__main__":
    asyncio.run(main())
