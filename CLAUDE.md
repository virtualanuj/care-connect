# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

CareConnect is currently **docs-only** — there is no application code, no
`pyproject.toml`, and no frontend yet. Everything in this repo so far is
in `docs/`. Before writing implementation code, check whether it's
expected to land in this repo directly or whether the user wants a
separate planning/spec pass first (see docs below).

Because there is no code yet, there are no build/lint/test commands to
run. Once implementation starts, the intended stack is FastAPI (Python,
dependency-managed via `uv` — never pip/poetry/conda) + PostgreSQL +
React, per `docs/spec.md` §7.

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
   contract (every endpoint, schema, status code). `docs/spec.md` §8
   intentionally just points here instead of duplicating it — if code and
   this file disagree, this file wins for the contract; if this file and
   `docs/spec.md` disagree on behavior, `docs/spec.md` wins.
4. **`docs/standards.md`** — checkable engineering rules (structure,
   error handling, testing, API, security, AI usage) that any code change
   must satisfy.
5. **`docs/review.md`** — the PR review policy (passes, severity levels,
   exclusions) applied by both AI and human reviewers.

## Architecture (from docs/spec.md §7)

Layered, deliberately flat (single FastAPI process + Postgres, no queue,
no microservices):

`API routers → Service layer → Ports (interfaces) → Adapters`

- **Service layer** (`AppointmentService`, `SlotService`, `TriageService`,
  `SummaryService`, `VisitNoteService`, `ClinicSettingsService`) holds
  all business rules and is framework/AI-provider agnostic — this is the
  TDD core (`docs/standards.md` requires one test per business rule, an
  injectable clock, and no network calls in unit tests).
- **`TriageService` depends on a `TriageProvider` interface**, not the
  Gemini SDK directly. Production wires `GeminiTriageProvider` (wraps
  `google-genai`, redacts patient-identifying fields before any outbound
  call); tests use `FakeTriageProvider`. No other module may import the
  Gemini SDK or hold an API key (`docs/standards.md`, AI usage).
- **Double-booking prevention is DB-enforced** via unique constraints
  (`(doctor_id, start_time)`, `(patient_id, start_time)`), not just
  checked in application code — so it holds under concurrent requests.
- **AI triage guardrails**: structured JSON output validated against a
  schema, a deterministic red-flag check runs before the model and can
  independently force `urgency = emergency`, PII is redacted before
  reaching Gemini, and every result is advisory-only with a
  staff-overridable result and a mandatory safety disclaimer.
- **Auth**: staff-only (doctor / front_desk_admin), email/password + JWT;
  every role check must be enforced server-side per route, matching the
  permissions table in `docs/spec.md` §1 (front-desk has full access;
  doctors are scoped to their own data and their own patients' data).

## Domain notes worth knowing before touching business logic

- Patient identity is **(phone number, name)** — one phone can have
  multiple registered patients (e.g. family members), so lookups by phone
  return a list, not a single record.
- The cancellation cutoff (`ClinicSettings.cancellation_cutoff_hours`)
  governs **both** cancellation and reschedule, not just cancellation.
- Emergency-held slot capacity can be authorized by **either** the AI
  triage result being `emergency` **or** independent front-desk judgment.
- `ClinicSettings` (cutoff hours, emergency-slot count, follow-up max
  days) are seeded with sensible defaults but are front-desk-editable at
  runtime — never hardcode these values in business logic.
