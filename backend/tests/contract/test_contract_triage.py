"""Triage endpoint responses must match docs/openapi.yaml."""

import uuid

from app.domain.errors import AiServiceUnavailable
from app.domain.models import Role, TriageModelOutput, Urgency
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def z(hour: int, minute: int = 0) -> str:
    return f"2026-03-02T{hour:02d}:{minute:02d}:00Z"


def test_triage_endpoints(booking_harness: ApiHarness, assert_contract: ContractCheck) -> None:
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
    h.llm.output = TriageModelOutput(Urgency.URGENT, "General", 0.7)

    def triage(text: str, patient: dict | None = None, headers=None):  # type: ignore[no-untyped-def,type-arg]
        return c.post(
            f"{API}/patients/{(patient or asha)['id']}/triage",
            json={"reportedSymptoms": text},
            headers=headers or admin,
        )

    created = triage("high fever")
    assert_contract(created)  # 201
    assert_contract(triage("crushing chest pain"))  # 201 red flag
    assert_contract(triage("", headers=admin))  # 400
    assert_contract(triage("cough", patient={"id": str(uuid.uuid4())}))  # 404
    assert_contract(
        c.post(f"{API}/patients/{asha['id']}/triage", json={"reportedSymptoms": "x"})
    )  # 401
    h.llm.output = AiServiceUnavailable("down")
    assert_contract(triage("sore throat"))  # 503
    h.llm.output = TriageModelOutput(Urgency.URGENT, "General", 0.7)

    assert_contract(c.get(f"{API}/patients/{asha['id']}/triage", headers=admin))
    assert_contract(c.get(f"{API}/patients/{uuid.uuid4()}/triage", headers=admin))  # 404

    triage_id = created.json()["id"]
    booking = c.post(
        f"{API}/appointments",
        json={
            "doctorId": doctor["id"],
            "patientId": asha["id"],
            "startTime": z(9, 0),
            "triageResultId": triage_id,
        },
        headers=admin,
    ).json()
    assert_contract(c.get(f"{API}/appointments/{booking['id']}/triage", headers=admin))
    assert_contract(c.get(f"{API}/appointments/{uuid.uuid4()}/triage", headers=admin))  # 404

    body = {"overriddenUrgency": "routine", "overrideReason": "reviewed"}
    override = f"{API}/triage-results/{triage_id}/override"
    assert_contract(c.patch(override, json=body, headers=admin))  # 200
    assert_contract(c.patch(override, json={"overriddenUrgency": "routine"}, headers=admin))  # 400
    assert_contract(
        c.patch(f"{API}/triage-results/{uuid.uuid4()}/override", json=body, headers=admin)
    )
    other = triage("cough").json()
    assert_contract(
        c.patch(f"{API}/triage-results/{other['id']}/override", json=body, headers=doc)
    )  # 403

    # An emergency booking by triage returns the documented Appointment shape.
    h.llm.output = TriageModelOutput(Urgency.EMERGENCY, "General", 0.9)
    emergency = triage("collapsed").json()
    assert_contract(
        c.post(
            f"{API}/appointments",
            json={
                "doctorId": doctor["id"],
                "patientId": asha["id"],
                "startTime": z(9, 40),
                "triageResultId": emergency["id"],
                "emergencyJustification": "triage",
            },
            headers=admin,
        )
    )
