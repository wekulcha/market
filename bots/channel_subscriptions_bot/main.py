import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, DB_PATH
from handlers import router
from storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("KULCHA_CHANNEL_SUBSCRIPTIONS_BOT_TOKEN is empty")
        sys.exit(1)

    storage = Storage(DB_PATH)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["storage"] = storage
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=False)
    try:
        me = await bot.get_me()
        logger.info("Channel subscriptions bot OK: @%s (id=%s)", me.username, me.id)
    except Exception:
        logger.exception("Cannot call getMe. Check KULCHA_CHANNEL_SUBSCRIPTIONS_BOT_TOKEN")
        sys.exit(1)

    logger.info("Starting long polling...")
    await dp.start_polling(
        bot,
        allowed_updates=["message", "my_chat_member", "chat_member"],
    )


if __name__ == "__main__":
    asyncio.run(main())
