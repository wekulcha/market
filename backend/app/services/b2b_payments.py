from __future__ import annotations

import hashlib
import hmac
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class PaymentError(ValueError):
    pass


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    REFUNDED = "REFUNDED"


@dataclass(frozen=True)
class PaymentRequest:
    idempotency_key: str
    amount_kopecks: int
    currency: str = "RUB"
    return_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentIntent:
    provider: str
    provider_payment_id: str
    status: PaymentStatus
    amount_kopecks: int
    currency: str
    confirmation_url: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentWebhookEvent:
    provider: str
    event_id: str
    provider_payment_id: str
    status: PaymentStatus
    amount_kopecks: int | None = None
    currency: str | None = None
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentIntent:
        raise NotImplementedError

    @abstractmethod
    async def get_payment(self, provider_payment_id: str) -> PaymentIntent:
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(
        self,
        payload: bytes,
        signature: str,
        *,
        now: int | None = None,
    ) -> PaymentWebhookEvent:
        raise NotImplementedError


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def derive_idempotency_key(*parts: object) -> str:
    canonical = "\x1f".join(str(part).strip() for part in parts)
    if not canonical or not canonical.replace("\x1f", ""):
        raise PaymentError("at least one idempotency key part is required")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign_webhook(payload: bytes, secret: str, *, timestamp: int) -> str:
    if not secret:
        raise PaymentError("webhook secret is required")
    signed_payload = str(timestamp).encode("ascii") + b"." + payload
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    *,
    max_age_seconds: int = 300,
    now: int | None = None,
) -> bool:
    if not payload or not signature or not secret or max_age_seconds < 0:
        return False
    parts: dict[str, str] = {}
    for item in signature.split(","):
        key, separator, value = item.strip().partition("=")
        if separator and key and value:
            parts[key] = value
    try:
        timestamp = int(parts["t"])
    except (KeyError, TypeError, ValueError):
        return False
    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - timestamp) > max_age_seconds:
        return False
    expected = sign_webhook(payload, secret, timestamp=timestamp)
    expected_digest = expected.partition("v1=")[2]
    return hmac.compare_digest(expected_digest, parts.get("v1", ""))


class MockPaymentProvider(PaymentProvider):
    """Deterministic in-memory provider that refuses to run in production."""

    name = "mock"
    _ALLOWED_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})

    def __init__(self, *, environment: str, webhook_secret: str):
        if environment.strip().lower() not in self._ALLOWED_ENVIRONMENTS:
            raise RuntimeError("MockPaymentProvider is disabled outside local/dev/test")
        if not webhook_secret:
            raise PaymentError("mock webhook secret is required")
        self._webhook_secret = webhook_secret
        self._by_provider_id: dict[str, PaymentIntent] = {}
        self._by_idempotency_key: dict[str, PaymentIntent] = {}

    async def create_payment(self, request: PaymentRequest) -> PaymentIntent:
        if not request.idempotency_key.strip():
            raise PaymentError("idempotency_key is required")
        if isinstance(request.amount_kopecks, bool) or request.amount_kopecks <= 0:
            raise PaymentError("amount_kopecks must be a positive integer")
        if not isinstance(request.amount_kopecks, int):
            raise PaymentError("amount_kopecks must be a positive integer")
        currency = request.currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise PaymentError("currency must be a three-letter ISO code")

        existing = self._by_idempotency_key.get(request.idempotency_key)
        if existing:
            if (
                existing.amount_kopecks != request.amount_kopecks
                or existing.currency != currency
            ):
                raise PaymentError("idempotency key was reused with different payment data")
            return existing

        provider_payment_id = f"mock_{derive_idempotency_key(request.idempotency_key)[:24]}"
        intent = PaymentIntent(
            provider=self.name,
            provider_payment_id=provider_payment_id,
            status=PaymentStatus.PENDING,
            amount_kopecks=request.amount_kopecks,
            currency=currency,
            confirmation_url=f"mock://payments/{provider_payment_id}/confirm",
            raw_payload={"metadata": dict(request.metadata)},
        )
        self._by_provider_id[provider_payment_id] = intent
        self._by_idempotency_key[request.idempotency_key] = intent
        return intent

    async def get_payment(self, provider_payment_id: str) -> PaymentIntent:
        try:
            return self._by_provider_id[provider_payment_id]
        except KeyError as exc:
            raise PaymentError("mock payment not found") from exc

    def parse_webhook(
        self,
        payload: bytes,
        signature: str,
        *,
        now: int | None = None,
    ) -> PaymentWebhookEvent:
        if not verify_webhook_signature(
            payload,
            signature,
            self._webhook_secret,
            now=now,
        ):
            raise PaymentError("invalid webhook signature")
        try:
            decoded = json.loads(payload.decode("utf-8"))
            event_id = str(decoded["event_id"])
            provider_payment_id = str(decoded["payment_id"])
            status = PaymentStatus(str(decoded["status"]).upper())
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise PaymentError("invalid mock webhook payload") from exc
        if not event_id or not provider_payment_id:
            raise PaymentError("webhook event and payment identifiers are required")
        amount = decoded.get("amount_kopecks")
        if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int)):
            raise PaymentError("webhook amount_kopecks must be an integer")
        currency = decoded.get("currency")
        return PaymentWebhookEvent(
            provider=self.name,
            event_id=event_id,
            provider_payment_id=provider_payment_id,
            status=status,
            amount_kopecks=amount,
            currency=str(currency).upper() if currency else None,
            raw_payload=decoded,
        )
