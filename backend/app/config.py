from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    # KULCHA B2B is an additive product contour.  The ``b2b_*`` prefix keeps
    # its configuration separate from the legacy Market applications while
    # still following the repository-wide ``MARKET_`` environment convention.
    b2b_app_name: str = "KULCHA B2B"
    app_env: str = "development"
    public_base_url: str = "http://localhost:8080"
    buyer_app_path: str = "/buyer"
    seller_app_path: str = "/seller"
    b2b_admin_app_path: str = "/admin"

    database_url: str = "postgresql+asyncpg://kulcha_market:kulcha_market@localhost:5433/kulcha_market"

    user_bot_token: str = ""
    admin_bot_token: str = ""
    superadmin_bot_token: str = ""
    telegram_proxy_url: str = ""
    superadmin_allowed_ids: Annotated[list[int], NoDecode] = []

    b2b_buyer_bot_token: str = ""
    b2b_buyer_bot_username: str = ""
    b2b_seller_bot_token: str = ""
    b2b_seller_bot_username: str = ""
    b2b_admin_bot_token: str = ""
    b2b_admin_bot_username: str = ""
    b2b_admin_telegram_ids: Annotated[list[int], NoDecode] = []
    telegram_init_data_max_age_seconds: int = 3600

    auth_access_secret: str = ""
    auth_access_ttl_minutes: int = 15
    auth_refresh_ttl_days: int = 30
    auth_cookie_domain: str = ""
    auth_cookie_secure: bool = True

    internal_api_secret: str = ""
    bot_api_secret: str = ""
    b2b_internal_api_secret: str = ""
    b2b_support_link: str = ""

    payment_provider: str = "mock"
    payment_webhook_secret: str = ""
    subscription_grace_period_days: int = 0
    catalog_access_policy: str = "TEASER"
    reservation_ttl_minutes: int = 30
    default_currency: str = "RUB"
    app_timezone: str = "Europe/Moscow"
    order_payment_method: str = "PAY_ON_DELIVERY"
    delivery_provider: str = "manual"
    offer_max_images: int = 8
    offer_image_max_bytes: int = 10 * 1024 * 1024
    object_storage_provider: str = "local"
    notification_max_attempts: int = 5
    notification_poll_seconds: int = 5

    uploads_dir: str = "./uploads"
    object_storage_endpoint: str = "https://storage.yandexcloud.net"
    object_storage_region: str = "ru-central1"
    object_storage_bucket: str = "kulcha-market-menu-items"
    object_storage_access_key_id: str = ""
    object_storage_secret_access_key: str = ""
    object_storage_public_base_url: str = "https://kulcha-market-menu-items.storage.yandexcloud.net"

    cors_allowed_origins: Annotated[list[str], NoDecode] = []
    cors_additional_origins: Annotated[list[str], NoDecode] = []

    @field_validator("superadmin_allowed_ids", "b2b_admin_telegram_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip().isdigit()]
        return []

    @field_validator("catalog_access_policy", mode="before")
    @classmethod
    def _validate_catalog_policy(cls, v: object) -> str:
        value = str(v or "TEASER").strip().upper()
        if value not in {"BLOCKED", "TEASER", "READ_ONLY"}:
            raise ValueError("catalog_access_policy must be BLOCKED, TEASER or READ_ONLY")
        return value

    @field_validator("payment_provider", mode="before")
    @classmethod
    def _normalise_payment_provider(cls, v: object) -> str:
        return str(v or "mock").strip().lower()

    @field_validator("cors_allowed_origins", "cors_additional_origins", mode="before")
    @classmethod
    def _parse_csv_list(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = []
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            return [x.strip() for x in raw.split(",") if x.strip()]
        return []

    model_config = {
        "env_prefix": "MARKET_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
