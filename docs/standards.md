# CareConnect — Engineering Standards

Short, checkable rules. Each one should be verifiable by reading a diff or
running a command — not a matter of taste.

## Commits and milestone tags

Work happens directly on `main` for now; there is no branching or PR
process.

- [ ] Every plan task from `docs/plan.md` is one or more commits on `main`
      with Conventional Commit subjects (`feat:`, `fix:`, `docs:`, `test:`,
      `refactor:`, `chore:`) and the task id in the subject or body (e.g.
      `feat(M3-B6): validate booking against generated slots`). Tests and
      the code that makes them pass may be separate commits (test-first is
      visible in history).
- [ ] A commit that changes an endpoint, field, status code, or error code
      also updates `docs/openapi.yaml`; a commit that adds config also
      updates `.env.example`.
- [ ] `main` is never left red: CI (ruff, mypy, unit, integration,
      contract, frontend) passes on every pushed commit.
- [ ] There is always a single Alembic migration head on `main`.
- [ ] After the last task of a milestone lands and its milestone proof in
      `docs/plan.md` passes on `main`, `main` is tagged
      `M<N>-<Name>` (e.g. `M3-Slots-and-booking`) — one tag per milestone,
      M0–M8 — and `main` plus the tag are pushed.

## Code structure and naming

- [ ] Code is layered as API → Service → Ports → Adapters (spec.md §7). A
      router file contains no business logic — only request parsing, a
      call into a service, and response serialization.
- [ ] Business rules (spec.md §4) live only in the service layer
      (`AppointmentService`, `SlotService`, `TriageService`,
      `SummaryService`, `VisitNoteService`, `ClinicSettingsService`, and
      the supporting services listed in spec.md §7). No rule is duplicated
      in a router or a repository.
- [ ] Services depend on interfaces (`*Repository`, `Clock`,
      `LLMProvider`), never on a concrete DB driver or the Gemini SDK
      directly.
- [ ] Names match the domain model in spec.md §2 exactly (`Appointment`,
      `AITriageResult`, `VisitNote`, `ClinicSettings`, etc.) — no renaming
      an entity ad hoc in code.
- [ ] One class/module per service or repository; a file that mixes two
      services' logic gets split.
- [ ] `uv run ruff check`, `uv run ruff format --check`, and the type
      checker (`uv run mypy` or equivalent) pass with no new suppressions.

## Error handling

- [ ] Every error response body matches the `Error` schema in
      `docs/openapi.yaml`: `{ code: <one of the catalogued codes>,
      message: string }`. No bare stack traces or framework default error
      bodies reach the client — including FastAPI's default request
      validation body, which a custom handler maps to `400`.
- [ ] A raw exception (DB `IntegrityError`, exclusion-constraint
      violation, etc.) never leaks past the service layer — it is caught
      and translated into a domain error with a specific `code` before
      reaching the API layer.
- [ ] HTTP status follows the mapping in `docs/openapi.yaml`: `400` =
      malformed or schema-invalid request, `401` = unauthenticated, `403`
      = permission denied (spec.md §1), `404` = not found, `409` = state
      conflict (double-booking, invalid lifecycle transition, duplicate
      patient, availability conflict, locked note), `422` = policy or
      business-rule violation (cancellation cutoff, follow-up window,
      emergency justification), `500` = unexpected error (generic body), `503` = AI provider unavailable.
- [ ] Each domain error has exactly one `code` value, defined once in the
      `ErrorCode` enum in `docs/openapi.yaml` and used consistently
      everywhere it's raised (e.g. `SLOT_ALREADY_BOOKED`,
      `PATIENT_ALREADY_BOOKED`, `CANCELLATION_WINDOW_CLOSED`,
      `INVALID_TRANSITION`, `FOLLOW_UP_WINDOW_EXCEEDED`,
      `AI_SERVICE_UNAVAILABLE`) — grep for the string before inventing a
      new one.

## Testing

- [ ] Every business rule in spec.md §4 has at least one test that
      exercises it directly (double-booking, real-slot validation, cutoff,
      emergency holdback, follow-up window, force-cancel, specialty
      search, walk-in fallback) — one test per rule, named after the rule,
      not after the function.
- [ ] Service-layer tests are written test-first (TDD) — a failing test
      exists before the implementation that makes it pass.
- [ ] Any code that reads "now" gets the time from an injected `Clock`,
      never `datetime.now()`/`time.time()` called directly in a service —
      cutoff, slot-in-the-past, holdback-release and follow-up-window tests
      must be able to fix the clock.
- [ ] Unit tests for the service layer run with zero network calls and no
      live database — repositories and `LLMProvider` are faked
      (`FakeLLMProvider`, in-memory repos). A test that needs real
      Postgres or a real Gemini call belongs in the separate integration
      suite, not the unit suite.
- [ ] The integration suite (real Postgres) includes a concurrent-booking
      test proving the exclusion constraints reject overlapping bookings
      for the same doctor and for the same patient, and that a cancelled
      slot can be rebooked.
- [ ] `uv run pytest` (unit suite) passes with no network access enabled
      in CI.

## API

- [ ] `docs/openapi.yaml` is the source of truth (spec.md §8) and wins on
      any conflict with another doc. Any new or changed endpoint, field,
      status code, or error code is added to `docs/openapi.yaml` in the
      same change — no undocumented endpoint ships.
- [ ] Request/response field names, types, and required/nullable markers
      in code match the corresponding schema in `docs/openapi.yaml`
      exactly (`camelCase` field names as defined there, including auth
      responses).
- [ ] A contract check that validates **real responses** against
      `docs/openapi.yaml` (e.g. `schemathesis` or `openapi-core`) runs in
      CI for every change from the first milestone — a handler that drifts
      from its documented schema fails CI.

## Data and migrations

- [ ] All schema changes, including constraints and the exclusion
      constraints for double-booking, are Alembic migrations; no
      hand-edited schema.
- [ ] Migrations are reversible, or the commit message justifies why not.
- [ ] Timestamps are stored and returned in UTC; conversion to the clinic
      zone (`ClinicSettings.clinicTimezone`) happens only at the edges
      where "today" or availability wall-times are computed.

## Security

- [ ] No secret (API key, DB credential, JWT signing key) is committed in
      code or in `docs/`. Secrets are read from environment/config only,
      and `.env` (or equivalent) is gitignored.
- [ ] Passwords are hashed with Argon2 or bcrypt; login is rate-limited;
      JWTs have a short TTL; `User.active` is checked on every request.
- [ ] Every route enforces its role requirement server-side, matching the
      permissions table in spec.md §1 — a role check in the frontend is
      never the only check. Front-desk-only actions (force-cancel, user
      management, `ClinicSettings` writes, doctor creation) reject a
      doctor token with `403` even if the UI would never show the button.
- [ ] A doctor-scoped write route enforces "own appointments only"
      (spec.md §1) server-side — it is not enough that the frontend only
      queries the doctor's own data.
- [ ] All request input is validated against its `docs/openapi.yaml`
      schema before touching business logic (types, required fields,
      enums) — malformed input never reaches a service method.
- [ ] Logs, error messages, and traces contain no patient names, phone
      numbers, symptoms, or notes.
- [ ] Sensitive actions (force-cancel, triage override, emergency-slot
      authorization, user create/deactivate, `ClinicSettings` changes)
      write an `AuditLog` entry with actor, target, reason, and time.

## AI usage

- [ ] The Gemini API is called only from inside `TriageService` and
      `SummaryService` (note drafting is routed through `SummaryService`)
      via the `LLMProvider` interface — no other module imports the Gemini
      SDK or holds an API key (spec.md §7).
- [ ] Triage calls return structured JSON validated against a defined
      schema (matching `AITriageResult` fields in `docs/openapi.yaml`)
      before use; the suggested specialty must resolve to an existing
      specialty. An unparseable or schema-invalid response is treated as
      `AI_SERVICE_UNAVAILABLE`, never passed through raw. Summary and
      draft outputs are free text validated as non-empty and
      length-bounded.
- [ ] Personal data (name, phone, email, date of birth) is scrubbed from
      all text before any prompt or payload is sent to Gemini — triage,
      summary, and draft alike (spec.md §5.1) — inside the adapter,
      unconditionally, not as an opt-in. Symptom, history, and note text
      is delimited in the prompt as untrusted data.
- [ ] A deterministic red-flag check (non-AI, rule-based keyword/symptom
      check for clearly emergent presentations) runs before the model is
      called, can independently force `urgency = emergency`, and still
      returns its result if the model call fails — the AI call is never
      the only path to flagging an emergency. The keyword list is
      reviewed like code.
- [ ] AI output is always advisory: it is stored as a suggestion, staff
      override is always available and preserved separately from the
      original with a reason (spec.md §2, §5), and the safety disclaimer
      (a server-side constant, never model-generated) is never omitted
      from a response that includes a triage, summary, or draft.
- [ ] Every AI call has a timeout; a stored `AITriageResult` records
      `source` (`model` or `red_flag`) and the model/prompt version.
