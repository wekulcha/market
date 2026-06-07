#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Fill secrets in .env and run ./deploy/up.sh again."
  exit 1
fi

docker compose up -d --build postgres backend

# Keep DB schema in sync with models (e.g. restaurant.image_link, orders.user_telegram_notify_message_id).
# Requires backend image with Alembic; uses MARKET_DATABASE_URL from compose.
echo "Applying database migrations..."
docker compose exec -T backend alembic upgrade head

docker compose up -d --build

docker compose ps
