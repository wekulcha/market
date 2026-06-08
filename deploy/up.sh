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

shared_gateway="$(printf '%s' "${MARKET_SHARED_GATEWAY:-}" | tr '[:upper:]' '[:lower:]')"
app_services=(
  postgres
  backend
  user_panel
  admin_panel
  superadmin_panel
  user_bot
  admin_bot
  superadmin_bot
)

docker compose up -d --build postgres backend

# Keep DB schema in sync with models (e.g. restaurant.image_link, orders.user_telegram_notify_message_id).
# Requires backend image with Alembic; uses MARKET_DATABASE_URL from compose.
echo "Applying database migrations..."
docker compose exec -T backend alembic upgrade head

if [[ "$shared_gateway" == "1" || "$shared_gateway" == "true" || "$shared_gateway" == "yes" ]]; then
  echo "MARKET_SHARED_GATEWAY is enabled; skipping kulcha-market-gateway."
  docker compose stop gateway >/dev/null 2>&1 || true
  docker compose rm -f gateway >/dev/null 2>&1 || true
  docker compose up -d --build "${app_services[@]}"
else
  docker compose up -d --build
fi

docker compose ps
