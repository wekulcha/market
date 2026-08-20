from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.services.object_storage import ObjectStorageNotConfiguredError, get_object_storage


MAX_IMAGE_PIXELS = 40_000_000


@dataclass(frozen=True)
class StoredImage:
    storage_key: str
    public_url: str
    mime_type: str
    size_bytes: int
    width: int
    height: int


def _optimise(raw: bytes, declared_type: str) -> tuple[bytes, bytes, str, int, int, str]:
    if declared_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(415, "Разрешены только JPEG и PNG")
    is_jpeg = raw.startswith(b"\xff\xd8\xff")
    is_png = raw.startswith(b"\x89PNG\r\n\x1a\n")
    if not (is_jpeg or is_png):
        raise HTTPException(415, "Содержимое файла не соответствует JPEG/PNG")
    if declared_type in {"image/jpeg", "image/jpg"} and not is_jpeg:
        raise HTTPException(415, "MIME type не соответствует JPEG-содержимому")
    if declared_type == "image/png" and not is_png:
        raise HTTPException(415, "MIME type не соответствует PNG-содержимому")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(413, "Слишком большое разрешение изображения")
            source.load()
            image = ImageOps.exif_transpose(source)
            mime = "image/png" if is_png else "image/jpeg"
            extension = ".png" if is_png else ".jpg"
            if mime == "image/jpeg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            output = io.BytesIO()
            save_args = {"optimize": True}
            if mime == "image/jpeg":
                save_args["quality"] = 88
            image.save(output, format="PNG" if is_png else "JPEG", **save_args)
            thumbnail = image.copy()
            thumbnail.thumbnail((640, 640))
            thumb_output = io.BytesIO()
            thumbnail.save(thumb_output, format="PNG" if is_png else "JPEG", **save_args)
            return (
                output.getvalue(),
                thumb_output.getvalue(),
                mime,
                image.width,
                image.height,
                extension,
            )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(415, "Повреждённое или неподдерживаемое изображение") from exc


async def store_offer_image(file: UploadFile, offer_id: UUID, revision_id: UUID) -> StoredImage:
    settings = get_settings()
    raw = await file.read(settings.offer_image_max_bytes + 1)
    if not raw:
        raise HTTPException(400, "Пустой файл")
    if len(raw) > settings.offer_image_max_bytes:
        raise HTTPException(413, "Изображение превышает допустимый размер")
    optimised, thumbnail, mime, width, height, extension = await asyncio.to_thread(
        _optimise,
        raw,
        (file.content_type or "").lower(),
    )
    image_id = uuid4()
    key = f"b2b/offers/{offer_id}/{revision_id}/{image_id}{extension}"
    thumb_key = f"b2b/offers/{offer_id}/{revision_id}/{image_id}-thumb{extension}"
    if settings.object_storage_provider.lower() == "local":
        root = Path(settings.uploads_dir).resolve()
        image_path = (root / key).resolve()
        thumb_path = (root / thumb_key).resolve()
        if root not in image_path.parents or root not in thumb_path.parents:
            raise HTTPException(400, "Некорректный путь изображения")

        def _write() -> None:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(optimised)
            thumb_path.write_bytes(thumbnail)

        await asyncio.to_thread(_write)
        public_url = f"{settings.public_base_url.rstrip('/')}/api/assets/{key}"
    else:
        try:
            storage = get_object_storage()
        except ObjectStorageNotConfiguredError as exc:
            raise HTTPException(503, str(exc)) from exc
        public_url = await storage.upload_file(io.BytesIO(optimised), key=key, content_type=mime)
        await storage.upload_file(io.BytesIO(thumbnail), key=thumb_key, content_type=mime)
    return StoredImage(
        storage_key=key,
        public_url=public_url,
        mime_type=mime,
        size_bytes=len(optimised),
        width=width,
        height=height,
    )
