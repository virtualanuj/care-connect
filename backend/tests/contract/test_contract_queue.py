"""The queue endpoint and emergency booking responses must match docs/openapi.yaml."""

from app.domain.models import Role
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def test_queue_and_emergency_booking(
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

    def emergency(**extra: object):  # type: ignore[no-untyped-def]
        body = {
            "doctorId": doctor["id"],
            "patientId": asha["id"],
            "startTime": "2026-03-02T09:40:00Z",
            **extra,
        }
        return c.post(f"{API}/appointments", json=body, headers=extra.pop("headers", admin))  # type: ignore[arg-type]

    assert_contract(emergency())  # 422 justification required
    assert_contract(emergency(emergencyJustification="front_desk_judgment"))  # 422 reason
    assert_contract(emergency(emergencyJustification="triage"))  # 422 not authorized
    doctor_try = c.post(
        f"{API}/appointments",
        json={
            "doctorId": doctor["id"],
            "patientId": asha["id"],
            "startTime": "2026-03-02T09:40:00Z",
            "emergencyJustification": "front_desk_judgment",
            "emergencyReason": "urgent",
        },
        headers=doc,
    )
    assert_contract(doctor_try)  # 403
    assert_contract(
        emergency(
            emergencyJustification="front_desk_judgment",
            emergencyReason="Chest pain",
            source="walk_in",
        )
    )  # 201

    assert_contract(c.get(f"{API}/queue", params={"date": "2026-03-02"}, headers=admin))
    assert_contract(c.get(f"{API}/queue", headers=admin))
    assert_contract(c.get(f"{API}/queue", params={"date": "soon"}, headers=admin))  # 400
    assert_contract(c.get(f"{API}/queue", params={"date": "2026-03-02"}))  # 401
