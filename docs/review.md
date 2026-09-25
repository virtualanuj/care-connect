# Review policy

Applies to every change (commit or group of commits, and the milestone as a whole before it is tagged), for both AI and human reviewers.

## Passes

1. **Correctness**: behaviour matches `docs/spec.md`; every changed rule
   has a test.
2. **Standards**: code follows `docs/standards.md`.
3. **Security**: secrets, role checks, input validation, prompt injection,
   PHI in logs.
4. **AI safety**: red-flag check, schema validation, fallback to
   `AI_SERVICE_UNAVAILABLE`, no PII in prompts.
5. **Data and migrations**: constraints live in Alembic migrations, no
   destructive or non-reversible change without justification, UTC
   storage, overlap constraints intact.
6. **Docs-only changes**: a change to `docs/openapi.yaml`, `docs/spec.md` or
   `docs/standards.md` is checked for contradictions with the other docs
   (openapi wins on any conflict).

## Before a milestone is tagged

Review the milestone's commits against every pass above, CI must be green
on `main`, and a Blocker finding must be fixed before the `m<N>-complete`
tag is created (see `docs/standards.md` → Commits and milestone tags).

## Severity

- **Blocker**: wrong clinical routing, missed emergency, secret leak,
  broken rule → must fix before the milestone is tagged.
- **Major**: missing test, contract mismatch → fix or justify in the commit message.
- **Minor**: naming, style → optional.

## Exclusions

- Generated files and lock files.
- Seed data is excluded **unless** it holds policy defaults
  (`ClinicSettings`) or the red-flag keyword list, which are reviewed like
  code.
