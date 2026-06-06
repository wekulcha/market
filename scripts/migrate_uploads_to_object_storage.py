#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.object_storage import (  # noqa: E402
    ObjectStorageNotConfiguredError,
    get_object_storage,
)


def resolve_uploads_dir(raw_value: str) -> Path:
    raw_path = Path(raw_value)
    candidates = [raw_path]
    if not raw_path.is_absolute():
        candidates.extend((ROOT / raw_path, ROOT / "backend" / raw_path))
    candidates.append(ROOT / "backend" / "uploads")

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def migrate_folder(uploads_dir: Path, folder: str, *, skip_existing: bool) -> tuple[int, int]:
    storage = get_object_storage()
    source_dir = uploads_dir / folder
    if not source_dir.exists():
        print(f"[skip] {source_dir} does not exist")
        return 0, 0

    uploaded = 0
    skipped = 0
    for path in sorted(source_dir.iterdir()):
        if not path.is_file():
            continue

        key = storage.build_legacy_key(folder, path.name)
        if skip_existing and asyncio.run(storage.object_exists(key)):
            skipped += 1
            print(f"[skip] s3://{storage.bucket}/{key} already exists")
            continue

        content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        with path.open("rb") as file_obj:
            asyncio.run(storage.upload_file(file_obj, key=key, content_type=content_type))
        uploaded += 1
        print(f"[ok] {path} -> {storage.public_url(key)}")

    return uploaded, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy backend/uploads assets to Yandex Object Storage legacy prefixes."
    )
    parser.add_argument(
        "--uploads-dir",
        default=None,
        help="Path to legacy uploads directory. Defaults to KULCHA_UPLOADS_DIR or backend/uploads if present.",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-upload files even if the target object already exists.",
    )
    args = parser.parse_args()

    settings = get_settings()
    uploads_dir = resolve_uploads_dir(args.uploads_dir or settings.uploads_dir)
    print(f"Using uploads dir: {uploads_dir}")

    try:
        get_object_storage()
    except ObjectStorageNotConfiguredError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    total_uploaded = 0
    total_skipped = 0
    for folder in ("meals", "restaurants"):
        uploaded, skipped = migrate_folder(
            uploads_dir,
            folder,
            skip_existing=not args.no_skip_existing,
        )
        total_uploaded += uploaded
        total_skipped += skipped

    print(f"Done. Uploaded: {total_uploaded}, skipped: {total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
