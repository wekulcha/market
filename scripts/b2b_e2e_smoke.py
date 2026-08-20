#!/usr/bin/env python3
"""Destructive local KULCHA B2B vertical smoke test through public HTTP contracts.

The script deliberately refuses mutations unless B2B_E2E_ALLOW_MUTATIONS=1 and
defaults to a loopback API. It never prints bot tokens, invite tokens or JWTs.
Run the local seed first so roles, a verified demo seller, categories and a plan exist.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
)


class SmokeFailure(RuntimeError):
    pass


def env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return default


def required_env(*names: str) -> str:
    value = env_value(*names)
    if not value:
        raise SmokeFailure(f"Set one of: {', '.join(names)}")
    return value


def telegram_init_data(telegram_id: int, username: str, bot_token: str) -> str:
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": f"e2e-{uuid.uuid4().hex}",
        "user": json.dumps(
            {
                "id": telegram_id,
                "is_bot": False,
                "first_name": "B2B E2E",
                "username": username,
                "language_code": "ru",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    # Backend intentionally mirrors Telegram's percent-encoding with ``unquote``;
    # avoid ``+`` for spaces so the data-check string stays byte-identical.
    return urlencode(fields, quote_via=quote)


class API:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200,),
        content_type: str = "application/json",
    ) -> Any:
        if body is not None and raw_body is not None:
            raise ValueError("body and raw_body are mutually exclusive")
        data = raw_body
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode()
        request_headers = {"Accept": "application/json", **(headers or {})}
        if data is not None:
            request_headers["Content-Type"] = content_type
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = response.status
                payload = response.read()
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise SmokeFailure(
                f"{method} {path} returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc.reason}") from exc
        if status not in expected:
            raise SmokeFailure(
                f"{method} {path} returned HTTP {status}; expected {expected}"
            )
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"{method} {path} returned non-JSON data") from exc


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(api: API, telegram_id: int, username: str, role: str, bot_token: str) -> str:
    payload = api.request(
        "POST",
        "/api/auth/telegram",
        body={
            "initDataRaw": telegram_init_data(telegram_id, username, bot_token),
            "role": role,
        },
    )
    token = str(payload.get("accessToken") or "")
    if not token:
        raise SmokeFailure(f"{role} login response has no access token")
    return token


def multipart_image() -> tuple[bytes, str]:
    boundary = f"----kulcha-b2b-{uuid.uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="e2e.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + PNG_1X1
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def assert_no_keys(
    payload: Any, forbidden_fragments: tuple[str, ...], context: str
) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in forbidden_fragments):
                raise SmokeFailure(f"{context} leaked forbidden field: {key}")
            assert_no_keys(value, forbidden_fragments, context)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_keys(value, forbidden_fragments, context)


def find_by(
    items: list[dict[str, Any]], key: str, value: Any, context: str
) -> dict[str, Any]:
    for item in items:
        if item.get(key) == value:
            return item
    raise SmokeFailure(f"{context}: no item with {key}={value!r}")


def main() -> None:
    if env_value("B2B_E2E_ALLOW_MUTATIONS") != "1":
        raise SmokeFailure(
            "Refusing mutations; set B2B_E2E_ALLOW_MUTATIONS=1 for a disposable local DB"
        )
    app_env = env_value("APP_ENV", "MARKET_APP_ENV", default="development").lower()
    if app_env in {"prod", "production"}:
        raise SmokeFailure("Refusing to run against APP_ENV=production")

    base_url = env_value("B2B_E2E_BASE_URL", default="http://127.0.0.1:8000")
    host = (urlsplit(base_url).hostname or "").lower()
    if (
        host not in {"127.0.0.1", "localhost", "backend", "kulcha-market-backend"}
        and env_value("B2B_E2E_ALLOW_REMOTE") != "1"
    ):
        raise SmokeFailure(
            "Refusing a non-local API; set B2B_E2E_ALLOW_REMOTE=1 only for disposable staging"
        )

    internal_secret = required_env(
        "B2B_INTERNAL_API_SECRET", "MARKET_B2B_INTERNAL_API_SECRET"
    )
    buyer_bot_token = required_env("BUYER_BOT_TOKEN", "MARKET_B2B_BUYER_BOT_TOKEN")
    seller_bot_token = required_env("SELLER_BOT_TOKEN", "MARKET_B2B_SELLER_BOT_TOKEN")
    admin_bot_token = required_env("ADMIN_BOT_TOKEN", "MARKET_B2B_ADMIN_BOT_TOKEN")
    admin_id_raw = required_env(
        "B2B_BOOTSTRAP_SUPERADMIN_TELEGRAM_ID",
        "B2B_E2E_ADMIN_TELEGRAM_ID",
    )
    buyer_id = int(env_value("B2B_E2E_BUYER_TELEGRAM_ID", default="900000002"))
    seller_id = int(env_value("B2B_DEMO_SELLER_TELEGRAM_ID", default="900000001"))
    admin_id = int(admin_id_raw)
    buyer_phone = env_value("B2B_E2E_BUYER_PHONE", default="+79990000002")
    run_id = uuid.uuid4().hex[:10]
    api = API(base_url)

    health_path = env_value("B2B_E2E_HEALTH_PATH", default="/health")
    api.request("GET", health_path)
    print("[ok] API health")

    admin_token = login(api, admin_id, "b2b_superadmin", "SUPERADMIN", admin_bot_token)
    admin_headers = bearer(admin_token)
    print("[ok] superadmin Telegram auth")

    invite = api.request(
        "POST",
        "/api/admin/invites",
        body={
            "label": f"E2E {run_id}",
            "expiresInDays": 1,
            "maxUses": 1,
            "trialDays": 0,
            "source": "b2b-e2e-smoke",
        },
        headers=admin_headers,
        expected=(201,),
    )
    invite_token = str(invite.get("token") or "")
    if not invite_token:
        raise SmokeFailure("Invite API did not return a one-time token")

    registration = api.request(
        "POST",
        "/api/internal/bots/buyer/register",
        body={
            "telegramId": buyer_id,
            "username": "b2b_e2e_buyer",
            "phone": buyer_phone,
            "inviteToken": invite_token,
        },
        headers={"X-B2B-Internal-Secret": internal_secret},
        expected=(201,),
    )
    buyer_profile_id = str(registration.get("buyerProfileId") or "")
    if not buyer_profile_id:
        raise SmokeFailure("Buyer registration response has no profile ID")
    invite_token = ""  # Do not retain the raw credential longer than needed.

    api.request(
        "POST",
        "/api/admin/subscriptions/override",
        body={
            "buyerId": buyer_profile_id,
            "status": "ACTIVE",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "reason": "Disposable local E2E smoke",
        },
        headers=admin_headers,
    )
    buyer_token = login(api, buyer_id, "b2b_e2e_buyer", "BUYER", buyer_bot_token)
    buyer_headers = bearer(buyer_token)
    print("[ok] invite activation, subscription and buyer auth")

    seller_token = login(api, seller_id, "demo_supplier", "SELLER", seller_bot_token)
    seller_headers = bearer(seller_token)
    offer_title = f"E2E томаты {run_id}"
    api.request(
        "PATCH",
        "/api/seller/me",
        body={"pickupAddress": "Москва, E2E-склад, 1", "pickupHours": "09:00–18:00"},
        headers=seller_headers,
    )
    offer = api.request(
        "POST",
        "/api/seller/offers",
        body={
            "name": offer_title,
            "description": "Автоматический локальный E2E товар",
            "category": "vegetables",
            "procurementUnitPriceKopecks": 8000,
            "currency": "RUB",
            "unit": "KG",
            "packageSize": "1",
            "totalQuantity": "100",
            "minimumQuantity": "10",
            "quantityStep": "5",
            "storageConditions": "Хранить в прохладном месте",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=14))
            .date()
            .isoformat(),
        },
        headers=seller_headers,
        expected=(201,),
    )
    offer_id = str(offer.get("id") or "")
    image_body, image_content_type = multipart_image()
    api.request(
        "POST",
        f"/api/seller/offers/{offer_id}/images",
        raw_body=image_body,
        content_type=image_content_type,
        headers=seller_headers,
        expected=(201,),
    )
    api.request(
        "POST", f"/api/seller/offers/{offer_id}/submit", body={}, headers=seller_headers
    )
    api.request(
        "POST",
        f"/api/admin/offers/{offer_id}/moderate",
        body={"decision": "APPROVE"},
        headers=admin_headers,
    )
    api.request(
        "POST",
        f"/api/admin/offers/{offer_id}/pricing",
        body={"markupType": "PERCENT", "markupPercent": "20"},
        headers=admin_headers,
    )
    api.request(
        "POST", f"/api/admin/offers/{offer_id}/publish", body={}, headers=admin_headers
    )
    print("[ok] seller offer, image, moderation, pricing and publication")

    api.request(
        "PATCH",
        "/api/buyer/me",
        body={
            "companyName": f"E2E Покупатель {run_id}",
            "legalForm": "ООО",
            "inn": "7700000001",
            "contactName": "E2E Контакт",
            "phone": buyer_phone,
        },
        headers=buyer_headers,
    )
    address = api.request(
        "POST",
        "/api/buyer/addresses",
        body={
            "label": f"E2E {run_id}",
            "value": "Москва, E2E-улица, 1",
            "contactName": "E2E Контакт",
            "contactPhone": buyer_phone,
            "isDefault": True,
        },
        headers=buyer_headers,
        expected=(201,),
    )
    catalog = api.request(
        "GET",
        f"/api/buyer/catalog?search={quote(offer_title, safe='')}&pageSize=20",
        headers=buyer_headers,
    )
    if catalog.get("accessPolicy") != "FULL":
        raise SmokeFailure(
            f"Buyer catalog access is {catalog.get('accessPolicy')}, expected FULL"
        )
    catalog_offer = find_by(catalog.get("items") or [], "id", offer_id, "buyer catalog")
    assert_no_keys(
        catalog_offer,
        (
            "supplier",
            "procurement",
            "margin",
            "sellercontact",
            "pickupaddress",
            "internal",
        ),
        "buyer catalog",
    )
    quantity = catalog_offer.get("minimumQuantity") or 10
    api.request(
        "POST",
        "/api/buyer/cart/items",
        body={"offerId": offer_id, "quantity": quantity},
        headers=buyer_headers,
        expected=(201,),
    )
    idempotency_key = f"b2b-e2e-{uuid.uuid4().hex}"
    checkout_body = {
        "addressId": address["id"],
        "recipientName": "E2E Контакт",
        "recipientPhone": buyer_phone,
        "deliveryWindow": "10:00–14:00",
        "comment": "Disposable local E2E smoke",
        "paymentMethod": "PAY_ON_DELIVERY",
        "idempotencyKey": idempotency_key,
    }
    order = api.request(
        "POST",
        "/api/buyer/orders",
        body=checkout_body,
        headers={**buyer_headers, "Idempotency-Key": idempotency_key},
        expected=(201,),
    )
    replay = api.request(
        "POST",
        "/api/buyer/orders",
        body=checkout_body,
        headers={**buyer_headers, "Idempotency-Key": idempotency_key},
        expected=(201,),
    )
    if replay.get("id") != order.get("id"):
        raise SmokeFailure("Checkout idempotency replay created a different order")
    order_id = str(order["id"])
    order_number = order["number"]
    detail = api.request("GET", f"/api/buyer/orders/{order_id}", headers=buyer_headers)
    assert_no_keys(
        detail,
        ("supplier", "procurement", "margin", "seller", "pickup", "internal"),
        "buyer order",
    )
    print("[ok] buyer catalog privacy, cart, checkout and idempotency")

    seller_orders = api.request(
        "GET", "/api/seller/orders?pageSize=100", headers=seller_headers
    )
    seller_group = find_by(
        seller_orders.get("items") or [], "number", order_number, "seller orders"
    )
    assert_no_keys(
        seller_group,
        ("buyer", "recipient", "deliveryaddress", "markup", "margin", "buyerunitprice"),
        "seller order",
    )
    group_id = seller_group["id"]
    api.request(
        "POST",
        f"/api/seller/orders/{group_id}/confirm",
        body={},
        headers=seller_headers,
    )
    api.request(
        "POST", f"/api/seller/orders/{group_id}/ready", body={}, headers=seller_headers
    )
    print("[ok] seller confirmation, readiness and privacy projection")

    delivery = api.request(
        "POST",
        "/api/admin/deliveries",
        body={
            "orderId": order_id,
            "courierName": "E2E Курьер",
            "courierContact": "+79990000003",
            "pickupWindow": "09:00–10:00",
            "deliveryWindow": "10:00–14:00",
            "costKopecks": 0,
        },
        headers=admin_headers,
        expected=(201,),
    )
    delivery_id = str((delivery.get("items") or [{}])[0].get("id") or "")
    if not delivery_id:
        raise SmokeFailure("Delivery API returned no delivery ID")
    for status in ("PICKED_UP", "IN_DELIVERY", "DELIVERED"):
        api.request(
            "POST",
            f"/api/admin/deliveries/{delivery_id}/status",
            body={"status": status, "comment": "Disposable local E2E smoke"},
            headers=admin_headers,
        )
    api.request(
        "POST",
        f"/api/admin/orders/{order_id}/transition",
        body={"status": "COMPLETED", "comment": "Disposable local E2E smoke"},
        headers=admin_headers,
    )
    final_order = api.request(
        "GET", f"/api/buyer/orders/{order_id}", headers=buyer_headers
    )
    if final_order.get("status") != "COMPLETED":
        raise SmokeFailure(
            f"Final order status is {final_order.get('status')}, expected COMPLETED"
        )
    api.request("GET", "/api/admin/dashboard", headers=admin_headers)
    print(f"[ok] delivery and completion; order={order_number}")
    print("KULCHA B2B destructive local E2E smoke passed")


if __name__ == "__main__":
    try:
        main()
    except (SmokeFailure, ValueError) as exc:
        raise SystemExit(f"B2B E2E FAILED: {exc}") from exc
