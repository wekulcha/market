# B2B security runbook

## Immediate secret incident response

The repository audit found real-format Telegram tokens in tracked legacy files.
Values are deliberately omitted here.

Affected Market paths include:

- `bots/admin_bot/.env`;
- `bots/user_bot/.env`;
- `bots/superadmin_bot/.env`;
- `scripts/kulcha-dev.env`.

The sibling Kulcha repository also contained a channel-subscriptions bot token in
tracked example/config/Compose files. Treat every exposed token as compromised even
if it appears unused or has an old variable prefix.

Required order:

1. Revoke/rotate affected bots in BotFather immediately.
2. Replace production secret-store values; restart only the intended bot consumers.
3. Confirm old tokens can no longer call `getMe`.
4. Remove secret files from tracking while preserving required local copies.
5. Coordinate a history rewrite with every collaborator and remote owner.
6. Invalidate old clones/build caches and scan container registries.

Safe inventory commands that show file names, not values:

```bash
git ls-files | rg '(^|/)\.env$|scripts/.*-dev\.env$'
git grep -IlE '[0-9]{8,12}:[A-Za-z0-9_-]{30,50}' -- ':!*.pyc'
```

After rotation and a local backup, stop tracking without deleting working copies:

```bash
git rm --cached bots/admin_bot/.env bots/user_bot/.env bots/superadmin_bot/.env
git rm --cached scripts/kulcha-dev.env
```

History rewriting is disruptive and must be approved/coordinated. One possible tool
is `git filter-repo`; do not run it casually on a shared branch:

```bash
git filter-repo \
  --path bots/admin_bot/.env \
  --path bots/user_bot/.env \
  --path bots/superadmin_bot/.env \
  --path scripts/kulcha-dev.env \
  --invert-paths
```

Rotation is still mandatory: history cleanup cannot retract a token already copied.

## Bot boundaries

- Buyer activation requires a personal invite and backend token validation.
- Buyer/seller contact handlers reject forwarded/foreign contacts by requiring
  `contact.user_id == from_user.id`.
- Bot-to-backend calls use a dedicated `B2B_INTERNAL_API_SECRET` header. Never place
  this secret in callback data, URLs or frontend bundles.
- Admin bot starts only with a non-empty `ADMIN_TELEGRAM_IDS`; every command and
  callback checks the actor. Backend RBAC remains authoritative.
- Offer mutations require an explicit confirmation callback and backend audit actor.
- Dangerous action callback data contains only offer ID and action, never contacts,
  prices or secrets.

## Telegram and webhooks

Local B2B bot containers default to long polling and delete an existing webhook on
startup. Production uses `BOT_MODE=webhook`; do not run both modes concurrently.

Webhook mode:

- use a separate random secret per bot;
- sets Telegram `secret_token`; aiogram checks
  `X-Telegram-Bot-Api-Secret-Token` before dispatch;
- routes exact role paths to bot containers, while payment webhooks go to backend;
- dispatches in the HTTP request and acknowledges only after handler completion;
- deduplicates successful updates for seven days and uses a short Redis lock so a
  concurrent duplicate gets a retryable error instead of a premature success;
- keeps buyer invite/contact FSM in Redis rather than process memory;
- rate-limit endpoints and never log update/contact bodies;
- rotate webhook secrets independently from bot tokens.

For production Redis require authentication/TLS, network ACLs, encryption/backup
policy and eviction settings that do not discard FSM/dedup keys. Redis contains
temporary invite/contact state and Telegram update IDs, and must never contain raw
bot tokens or update/contact bodies.

## Web security

- Caddy routes `/api` and `/webhooks` before SPA fallback.
- HSTS, nosniff, referrer and permissions policies are enabled for B2B.
- `X-Frame-Options: DENY` is intentionally not set because Telegram Web Apps need
  compatible embedding/webview behavior. Add a tested CSP/`frame-ancestors` policy
  before production rather than copying a desktop-only policy.
- CORS must contain only the real B2B/legacy origins in production; remove generic
  tunnel origin patterns.
- Telegram initData validation must enforce signature and `auth_date` max age.
- Payment webhook signatures, idempotency keys and raw-body verification are backend
  responsibilities; Telegram update dedup is enforced by bot adapters. Mock payment
  must be rejected in production.

## Production secret rules

- Use a secret manager or protected deployment environment, not tracked `.env`.
- Use independent values for legacy internal secret, B2B internal secret, auth secret,
  payment webhook secret and each Telegram token/webhook secret.
- Empty/default/change-me values must fail startup in production.
- Restrict Docker/socket/host access; tokens in container env are sensitive.
- Scan Git and built images with an approved secret scanner on every release.
