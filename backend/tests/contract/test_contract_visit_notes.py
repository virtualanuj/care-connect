"""Summary and visit-note responses must match docs/openapi.yaml."""

from app.domain.errors import AiServiceUnavailable
from app.domain.models import Role
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def test_summary_and_visit_note_endpoints(
    booking_harness: ApiHarness, assert_contract: ContractCheck
) -> None:
    h = booking_harness
    c = h.client
    admin = h.admin_headers()
    doctor_user = h.create_user("doc@clinic.test", Role.DOCTOR)
    doc = h.headers_for("doc@clinic.test")
    specialty = c.post(
        f"{API}/specialties",
        json={"name": "General", "defaultSlotLengthMinutes": 20},
        headers=admin,
    ).json()
    doctor = c.post(
        f"{API}/doctors",
        json={"userId": str(doctor_user.id), "name": "Dr", "specialtyId": specialty["id"]},
        headers=admin,
    ).json()
    c.post(
        f"{API}/doctors/{doctor['id']}/availability",
        json={"dayOfWeek": "monday", "startTime": "09:00", "endTime": "10:00"},
        headers=admin,
    )
    asha = c.post(
        f"{API}/patients", json={"name": "Asha", "phone": "9876543210"}, headers=admin
    ).json()
    appointment = c.post(
        f"{API}/appointments",
        json={
            "doctorId": doctor["id"],
            "patientId": asha["id"],
            "startTime": "2026-03-02T09:00:00Z",
        },
        headers=admin,
    ).json()
    base = f"{API}/appointments/{appointment['id']}"

    assert_contract(c.get(f"{base}/summary", headers=doc))  # 404
    assert_contract(c.post(f"{base}/summary", headers=doc))  # 200
    assert_contract(c.get(f"{base}/summary", headers=doc))  # 200
    h.llm.text_output = AiServiceUnavailable("down")
    assert_contract(c.post(f"{base}/summary", headers=doc))  # 503
    h.llm.text_output = "Draft."

    assert_contract(c.get(f"{base}/visit-note", headers=doc))  # 404
    assert_contract(c.put(f"{base}/visit-note", json={"doctorNotes": "n"}, headers=doc))  # 409
    for step in ("check-in", "start-consultation"):
        c.post(f"{base}/{step}", headers=admin)
    assert_contract(c.post(f"{base}/visit-note/draft", headers=doc))  # 422
    assert_contract(c.put(f"{base}/visit-note", json={"doctorNotes": ""}, headers=doc))  # 400
    assert_contract(c.put(f"{base}/visit-note", json={"doctorNotes": "Cough."}, headers=doc))
    assert_contract(c.post(f"{base}/visit-note/draft", headers=doc))  # 200
    assert_contract(
        c.post(f"{base}/visit-note/finalize", json={"finalSummary": "s"}, headers=admin)
    )  # 403
    assert_contract(c.post(f"{base}/visit-note/finalize", json={"finalSummary": "s"}, headers=doc))
    assert_contract(
        c.post(f"{base}/visit-note/finalize", json={"finalSummary": "s"}, headers=doc)
    )  # 409
    assert_contract(c.get(f"{base}/visit-note", headers=admin))
