"""Catalog + checkout load scenario for disposable KULCHA B2B staging only."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from locust import HttpUser, between, task
from locust.exception import StopUser


@dataclass(frozen=True)
class BuyerCredential:
    access_token: str
    address_id: str
    offer_id: str
    quantity: str
    recipient_name: str
    recipient_phone: str


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes"}


def _credential(raw: dict[str, Any]) -> BuyerCredential:
    required = ("accessToken", "addressId", "offerId", "recipientPhone")
    missing = [key for key in required if not str(raw.get(key) or "").strip()]
    if missing:
        raise RuntimeError(f"Load credential is missing: {', '.join(missing)}")
    return BuyerCredential(
        access_token=str(raw["accessToken"]),
        address_id=str(raw["addressId"]),
        offer_id=str(raw["offerId"]),
        quantity=str(raw.get("quantity") or "10"),
        recipient_name=str(raw.get("recipientName") or "Нагрузочный тест"),
        recipient_phone=str(raw["recipientPhone"]),
    )


def _load_credentials() -> list[BuyerCredential]:
    path = (os.environ.get("B2B_LOAD_BUYER_CREDENTIALS_FILE") or "").strip()
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("B2B load credentials file must contain a JSON array")
        return [_credential(item) for item in payload]
    token = (os.environ.get("B2B_LOAD_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "Set B2B_LOAD_BUYER_CREDENTIALS_FILE or B2B_LOAD_ACCESS_TOKEN"
        )
    return [
        _credential(
            {
                "accessToken": token,
                "addressId": os.environ.get("B2B_LOAD_ADDRESS_ID"),
                "offerId": os.environ.get("B2B_LOAD_OFFER_ID"),
                "quantity": os.environ.get("B2B_LOAD_QUANTITY") or "10",
                "recipientPhone": os.environ.get("B2B_LOAD_RECIPIENT_PHONE"),
            }
        )
    ]


_POOL = _load_credentials()
_POOL_LOCK = threading.Lock()


class B2BBuyerUser(HttpUser):
    wait_time = between(0.2, 1.0)
    credential: BuyerCredential

    def on_start(self) -> None:
        with _POOL_LOCK:
            if not _POOL:
                raise StopUser("Provide one unique buyer credential per Locust user")
            self.credential = _POOL.pop()
        self.headers = {"Authorization": f"Bearer {self.credential.access_token}"}

    @task(8)
    def catalog(self) -> None:
        with self.client.get(
            "/api/buyer/catalog?page=1&pageSize=20&sort=NEWEST",
            headers=self.headers,
            name="GET /api/buyer/catalog",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError:
                response.failure("non-JSON catalog response")
                return
            if payload.get("accessPolicy") != "FULL":
                response.failure(f"accessPolicy={payload.get('accessPolicy')}")

    @task(1)
    def checkout(self) -> None:
        if not _truthy("B2B_LOAD_ENABLE_CHECKOUT"):
            self.catalog()
            return
        if not _truthy("B2B_LOAD_ALLOW_MUTATIONS"):
            raise StopUser("Checkout load requires B2B_LOAD_ALLOW_MUTATIONS=1")

        cart = self.client.post(
            "/api/buyer/cart/items",
            json={
                "offerId": self.credential.offer_id,
                "quantity": self.credential.quantity,
            },
            headers=self.headers,
            name="POST /api/buyer/cart/items",
        )
        if cart.status_code not in {200, 201}:
            return

        key = f"b2b-load-{uuid.uuid4().hex}"
        order = self.client.post(
            "/api/buyer/orders",
            json={
                "addressId": self.credential.address_id,
                "recipientName": self.credential.recipient_name,
                "recipientPhone": self.credential.recipient_phone,
                "paymentMethod": "PAY_ON_DELIVERY",
                "comment": "Disposable staging load test",
                "idempotencyKey": key,
            },
            headers={**self.headers, "Idempotency-Key": key},
            name="POST /api/buyer/orders",
        )
        if order.status_code != 201 or not _truthy("B2B_LOAD_CANCEL_ORDERS"):
            return
        try:
            order_id = order.json()["id"]
        except (ValueError, KeyError):
            return
        self.client.post(
            f"/api/buyer/orders/{order_id}/cancel",
            headers=self.headers,
            name="POST /api/buyer/orders/:id/cancel",
        )
