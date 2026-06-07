import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN, INTERNAL_API_SECRET, TELEGRAM_PROXY_URL
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("Set MARKET_ADMIN_BOT_TOKEN")
        return
    if not INTERNAL_API_SECRET:
        logger.warning(
            "MARKET_INTERNAL_API_SECRET is not set: кнопки смены статуса заказа в боте не будут работать. "
            "Задайте одинаковый секрет в backend и admin_bot (см. .env.example)."
        )
    session = AiohttpSession(proxy=TELEGRAM_PROXY_URL) if TELEGRAM_PROXY_URL else None
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
