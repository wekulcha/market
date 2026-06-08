import html
import httpx
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from config import (
    API_BASE,
    BOT_API_SECRET,
    SUPPORT_LINK,
    USER_MINI_APP_BASE,
)

STATUS_RU = {
    "CREATED": "Принят",
    "ACCEPTED": "Собирается",
    "COOKING": "Собирается",
    "DELIVERY": "Собирается",
    "DONE": "Завершён",
    "CANCELLED": "Отменён",
}

ORDER_TYPE_RU = {
    "DELIVERY": "Доставка",
    "DINE_IN": "На месте",
}
from keyboards import main_menu_keyboard, request_phone_keyboard

router = Router()


def _bot_headers() -> dict:
    h = {}
    if BOT_API_SECRET:
        h["X-Market-Bot-Secret"] = BOT_API_SECRET
    return h


def _has_registered_phone(phone: str | None) -> bool:
    if not phone or phone.startswith("tg-"):
        return False
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10 and digits.startswith("9"):
        return True
    if len(digits) == 11 and digits.startswith(("7", "8")):
        return True
    return False


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"tg_{user_id}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_BASE}/users", params={"telegramId": user_id})
            if r.status_code == 200 and r.json():
                user = r.json()[0]
                if _has_registered_phone(user.get("phone")):
                    await message.answer(
                        "<b>Добро пожаловать в Kulcha Market!</b>\n"
                        "━━━━━━━━━━━━━━\n"
                        "Рады снова вас видеть. Откройте каталог, корзину или профиль кнопками ниже.",
                        reply_markup=main_menu_keyboard(),
                    )
                    return
                await message.answer(
                    "<b>Kulcha Market</b> · доставка продуктов\n"
                    "━━━━━━━━━━━━━━\n"
                    "Чтобы оформлять заказы, нужно завершить регистрацию: нажмите /start и "
                    "поделитесь <b>номером телефона</b> кнопкой ниже.",
                    reply_markup=request_phone_keyboard(),
                )
                return
        except Exception:
            pass
    await message.answer(
        "<b>Kulcha Market</b> · доставка продуктов\n"
        "━━━━━━━━━━━━━━\n"
        "Чтобы оформлять заказы, один раз поделитесь <b>номером телефона</b> "
        "(кнопка ниже). Мы сохраним телефон, ник в Telegram и ваш ID.",
        reply_markup=request_phone_keyboard(),
    )


@router.message(F.contact)
async def on_contact(message: Message):
    if not message.contact:
        return
    user_id = message.from_user.id
    phone = message.contact.phone_number or ""
    username = message.from_user.username or f"tg_{user_id}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{API_BASE}/users",
                headers={**_bot_headers(), "Content-Type": "application/json"},
                json={
                    "username": username,
                    "phone": phone,
                    "telegramId": user_id,
                    "email": None,
                    "address": None,
                },
            )
            if r.status_code in (200, 201):
                await message.answer(
                    "<b>Готово!</b>\n"
                    "━━━━━━━━━━━━━━\n"
                    "Регистрация прошла успешно. Можно выбирать товары и заказывать в мини-приложении.",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await message.answer(
                    "Не удалось сохранить профиль. Попробуйте позже или напишите в поддержку.",
                    reply_markup=main_menu_keyboard(),
                )
        except Exception as e:
            await message.answer(
                f"Ошибка сети: <code>{e}</code>",
                reply_markup=main_menu_keyboard(),
            )


@router.message(F.text == "📦 Статус заказа")
async def order_status(message: Message):
    if not BOT_API_SECRET:
        await message.answer(
            "<b>Статус заказа</b>\n━━━━━━━━━━━━━━\n"
            "Сервис временно недоступен (не задан <code>MARKET_BOT_API_SECRET</code> на сервере бота)."
        )
        return
    uid = message.from_user.id
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{API_BASE}/orders",
            params={"userId": uid},
            headers={"X-Market-Bot-Secret": BOT_API_SECRET},
        )
    if r.status_code != 200:
        await message.answer("Не удалось загрузить заказы. Попробуйте позже.")
        return
    orders = r.json()
    if not orders:
        await message.answer("У вас пока нет заказов. Оформите заказ в мини-приложении.")
        return
    active_statuses = {"CREATED", "ACCEPTED", "COOKING", "DELIVERY"}
    active = [o for o in orders if o.get("status") in active_statuses]
    o = active[0] if active else orders[0]
    st = o.get("status") or ""
    ot = o.get("orderType") or ""
    total = o.get("total")
    addr = o.get("deliveryAddress") or ""
    table = o.get("tableNumber") or ""
    place_lines = []
    if addr:
        place_lines.append(f"📍 Адрес: {html.escape(addr)}")
    if table:
        place_lines.append(f"🪑 Место: <b>{html.escape(table)}</b>")
    lines = [
        "<b>📦 Заказ</b>",
        "━━━━━━━━━━━━━━",
        f"№ <code>{o.get('id')}</code>",
        f"📌 Статус: <b>{STATUS_RU.get(st, st)}</b>",
        f"🧾 {ORDER_TYPE_RU.get(ot, ot)}",
    ]
    if place_lines:
        lines.append("")
        lines.extend(place_lines)
    lines.extend(
        [
            "",
            f"💰 <b>{total} ₽</b>" if total is not None else "",
            "",
            "<i>Подробности — в мини-приложении → «Профиль».</i>",
        ]
    )
    await message.answer("\n".join(x for x in lines if x != ""))


@router.message(F.text == "💬 Поддержка")
async def support(message: Message):
    await message.answer(
        f"<b>Поддержка</b>\n━━━━━━━━━━━━━━\nНапишите нам в боте: {SUPPORT_LINK}"
    )


@router.message(F.text == "🛒 Каталог")
async def catalog_fallback(message: Message):
    if USER_MINI_APP_BASE.startswith("https://"):
        return
    await message.answer(f"Откройте в браузере: {USER_MINI_APP_BASE.rstrip('/')}/catalog")


@router.message(F.text == "🧺 Корзина")
async def cart_fallback(message: Message):
    if USER_MINI_APP_BASE.startswith("https://"):
        return
    await message.answer(f"Откройте в браузере: {USER_MINI_APP_BASE.rstrip('/')}/cart")


@router.message(F.text == "👤 Профиль")
async def profile_fallback(message: Message):
    if USER_MINI_APP_BASE.startswith("https://"):
        return
    await message.answer(f"Откройте в браузере: {USER_MINI_APP_BASE.rstrip('/')}/profile")
