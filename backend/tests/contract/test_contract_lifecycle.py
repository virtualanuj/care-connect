"""Lifecycle endpoint responses must match docs/openapi.yaml."""

import uuid
from datetime import UTC, datetime

from app.domain.models import Role
from tests.api_harness import ApiHarness
from tests.contract.conftest import ContractCheck

API = "/api/v1"


def z(hour: int, minute: int = 0) -> str:
    return f"2026-03-02T{hour:02d}:{minute:02d}:00Z"


def test_lifecycle_endpoints(booking_harness: ApiHarness, assert_contract: ContractCheck) -> None:
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
    patients = [
        c.post(f"{API}/patients", json={"name": n, "phone": "9876543210"}, headers=admin).json()
        for n in ("Asha", "Kiran", "Meera")
    ]

    def book(patient: dict, start: str) -> dict:  # type: ignore[type-arg]
        body = {"doctorId": doctor["id"], "patientId": patient["id"], "startTime": start}
        return c.post(f"{API}/appointments", json=body, headers=admin).json()  # type: ignore[no-any-return]

    def post(appointment: dict, action: str, body: dict | None = None, headers=None):  # type: ignore[no-untyped-def,type-arg]
        return c.post(
            f"{API}/appointments/{appointment['id']}/{action}", json=body, headers=headers or admin
        )

    walked = book(patients[0], z(9, 0))
    for step in ("check-in", "start-consultation", "complete"):
        assert_contract(post(walked, step))  # 200 each
    assert_contract(post(walked, "complete"))  # 409 invalid transition
    assert_contract(post({"id": str(uuid.uuid4())}, "check-in"))  # 404
    assert_contract(post(walked, "check-in", headers={}))  # 401

    assert_contract(post(walked, "follow-up", {"startTime": "2026-03-09T09:00:00Z"}))  # 201
    assert_contract(post(walked, "follow-up", {"startTime": "2026-03-09T09:05:00Z"}))  # 422
    fresh = book(patients[1], z(9, 20))
    assert_contract(post(fresh, "follow-up", {"startTime": "2026-03-09T09:20:00Z"}))  # 409

    assert_contract(post(fresh, "reschedule", {"newStartTime": z(9, 0)}))  # 409 slot taken
    assert_contract(post(fresh, "reschedule", {"newStartTime": "nope"}))  # 400
    assert_contract(post(fresh, "force-cancel", {"reason": "x"}, headers=doc))  # 403
    assert_contract(post(fresh, "force-cancel", {}))  # 400
    assert_contract(post(fresh, "cancel"))  # 200
    assert_contract(post(fresh, "cancel"))  # 409

    third = book(patients[2], z(9, 20))
    assert_contract(post(third, "no-show"))
    another = book(patients[1], z(9, 20))
    assert_contract(post(another, "reschedule", {"newStartTime": z(9, 20)}))  # 409 (own slot)
    assert_contract(post(another, "force-cancel", {"reason": "cleanup"}))  # 200

    late = book(patients[2], z(9, 20))
    h.clock.set(datetime(2026, 3, 2, 8, 30, tzinfo=UTC))
    admin_now = h.headers_for("admin@clinic.test")
    assert_contract(post(late, "cancel", headers=admin_now))  # 422 inside the cutoff
    assert_contract(post(late, "reschedule", {"newStartTime": z(9, 20)}, headers=admin_now))  # 422
