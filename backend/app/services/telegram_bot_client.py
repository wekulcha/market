from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_message(
    bot_token: str,
    chat_id: int,
    text: str,
    parse_mode: str | None = "HTML",
    reply_markup: dict | None = None,
) -> int | None:
    """Отправляет сообщение. Возвращает message_id при успехе."""
    if not bot_token:
        logger.warning("Telegram send skipped: empty bot token")
        return None

    body: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    if reply_markup:
        body["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    proxy_url = get_settings().telegram_proxy_url or None
    try:
        async with httpx.AsyncClient(timeout=15.0, proxy=proxy_url) as client:
            resp = await client.post(url, json=body)
            if resp.status_code < 200 or resp.status_code >= 300:
                logger.warning("Telegram sendMessage failed: %s body=%s", resp.status_code, resp.text)
                return None
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Telegram sendMessage not ok: %s", data)
                return None
            return int(data["result"]["message_id"])
    except Exception as e:
        logger.warning("Telegram sendMessage error: %r", e)
        return None


async def edit_message_text(
    bot_token: str,
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: str | None = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    if not bot_token or message_id <= 0:
        return False

    body: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    if reply_markup:
        body["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    proxy_url = get_settings().telegram_proxy_url or None
    try:
        async with httpx.AsyncClient(timeout=15.0, proxy=proxy_url) as client:
            resp = await client.post(url, json=body)
            if resp.status_code < 200 or resp.status_code >= 300:
                if "message is not modified" in resp.text.lower():
                    return True
                logger.warning(
                    "Telegram editMessageText failed: %s body=%s",
                    resp.status_code,
                    resp.text,
                )
                return False
            data = resp.json()
            if not data.get("ok"):
                description = str(data.get("description", ""))
                if "message is not modified" in description.lower():
                    return True
                logger.warning("Telegram editMessageText not ok: %s", data)
                return False
            return True
    except Exception as e:
        logger.warning("Telegram editMessageText error: %r", e)
        return False


async def delete_message(bot_token: str, chat_id: int, message_id: int) -> bool:
    if not bot_token or message_id <= 0:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
    proxy_url = get_settings().telegram_proxy_url or None
    try:
        async with httpx.AsyncClient(timeout=15.0, proxy=proxy_url) as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "message_id": message_id},
            )
            if resp.status_code < 200 or resp.status_code >= 300:
                logger.warning("Telegram deleteMessage failed: %s", resp.status_code)
                return False
            data = resp.json()
            return bool(data.get("ok"))
    except Exception as e:
        logger.warning("Telegram deleteMessage error: %r", e)
        return False
