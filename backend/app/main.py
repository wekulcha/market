from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import get_db
from app.middleware import RequestContextMiddleware
from app.routers import (
    admin,
    activity,
    auth,
    courier_panel,
    couriers,
    meal_assets,
    meals,
    restaurant_assets,
    order_positions,
    orders,
    restaurant_staff,
    restaurants,
    staff,
    subscription_logs,
    support_internal,
    users,
)
from app.routers import (
    b2b_admin,
    b2b_assets,
    b2b_auth,
    b2b_buyer,
    b2b_internal,
    b2b_seller,
    b2b_webhooks,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    settings = get_settings()
    logger.info("Kulcha Market backend started (user_bot_token configured: %s, admin_bot_token configured: %s)",
                bool(settings.user_bot_token), bool(settings.admin_bot_token))
    yield


settings = get_settings()
app = FastAPI(title=f"{settings.b2b_app_name} / Kulcha Market backend", version="3.0.0", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "https://market.wekulcha.ru",
    "https://adminmarket.wekulcha.online",
    "https://supmarket.wekulcha.online",
    settings.public_base_url,
    *settings.cors_allowed_origins,
    *settings.cors_additional_origins,
]
origins = list(dict.fromkeys(origin.rstrip("/") for origin in origins if origin.strip()))

_CORS_ORIGIN_REGEX = re.compile(r"https://.*\.ngrok-free\.app")
_ALLOW_DEV_TUNNELS = settings.app_env.strip().lower() in {"dev", "development", "local", "test"}


def _apply_cors(request: Request, response: JSONResponse) -> JSONResponse:
    """Дублирует логику CORSMiddleware для ответов из exception handler (иначе 500 без CORS)."""
    origin = request.headers.get("origin")
    if not origin:
        return response
    allowed = origin in origins or (
        _ALLOW_DEV_TUNNELS and bool(_CORS_ORIGIN_REGEX.fullmatch(origin))
    )
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def _is_b2b_path(path: str) -> bool:
    return path.startswith(
        (
            "/api/auth",
            "/api/buyer",
            "/api/seller",
            "/api/admin",
            "/api/internal/bots",
            "/api/assets",
            "/webhooks",
        )
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.ngrok-free\.app" if _ALLOW_DEV_TUNNELS else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if not _is_b2b_path(request.url.path):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": jsonable_encoder(exc.detail)},
            headers=exc.headers,
        )
    message = exc.detail if isinstance(exc.detail, str) else "Запрос не выполнен"
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": message,
                "requestId": getattr(request.state, "request_id", None),
            }
        },
        headers=exc.headers,
    )
    return _apply_cors(request, response)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    if not _is_b2b_path(request.url.path):
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})
    details = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "type": str(error.get("type", "validation_error")),
            "message": str(error.get("msg", "Некорректное значение")),
        }
        for error in exc.errors()
    ]
    response = JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Проверьте заполнение полей",
                "details": details,
                "requestId": getattr(request.state, "request_id", None),
            }
        },
    )
    return _apply_cors(request, response)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    response = JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error",
                "requestId": getattr(request.state, "request_id", None),
            }
        },
    )
    return _apply_cors(request, response)


app.include_router(auth.router)
app.include_router(activity.router)
app.include_router(users.router)
app.include_router(restaurants.router)
app.include_router(meals.router)
app.include_router(meal_assets.router)
app.include_router(restaurant_assets.router)
app.include_router(orders.router)
app.include_router(order_positions.router)
app.include_router(staff.router)
app.include_router(restaurant_staff.router)
app.include_router(couriers.router)
app.include_router(courier_panel.router)
app.include_router(subscription_logs.router)
app.include_router(admin.router)
app.include_router(support_internal.router)
app.include_router(b2b_auth.router)
app.include_router(b2b_buyer.router)
app.include_router(b2b_seller.router)
app.include_router(b2b_admin.router)
app.include_router(b2b_internal.router)
app.include_router(b2b_assets.router)
app.include_router(b2b_webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
