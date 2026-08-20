from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def app_button(text: str, url: str, *, as_web_app: bool = True) -> InlineKeyboardButton:
    if as_web_app and url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=text, url=url)


def link_keyboard(
    *rows: tuple[str, str] | tuple[str, str, bool],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [app_button(row[0], row[1], as_web_app=row[2] if len(row) == 3 else True)]
            for row in rows
            if row[1]
        ]
    )


def safe_text(value: object) -> str:
    return html.escape(str(value))


def display_status(payload: dict, *, fallback: str = "не указан") -> str:
    raw = payload.get("status") or payload.get("subscriptionStatus") or fallback
    return safe_text(raw)
