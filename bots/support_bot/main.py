import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN or not BOT_TOKEN.strip():
        logger.error(
            "MARKET_SUPPORT_BOT_TOKEN is empty. Set it in .env / docker-compose for the support bot."
        )
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    # Если у бота был включён webhook (BotFather / тесты), long polling не получает апдейты.
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        me = await bot.get_me()
        logger.info("Support bot OK: @%s (id=%s)", me.username, me.id)
    except Exception:
        logger.exception("Cannot call getMe — проверьте MARKET_SUPPORT_BOT_TOKEN")
        sys.exit(1)

    logger.info("Starting long polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
