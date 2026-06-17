import hashlib
import hmac
import time

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import ADMIN_MINI_APP_URL, BOT_TOKEN, SUPPORT_LINK


def generate_bot_auth_token(telegram_id: int, ttl: int = 600) -> str | None:
    if not BOT_TOKEN or not telegram_id:
        return None
    expiry = int(time.time()) + ttl
    data = f"{telegram_id}_{expiry}"
    sig = hmac.new(BOT_TOKEN.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{telegram_id}_{expiry}_{sig}"


def _with_auth(url: str, telegram_id: int | None) -> str:
    token = generate_bot_auth_token(telegram_id or 0, ttl=7 * 24 * 60 * 60)
    if not token:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}tg_auth={token}"


def _orders_button(telegram_id: int | None = None) -> KeyboardButton:
    if ADMIN_MINI_APP_URL.startswith("https://"):
        return KeyboardButton(
            text="📥 Активные заказы",
            web_app=WebAppInfo(url=_with_auth(ADMIN_MINI_APP_URL, telegram_id)),
        )
    return KeyboardButton(text="📥 Активные заказы")


def main_menu_keyboard(telegram_id: int | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [_orders_button(telegram_id)],
            [KeyboardButton(text="📊 Итоги за сегодня")],
            [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
