# CareConnect runbook

Operational notes for running, upgrading, backing up and restoring the
production-like stack. Product behavior lives in `spec.md`; the API in
`openapi.yaml`.

## 1. Run the stack

```bash
export POSTGRES_PASSWORD='<strong password>'
export JWT_SECRET="$(openssl rand -base64 48)"       # >= 32 chars, required
export SEED_ADMIN_EMAIL='admin@your-clinic.example'   # first start only
export SEED_ADMIN_PASSWORD='<>= 12 chars>'
export GEMINI_API_KEY='<key>'                         # optional; AI features return 503 without it
export CORS_ALLOWED_ORIGINS=''                        # empty: the web container proxies /api same-origin
docker compose --profile prod up -d --build
```

The web container (nginx) serves the app on `WEB_PORT` (default 8080) and
proxies `/api/` to the API. Terminate TLS in front of it (load balancer or
reverse proxy); the app does not speak HTTPS itself.

The API container **migrates the database on every start**
(`alembic upgrade head`), seeds the admin when `SEED_ADMIN_*` are set
(idempotent; an existing user is never modified), then serves. It refuses
to start when `ENV=production` and `JWT_SECRET` is missing or short.

Remove `SEED_ADMIN_PASSWORD` from the environment after the first start.

## 2. Health and logs

- Liveness: `GET /api/v1/health` -> `{"status":"ok"}` (also the container
  healthcheck).
- Logs are one JSON line per request on stdout:
  `{"requestId","method","path","status","durationMs"}`. Query strings,
  bodies, names, phones, symptoms and notes are never logged. Every response
  carries `X-Request-ID`; quote it when reporting a problem. The API runs
  with `--no-access-log` for this reason: uvicorn's own access log would
  include query strings (patient phone lookups).
- Unexpected errors are logged by type only.

## 3. Upgrade

1. Take a backup (section 4).
2. `git pull && docker compose --profile prod up -d --build`.
3. The API applies pending migrations at startup. Check
   `docker compose logs api` for `Running upgrade` lines and a healthy
   container.

Rollback: restore the backup and redeploy the previous image. Migrations
have `downgrade()` implementations, but the backup is the safe path for
production data.

## 4. Backup and restore

Backup (custom format, safe while the app runs):

```bash
docker compose exec -T db pg_dump -U careconnect -Fc careconnect > careconnect-$(date +%F).dump
```

Restore into an empty database (stop the API first):

```bash
docker compose --profile prod stop api web
docker compose exec -T db dropdb -U careconnect --if-exists careconnect
docker compose exec -T db createdb -U careconnect careconnect
docker compose exec -T db pg_restore -U careconnect -d careconnect --no-owner < careconnect-2026-01-01.dump
docker compose --profile prod up -d api web
```

Backups contain patient data: encrypt them at rest, restrict access, and keep
them no longer than the clinic's retention policy. Test a restore regularly.

## 5. Secrets and access

- Rotate `JWT_SECRET` to sign everyone out (all tokens become invalid).
- Deactivating a staff user ends their live session immediately (roles and
  the active flag are re-read from the database on every request).
- Password resets are front-desk actions and are audited (Audit log page).

## 6. Known limits (single-process design)

- The login rate limiter is in memory: run **one** API process/replica, or
  move the limiter to shared storage before scaling out.
- Request size is limited by `Content-Length` (`MAX_REQUEST_BYTES`, default
  1 MB) and again by nginx (`client_max_body_size 1m`).
