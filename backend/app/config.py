from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://kulcha_market:kulcha_market@localhost:5433/kulcha_market"

    user_bot_token: str = ""
    admin_bot_token: str = ""
    superadmin_bot_token: str = ""
    superadmin_allowed_ids: Annotated[list[int], NoDecode] = []

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
    object_storage_bucket: str = "kulcha-market-menu-items"
    object_storage_access_key_id: str = ""
    object_storage_secret_access_key: str = ""
    object_storage_public_base_url: str = "https://kulcha-market-menu-items.storage.yandexcloud.net"

    cors_allowed_origins: Annotated[list[str], NoDecode] = []
    cors_additional_origins: Annotated[list[str], NoDecode] = []

    @field_validator("superadmin_allowed_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: object) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip().isdigit()]
        return []

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
