import os

BOT_TOKEN = os.environ.get("MARKET_USER_BOT_TOKEN", "")
TELEGRAM_PROXY_URL = os.environ.get("MARKET_TELEGRAM_PROXY_URL", "").strip()
# Должен совпадать с MARKET_BOT_API_SECRET в backend (если задан).
BOT_API_SECRET = os.environ.get("MARKET_BOT_API_SECRET", "")
API_BASE = os.environ.get("MARKET_API_BASE", "http://localhost:8000/api/v1")
# Базовый URL мини-приложения пользователя (без слэша в конце). Пример: https://your-domain.com или ngrok URL
USER_MINI_APP_BASE = (os.environ.get("MARKET_USER_MINI_APP_URL") or "https://market.wekulcha.ru").rstrip("/")
USER_MINI_APP_VERSION = os.environ.get("MARKET_USER_MINI_APP_VERSION", "").strip()
SUPPORT_LINK = os.environ.get("MARKET_SUPPORT_LINK", "https://t.me/wekulcha_sup_bot")
