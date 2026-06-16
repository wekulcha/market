import hashlib
import hmac
import time

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import BOT_TOKEN, SUPPORT_LINK, USER_MINI_APP_BASE, USER_MINI_APP_VERSION


def _generate_bot_auth_token(telegram_id: int, ttl: int = 7 * 24 * 60 * 60) -> str:
    expiry = int(time.time()) + ttl
    data = f"{telegram_id}_{expiry}"
    sig = hmac.new(BOT_TOKEN.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{telegram_id}_{expiry}_{sig}"


def _append_query(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={value}"


def _with_auth(url: str, telegram_id: int | None) -> str:
    if not BOT_TOKEN or telegram_id is None:
        return url
    return _append_query(url, "tg_auth", _generate_bot_auth_token(telegram_id))


def _with_version(url: str) -> str:
    if USER_MINI_APP_VERSION:
        return _append_query(url, "v", USER_MINI_APP_VERSION)
    return url


def main_menu_keyboard(telegram_id: int | None = None) -> ReplyKeyboardMarkup:
    base = USER_MINI_APP_BASE.rstrip("/")
    if base.startswith("https://"):
        catalog_url = _with_version(_with_auth(f"{base}/catalog", telegram_id))
        cart_url = _with_version(_with_auth(f"{base}/cart", telegram_id))
        profile_url = _with_version(_with_auth(f"{base}/profile", telegram_id))
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Каталог", web_app=WebAppInfo(url=catalog_url))],
                [
                    KeyboardButton(text="🧺 Корзина", web_app=WebAppInfo(url=cart_url)),
                    KeyboardButton(text="👤 Профиль", web_app=WebAppInfo(url=profile_url)),
                ],
                [KeyboardButton(text="📦 Статус заказа")],
                [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
            ],
            resize_keyboard=True,
            input_field_placeholder="Выберите действие",
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Каталог")],
            [KeyboardButton(text="🧺 Корзина"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="📦 Статус заказа")],
            [KeyboardButton(text="💬 Поддержка", url=SUPPORT_LINK)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Поделитесь номером телефона",
    )
