# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

CareConnect is **implemented**: milestones M0–M8 in `docs/plan.md` are
complete and tagged (`M0-Foundation` … `M8-Hardening`). Stack: FastAPI
(Python 3.12, dependency-managed via `uv` — never pip/poetry/conda) +
PostgreSQL 16 + React 19/TypeScript/Vite styled with Tailwind v4. Layout:
`backend/` (app, alembic, tests), `frontend/` (src, e2e), `docs/`.
Setup, run and test commands are in `README.md`; operations in
`docs/runbook.md`; open release sign-offs in `docs/release-checklist.md`.

Checks before any change is done: backend `uv run ruff check . && uv run
ruff format --check . && uv run mypy && uv run pytest` (integration needs
`docker compose up -d db`); frontend `npm run lint && npm run typecheck &&
npm test && npm run build`, and `npm run gen:api` must leave
`src/api/schema.d.ts` unchanged. `npm run e2e` resets the local database.

## Documentation hierarchy — read in this order

Each doc has a distinct authority; don't duplicate one into another.

1. **`docs/intent.md`** — product scope only (problem, measurable
   outcome, affected users, constraints, out of scope). No technical
   design.
2. **`docs/spec.md`** — the behavioral contract: roles/permissions,
   domain model, appointment lifecycle, business rules, AI triage
   input/output/guardrails, Given/When/Then user stories, and the layered
   architecture (with a Mermaid diagram in §7). §9 traces resolved
   ambiguities back to stakeholder decisions.
3. **`docs/openapi.yaml`** — the single source of truth for the API
   contract (every endpoint, schema, status code, error code).
   `docs/spec.md` §8 intentionally just points here instead of
   duplicating it — if this file disagrees with code **or** with
   `docs/spec.md`, this file wins; fix the other document to match.
4. **`docs/standards.md`** — checkable engineering rules (structure,
   error handling, testing, API, security, AI usage) that any code change
   must satisfy.
5. **`docs/review.md`** — the review policy (passes, severity levels,
   exclusions) applied by both AI and human reviewers.
6. **`docs/plan.md`** — the milestone plan (M0–M8), each milestone a
   demoable backend + frontend feature slice in priority order.

## Git workflow

For now, work directly on `main` — no branches or PRs. Each plan task is
one or more Conventional Commits with the task id in the subject (e.g.
`feat(M3-B6): ...`). After a milestone (M0–M8 in `docs/plan.md`) is
complete and its milestone proof passes, tag `main` `M<N>-<Name>` (e.g.
`M7-Visit-notes-and-summaries`) and push `main` plus the tag. Full rules:
`docs/standards.md` → Commits and milestone tags; steps in `docs/plan.md`
§3.1. Create commits and tags only when the user asks (or as part of a
milestone release the user has asked for); never push otherwise.

## Architecture (from docs/spec.md §7)

Layered, deliberately flat (single FastAPI process + Postgres, no queue,
no microservices):

`API routers → Service layer → Ports (interfaces) → Adapters`

- **Service layer** (`AppointmentService`, `SlotService`, `TriageService`,
  `SummaryService`, `VisitNoteService`, `ClinicSettingsService`) holds
  all business rules and is framework/AI-provider agnostic — this is the
  TDD core (`docs/standards.md` requires one test per business rule, an
  injectable clock, and no network calls in unit tests).
- **`TriageService` and `SummaryService` depend on an `LLMProvider`
  interface**, not the Gemini SDK directly. Production wires
  `GeminiLLMProvider` (wraps `google-genai`, scrubs patient-identifying
  data from free text before any outbound call); tests use
  `FakeLLMProvider`. No other module may import the Gemini SDK or hold an
  API key (`docs/standards.md`, AI usage).
- **Double-booking prevention is DB-enforced** via Postgres exclusion
  constraints on `tstzrange(start, end)` (one per doctor, one per
  patient, ignoring cancelled/no-show rows), not just checked in
  application code — so real overlaps are rejected under concurrent
  requests.
- **AI triage guardrails**: structured JSON output validated against a
  schema, a deterministic red-flag check runs before the model (and still
  returns `emergency` if the model is down), PII is scrubbed before
  reaching Gemini, the disclaimer is a server constant, and every result
  is advisory-only with a staff-overridable result (override wins, with a
  reason and audit entry).
- **Auth**: staff-only (doctor / front_desk_admin), email/password + JWT;
  every role check must be enforced server-side per route, matching the
  permissions table in `docs/spec.md` §1 (front-desk has full access;
  doctors edit their own doctor data, read all patients, and write only
  for appointments they hold).

## Domain notes worth knowing before touching business logic

- Patient identity is **(phone number, name)** — one phone can have
  multiple registered patients (e.g. family members), so lookups by phone
  return a list, not a single record. Phone is stored E.164 and name is
  normalized; the pair is unique.
- The cancellation cutoff (`ClinicSettings.cancellation_cutoff_hours`)
  governs **both** cancellation and reschedule, not just cancellation.
- Timestamps are UTC; the clinic's IANA zone lives in `ClinicSettings`
  and defines "today" and availability wall-times.
- Emergency holdback is the **last N** slots of each doctor's day.
- Emergency-held slot capacity can be authorized by **either** the AI
  triage result being `emergency` **or** independent front-desk judgment.
- `ClinicSettings` (cutoff hours, emergency-slot count, follow-up max
  days) are seeded with sensible defaults but are front-desk-editable at
  runtime — never hardcode these values in business logic.
