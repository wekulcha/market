import asyncio

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
    TELEGRAM_PROXY_URL,
    USER_BOT_TOKEN,
)

router = Router()


def _internal_headers() -> dict:
    if not INTERNAL_API_SECRET:
        return {}
    return {"X-Market-Internal-Secret": INTERNAL_API_SECRET}


def allowed(user_id: int) -> bool:
    # Empty configuration must never turn privileged bot commands public.
    return bool(ALLOWED_TELEGRAM_IDS) and user_id in ALLOWED_TELEGRAM_IDS


def _user_id(payload: dict) -> int | None:
    raw = payload.get("id") or payload.get("telegramId")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _has_registered_phone(phone: str | None) -> bool:
    if not phone or str(phone).startswith("tg-"):
        return False
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    return 6 <= len(digits) <= 15


async def _fetch_users() -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/users", timeout=15.0)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


async def _send_user_bot_message(client: httpx.AsyncClient, chat_id: int, text: str) -> bool:
    if not USER_BOT_TOKEN:
        return False
    response = await client.post(
        f"https://api.telegram.org/bot{USER_BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=15.0,
    )
    if response.status_code < 200 or response.status_code >= 300:
        return False
    payload = response.json()
    return bool(payload.get("ok"))


async def _send_bulk(recipients: list[int], text: str) -> tuple[int, int]:
    sent = 0
    failed = 0
    async with httpx.AsyncClient(proxy=TELEGRAM_PROXY_URL or None) as client:
        for chat_id in recipients:
            ok = await _send_user_bot_message(client, chat_id, text)
            if ok:
                sent += 1
            else:
                failed += 1
            await asyncio.sleep(0.05)
    return sent, failed


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
        "Команды: /health, /stats, /order <id>, /restaurant <id>, /user <telegram_id>, "
        "/broadcast <текст>, /broadcast_test <me|registered|unregistered|id,id> <текст>",
        reply_markup=keyboard,
    )


@router.message(Command("broadcast"), F.text)
async def cmd_broadcast(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /broadcast <текст сообщения>")
        return
    if not USER_BOT_TOKEN:
        await message.answer("Не задан MARKET_USER_BOT_TOKEN для отправки через user bot.")
        return
    try:
        users = await _fetch_users()
        recipients = sorted({uid for uid in (_user_id(user) for user in users) if uid is not None})
        if not recipients:
            await message.answer("Нет пользователей для рассылки.")
            return
        await message.answer(f"Начинаю рассылку для {len(recipients)} пользователей.")
        sent, failed = await _send_bulk(recipients, text)
        await message.answer(f"Рассылка завершена. Отправлено: {sent}. Ошибок: {failed}.")
    except Exception as e:
        await message.answer(f"Ошибка рассылки: {e}")


@router.message(Command("broadcast_test"), F.text)
async def cmd_broadcast_test(message: Message):
    if not allowed(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /broadcast_test <me|registered|unregistered|id,id> <текст>")
        return
    if not USER_BOT_TOKEN:
        await message.answer("Не задан MARKET_USER_BOT_TOKEN для отправки через user bot.")
        return

    target, text = parts[1].strip(), parts[2].strip()
    try:
        recipients: list[int] = []
        if target == "me":
            recipients = [message.from_user.id]
        elif target in {"registered", "unregistered"}:
            users = await _fetch_users()
            want_registered = target == "registered"
            for user in users:
                if _has_registered_phone(user.get("phone")) == want_registered:
                    uid = _user_id(user)
                    if uid is not None:
                        recipients = [uid]
                        break
        else:
            recipients = [
                int(item.strip())
                for item in target.split(",")
                if item.strip().lstrip("-").isdigit()
            ]

        recipients = sorted(set(recipients))
        if not recipients:
            await message.answer("Не нашёл получателей для тестовой рассылки.")
            return
        sent, failed = await _send_bulk(recipients, text)
        await message.answer(
            f"Тестовая рассылка: {', '.join(str(uid) for uid in recipients)}\n"
            f"Отправлено: {sent}. Ошибок: {failed}."
        )
    except Exception as e:
        await message.answer(f"Ошибка тестовой рассылки: {e}")


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
