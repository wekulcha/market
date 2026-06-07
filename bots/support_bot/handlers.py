import html
import logging
import re

import httpx
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import API_BASE, INTERNAL_SECRET, SUPPORT_GROUP_ID

logger = logging.getLogger(__name__)

router = Router()

_TICKET_RE = re.compile(r"#T(\d+)")


def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    if INTERNAL_SECRET:
        h["X-Market-Internal-Secret"] = INTERNAL_SECRET
    return h


def _esc(s: str | None) -> str:
    return html.escape(s or "")


async def _open_ticket(user_id: int, username: str | None) -> dict | None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{API_BASE}/internal/support/tickets/open",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"userTelegramId": user_id, "username": username},
        )
    if r.status_code not in (200, 201):
        return None
    return r.json()


async def _get_ticket(ticket_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{API_BASE}/internal/support/tickets/{ticket_id}",
            headers=_headers(),
        )
    if r.status_code != 200:
        return None
    return r.json()


async def _close_ticket(ticket_id: int) -> bool:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{API_BASE}/internal/support/tickets/{ticket_id}/close",
            headers=_headers(),
        )
    return r.status_code in (200, 204)


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message):
    logger.info("cmd_start from user_id=%s", message.from_user.id if message.from_user else None)
    await message.answer(
        "<b>Поддержка Kulcha Market</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Опишите проблему одним или несколькими сообщениями. "
        "При необходимости приложите <b>фото</b>.\n\n"
        "Мы передадим обращение команде и ответим здесь.",
    )


@router.message(
    F.chat.type == ChatType.PRIVATE,
    F.photo | F.document | (F.text & ~F.text.startswith("/")),
)
async def user_message(message: Message):
    if not INTERNAL_SECRET:
        await message.answer("Сервис поддержки временно недоступен.")
        return
    uid = message.from_user.id
    uname = message.from_user.username
    data = await _open_ticket(uid, uname)
    if not data:
        await message.answer("Не удалось создать обращение. Попробуйте позже.")
        return
    tid = int(data["id"])
    text = message.text or message.caption or ""
    if message.photo:
        text = (text + "\n[фото приложено]").strip()

    header = (
        f"🎫 <b>#T{tid}</b> · открыто\n"
        f"👤 {_esc(uname and '@' + uname or '')} — <code>{uid}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{_esc(text) if text else '<i>без текста</i>'}"
    )
    await message.bot.send_message(SUPPORT_GROUP_ID, header, parse_mode="HTML")

    if message.photo:
        photo = message.photo[-1]
        await message.bot.send_photo(SUPPORT_GROUP_ID, photo.file_id)

    await message.answer(
        "<b>Спасибо!</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Мы передали обращение в поддержку. "
        "Пожалуйста, ожидайте ответа здесь.",
        parse_mode="HTML",
    )


@router.message(F.chat.id == SUPPORT_GROUP_ID, F.reply_to_message)
async def staff_reply(message: Message):
    if not INTERNAL_SECRET or not message.text:
        return
    replied = message.reply_to_message
    if not replied or not replied.text:
        return
    m = _TICKET_RE.search(replied.text)
    if not m:
        return
    ticket_id = int(m.group(1))
    t = await _get_ticket(ticket_id)
    if not t or t.get("status") != "open":
        await message.reply("Обращение закрыто или не найдено.")
        return
    uid = int(t["userTelegramId"])
    await message.bot.send_message(uid, f"<b>Ответ поддержки:</b>\n{_esc(message.text)}", parse_mode="HTML")


@router.message(F.chat.id == SUPPORT_GROUP_ID, Command("close"))
async def staff_close(message: Message):
    if not INTERNAL_SECRET:
        return
    parts = (message.text or "").split()
    ticket_id: int | None = None
    if len(parts) >= 2 and parts[1].isdigit():
        ticket_id = int(parts[1])
    elif message.reply_to_message and message.reply_to_message.text:
        m = _TICKET_RE.search(message.reply_to_message.text)
        if m:
            ticket_id = int(m.group(1))
    if not ticket_id:
        await message.reply("Используйте: <code>/close 123</code> или reply на сообщение с #T.", parse_mode="HTML")
        return
    t = await _get_ticket(ticket_id)
    if not t:
        await message.reply("Тикет не найден.")
        return
    ok = await _close_ticket(ticket_id)
    if ok:
        await message.answer(f"Обращение #T{ticket_id} закрыто.")
        await message.bot.send_message(
            int(t["userTelegramId"]),
            f"<b>Обращение #{ticket_id} закрыто.</b>\nЕсли нужна помощь снова — напишите сюда.",
            parse_mode="HTML",
        )
    else:
        await message.reply("Не удалось закрыть обращение.")
