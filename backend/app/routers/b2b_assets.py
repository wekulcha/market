from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings


router = APIRouter(prefix="/api/assets", tags=["b2b-assets"])


@router.get("/{asset_path:path}")
async def local_asset(asset_path: str):
    settings = get_settings()
    if settings.object_storage_provider.lower() != "local":
        raise HTTPException(404, "Not found")
    root = Path(settings.uploads_dir).resolve()
    path = (root / asset_path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "Not found")
    suffix = path.suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
