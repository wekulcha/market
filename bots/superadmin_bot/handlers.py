import httpx
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart, Command

from config import (
    API_BASE,
    ALLOWED_TELEGRAM_IDS,
    INTERNAL_API_SECRET,
    SUPERADMIN_MINI_APP_BASE,
    SUPPORT_LINK,
)

router = Router()


def _internal_headers() -> dict:
    if not INTERNAL_API_SECRET:
        return {}
    return {"X-Market-Internal-Secret": INTERNAL_API_SECRET}


def allowed(user_id: int) -> bool:
    return not ALLOWED_TELEGRAM_IDS or user_id in ALLOWED_TELEGRAM_IDS


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Открыть панель",
            web_app=WebAppInfo(url=SUPERADMIN_MINI_APP_BASE),
        )],
        [InlineKeyboardButton(text="Поддержка", url=SUPPORT_LINK)],
    ])
    await message.answer(
        "Бот суперадмина Kulcha Market.\n"
        "Команды: /health, /stats, /order <id>, /restaurant <id>, /user <telegram_id>",
        reply_markup=keyboard,
    )


@router.message(Command("health"))
async def cmd_health(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/restaurants", timeout=5.0)
        if r.status_code == 200:
            await message.answer("Сервисы: ОК")
        else:
            await message.answer("Сервисы: ошибка")
    except Exception as e:
        await message.answer(f"Сервисы: ошибка — {e}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        async with httpx.AsyncClient() as client:
            orders = await client.get(f"{API_BASE}/orders")
            restaurants = await client.get(f"{API_BASE}/restaurants")
        o = orders.json() if orders.status_code == 200 else []
        r = restaurants.json() if restaurants.status_code == 200 else []
        total = sum(float(x.get("total", 0)) for x in o)
        await message.answer(
            f"Статистика за сегодня (общая):\n"
            f"Магазинов: {len(r)}\n"
            f"Заказов: {len(o)}\n"
            f"Сумма заказов: {total:.0f} ₽"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("order"), F.text)
async def cmd_order(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /order <id>")
        return
    try:
        oid = int(parts[1])
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/orders/{oid}", headers=_internal_headers())
        if r.status_code != 200:
            await message.answer("Заказ не найден.")
            return
        o = r.json()
        await message.answer(
            f"Заказ №{o.get('id')}\n"
            f"Статус: {o.get('status')}\n"
            f"Сумма: {o.get('total')} ₽\n"
            f"Тип: {o.get('orderType')}"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("restaurant"), F.text)
async def cmd_restaurant(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /restaurant <id>")
        return
    try:
        rid = int(parts[1])
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/restaurants/{rid}")
        if r.status_code != 200:
            await message.answer("Магазин не найден.")
            return
        rest = r.json()
        await message.answer(
            f"Магазин №{rest.get('id')}\n"
            f"Название: {rest.get('name')}\n"
            f"Адрес: {rest.get('address')}"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("user"), F.text)
async def cmd_user(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /user <userId>")
        return
    try:
        uid = int(parts[1])
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/users/{uid}")
        if r.status_code != 200:
            await message.answer("Пользователь не найден.")
            return
        u = r.json()
        await message.answer(
            f"Пользователь №{u.get('id')}\n"
            f"Username: {u.get('username')}\n"
            f"Телефон: {u.get('phone')}"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
