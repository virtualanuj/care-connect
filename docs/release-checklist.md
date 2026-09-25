# Release checklist

Automated gates (all enforced by CI on every push to `main`):

- [x] `backend-unit`: ruff, ruff format, mypy strict, unit tests with sockets disabled
- [x] `backend-integration`: migrations to a single head, integration tests against Postgres
      (permission matrix over every route, doctor-scoping matrix, PHI-free logs, demo seed,
      performance budget and query plans)
- [x] `contract`: hand-written contract tests plus a Schemathesis sweep of **every** operation in
      `docs/openapi.yaml` as front-desk, doctor and anonymous
- [x] `frontend`: lint, typecheck, unit tests, build, generated API types in sync with `openapi.yaml`
- [x] `e2e`: Playwright specs per feature, an axe accessibility pass over every main screen at tablet
      width, and the full journey (`e2e/journey.spec.ts`, video and trace uploaded as artifacts)
- [x] `security`: `pip-audit`, `npm audit --audit-level=high`, gitleaks secret scan

Human sign-offs that no test can give. **These are open**, and the release gate in
`docs/plan.md` (M8) is not met until each has an owner and a date:

- [ ] **Red-flag phrase list approved by the clinical owner.** The list is a code constant
      (`backend/app/domain/red_flags.py`, versioned by `RED_FLAG_LIST_VERSION`); a change is a
      reviewed code change (`docs/review.md`). Record the approver and the approved version here.
- [ ] **Clinic sign-off of `ClinicSettings` defaults**: cancellation cutoff 2 h, emergency
      holdback 1 slot per doctor per day, follow-up window 30 days, clinic time zone.
- [ ] **Gemini terms confirmed**: data sent to the provider is not used for training (the app
      already scrubs patient identifiers before any outbound call, but the contractual position is
      a legal/compliance decision). Record the plan/tier and the date checked.
- [ ] **Data protection review** of retention, backup encryption and access (see the runbook), by
      whoever owns compliance for the clinic.
- [ ] **Decisions with a safety or privacy trade-off** acknowledged by the product owner: a staff
      override always wins over the AI/red-flag result when determining effective urgency
      (`docs/spec.md` section 5), and doctors can read all patients (section 1, decision 16).

Known limits (also in `docs/runbook.md`): single API process (in-memory login rate limiter);
request size limited by declared `Content-Length` and by nginx, not by a streaming counter.
