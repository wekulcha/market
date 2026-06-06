import html
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import Chat, ChatMemberUpdated, Message, User

from config import ADMIN_USER_ID, TIMEZONE
from storage import Storage

logger = logging.getLogger(__name__)
router = Router()

ACTIVE_STATUSES = {"creator", "administrator", "member"}
INACTIVE_STATUSES = {"left", "kicked"}

try:
    LOCAL_TZ = ZoneInfo(TIMEZONE)
except ZoneInfoNotFoundError:
    logger.warning("Unknown timezone %s, using Europe/Moscow", TIMEZONE)
    LOCAL_TZ = ZoneInfo("Europe/Moscow")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def local_time(value: datetime) -> str:
    return value.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M:%S %Z")


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def is_admin_user(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == ADMIN_USER_ID)


def parse_stored_time(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_stored_time(value: str | None) -> str:
    parsed = parse_stored_time(value)
    if parsed is None:
        return "неизвестно"
    return local_time(parsed)


async def answer_long(message: Message, lines: list[str]) -> None:
    chunk: list[str] = []
    chunk_size = 0

    for line in lines:
        next_size = chunk_size + len(line) + 1
        if chunk and next_size > 3900:
            await message.answer("\n".join(chunk))
            chunk = []
            chunk_size = 0

        chunk.append(line)
        chunk_size += len(line) + 1

    if chunk:
        await message.answer("\n".join(chunk))


def status_value(member) -> str:
    status = getattr(member, "status", "")
    return status.value if hasattr(status, "value") else str(status)


def is_active_member(member) -> bool:
    status = status_value(member)
    if status == ChatMemberStatus.RESTRICTED.value:
        return bool(getattr(member, "is_member", False))
    return status in ACTIVE_STATUSES


def full_name(user: User) -> str:
    return " ".join(part for part in [user.first_name, user.last_name] if part) or "Unknown"


def user_label(user: User) -> str:
    parts = [full_name(user)]
    if user.username:
        parts.append(f"@{user.username}")
    parts.append(f"id: {user.id}")
    return ", ".join(parts)


def chat_label(chat: Chat) -> str:
    title = chat.title or str(chat.id)
    if chat.username:
        return f"{title} (@{chat.username})"
    return title


async def send_owner_message(bot: Bot, owner_user_id: int, text: str) -> None:
    try:
        await bot.send_message(owner_user_id, text)
    except TelegramForbiddenError:
        logger.warning("Cannot send message to owner %s: chat with bot is closed", owner_user_id)
    except TelegramBadRequest:
        logger.exception("Bad request while sending notification to owner %s", owner_user_id)
    except Exception:
        logger.exception("Failed to send notification to owner %s", owner_user_id)


async def resolve_owner_user_id(
    event: ChatMemberUpdated,
    bot: Bot,
    storage: Storage,
) -> int | None:
    try:
        administrators = await bot.get_chat_administrators(event.chat.id)
    except Exception:
        logger.exception("Cannot read administrators for chat %s", event.chat.id)
        administrators = []

    for administrator in administrators:
        if status_value(administrator) == ChatMemberStatus.CREATOR.value:
            if storage.owner_exists(administrator.user.id):
                return administrator.user.id

    if event.from_user and storage.owner_exists(event.from_user.id):
        return event.from_user.id

    return None


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message, storage: Storage) -> None:
    if not message.from_user:
        return

    storage.upsert_owner(message.from_user)
    logger.info("Registered owner user_id=%s username=%s", message.from_user.id, message.from_user.username)
    await message.answer(
        "<b>Готово, я тебя запомнил.</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Теперь добавь меня <b>администратором</b> в канал. "
        "Когда кто-то подпишется или отпишется, я пришлю событие сюда."
    )


@router.message(Command("help"), F.chat.type == ChatType.PRIVATE)
async def cmd_help(message: Message) -> None:
    lines = [
        "<b>Команды</b>",
        "━━━━━━━━━━━━━━",
        "/start - запомнить тебя как владельца",
        "/channels - показать привязанные каналы",
    ]
    if is_admin_user(message):
        lines.extend(
            [
                "",
                "<b>Админ-команды</b>",
                "/users - список известных пользователей",
                "/usersubs &lt;user_id&gt; - активные подписки пользователя",
            ]
        )
    lines.extend(["", "После /start добавь меня администратором в канал."])
    await message.answer("\n".join(lines))


@router.message(Command("channels"), F.chat.type == ChatType.PRIVATE)
async def cmd_channels(message: Message, storage: Storage) -> None:
    if not message.from_user:
        return

    rows = storage.list_channels_for_owner(message.from_user.id)
    if not rows:
        await message.answer("Пока нет привязанных каналов.")
        return

    lines = ["<b>Привязанные каналы</b>", "━━━━━━━━━━━━━━"]
    for row in rows:
        username = f" (@{esc(row['username'])})" if row["username"] else ""
        lines.append(f"• {esc(row['title'] or row['chat_id'])}{username}")

    await message.answer("\n".join(lines))


@router.message(Command("users"))
async def cmd_users(message: Message, storage: Storage) -> None:
    if not is_admin_user(message):
        return

    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Эта команда доступна только в личке с ботом.")
        return

    users = storage.list_known_users()
    if not users:
        await message.answer("Пока нет известных пользователей.")
        return

    lines = [
        "<b>Известные пользователи</b>",
        "━━━━━━━━━━━━━━",
        f"Всего: <b>{len(users)}</b>",
        "",
    ]
    for row in users:
        username = f" @{esc(row['username'])}" if row["username"] else ""
        name = f" {esc(row['full_name'])}" if row["full_name"] else ""
        owner_mark = "owner" if row["is_owner"] else "subscriber"
        last_event = row["last_event_type"] or "нет событий"
        lines.extend(
            [
                f"• <code>{row['user_id']}</code>{username}{name}",
                (
                    f"  тип: <b>{owner_mark}</b> | "
                    f"подписок: <b>{row['active_subscriptions_count']}</b> | "
                    f"событий: <b>{row['events_count']}</b>"
                ),
                f"  последнее: {esc(last_event)} · {esc(format_stored_time(row['last_seen']))}",
            ]
        )

    await answer_long(message, lines)


@router.message(Command("usersubs"))
async def cmd_user_subscriptions(message: Message, storage: Storage) -> None:
    if not is_admin_user(message):
        return

    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Эта команда доступна только в личке с ботом.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.answer("Использование: <code>/usersubs 1038155901</code>")
        return

    user_id = int(parts[1].strip())
    user = storage.get_known_user(user_id)
    subscriptions = storage.list_user_subscriptions(user_id)

    if user is None and not subscriptions:
        await message.answer(f"Пользователь <code>{user_id}</code> пока не найден в логах.")
        return

    username = f" @{esc(user['username'])}" if user and user["username"] else ""
    name = f" {esc(user['full_name'])}" if user and user["full_name"] else ""
    lines = [
        "<b>Подписки пользователя</b>",
        "━━━━━━━━━━━━━━",
        f"Пользователь: <code>{user_id}</code>{username}{name}",
    ]

    if user:
        lines.append(f"Первое событие: {esc(format_stored_time(user['first_seen']))}")
        lines.append(f"Последнее событие: {esc(format_stored_time(user['last_seen']))}")

    lines.extend(["", f"Активных подписок: <b>{len(subscriptions)}</b>"])

    if not subscriptions:
        lines.append("По текущим логам активных подписок нет.")
        await message.answer("\n".join(lines))
        return

    lines.append("")
    for row in subscriptions:
        title = row["title"] or row["chat_id"]
        username_part = f" (@{esc(row['username'])})" if row["username"] else ""
        lines.extend(
            [
                f"• <b>{esc(title)}</b>{username_part}",
                f"  chat_id: <code>{row['chat_id']}</code>",
                f"  подписался: {esc(format_stored_time(row['subscribed_at']))}",
            ]
        )

    await answer_long(message, lines)


@router.my_chat_member(F.chat.type == ChatType.CHANNEL)
async def on_bot_channel_status(
    event: ChatMemberUpdated,
    bot: Bot,
    storage: Storage,
) -> None:
    old_status = status_value(event.old_chat_member)
    new_status = status_value(event.new_chat_member)
    logger.info(
        "Bot channel status changed chat_id=%s old=%s new=%s actor_id=%s",
        event.chat.id,
        old_status,
        new_status,
        event.from_user.id if event.from_user else None,
    )

    if new_status == ChatMemberStatus.ADMINISTRATOR.value:
        owner_user_id = await resolve_owner_user_id(event, bot, storage)
        if owner_user_id is None:
            logger.warning(
                "Channel %s was not bound: owner/actor did not run /start",
                event.chat.id,
            )
            return

        storage.bind_channel(event.chat, owner_user_id, new_status)
        await send_owner_message(
            bot,
            owner_user_id,
            "<b>Канал привязан.</b>\n"
            "━━━━━━━━━━━━━━\n"
            f"Канал: <b>{esc(chat_label(event.chat))}</b>\n"
            f"Статус бота: <b>{esc(new_status)}</b>\n"
            f"Время: <b>{esc(local_time(utc_now()))}</b>",
        )
        return

    if new_status == ChatMemberStatus.MEMBER.value:
        owner_user_id = storage.unbind_channel(event.chat.id)
        if owner_user_id is None:
            owner_user_id = await resolve_owner_user_id(event, bot, storage)

        if owner_user_id is not None:
            await send_owner_message(
                bot,
                owner_user_id,
                "<b>Мне нужны права администратора.</b>\n"
                "━━━━━━━━━━━━━━\n"
                "Без этого я не смогу отслеживать подписки.\n"
                f"Канал: <b>{esc(chat_label(event.chat))}</b>",
            )
        return

    if old_status in {"administrator", "member"} and new_status in INACTIVE_STATUSES:
        owner_user_id = storage.unbind_channel(event.chat.id)
        if owner_user_id is not None:
            await send_owner_message(
                bot,
                owner_user_id,
                "<b>Канал отвязан.</b>\n"
                "━━━━━━━━━━━━━━\n"
                f"Канал: <b>{esc(chat_label(event.chat))}</b>\n"
                f"Время: <b>{esc(local_time(utc_now()))}</b>",
            )


@router.chat_member(F.chat.type == ChatType.CHANNEL)
async def on_channel_member_change(
    event: ChatMemberUpdated,
    bot: Bot,
    storage: Storage,
) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return

    was_active = is_active_member(event.old_chat_member)
    is_active = is_active_member(event.new_chat_member)
    old_status = status_value(event.old_chat_member)
    new_status = status_value(event.new_chat_member)
    logger.info(
        "Channel member changed chat_id=%s user_id=%s old=%s new=%s",
        event.chat.id,
        user.id,
        old_status,
        new_status,
    )

    if not was_active and is_active:
        event_type = "subscribe"
        event_title = "Новая подписка"
    elif was_active and not is_active:
        event_type = "unsubscribe"
        event_title = "Отписка"
    else:
        return

    owner_user_id = storage.get_channel_owner(event.chat.id)
    if owner_user_id is None:
        logger.info("Skip %s in chat %s: channel is not bound", event_type, event.chat.id)
        return

    event_time = utc_now()
    storage.record_event(
        chat_id=event.chat.id,
        user=user,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        event_time=event_time,
        actor_user_id=event.from_user.id if event.from_user else None,
    )

    await send_owner_message(
        bot,
        owner_user_id,
        f"<b>{esc(event_title)}</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"Канал: <b>{esc(chat_label(event.chat))}</b>\n"
        f"Пользователь: <b>{esc(user_label(user))}</b>\n"
        f"Время: <b>{esc(local_time(event_time))}</b>",
    )
