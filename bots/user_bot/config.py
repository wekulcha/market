import os

BOT_TOKEN = os.environ.get("KULCHA_USER_BOT_TOKEN", "")
# Должен совпадать с kulcha.security.bot-api-secret в backend (если задан)
BOT_API_SECRET = os.environ.get("KULCHA_BOT_API_SECRET", "")
API_BASE = os.environ.get("KULCHA_API_BASE", "http://localhost:8000/api/v1")
# Базовый URL мини-приложения пользователя (без слэша в конце). Пример: https://your-domain.com или ngrok URL
USER_MINI_APP_BASE = (os.environ.get("KULCHA_USER_MINI_APP_URL") or "https://kulcha-user.example.com").rstrip("/")
USER_MINI_APP_VERSION = os.environ.get("KULCHA_USER_MINI_APP_VERSION", "").strip()
SUPPORT_LINK = os.environ.get("KULCHA_SUPPORT_LINK", "https://t.me/wekulcha_sup_bot")
