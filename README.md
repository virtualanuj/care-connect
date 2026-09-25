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
uv run python -m app.db.seed --demo   # (ENV=dev) a fuller demo clinic: 3 specialties, 6 doctors
#   (demo.doctor1..6@clinic.test, same dev passphrase), 40 patients, today's queue in every status
uv run uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health

# Frontend (second terminal)
cd frontend
npm ci
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

## Local accounts

`SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` create the front-desk admin (only if that user does not
exist yet). With `ENV=dev`, the seed also adds `doctor@clinic.test` (`dev doctor passphrase`); `--demo`
adds `demo.doctor1..6@clinic.test` with the same passphrase. `npm run e2e` wipes the local users and
re-creates the admin as `admin@clinic.test` / `e2e admin passphrase`, so re-run the seed afterwards.
Too many failed logins are rate-limited (in memory); restart the API to clear it.

## AI triage configuration

Triage uses Gemini through one adapter (`backend/app/adapters/ai/`). Set `GEMINI_API_KEY` (and
optionally `GEMINI_MODEL`) in `backend/.env`. Without a key the AI is reported as unavailable,
but the deterministic red-flag safety rule still returns an emergency result.

For local development or end-to-end tests without a key, set `ENV=dev` and
`LLM_PROVIDER=fake` (deterministic, no network; a symptom containing `simulate-ai-outage` behaves
like an outage) or `LLM_PROVIDER=fake-down` (always unavailable). These are rejected when
`ENV` is not `dev`. The red-flag phrase list lives in `backend/app/domain/red_flags.py` and must be
signed off by the clinical lead before release.

## Production-like stack

`docker compose --profile prod up -d --build` runs the API (migrating on start) and the web
container (nginx, same-origin `/api` proxy) next to Postgres. Environment, TLS, backup/restore and
upgrade steps are in [`docs/runbook.md`](docs/runbook.md). Logs are one PHI-free JSON line per
request with an `X-Request-ID`; `CORS_ALLOWED_ORIGINS` (exact origins, no `*`) and
`MAX_REQUEST_BYTES` are the HTTP hardening settings.

## Tests and checks

```bash
# Backend (from backend/)
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest tests/unit          # no network, no database
uv run pytest tests/contract      # responses validated against docs/openapi.yaml
                                  # (the live Gemini test runs only if GEMINI_API_KEY is set)
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
docs/                 intent, spec, openapi.yaml (source of truth), standards, review, plan,
                      runbook, release-checklist
backend/app/          api (routers, schemas, errors) -> services -> domain ports -> adapters
backend/alembic/      database migrations
backend/tests/        unit, integration, contract, fakes
frontend/src/         api client (generated types), components, routes, features
                      (Tailwind v4 styling in `src/index.css`)
docker-compose.yml    local PostgreSQL; `--profile prod` adds the api + web containers
```

## Working agreement

Work directly on `main` in Conventional Commits that name the plan task
(e.g. `feat(M3-B6): ...`); tag `main` `M<N>-<Name>` (e.g. `M7-Visit-notes-and-summaries`) and
push when a milestone's proof passes. See `docs/standards.md` and `docs/plan.md` §3.1.
