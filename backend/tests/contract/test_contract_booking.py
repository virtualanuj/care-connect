"""Real responses of the slot and appointment endpoints must match docs/openapi.yaml."""

import uuid

from app.domain.models import Role
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def z(hour: int, minute: int = 0) -> str:
    return f"2026-03-02T{hour:02d}:{minute:02d}:00Z"


def test_slots_and_appointments(
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
    kiran = c.post(
        f"{API}/patients", json={"name": "Kiran", "phone": "9876543210"}, headers=admin
    ).json()

    # slots
    day = {"date": "2026-03-02"}
    assert_contract(c.get(f"{API}/slots", params={**day, "doctorId": doctor["id"]}, headers=admin))
    assert_contract(
        c.get(
            f"{API}/slots",
            params={**day, "doctorId": doctor["id"], "includeEmergency": "true"},
            headers=admin,
        )
    )
    assert_contract(
        c.get(f"{API}/slots", params={**day, "specialtyId": specialty["id"]}, headers=admin)
    )
    assert_contract(c.get(f"{API}/slots", params=day, headers=admin))  # 400
    assert_contract(
        c.get(f"{API}/slots", params={**day, "doctorId": str(uuid.uuid4())}, headers=admin)
    )  # 404
    assert_contract(c.get(f"{API}/slots", params={**day, "doctorId": doctor["id"]}))  # 401

    # booking
    book = {"doctorId": doctor["id"], "patientId": asha["id"], "startTime": z(9, 0)}
    created = c.post(f"{API}/appointments", json=book, headers=admin)
    assert_contract(created)  # 201
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "patientId": kiran["id"]}, headers=admin)
    )  # 409
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "startTime": z(9, 5)}, headers=admin)
    )  # 422
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "startTime": z(9, 40)}, headers=admin)
    )  # 422
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "startTime": "nope"}, headers=admin)
    )  # 400
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "patientId": str(uuid.uuid4())}, headers=admin)
    )  # 404
    assert_contract(
        c.post(f"{API}/appointments", json={**book, "startTime": z(9, 20)}, headers=doc)
    )  # 201 (own)

    # reads
    appointment_id = created.json()["id"]
    assert_contract(c.get(f"{API}/appointments", headers=admin))
    assert_contract(
        c.get(
            f"{API}/appointments", params={"date": "2026-03-02", "status": "booked"}, headers=admin
        )
    )
    assert_contract(
        c.get(f"{API}/appointments", params={"doctorId": str(uuid.uuid4())}, headers=doc)
    )  # 403
    assert_contract(c.get(f"{API}/appointments/{appointment_id}", headers=admin))
    assert_contract(c.get(f"{API}/appointments/{uuid.uuid4()}", headers=admin))  # 404
