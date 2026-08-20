from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


def _path_env(name: str, default: str) -> str:
    value = (os.environ.get(name) or default).strip()
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/") or "/"


def _positive_float_env(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if 0 < value <= 65535 else default


def _telegram_ids_env(name: str) -> frozenset[int]:
    values: set[int] = set()
    for raw in (os.environ.get(name) or "").split(","):
        item = raw.strip()
        if item.isdigit() and int(item) > 0:
            values.add(int(item))
    return frozenset(values)


def _clean_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise RuntimeError("PUBLIC_BASE_URL must be an absolute http(s) URL")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


@dataclass(frozen=True, slots=True)
class BotSettings:
    role: str
    app_name: str
    token: str
    username: str
    api_base: str
    internal_api_secret: str
    public_base_url: str
    app_path: str
    support_url: str
    telegram_proxy_url: str
    request_timeout_seconds: float
    admin_telegram_ids: frozenset[int]
    bot_mode: str
    webhook_secret: str
    webhook_host: str
    webhook_port: int
    webhook_path: str
    redis_url: str

    def app_url(self, suffix: str = "") -> str:
        suffix_path = suffix.strip()
        if (
            suffix_path
            and not suffix_path.startswith("/")
            and not suffix_path.startswith("?")
        ):
            suffix_path = f"/{suffix_path}"
        return f"{self.public_base_url}{self.app_path}{suffix_path}"

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url}{self.webhook_path}"

    def validate_runtime(self, *, require_admin_allowlist: bool = False) -> None:
        missing: list[str] = []
        if not self.token:
            missing.append(f"{self.role.upper()}_BOT_TOKEN")
        if not self.internal_api_secret:
            missing.append("B2B_INTERNAL_API_SECRET")
        if require_admin_allowlist and not self.admin_telegram_ids:
            missing.append("ADMIN_TELEGRAM_IDS")
        if self.bot_mode not in {"polling", "webhook"}:
            raise RuntimeError("BOT_MODE must be polling or webhook")
        if self.bot_mode == "webhook":
            if not self.webhook_secret:
                missing.append(f"{self.role.upper()}_BOT_WEBHOOK_SECRET")
            elif not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", self.webhook_secret):
                raise RuntimeError(
                    "BOT_WEBHOOK_SECRET must contain 32-256 letters, digits, underscores or hyphens"
                )
            if not self.public_base_url.startswith("https://"):
                raise RuntimeError("PUBLIC_BASE_URL must use HTTPS in webhook mode")
            if not self.redis_url:
                missing.append("REDIS_URL")
        if missing:
            raise RuntimeError(
                f"Required environment variables are missing: {', '.join(missing)}"
            )


def load_bot_settings(role: str) -> BotSettings:
    normalized_role = role.strip().lower()
    role_config = {
        "buyer": ("BUYER", "BUYER_APP_PATH", "/buyer", 8081),
        "seller": ("SELLER", "SELLER_APP_PATH", "/seller", 8082),
        "admin": ("ADMIN", "ADMIN_APP_PATH", "/admin", 8083),
    }
    try:
        env_role, path_env, default_path, default_webhook_port = role_config[
            normalized_role
        ]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported bot role: {role}") from exc

    public_base_url = _clean_base_url(
        os.environ.get("PUBLIC_BASE_URL") or "http://localhost:8080"
    )
    api_base = (
        (os.environ.get("B2B_API_BASE") or "http://localhost:8000").strip().rstrip("/")
    )
    if not api_base.startswith(("http://", "https://")):
        raise RuntimeError("B2B_API_BASE must be an absolute http(s) URL")

    return BotSettings(
        role=normalized_role,
        app_name=(os.environ.get("APP_NAME") or "KULCHA B2B").strip(),
        token=(os.environ.get(f"{env_role}_BOT_TOKEN") or "").strip(),
        username=(os.environ.get(f"{env_role}_BOT_USERNAME") or "").strip().lstrip("@"),
        api_base=api_base,
        internal_api_secret=(os.environ.get("B2B_INTERNAL_API_SECRET") or "").strip(),
        public_base_url=public_base_url,
        app_path=_path_env(path_env, default_path),
        support_url=(os.environ.get("B2B_SUPPORT_URL") or "").strip(),
        telegram_proxy_url=(os.environ.get("B2B_TELEGRAM_PROXY_URL") or "").strip(),
        request_timeout_seconds=_positive_float_env(
            "B2B_BOT_REQUEST_TIMEOUT_SECONDS", 15.0
        ),
        admin_telegram_ids=_telegram_ids_env("ADMIN_TELEGRAM_IDS"),
        bot_mode=(
            os.environ.get("BOT_MODE")
            or os.environ.get(f"{env_role}_BOT_MODE")
            or "polling"
        )
        .strip()
        .lower(),
        webhook_secret=(
            os.environ.get("BOT_WEBHOOK_SECRET")
            or os.environ.get(f"{env_role}_BOT_WEBHOOK_SECRET")
            or ""
        ).strip(),
        webhook_host=(os.environ.get("BOT_WEBHOOK_HOST") or "0.0.0.0").strip(),
        webhook_port=_positive_int_env("BOT_WEBHOOK_PORT", default_webhook_port),
        webhook_path=f"/webhooks/telegram/{normalized_role}",
        redis_url=(os.environ.get("REDIS_URL") or "").strip(),
    )
