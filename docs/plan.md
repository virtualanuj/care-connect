# CareConnect — Implementation Plan

Ordered, thin (≤30 min) vertical slices from `docs/spec.md`,
`docs/openapi.yaml`, and `docs/standards.md`. Backend/API-only — "demo"
means exercisable via curl/Swagger UI. Slices 1–7 reach the first
demoable booking flow; everything after layers on rules, auth, AI, and
the remaining API surface in dependency order.

## 1. Project scaffolding
- **Goal**: a runnable FastAPI app and test harness exist.
- **Stories**: none — foundation.
- **Files**: `pyproject.toml` (`uv init`), `app/main.py`,
  `app/api/routers/health.py`, `tests/unit/test_health.py`.
- **Risks**: uv/Python version mismatch between machines.
- **Proof**: `uv run pytest` passes; `GET /health` returns 200.

## 2. Postgres + migrations wired
- **Goal**: the app connects to a real Postgres via Alembic-managed schema.
- **Stories**: none — foundation.
- **Files**: `docker-compose.yml`, `app/db/session.py`, `alembic.ini`,
  `alembic/env.py`.
- **Risks**: DB connection string drifting between local and CI.
- **Proof**: `alembic upgrade head` succeeds against a fresh DB; a smoke
  test opens a session and runs `SELECT 1`.

## 3. Core booking models + first migration
- **Goal**: `Specialty`, `Doctor`, `Patient`, `Appointment` tables exist
  with the minimal columns needed to book.
- **Stories**: none — foundation for slices 5–7.
- **Files**: `app/db/models.py`, `alembic/versions/0001_core_tables.py`.
- **Risks**: getting the double-booking unique constraints wrong now
  means a follow-up migration.
- **Proof**: migration applies cleanly; a unit test inserts one row of
  each table via the ORM.

## 4. Seed fixture data
- **Goal**: one specialty + one doctor + one patient exist for manual use.
- **Stories**: supports the demo, not a listed story.
- **Files**: `app/db/seed.py`.
- **Risks**: seed script drifting from the schema as models evolve.
- **Proof**: running the script twice is idempotent; a test asserts the
  expected rows exist after seeding.

## 5. Book an appointment — doctor double-booking
- **Goal**: `POST /appointments` creates a booked appointment; a
  DB-level unique constraint on `(doctor_id, start_time)` rejects a
  doctor overlap.
- **Stories**: "Booking prevents double-booking" — doctor half (spec.md §6).
- **Files**: `app/services/appointment_service.py`,
  `app/domain/ports.py` (`AppointmentRepository`),
  `app/adapters/postgres/appointment_repository.py`,
  `app/api/routers/appointments.py`,
  `tests/unit/services/test_appointment_service.py`.
- **Risks**: translating the raw `IntegrityError` into the documented
  `SLOT_ALREADY_BOOKED` code (standards.md) is easy to get wrong first try.
- **Proof**: unit test (fake repository, no DB) — booking the same
  doctor+time twice raises `SlotAlreadyBookedError`.

## 6. Patient double-booking constraint
- **Goal**: the same guarantee for `(patient_id, start_time)`.
- **Stories**: "Booking prevents double-booking" — patient half (spec.md §6).
- **Files**: `alembic/versions/0002_patient_unique_constraint.py`,
  extend `test_appointment_service.py`.
- **Risks**: none beyond slice 5.
- **Proof**: unit test — the same patient double-booked with two
  different doctors at the same time is rejected.

## 7. View a booked appointment — first demoable milestone
- **Goal**: `GET /appointments/{id}` and `GET /appointments`
  (list/query). Combined with slices 1–6: seed → book via
  curl/Swagger → view → duplicate rejected, end to end.
- **Stories**: makes all booking stories observable.
- **Files**: extend `app/api/routers/appointments.py`,
  `app/services/appointment_service.py`.
- **Risks**: none.
- **Proof**: integration test against real Postgres — book, then GET
  returns the same appointment; a conflicting second POST returns 409.

## 8. Auth: login + JWT + role on token
- **Goal**: `POST /auth/login`, `GET /auth/me`; every route below can
  require a role.
- **Stories**: none directly — prerequisite for every permission-gated
  story from here on.
- **Files**: `app/api/routers/auth.py`, `app/services/auth_service.py`,
  `app/domain/ports.py` (`UserRepository`), `app/security.py`,
  `tests/unit/services/test_auth_service.py`.
- **Risks**: JWT secret must come from env, never hardcoded (standards.md,
  Security).
- **Proof**: unit test — correct credentials issue a token with the
  right role; wrong password is rejected.

## 9. Role enforcement on appointment routes
- **Goal**: `/appointments*` requires a valid token; a doctor is scoped
  to their own patients (spec.md §1).
- **Stories**: none directly — permissions substrate.
- **Files**: `app/api/deps.py`, update `app/api/routers/appointments.py`.
- **Risks**: forgetting the dependency on one route silently violates
  standards.md's server-side role-check rule.
- **Proof**: integration test — a doctor token booking for a patient
  that isn't theirs returns 403; a front-desk token is unrestricted.

## 10. Doctor & specialty CRUD
- **Goal**: `POST/GET/PATCH /doctors`, `POST/GET /specialties`,
  `slotLengthMinutes` seeded from the specialty default (spec.md §4).
- **Stories**: none directly — needed for slot generation.
- **Files**: `app/api/routers/doctors.py`,
  `app/api/routers/specialties.py`, `app/services/doctor_service.py`.
- **Risks**: forgetting "doctor edits own profile only" (§1).
- **Proof**: unit test — a doctor created without an explicit slot
  length inherits the specialty default; a doctor token editing another
  doctor's profile returns 403.

## 11. Patient registration + phone lookup
- **Goal**: `POST /patients`, `GET /patients?phone=`.
- **Stories**: "Patient lookup by phone returns all matches" (spec.md §6).
- **Files**: `app/api/routers/patients.py`,
  `app/services/patient_service.py`.
- **Risks**: none — multiple patients per phone is intentional (§2), not
  a dedup bug.
- **Proof**: unit test — two patients registered under the same phone
  number are both returned by a phone-only lookup.

## 12. Medical history entries
- **Goal**: `POST/GET /patients/{id}/medical-history`, free text,
  append-only.
- **Stories**: supports the pre-visit summary story (slice 30).
- **Files**: extend `app/api/routers/patients.py`,
  `app/services/patient_service.py`.
- **Risks**: none.
- **Proof**: unit test — two entries added in sequence both return, in
  order; no update/delete endpoint exists.

## 13. Availability weekly rules
- **Goal**: `POST/GET /doctors/{id}/availability`.
- **Stories**: needed for slot generation (slice 15).
- **Files**: `app/api/routers/availability.py`,
  `app/services/availability_service.py`, migration for `Availability`.
- **Risks**: none.
- **Proof**: unit test — availability rules round-trip through create/list.

## 14. Availability exceptions
- **Goal**: `POST/GET /doctors/{id}/availability-exceptions` (holiday,
  extra hours).
- **Stories**: none directly — completeness for slot generation.
- **Files**: extend `app/api/routers/availability.py`, migration for
  `AvailabilityException`.
- **Risks**: none.
- **Proof**: unit test — an `unavailable` exception is stored and
  retrievable (consumed by `SlotService` in slice 15).

## 15. SlotService — one doctor
- **Goal**: `GET /slots?doctorId=&date=` returns open slots sized by
  that doctor's `slotLengthMinutes`, minus existing appointments and
  exceptions.
- **Stories**: prerequisite for slices 16–19.
- **Files**: `app/services/slot_service.py`, `app/api/routers/slots.py`,
  `tests/unit/services/test_slot_service.py`.
- **Risks**: off-by-one slot-boundary bugs — needs a table test with
  fixed availability/appointment fixtures.
- **Proof**: unit test — a 9–10am rule with a 20-minute slot length
  yields exactly 3 slots; one existing appointment removes exactly one.

## 16. Emergency holdback
- **Goal**: the first N slots/day (`ClinicSettings.emergency_slots_per_doctor_per_day`)
  are excluded from the default `/slots` response.
- **Stories**: "Emergency slot reserved from normal booking" (spec.md §6).
- **Files**: extend `slot_service.py`; add `ClinicSettings` model +
  seeded-defaults migration.
- **Risks**: none beyond slice 15.
- **Proof**: unit test — with the holdback set to 1, the day's first slot
  is absent by default and present with `includeEmergency=true`.

## 17. Book into an emergency slot (front-desk judgment)
- **Goal**: `POST /appointments` accepts `isEmergencySlot=true` +
  `emergencyJustification=front_desk_judgment` and bypasses the holdback.
- **Stories**: "Emergency slot usable via triage or front-desk judgment"
  — front-desk-judgment half (spec.md §6; triage half completes in slice 29).
- **Files**: extend `appointment_service.py`.
- **Risks**: a request without a justification must 422, not silently pass.
- **Proof**: unit test — an emergency booking without a justification is
  rejected; with `front_desk_judgment` it succeeds.

## 18. Specialty-wide slot search
- **Goal**: `GET /slots?specialtyId=&date=` unions candidate slots
  across every doctor in that specialty.
- **Stories**: "Specialty-wide search offers a choice" (spec.md §6).
- **Files**: extend `slot_service.py`.
- **Risks**: must return every option, never auto-pick one (§4).
- **Proof**: unit test — two doctors in the same specialty with open
  slots both appear in one specialty-search response.

## 19. Walk-in fallback
- **Goal**: booking flow offers other doctors in the same specialty when
  the requested doctor has none available.
- **Stories**: "Walk-in fallback to another doctor in the specialty" (spec.md §6).
- **Files**: compose slices 15+18, e.g. `app/services/walk_in_service.py`.
- **Risks**: none — pure composition.
- **Proof**: unit test — requesting an unavailable specific doctor
  returns the fallback list from other doctors in their specialty.

## 20. Injectable clock
- **Goal**: a `Clock` port + `SystemClock`/`FixedClock` adapters exist;
  `AppointmentService` reads "now" only through it.
- **Stories**: prerequisite for slices 21, 22, 25 (standards.md, Testing).
- **Files**: `app/domain/ports.py` (`Clock`),
  `app/adapters/system_clock.py`, `tests/fakes/fixed_clock.py`.
- **Risks**: a stray `datetime.now()` call left behind — grep for it as
  part of this slice.
- **Proof**: unit test — a cutoff-style check gives different results
  only when the fake clock is advanced, never from wall-clock time.

## 21. Cancellation cutoff
- **Goal**: `POST /appointments/{id}/cancel` rejects inside
  `ClinicSettings.cancellation_cutoff_hours`; `GET/PATCH
  /clinic-settings` exists (front-desk only).
- **Stories**: "Cancellation and reschedule both blocked inside the
  cutoff window" — cancel half (spec.md §6).
- **Files**: `app/api/routers/clinic_settings.py`,
  `app/services/clinic_settings_service.py`, extend
  `appointment_service.py`.
- **Risks**: `PATCH /clinic-settings` must be front-desk-only (§1) —
  reuse slice 9's dependency.
- **Proof**: unit test (fixed clock) — cancelling inside the cutoff
  raises `CancellationWindowClosedError`; outside it succeeds.

## 22. Reschedule (same cutoff)
- **Goal**: `POST /appointments/{id}/reschedule` = cancel-old + book-new
  in one transaction, same cutoff check.
- **Stories**: "Cancellation and reschedule both blocked inside the
  cutoff window" — reschedule half (spec.md §6).
- **Files**: extend `appointment_service.py`, `appointments.py` router.
- **Risks**: must be transactional — a failed new-slot booking can't
  leave the old one cancelled.
- **Proof**: integration test — a reschedule whose new booking fails
  leaves the original appointment still `booked`.

## 23. Force-cancel
- **Goal**: `POST /appointments/{id}/force-cancel`, front-desk only,
  bypasses the cutoff, logged distinctly.
- **Stories**: completes the cutoff story's "force-cancel offered as the
  only path forward" (spec.md §6).
- **Files**: extend `appointment_service.py`, `appointments.py` router.
- **Risks**: a doctor token must get 403, not a silent bypass.
- **Proof**: unit test — front-desk force-cancel succeeds inside the
  cutoff; doctor-token attempt returns 403.

## 24. Lifecycle state machine
- **Goal**: check-in / start-consultation / complete / no-show
  endpoints; invalid transitions rejected.
- **Stories**: implements spec.md §3; load-bearing for slice 26.
- **Files**: `app/domain/appointment_lifecycle.py` (pure transition
  table), extend `appointment_service.py` + router with 4 endpoints.
- **Risks**: the transition table needs exhaustive coverage, not ad hoc
  spot checks.
- **Proof**: parametrized unit test — every valid transition in §3
  succeeds and every other (status, target) pair raises
  `InvalidTransitionError`.

## 25. Follow-up booking + window rule
- **Goal**: `POST /appointments/{id}/follow-up` rejects beyond
  `ClinicSettings.follow_up_max_days`.
- **Stories**: "Follow-up must fall within the policy window" (spec.md §6).
- **Files**: extend `appointment_service.py`.
- **Risks**: none beyond reusing slice 20's clock.
- **Proof**: unit test — a follow-up exactly at the boundary succeeds,
  one day beyond it is rejected.

## 26. Front-desk daily queue
- **Goal**: `GET /queue?date=` groups today's appointments into
  booked/walk-ins/in-progress/completed/no-shows.
- **Stories**: "Front-desk daily queue" (spec.md §6).
- **Files**: `app/services/queue_service.py`, `app/api/routers/queue.py`.
- **Risks**: "walk-in" isn't a stored status — it's inferred, so the
  bucketing logic needs its own test, not just a query.
- **Proof**: unit test — one appointment per category is correctly
  bucketed given a fixed "today."

## 27. TriageProvider port + fake + red-flag check
- **Goal**: `TriageProvider` interface, `FakeTriageProvider`, and a
  deterministic keyword-based red-flag check, wired into
  `TriageService` — zero Gemini dependency yet.
- **Stories**: prerequisite for slices 28–29; implements the red-flag
  guardrail (standards.md, AI usage).
- **Files**: `app/domain/ports.py` (`TriageProvider`),
  `app/adapters/ai/fake_triage_provider.py`,
  `app/services/triage_service.py`,
  `app/services/red_flag_check.py`,
  `tests/unit/services/test_triage_service.py`.
- **Risks**: keep the red-flag list small and explicit; it may only
  raise urgency, never lower the model's own `emergency` call.
- **Proof**: unit test — a symptom string matching a red-flag keyword
  yields `urgency=emergency` even when the fake provider returns `routine`.

## 28. PII redaction + Gemini adapter
- **Goal**: `GeminiTriageProvider` wraps `google-genai`, redacts
  name/phone before the outbound call, validates the JSON response
  against the `AITriageResult` schema, maps failures to
  `AI_SERVICE_UNAVAILABLE`.
- **Stories**: "Patient identity redacted before reaching the AI
  provider" (spec.md §6); schema-validation + fallback guardrails
  (standards.md).
- **Files**: `app/adapters/ai/gemini_triage_provider.py`,
  `app/adapters/ai/redact.py`.
- **Risks**: first slice touching a real external API — needs a
  contract test kept separate from the unit suite, skippable without an
  API key (standards.md, Testing).
- **Proof**: unit test — redaction strips name/phone from a sample
  payload before it reaches a mocked client; a separate CI-skippable
  contract test exercises a real Gemini call.

## 29. Triage endpoints
- **Goal**: `POST/GET /appointments/{id}/triage`,
  `PATCH .../triage/override`.
- **Stories**: "AI triage shown with disclaimer and confidence, and
  overridable" (spec.md §6); completes slice 17's triage-justification half.
- **Files**: `app/api/routers/triage.py`, extend `triage_service.py`.
- **Risks**: an override must be stored alongside, not over, the
  original result (§2) — getting this wrong breaks the audit trail.
- **Proof**: unit test — overriding urgency leaves the original
  `urgency` field unchanged and populates `overriddenUrgency` separately.

## 30. Pre-visit summary
- **Goal**: `GET /appointments/{id}/summary` assembles history +
  symptoms + triage via `SummaryService` (reuses the `TriageProvider` port).
- **Stories**: "Pre-visit summary available to doctor" (spec.md §6).
- **Files**: `app/services/summary_service.py`,
  `app/api/routers/summary.py`.
- **Risks**: keep the cache simple — stored on first read, regenerated
  only when underlying data changes (§5); don't over-build it.
- **Proof**: unit test — calling summary twice with no underlying
  change hits the fake provider exactly once.

## 31. Visit notes + AI draft + finalize
- **Goal**: `GET/PUT /appointments/{id}/visit-note`,
  `POST .../draft`, `POST .../finalize`.
- **Stories**: "Draft visit summary from notes" (spec.md §6).
- **Files**: `app/services/visit_note_service.py`,
  `app/api/routers/visit_notes.py`.
- **Risks**: `/draft` must never write `finalSummary` (§5).
- **Proof**: unit test — `/draft` populates `aiDraftSummary` only;
  `finalSummary` stays null until `/finalize` is called explicitly.

## 32. OpenAPI contract check
- **Goal**: an automated check that live route schemas match
  `docs/openapi.yaml` (standards.md, API).
- **Stories**: none — closes the standards.md requirement deferred
  across every slice above.
- **Files**: `tests/contract/test_openapi_contract.py`.
- **Risks**: FastAPI's generated schema and the hand-written
  `docs/openapi.yaml` can drift on field-naming style (`camelCase` vs.
  default `snake_case`) — this is where that gets caught.
- **Proof**: `uv run pytest tests/contract` passes, diffing FastAPI's
  generated schema against `docs/openapi.yaml`.
