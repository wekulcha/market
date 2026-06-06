from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kulcha"

    user_bot_token: str = ""
    admin_bot_token: str = ""
    superadmin_bot_token: str = ""
    superadmin_allowed_ids: list[int] = []

    auth_access_secret: str = ""
    auth_access_ttl_minutes: int = 15
    auth_refresh_ttl_days: int = 30
    auth_cookie_domain: str = ""
    auth_cookie_secure: bool = True

    internal_api_secret: str = ""
    bot_api_secret: str = ""

    uploads_dir: str = "./uploads"
    object_storage_endpoint: str = "https://storage.yandexcloud.net"
    object_storage_region: str = "ru-central1"
    object_storage_bucket: str = "kulcha-main-menu-items"
    object_storage_access_key_id: str = ""
    object_storage_secret_access_key: str = ""
    object_storage_public_base_url: str = "https://kulcha-main-menu-items.storage.yandexcloud.net"

    cors_additional_origins: list[str] = []

    @field_validator("superadmin_allowed_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip().isdigit()]
        return []

    model_config = {
        "env_prefix": "KULCHA_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
