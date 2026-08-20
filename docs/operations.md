# B2B operations runbook

Run commands from `market/`. Never print `.env`, tokens, contacts or raw Telegram
`initData` into tickets or shared logs.

## Pre-deploy checks

```bash
git status --short
docker compose config --quiet
docker compose --profile b2b config --quiet
bash -n deploy/up.sh deploy/down.sh
```

Review pending migrations before applying:

```bash
docker compose run --rm backend alembic current
docker compose run --rm backend alembic heads
docker compose run --rm backend alembic history --verbose
```

Take and verify a backup using `backup-restore.md`, then:

```bash
docker compose up -d --build postgres backend
docker compose exec -T backend alembic upgrade head
docker compose --profile b2b up -d --build
docker compose --profile b2b ps
```

The release script in `deploy/up.sh` is legacy-aware, but operators must explicitly
use the `b2b` profile for the new panel, bots and worker.

## Health and readiness

Compose checks backend `/health` and the panel static `/health`. The current backend
health endpoint proves process liveness, not full dependency readiness. Treat a
successful database query and a processing worker as additional readiness signals.

```bash
docker compose ps
docker compose exec -T backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)"
docker compose exec -T b2b_panel wget -qO- http://127.0.0.1/health
docker compose exec -T buyer_bot python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/health').status)"
```

Последняя команда применима только к webhook mode; в polling mode HTTP listener
намеренно отсутствует, а Compose healthcheck полагается на состояние bot container.
Webhook health возвращает `503`, если Redis dedup/FSM недоступен. Аналогично
проверяйте seller/admin на портах 8082/8083.

For the public edge:

```bash
curl --fail --silent --show-error "${PUBLIC_BASE_URL}/api/health"
curl --fail --silent --show-error "${PUBLIC_BASE_URL}/ready"
curl --fail --silent --show-error "${PUBLIC_BASE_URL}/buyer" >/dev/null
```

Caddy явно переписывает публичный `/api/health` в backend `/health`; `/health`,
`/ready` и `/metrics` также идут напрямую в backend, поэтому эти запросы не попадают
в SPA fallback. Ограничьте публичный доступ к `/metrics` на внешнем edge/ACL, если
метрики собираются из доверенной сети.

## Logs

```bash
docker compose logs --since=15m backend notification_worker
docker compose logs --since=15m buyer_bot seller_bot b2b_admin_bot
docker compose logs --since=15m gateway b2b_panel
```

Expected worker lifecycle messages include `notification_worker_started`,
`notification_batch_processed` and `notification_worker_iteration_failed`. Alert on:

- backend or worker restart loops;
- growing pending/failed notification count;
- webhook 4xx/5xx spikes;
- reservations past `expires_at` that remain active;
- Telegram 429/5xx and exhausted attempts;
- database volume usage and backup age.

Logs must contain correlation/event IDs and entity IDs, not phones, token values,
full initData, payment payloads or message bodies.

## Notification worker

The worker is a single safe process initially. Outbox claiming must remain guarded by
database locking/idempotency before horizontal scaling.

```bash
docker compose --profile b2b ps notification_worker
docker compose restart notification_worker
```

Restarting is safe because jobs and attempt counters live in PostgreSQL. Do not
manually mark a job sent. Requeue/retry only through an audited backend/admin command;
retain the original idempotency key and bounded max attempts.

## Migrations

- Deploy additive/backward-compatible schema before code that requires it.
- Never autogenerate and apply a migration directly on production.
- Verify a clean-db upgrade in CI/local Compose.
- Record the Alembic head in the release notes.
- A destructive downgrade is not a default rollback strategy; see `rollback.md`.

## Caddy shared gateway

Validate the final, merged config inside the gateway container:

```bash
docker exec kulcha-gateway caddy validate --config /etc/caddy/Caddyfile
docker exec kulcha-gateway caddy reload --config /etc/caddy/Caddyfile
```

Ensure the container is attached to `kulcha-market_default`. `/api` and `/webhooks`
handlers must precede any SPA fallback, `/b2b-static/*` must use `handle_path`, and
three exact Telegram webhook paths must route to bots before the generic payment
webhook handler routes to backend. Exact `/health`, `/ready`, `/metrics` routes must
also reach backend before the SPA fallback.

## Smoke and load harnesses

`scripts/b2b_e2e_smoke.py` is intentionally destructive and requires an explicit
mutation flag. It is not a production probe. The Locust scenario also writes orders;
use unique buyer credentials and an isolated staging database. Exact commands and
credential schema are in `B2B_README.md`. Archive only aggregate results, never the
credential file, JWTs, initData, contacts or response bodies containing PII.
