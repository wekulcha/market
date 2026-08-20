# ADR-0001: additive KULCHA B2B runtime

- Status: accepted
- Date: 2026-08-20

## Context

The repository already contains a FastAPI/PostgreSQL backend, three legacy React
panels, aiogram bots and a Caddy edge. KULCHA B2B needs buyer, seller and admin
surfaces without breaking the existing Market launch or duplicating business logic.

## Decision

1. Extend `market/`; do not create a second backend or database.
2. Keep B2B domain code additive and expose it through `/api`.
3. Build one `b2b_panel` SPA with absolute `/buyer`, `/seller`, `/admin` routes.
4. Namespace its static bundles under `/b2b-static/` to coexist with legacy assets.
5. Run three thin aiogram adapters: polling for local/dev, HTTPS webhook for
   production. They call backend internal endpoints using `X-B2B-Internal-Secret`.
   Webhook secret headers are verified by aiogram before update dispatch.
6. Enforce buyer invite and all RBAC in backend. Bot-side checks are defense in depth.
7. Use a PostgreSQL notification outbox and dedicated worker. A domain mutation and
   its event are committed atomically; retry state survives process restarts.
8. Add B2B runtime services behind Docker Compose profile `b2b`; legacy default
   service selection remains unchanged.
9. Route `/api` and `/webhooks` before the SPA in Caddy. Keep bot tokens and IDs in
   environment/secrets only.
10. Use RedisStorage for buyer invite/contact FSM in webhook mode. Seller/admin have
    no conversational state; the PostgreSQL outbox remains the notification source.
11. Process webhook updates in the HTTP request, acknowledge only after successful
    dispatch and use Redis per-role `update_id` done/lock keys for retry-safe dedup.
12. Keep delivery provider-configurable with `manual` as the MVP default. External
    delivery integrations implement the backend provider boundary without changing
    order state ownership or exposing contacts to buyer/seller projections.

## Consequences

- Legacy deploys can continue without the profile.
- A B2B deploy still migrates the shared database and therefore requires a backup,
  reviewed Alembic upgrade and backward-compatible rollout.
- Polling intentionally calls `deleteWebhook`; webhook mode calls `setWebhook` with
  a unique secret. The modes must never run concurrently for one token.
- A shared public `app.wekulcha.ru` gateway must merge B2B handlers into its existing
  site block. Running two independent Caddy instances on ports 80/443 is unsupported.
- PostgreSQL is the source of truth for delivery attempts. Redis remains optional
  for notification delivery but is required for all webhook adapters' update dedup;
  buyer additionally requires it for FSM.

## Rejected alternatives

- A second B2B database: creates cross-system order/user consistency problems.
- Copying three independent backend clients into bot folders: creates auth and retry
  drift; `bots/b2b_common` is used instead.
- Reusing the legacy admin/superadmin bot unchanged: its access model and restaurant
  actions do not match B2B roles or moderation.
- Sending notifications only with FastAPI `BackgroundTasks`: jobs are lost on crash
  and cannot provide bounded retry/final-failure audit.
