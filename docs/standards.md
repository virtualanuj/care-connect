# CareConnect — Engineering Standards

Short, checkable rules. Each one should be verifiable by reading a diff or
running a command — not a matter of taste.

## Code structure and naming

- [ ] Code is layered as API → Service → Ports → Adapters (spec.md §7). A
      router file contains no business logic — only request parsing, a
      call into a service, and response serialization.
- [ ] Business rules (spec.md §4) live only in the service layer
      (`AppointmentService`, `SlotService`, `TriageService`,
      `SummaryService`, `VisitNoteService`, `ClinicSettingsService`). No
      rule is duplicated in a router or a repository.
- [ ] Services depend on interfaces (`*Repository`, `TriageProvider`), never
      on a concrete DB driver or the Gemini SDK directly.
- [ ] Names match the domain model in spec.md §2 exactly (`Appointment`,
      `AITriageResult`, `VisitNote`, `ClinicSettings`, etc.) — no renaming
      an entity ad hoc in code.
- [ ] One class/module per service or repository; a file that mixes two
      services' logic gets split.

## Error handling

- [ ] Every error response body matches the `Error` schema in
      `docs/openapi.yaml`: `{ code: UPPER_SNAKE_CASE_STRING, message:
      string }`. No bare stack traces or framework default error bodies
      reach the client.
- [ ] A raw exception (DB `IntegrityError`, etc.) never leaks past the
      service layer — it is caught and translated into a domain error
      with a specific `code` before reaching the API layer.
- [ ] HTTP status follows the mapping already used in `docs/openapi.yaml`:
      `403` = permission denied (spec.md §1), `409` = business-rule
      conflict (double-booking, cutoff closed, invalid lifecycle
      transition), `422` = request outside a policy window
      (follow-up/emergency validation), `503` = AI provider unavailable.
- [ ] Each domain error has exactly one `code` value used consistently
      everywhere it's raised (e.g. `SLOT_ALREADY_BOOKED`,
      `CANCELLATION_WINDOW_CLOSED`, `INVALID_TRANSITION`,
      `FOLLOW_UP_WINDOW_EXCEEDED`, `AI_SERVICE_UNAVAILABLE`) — grep for the
      string before inventing a new one.

## Testing

- [ ] Every business rule in spec.md §4 has at least one test that
      exercises it directly (double-booking, cutoff, emergency holdback,
      follow-up window, force-cancel, specialty search, walk-in
      fallback) — one test per rule, named after the rule, not after the
      function.
- [ ] Service-layer tests are written test-first (TDD) — a failing test
      exists before the implementation that makes it pass.
- [ ] Any code that reads "now" gets the time from an injected clock
      (e.g. a `Clock` port), never `datetime.now()`/`time.time()` called
      directly in a service — cutoff and follow-up-window tests must be
      able to fix the clock.
- [ ] Unit tests for the service layer run with zero network calls and no
      live database — repositories and `TriageProvider` are faked
      (`FakeTriageProvider`, in-memory repos). A test that needs real
      Postgres or a real Gemini call belongs in the separate integration
      suite, not the unit suite.
- [ ] `uv run pytest` (unit suite) passes with no network access enabled
      in CI.

## API

- [ ] `docs/openapi.yaml` is the source of truth (spec.md §8). Any new or
      changed endpoint, field, or status code is added to
      `docs/openapi.yaml` in the same change — no undocumented endpoint
      ships.
- [ ] Request/response field names, types, and required/nullable markers
      in code match the corresponding schema in `docs/openapi.yaml`
      exactly (`camelCase` field names as defined there).
- [ ] A contract check (schema validation of real responses against
      `docs/openapi.yaml`, or an equivalent test) runs before merge — a
      handler that drifts from its documented schema fails CI.

## Security

- [ ] No secret (API key, DB credential, JWT signing key) is committed in
      code or in `docs/`. Secrets are read from environment/config only,
      and `.env` (or equivalent) is gitignored.
- [ ] Every route enforces its role requirement server-side, matching the
      permissions table in spec.md §1 — a role check in the frontend is
      never the only check. Front-desk-only actions (force-cancel,
      `ClinicSettings` writes) reject a doctor token with `403` even if
      the UI would never show the button.
- [ ] A doctor-scoped route enforces "own patients only" server-side
      (spec.md §1) — it is not enough that the frontend only queries the
      doctor's own data.
- [ ] All request input is validated against its `docs/openapi.yaml`
      schema before touching business logic (types, required fields,
      enums) — malformed input never reaches a service method.

## AI usage

- [ ] The Gemini API is called only from inside `TriageService` (and
      `SummaryService`) via the `TriageProvider` interface — no other
      module imports the Gemini SDK or holds an API key (spec.md §7).
- [ ] Every AI call returns structured JSON that is validated against a
      defined schema (matching `AITriageResult`/summary fields in
      `docs/openapi.yaml`) before use — an unparseable or schema-invalid
      response is treated as `AI_SERVICE_UNAVAILABLE`, never passed
      through raw.
- [ ] Patient-identifying fields (name, phone, any other direct
      identifier) are redacted before any prompt or payload is sent to
      Gemini (spec.md §5, §7) — this redaction step runs inside the
      adapter, unconditionally, not as an opt-in.
- [ ] A deterministic red-flag check (non-AI, rule-based keyword/symptom
      check for clearly emergent presentations) runs before the model is
      called, and can independently force `urgency = emergency` —
      the AI call is never the only path to flagging an emergency.
- [ ] AI output is always advisory: it is stored as a suggestion, staff
      override is always available and preserved separately from the
      original (spec.md §2, §5), and the safety disclaimer is never
      omitted from a response that includes a triage result.
