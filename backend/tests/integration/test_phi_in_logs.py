"""No patient data may reach the logs or an error body, whatever the request does."""

import logging

import pytest

from app.domain.models import TriageModelOutput, Urgency
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z
from tests.integration.test_lifecycle_api import act

pytestmark = pytest.mark.integration

SECRETS = ["Zephyrina Quillfeather", "9123456780", "crushing purple rash", "secret clinical remark"]


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    booking_harness.llm.output = TriageModelOutput(Urgency.ROUTINE, "General", 0.8)
    return Ctx(booking_harness)


def test_names_phones_symptoms_and_notes_never_appear_in_logs_or_error_bodies(
    ctx: Ctx, caplog: pytest.LogCaptureFixture
) -> None:
    bodies: list[str] = []
    with caplog.at_level(logging.DEBUG):
        patient = ctx.post(
            "/patients", {"name": SECRETS[0], "phone": SECRETS[1], "email": "z@example.test"}
        ).json()
        bodies.append(str(ctx.post("/patients", {"name": SECRETS[0], "phone": SECRETS[1]}).json()))
        ctx.c.get(f"{API}/patients", params={"phone": SECRETS[1]}, headers=ctx.admin)
        ctx.post(f"/patients/{patient['id']}/triage", {"reportedSymptoms": SECRETS[2]})
        bodies.append(ctx.post(f"/patients/{patient['id']}/triage", {"reportedSymptoms": ""}).text)
        appointment = ctx.book(patient, z(9, 0), reportedSymptoms=SECRETS[2]).json()
        act(ctx, appointment, "check-in")
        act(ctx, appointment, "start-consultation")
        note_url = f"{API}/appointments/{appointment['id']}/visit-note"
        ctx.c.put(note_url, json={"doctorNotes": SECRETS[3]}, headers=ctx.doc)
        ctx.c.post(f"{note_url}/draft", headers=ctx.doc)
        ctx.h.llm.text_output = Exception(SECRETS[3])  # an unexpected failure carrying PHI
        bodies.append(ctx.c.post(f"{note_url}/draft", headers=ctx.doc).text)

    # The HTTP test client logs the URLs it calls; that is the test harness, not the server.
    server_records = [r for r in caplog.records if not r.name.startswith(("httpx", "httpcore"))]
    logged = "\n".join(f"{r.getMessage()} {r.exc_text or ''} {r.args!r}" for r in server_records)
    for secret in SECRETS:
        assert secret not in logged, f"{secret!r} leaked into the logs"
        assert all(secret not in body for body in bodies), f"{secret!r} leaked into an error body"
