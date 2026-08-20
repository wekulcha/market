from __future__ import annotations

from prometheus_client import Counter, Histogram


API_REQUESTS = Counter(
    "kulcha_b2b_api_requests_total",
    "HTTP requests handled by the shared KULCHA Market API.",
    ("method", "route", "status"),
)
API_LATENCY = Histogram(
    "kulcha_b2b_api_request_duration_seconds",
    "HTTP request latency by route template.",
    ("method", "route"),
)
PAYMENT_WEBHOOKS = Counter(
    "kulcha_b2b_payment_webhooks_total",
    "Payment webhook processing outcomes.",
    ("provider", "result"),
)
NOTIFICATION_DELIVERIES = Counter(
    "kulcha_b2b_notification_deliveries_total",
    "Notification delivery outcomes.",
    ("channel", "scope", "result"),
)
WORKER_ITERATION_FAILURES = Counter(
    "kulcha_b2b_worker_iteration_failures_total",
    "Unhandled notification worker iteration failures.",
)


def route_template(scope: dict) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else "unmatched"
