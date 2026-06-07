#!/usr/bin/env python3
"""Local-only seed for Kulcha Market test products.

Run from the workspace root:
    python market/scripts/seed_market_local.py

Or from market/:
    python scripts/seed_market_local.py

Optional admin access for the admin mini app:
    MARKET_LOCAL_ADMIN_TELEGRAM_ID=123456789 python scripts/seed_market_local.py

The script refuses to run against a database URL that does not look local unless
MARKET_LOCAL_SEED_ALLOW_ANY_DB=1 is set.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TypedDict


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models.enums import StaffPermission  # noqa: E402
from app.models.meal import Meal  # noqa: E402
from app.models.restaurant import Restaurant  # noqa: E402
from app.models.staff import Staff  # noqa: E402
from app.models.user import User  # noqa: E402


MARKET_NAME = "Kulcha Market"
MARKET_ADDRESS = "Локальный тестовый магазин"


class ProductSeed(TypedDict):
    name: str
    description: str
    category: str
    price: str
    weight: int
    bg: str
    fg: str


PRODUCTS: tuple[ProductSeed, ...] = (
    {
        "name": "Помидоры черри",
        "description": "Сладкие красные томаты для салатов и перекусов.",
        "category": "VEGETABLES_HERBS",
        "price": "180",
        "weight": 250,
        "bg": "#e8f7b8",
        "fg": "#d64032",
    },
    {
        "name": "Огурцы свежие",
        "description": "Хрустящие огурцы локальной поставки.",
        "category": "VEGETABLES_HERBS",
        "price": "120",
        "weight": 500,
        "bg": "#dff4c8",
        "fg": "#3c9a45",
    },
    {
        "name": "Клубника",
        "description": "Ароматные ягоды для десертов и завтраков.",
        "category": "FRUITS_BERRIES",
        "price": "350",
        "weight": 250,
        "bg": "#ffe2e8",
        "fg": "#e44d72",
    },
    {
        "name": "Яблоки Гала",
        "description": "Сочные сладкие яблоки.",
        "category": "FRUITS_BERRIES",
        "price": "160",
        "weight": 1000,
        "bg": "#fff0bf",
        "fg": "#d94c3d",
    },
    {
        "name": "Молоко 3.2%",
        "description": "Пастеризованное молоко, бутылка 1 л.",
        "category": "DAIRY_EGGS",
        "price": "95",
        "weight": 1000,
        "bg": "#d9efff",
        "fg": "#5a9dcc",
    },
    {
        "name": "Яйца C0",
        "description": "Крупные куриные яйца, упаковка 10 шт.",
        "category": "DAIRY_EGGS",
        "price": "140",
        "weight": 600,
        "bg": "#f7f0d4",
        "fg": "#c99a40",
    },
    {
        "name": "Курага",
        "description": "Мягкая сушеная курага без лишнего сахара.",
        "category": "DRIED_FRUITS_NUTS",
        "price": "260",
        "weight": 300,
        "bg": "#fff0bf",
        "fg": "#d8912d",
    },
    {
        "name": "Миндаль",
        "description": "Обжаренный миндаль для перекуса.",
        "category": "DRIED_FRUITS_NUTS",
        "price": "420",
        "weight": 250,
        "bg": "#f2e8cf",
        "fg": "#9b6a34",
    },
    {
        "name": "Куриное филе",
        "description": "Охлажденное филе грудки.",
        "category": "MEAT_POULTRY",
        "price": "390",
        "weight": 700,
        "bg": "#ffe0dd",
        "fg": "#d95d4d",
    },
    {
        "name": "Филе лосося",
        "description": "Охлажденное филе для запекания.",
        "category": "FISH_SEAFOOD",
        "price": "890",
        "weight": 400,
        "bg": "#d9f4f2",
        "fg": "#2f9d96",
    },
    {
        "name": "Сосиски молочные",
        "description": "Нежные сосиски для быстрого ужина.",
        "category": "SAUSAGE",
        "price": "240",
        "weight": 450,
        "bg": "#ffe6d9",
        "fg": "#bd6842",
    },
    {
        "name": "Рис жасмин",
        "description": "Ароматный длиннозерный рис.",
        "category": "PASTA_GRAINS",
        "price": "180",
        "weight": 900,
        "bg": "#f2e8cf",
        "fg": "#a98237",
    },
    {
        "name": "Оливковое масло",
        "description": "Extra virgin, бутылка 500 мл.",
        "category": "OILS_SAUCES_SPICES",
        "price": "520",
        "weight": 500,
        "bg": "#f0ead6",
        "fg": "#8d7a32",
    },
    {
        "name": "Огурцы маринованные",
        "description": "Хрустящие соленья в банке.",
        "category": "CANNED_PICKLES",
        "price": "190",
        "weight": 680,
        "bg": "#dff4c8",
        "fg": "#5e9f44",
    },
    {
        "name": "Батон нарезной",
        "description": "Свежий пшеничный батон.",
        "category": "BREAD_BAKERY",
        "price": "70",
        "weight": 400,
        "bg": "#ffe1bc",
        "fg": "#bf7b2d",
    },
    {
        "name": "Шоколад молочный",
        "description": "Плитка молочного шоколада.",
        "category": "SWEETS",
        "price": "130",
        "weight": 90,
        "bg": "#f3ddff",
        "fg": "#8b4a2b",
    },
)


def _image_data_uri(bg: str, fg: str) -> str:
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">
  <rect width="480" height="360" rx="42" fill="{bg}"/>
  <circle cx="165" cy="170" r="82" fill="{fg}" opacity="0.92"/>
  <circle cx="270" cy="135" r="58" fill="white" opacity="0.42"/>
  <circle cx="305" cy="225" r="74" fill="{fg}" opacity="0.72"/>
  <path d="M130 265 C205 315 320 305 382 238" fill="none" stroke="white" stroke-width="18" opacity="0.65" stroke-linecap="round"/>
</svg>
""".strip()
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _assert_local_database(database_url: str) -> None:
    if os.environ.get("MARKET_LOCAL_SEED_ALLOW_ANY_DB") == "1":
        return

    normalized = database_url.lower()
    local_markers = (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "@db:",
        "@postgres:",
        "sqlite",
    )
    if any(marker in normalized for marker in local_markers):
        return

    print("Refusing to seed because MARKET_DATABASE_URL does not look local:")
    print(database_url)
    print("Set MARKET_LOCAL_SEED_ALLOW_ANY_DB=1 only if you are absolutely sure.")
    raise SystemExit(2)


async def _upsert_market() -> tuple[int, int]:
    async with async_session() as session:
        restaurant = await session.scalar(
            select(Restaurant).where(Restaurant.name == MARKET_NAME)
        )
        if restaurant is None:
            restaurant = Restaurant(
                name=MARKET_NAME,
                address=MARKET_ADDRESS,
                image_link=None,
                is_active=True,
                working_hours_from="09:00",
                working_hours_to="23:00",
                orders_accept_from="09:00",
                orders_accept_to="23:00",
                telegram_group_chat_id=None,
            )
            session.add(restaurant)
            await session.flush()
        else:
            restaurant.address = MARKET_ADDRESS
            restaurant.is_active = True
            restaurant.working_hours_from = restaurant.working_hours_from or "09:00"
            restaurant.working_hours_to = restaurant.working_hours_to or "23:00"
            restaurant.orders_accept_from = restaurant.orders_accept_from or "09:00"
            restaurant.orders_accept_to = restaurant.orders_accept_to or "23:00"

        changed = 0
        for product in PRODUCTS:
            existing = await session.scalar(
                select(Meal).where(
                    Meal.restaurant_id == restaurant.id,
                    Meal.name == product["name"],
                )
            )
            image_link = _image_data_uri(product["bg"], product["fg"])
            if existing is None:
                existing = Meal(
                    restaurant_id=restaurant.id,
                    name=product["name"],
                    description=product["description"],
                    weight=product["weight"],
                    calorie=None,
                    image_link=image_link,
                    category=product["category"],
                    price=Decimal(product["price"]),
                    is_available=True,
                )
                session.add(existing)
            else:
                existing.description = product["description"]
                existing.weight = product["weight"]
                existing.image_link = image_link
                existing.category = product["category"]
                existing.price = Decimal(product["price"])
                existing.is_available = True
            changed += 1

        admin_id_raw = os.environ.get("MARKET_LOCAL_ADMIN_TELEGRAM_ID", "").strip()
        if admin_id_raw:
            admin_id = int(admin_id_raw)
            user = await session.scalar(select(User).where(User.id == admin_id))
            if user is None:
                user = User(
                    id=admin_id,
                    username=f"local_admin_{admin_id}",
                    phone=f"tg-market-local-{admin_id}",
                    email=None,
                    address=None,
                    registered_at=datetime.utcnow(),
                    is_active=True,
                )
                session.add(user)
                await session.flush()

            for permission in (
                StaffPermission.CAN_EDIT_MENU,
                StaffPermission.CAN_LOOK_ORDERS,
            ):
                staff = await session.scalar(
                    select(Staff).where(
                        Staff.user_id == admin_id,
                        Staff.restaurant_id == restaurant.id,
                        Staff.permission == permission,
                    )
                )
                if staff is None:
                    session.add(
                        Staff(
                            user_id=admin_id,
                            restaurant_id=restaurant.id,
                            permission=permission,
                        )
                    )

        await session.commit()
        return restaurant.id, changed


async def main() -> None:
    settings = get_settings()
    _assert_local_database(settings.database_url)
    restaurant_id, changed = await _upsert_market()
    print(f"Seeded {changed} products for {MARKET_NAME} (restaurant_id={restaurant_id}).")
    print("Use this id in frontend env if needed:")
    print(f"VITE_MARKET_RESTAURANT_ID={restaurant_id}")


if __name__ == "__main__":
    asyncio.run(main())
