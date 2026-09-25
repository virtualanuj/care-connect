# CareConnect

Clinic scheduling and AI-assisted triage for front-desk staff and doctors.
Design docs live in `docs/` (read `CLAUDE.md` for the order); the
milestone task list is `docs/plan.md`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically)
- Node.js 22+ and npm
- Docker (for PostgreSQL)

## Setup

```bash
# Database
docker compose up -d db --wait

# Backend
cd backend
cp .env.example .env          # local settings; never commit secrets
uv sync
uv run alembic upgrade head
# First front-desk admin (set SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD in .env, >= 12 chars)
uv run python -m app.db.seed  # with ENV=dev also adds sample data: General Medicine, a doctor
#   (doctor@clinic.test / "dev doctor passphrase"), Mon-Fri 09:00-12:00 availability, sample patients
uv run uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health

# Frontend (second terminal)
cd frontend
npm ci
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

## Tests and checks

```bash
# Backend (from backend/)
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest tests/unit          # no network, no database
uv run pytest tests/contract      # responses validated against docs/openapi.yaml
uv run pytest tests/integration   # needs `docker compose up -d db`
uv run pytest                     # everything

# Frontend (from frontend/)
npm run lint && npm run typecheck && npm test && npm run build
npm run gen:api                   # regenerate src/api/schema.d.ts from docs/openapi.yaml
npm run e2e                       # Playwright; starts API on :8100 and web on :5273, resets
                                  # the LOCAL database (needs `docker compose up -d db`, migrated)
```

## Layout

```
docs/                 intent, spec, openapi.yaml (source of truth), standards, review, plan
backend/app/          api (routers, schemas, errors) -> services -> domain ports -> adapters
backend/alembic/      database migrations
backend/tests/        unit, integration, contract, fakes
frontend/src/         api client (generated types), components, routes, features
docker-compose.yml    local PostgreSQL
```

## Working agreement

Work directly on `main` in Conventional Commits that name the plan task
(e.g. `feat(M3-B6): ...`); tag `main` `m<N>-complete` when a milestone's proof
passes. See `docs/standards.md` and `docs/plan.md` §3.1.
