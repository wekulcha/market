from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    admin,
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    settings = get_settings()
    logger.info("Kulcha Market backend started (user_bot_token configured: %s, admin_bot_token configured: %s)",
                bool(settings.user_bot_token), bool(settings.admin_bot_token))
    yield


app = FastAPI(title="Kulcha Market backend", version="2.0.0", lifespan=lifespan)

settings = get_settings()

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "https://app.wekulcha.ru",
    "https://admin.wekulcha.online",
    "https://superadmin.wekulcha.online",
    *settings.cors_additional_origins,
]

_CORS_ORIGIN_REGEX = re.compile(r"https://.*\.ngrok-free\.app")


def _apply_cors(request: Request, response: JSONResponse) -> JSONResponse:
    """Дублирует логику CORSMiddleware для ответов из exception handler (иначе 500 без CORS)."""
    origin = request.headers.get("origin")
    if not origin:
        return response
    allowed = origin in origins or bool(_CORS_ORIGIN_REGEX.fullmatch(origin))
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.ngrok-free\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return _apply_cors(request, response)


app.include_router(auth.router)
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


@app.get("/health")
async def health():
    return {"status": "ok"}
