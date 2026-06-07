import os

BOT_TOKEN = os.environ.get("MARKET_SUPERADMIN_BOT_TOKEN", "")
API_BASE = os.environ.get("MARKET_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_API_SECRET = os.environ.get("MARKET_INTERNAL_API_SECRET", "")
SUPERADMIN_MINI_APP_BASE = (
    os.environ.get("MARKET_SUPERADMIN_MINI_APP_URL") or "https://supadmin.wekulcha.online"
).rstrip("/")
ALLOWED_TELEGRAM_IDS: set[int] = set(
    int(x) for x in os.environ.get("MARKET_SUPERADMIN_ALLOWED_IDS", "").split(",") if x.strip().isdigit()
)
SUPPORT_LINK = os.environ.get("MARKET_SUPPORT_LINK", "https://t.me/wekulcha_sup_bot")
