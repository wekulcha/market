# B2B release rollback

## Principles

- Prefer application rollback with a forward-compatible schema.
- Never assume `alembic downgrade` is data-safe.
- Preserve notification idempotency/outbox rows across rollback.
- Back up before release and before any schema reversal.

## Application rollback

1. Record current image IDs, Git revision and Alembic revision.
2. Stop new B2B traffic or enable maintenance mode at the edge.
3. Check whether the previous application supports the current schema.
4. Build/deploy the previously approved Git revision or immutable image tag.
5. Keep `notification_worker` stopped until its code/schema compatibility is known.
6. Run smoke checks, then resume worker and traffic.

Useful evidence commands:

```bash
git rev-parse HEAD
docker compose images
docker compose exec -T backend alembic current
docker compose --profile b2b ps
```

Do not use `git reset --hard` in a dirty workspace. Check out the approved revision
in a separate deployment directory/worktree or deploy immutable registry images.

## Schema rollback

Only use an Alembic downgrade when the migration has a reviewed downgrade path and
a restore test proves it preserves required data:

```bash
docker compose stop backend notification_worker buyer_bot seller_bot b2b_admin_bot
docker compose run --rm backend alembic downgrade <reviewed_revision>
```

If a migration drops/transforms data, restore the pre-release backup instead. Follow
`backup-restore.md`, reconcile any orders/payments created after the backup, and keep
an incident audit trail.

## Post-rollback verification

- `/buyer`, `/seller`, `/admin` load without asset errors;
- `/api` is never served by SPA;
- login/roles and privacy projections work;
- no negative inventory or stuck reservation;
- payment/webhook idempotency remains intact;
- worker does not duplicate already-sent notifications;
- Caddy and container logs contain no new 5xx loop.

