# KULCHA B2B production checklist

Every item requires evidence; an unchecked critical item blocks production.

## Secrets and access

- [ ] All previously tracked Telegram tokens were revoked and rotated.
- [ ] Git history/container registry cleanup was coordinated and completed.
- [ ] `BUYER_BOT_TOKEN`, `SELLER_BOT_TOKEN`, `ADMIN_BOT_TOKEN` are independent.
- [ ] `B2B_INTERNAL_API_SECRET`, auth and payment secrets are random/independent.
- [ ] `ADMIN_TELEGRAM_IDS` is non-empty and contains only current operators.
- [ ] Bootstrap superadmin has backend role mapping; env allowlist is defense in depth.
- [ ] No mock payment is reachable when `APP_ENV=production`.
- [ ] Secret scan covers Git history and built images.

## Database and release

- [ ] Clean database upgrades to Alembic head.
- [ ] Pre-release backup exists, checksum verified, restore test passed.
- [ ] Migration and prior application version are backward-compatible.
- [ ] Rollback owner, approved revision and maintenance procedure are recorded.
- [ ] PostgreSQL volume/off-host backup retention and encryption are configured.
- [ ] Object storage versioning/retention and restore are tested.

## Telegram

- [ ] Bot usernames and Mini App URLs match `PUBLIC_BASE_URL`.
- [ ] Buyer invite replay/expiry/revocation tests pass.
- [ ] Foreign/forwarded Telegram contacts are rejected.
- [ ] Admin command and every callback fail closed for non-allowlisted IDs.
- [ ] Dangerous quick actions require confirmation and create audit events.
- [ ] Exactly one update consumer exists per token.
- [ ] Production uses webhook mode with three unique secret headers.
- [ ] Caddy routes each Telegram webhook to its matching bot, not the backend/SPA.
- [ ] Buyer webhook FSM uses authenticated/TLS Redis and survives bot restart.
- [ ] All bot adapters deduplicate successful `update_id` values; failure is retried
      and concurrent delivery is never acknowledged before completion.
- [ ] If polling is temporarily accepted: decision/owner and webhook migration date are recorded.

## Edge and web

- [ ] `B2B_DOMAIN` DNS points to the one gateway that owns ports 80/443.
- [ ] Shared gateway is attached to `kulcha-market_default`.
- [ ] Final Caddy config validates before reload.
- [ ] `/api` and payment webhooks reach backend, while exact Telegram webhooks reach
      matching bots; none reaches SPA fallback.
- [ ] `/health`, `/ready` and `/metrics` reach backend; metrics access is restricted
      according to the monitoring network policy.
- [ ] Direct nested `/buyer/*`, `/seller/*`, `/admin/*` routes return the SPA.
- [ ] `/b2b-static/*` loads B2B assets without colliding with legacy `/assets`.
- [ ] TLS renewal, HSTS and security headers are verified.
- [ ] Production CORS has only explicit trusted origins; tunnel regex is disabled.
- [ ] CSP/frame policy is tested in native Telegram and Telegram Web.

## Domain safety

- [ ] Buyer responses never expose acquisition price or seller contacts.
- [ ] Seller responses never expose buyer contacts, markup or margin.
- [ ] Admin/superadmin endpoints enforce backend RBAC and IDOR tests.
- [ ] Price/order snapshots and Decimal money tests pass.
- [ ] Concurrent last-stock reservation test passes; stock never becomes negative.
- [ ] Cancellation/expiry returns stock exactly once.
- [ ] Payment and Telegram webhook idempotency tests pass.
- [ ] `DELIVERY_PROVIDER` is explicitly approved; any non-`manual` adapter has
      contract/webhook/idempotency/rollback tests and production credentials.

## Operations and observability

- [ ] Backend and panel healthchecks are green.
- [ ] Database-aware readiness is monitored.
- [ ] Notification worker processes outbox, retries transient failures and records final failure.
- [ ] Redis memory/eviction/availability, buyer FSM loss and webhook dedup failures are monitored.
- [ ] Failed notification replay is audited and idempotent.
- [ ] Alerts cover API/webhook/notification errors, restart loops, DB disk and backup age.
- [ ] Logs have correlation IDs and exclude PII/secrets/initData/payment bodies.
- [ ] Log retention and incident contacts are configured.

## Final validation commands

```bash
docker compose config --quiet
docker compose --profile b2b config --quiet
docker compose --profile b2b build
docker compose exec -T backend alembic current
docker compose --profile b2b ps
docker exec kulcha-gateway caddy validate --config /etc/caddy/Caddyfile
```

Record actual formatter, lint, typecheck, backend/frontend test and E2E output in the
release evidence. Never mark a command passed if it was not run.
