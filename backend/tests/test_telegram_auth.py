from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from urllib.parse import quote

from app.services.telegram_auth import verify_telegram_init_data


BOT_TOKEN = "123456:test-token"


def signed_init_data(*, auth_date: int, user_id: int = 42) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps(
            {"id": user_id, "username": "tester"},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{key}={quote(value, safe='')}" for key, value in values.items())


class TelegramInitDataTests(unittest.TestCase):
    def test_accepts_valid_fresh_payload(self) -> None:
        payload = signed_init_data(auth_date=1_000)
        user = verify_telegram_init_data(payload, BOT_TOKEN, max_age_seconds=60, now=1_030)
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], 42)

    def test_rejects_replayed_payload(self) -> None:
        payload = signed_init_data(auth_date=1_000)
        self.assertIsNone(
            verify_telegram_init_data(payload, BOT_TOKEN, max_age_seconds=60, now=1_061)
        )

    def test_rejects_missing_auth_date_even_with_valid_signature(self) -> None:
        values = {
            "query_id": "test-query",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
        check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        payload = "&".join(f"{key}={quote(value, safe='')}" for key, value in values.items())
        self.assertIsNone(verify_telegram_init_data(payload, BOT_TOKEN, now=1_000))

    def test_rejects_tampered_payload(self) -> None:
        payload = signed_init_data(auth_date=1_000).replace("tester", "attacker")
        self.assertIsNone(verify_telegram_init_data(payload, BOT_TOKEN, now=1_000))


if __name__ == "__main__":
    unittest.main()
