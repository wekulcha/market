from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services import staff_access
from app.services.object_storage import (
    ALLOWED_IMAGE_TYPES,
    ObjectStorageNotConfiguredError,
    ObjectStorageService,
    get_object_storage,
)
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/restaurant-assets", tags=["restaurant-assets"])


@router.post("/upload")
async def upload(
    restaurantId: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    settings = get_settings()
    tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
    if not tg:
        raise HTTPException(401, "Invalid Telegram init data")
    result = await db.execute(select(User).where(User.id == tg["id"]))
    actor = result.scalars().first()
    if not actor:
        raise HTTPException(403, "Unknown user")
    await staff_access.require_can_edit_menu(db, actor.id, restaurantId)

    if not file.size:
        raise HTTPException(400, "Empty file")
    ct = (file.content_type or "").lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only JPG, JPEG, PNG allowed")

    try:
        storage = get_object_storage()
    except ObjectStorageNotConfiguredError as exc:
        raise HTTPException(500, str(exc)) from exc

    ct = storage.normalize_content_type(ct)
    key = storage.build_asset_key("restaurants", restaurantId, ct)
    url = await storage.upload_file(file.file, key=key, content_type=ct)
    return {"path": url}


@router.get("/{filename}")
async def serve(filename: str):
    try:
        ObjectStorageService.ensure_valid_filename(filename)
    except ValueError:
        raise HTTPException(400, "Invalid filename")

    try:
        storage = get_object_storage()
    except ObjectStorageNotConfiguredError:
        storage = None

    settings = get_settings()
    dir_path = Path(settings.uploads_dir, "restaurants").resolve()
    file_path = (dir_path / filename).resolve()
    if not str(file_path).startswith(str(dir_path)) or not file_path.is_file():
        if storage:
            key = storage.build_legacy_key("restaurants", filename)
            if await storage.object_exists(key):
                return RedirectResponse(storage.public_url(key), status_code=307)
        raise HTTPException(404)

    media_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000"},
    )
