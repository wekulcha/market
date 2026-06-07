import os

BOT_TOKEN = os.environ.get("MARKET_ADMIN_BOT_TOKEN", "")
API_BASE = os.environ.get("MARKET_API_BASE", "http://localhost:8000/api/v1")
# Совпадает с MARKET_INTERNAL_API_SECRET в backend (для callback-кнопок статуса заказа).
INTERNAL_API_SECRET = os.environ.get("MARKET_INTERNAL_API_SECRET", "")
# URL мини-приложения админки (полный URL, без слэша в конце). Пример: https://your-domain.com/admin
ADMIN_MINI_APP_URL = (os.environ.get("MARKET_ADMIN_MINI_APP_URL") or "https://adminmarket.wekulcha.online").rstrip("/")
SUPPORT_LINK = os.environ.get("MARKET_SUPPORT_LINK", "https://t.me/wekulcha_sup_bot")
