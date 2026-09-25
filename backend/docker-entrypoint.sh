#!/bin/sh
# Migrate on every start (idempotent), seed the first admin if asked, then serve.
# --no-access-log: the app writes its own PHI-free access log; uvicorn's would include query strings.
set -eu

alembic upgrade head

if [ -n "${SEED_ADMIN_EMAIL:-}" ] && [ -n "${SEED_ADMIN_PASSWORD:-}" ]; then
    python -m app.db.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers
