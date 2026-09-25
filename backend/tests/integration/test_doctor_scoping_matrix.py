"""Every appointment-scoped route x {anonymous, other doctor, own doctor, front-desk}.

Complements test_permissions.py (which uses unknown ids): here the records are real, so the
ownership rule of spec.md section 1 is exercised on every route that takes an appointment id.
"""

import pytest

from app.domain.models import TriageModelOutput, Urgency
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z

pytestmark = pytest.mark.integration

# (method, path suffix, body); whole-appointment operations a doctor may only do on their own.
SCOPED: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "", None),
    ("GET", "/triage", None),
    ("GET", "/summary", None),
    ("POST", "/summary", None),
    ("GET", "/visit-note", None),
    ("PUT", "/visit-note", {"doctorNotes": "n"}),
    ("POST", "/visit-note/draft", None),
    ("POST", "/visit-note/finalize", {"finalSummary": "s"}),
    ("POST", "/check-in", None),
    ("POST", "/start-consultation", None),
    ("POST", "/complete", None),
    ("POST", "/no-show", None),
    ("POST", "/cancel", None),
    ("POST", "/force-cancel", {"reason": "r"}),
    ("POST", "/reschedule", {"newStartTime": "2026-03-02T09:20:00Z"}),
    ("POST", "/follow-up", {"startTime": "2026-03-09T09:00:00Z"}),
]


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    booking_harness.llm.output = TriageModelOutput(Urgency.ROUTINE, "General", 0.8)
    return Ctx(booking_harness)


# Role rules that are stricter than plain ownership (spec.md section 1 and openapi.yaml).
FRONT_DESK_ONLY = {"/force-cancel"}  # doctors never force-cancel, even their own visits
DOCTOR_ONLY = {"/visit-note/finalize"}  # front-desk never finalizes a visit summary


@pytest.mark.parametrize(("method", "suffix", "body"), SCOPED)
def test_only_the_appointments_own_doctor_and_front_desk_get_past_the_ownership_gate(
    ctx: Ctx, method: str, suffix: str, body: dict[str, object] | None
) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    url = f"{API}/appointments/{appointment['id']}{suffix}"
    other = ctx.h.headers_for("other@clinic.test")

    def call(headers: dict[str, str]) -> int:
        return ctx.c.request(method, url, json=body, headers=headers).status_code

    def passes_gate(headers: dict[str, str]) -> bool:
        # Past the gate a request may still fail on state or validation, never on identity.
        return call(headers) not in (401, 403)

    assert call({}) == 401
    assert call(other) == 403, "another doctor must be refused before anything happens"
    assert passes_gate(ctx.doc) is (suffix not in FRONT_DESK_ONLY)
    assert passes_gate(ctx.admin) is (suffix not in DOCTOR_ONLY)
