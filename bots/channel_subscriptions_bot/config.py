import os
from pathlib import Path


DEFAULT_BOT_TOKEN = "8653190572:AAGMbnk-FGktiB5iIMMEh9kKPMs7xd4Q0TA"
DEFAULT_ADMIN_USER_ID = 1038155901

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.environ.get("KULCHA_CHANNEL_SUBSCRIPTIONS_BOT_TOKEN", DEFAULT_BOT_TOKEN).strip()
ADMIN_USER_ID = int(os.environ.get("KULCHA_CHANNEL_SUBSCRIPTIONS_ADMIN_ID", DEFAULT_ADMIN_USER_ID))
DB_PATH = Path(
    os.environ.get(
        "KULCHA_CHANNEL_SUBSCRIPTIONS_DB",
        str(BASE_DIR / "subscriptions.sqlite3"),
    )
)
TIMEZONE = os.environ.get("KULCHA_CHANNEL_SUBSCRIPTIONS_TZ", "Europe/Moscow").strip()
