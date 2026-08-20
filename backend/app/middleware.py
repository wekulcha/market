from __future__ import annotations

import logging
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.services.b2b_metrics import API_LATENCY, API_REQUESTS, route_template


logger = logging.getLogger("kulcha.request")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id and emit a PII-free request completion log."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.perf_counter() - started
            route = route_template(request.scope)
            API_REQUESTS.labels(request.method, route, "500").inc()
            API_LATENCY.labels(request.method, route).observe(elapsed)
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        elapsed = time.perf_counter() - started
        route = route_template(request.scope)
        API_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        API_LATENCY.labels(request.method, route).observe(elapsed)
        duration_ms = round(elapsed * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
