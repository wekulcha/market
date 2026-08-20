# PostgreSQL backup and restore

These commands operate on the shared Market/B2B PostgreSQL database. Run from
`market/`, use encrypted restricted storage, and test restoration regularly.

## Backup

Create a custom-format logical backup using the credentials already present inside
the PostgreSQL container:

```bash
mkdir -p backups
docker compose exec -T postgres sh -c \
  'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --no-owner' \
  > "backups/kulcha-market-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Protect the file:

```bash
chmod 600 backups/*.dump
sha256sum backups/*.dump
```

`backups/` must remain outside Git and should be copied to encrypted off-host
storage with retention. Object storage images require a separate versioning/export
policy; PostgreSQL backup does not contain object bytes.

Redis stores temporary buyer FSM plus bot webhook dedup/lock keys. Its Compose AOF
volume helps local restarts but is not a replacement for PostgreSQL backup. After
Redis loss an unregistered buyer reopens the same invite deep link; backend
invitation state stays authoritative. Telegram may redeliver updates whose seven-day
dedup markers were lost, so backend mutations must remain idempotent and audited.
Define a managed-Redis backup/retention policy separately if the production recovery
objective requires preserving in-progress conversations and dedup history.

## Non-destructive restore test

Choose one dump explicitly; do not use an unresolved wildcard in automation:

```bash
export B2B_RESTORE_FILE="$PWD/backups/kulcha-market-YYYYMMDDTHHMMSSZ.dump"
test -f "$B2B_RESTORE_FILE"
docker compose exec -T postgres sh -c \
  'dropdb --if-exists --username="$POSTGRES_USER" kulcha_market_restore_test && createdb --username="$POSTGRES_USER" kulcha_market_restore_test'
docker compose exec -T postgres sh -c \
  'pg_restore --username="$POSTGRES_USER" --dbname=kulcha_market_restore_test --no-owner --exit-on-error' \
  < "$B2B_RESTORE_FILE"
docker compose exec -T postgres sh -c \
  'psql --username="$POSTGRES_USER" --dbname=kulcha_market_restore_test --command="select count(*) from alembic_version;"'
```

Validate representative counts, foreign keys, B2B orders/reservations, audit events
and the recorded Alembic revision. Drop the test database only after validation.

## In-place disaster restore

This is destructive. Obtain explicit approval, stop writers and preserve the current
database as a final backup first.

```bash
docker compose stop backend notification_worker buyer_bot seller_bot b2b_admin_bot
docker compose exec -T postgres sh -c \
  'dropdb --if-exists --force --username="$POSTGRES_USER" "$POSTGRES_DB" && createdb --username="$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T postgres sh -c \
  'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --no-owner --exit-on-error' \
  < "$B2B_RESTORE_FILE"
docker compose up -d backend
docker compose exec -T backend alembic current
docker compose --profile b2b up -d
```

After restore, verify auth, one read-only query per role, outbox state and object URLs
before reopening traffic. A database restore does not rotate compromised credentials.
