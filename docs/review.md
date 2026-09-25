# Review policy

Applies to every pull request, for both AI and human reviewers.

## Passes

1. **Correctness**: behaviour matches `docs/spec.md`; every changed rule
   has a test.
2. **Standards**: code follows `docs/standards.md`.
3. **Security**: secrets, role checks, input validation, prompt injection.
4. **AI safety**: red-flag check, schema validation, fallback to
   `UNAVAILABLE`, no PII in prompts.

## Severity

- **Blocker**: wrong clinical routing, missed emergency, secret leak,
  broken rule → must fix before merge.
- **Major**: missing test, contract mismatch → fix or justify in the PR.
- **Minor**: naming, style → optional.

## Exclusions

- Generated files, lock files, seed data.
