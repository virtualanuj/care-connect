import threading
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.adapters.postgres.appointment_repository import PostgresAppointmentRepository
from app.db.session import get_session_factory
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Role,
)
from tests.api_harness import ApiHarness

pytestmark = pytest.mark.integration
API = "/api/v1"
MONDAY = "2026-03-02"


def z(hour: int, minute: int = 0) -> str:
    return f"2026-03-02T{hour:02d}:{minute:02d}:00Z"


class Ctx:
    """Two doctors (Monday 09:00-10:00, 20-minute slots), two patients, an admin."""

    def __init__(self, h: ApiHarness) -> None:
        self.h = h
        self.c = h.client
        self.admin = h.admin_headers()
        self.doc_user = h.create_user("doc@clinic.test", Role.DOCTOR)
        self.other_user = h.create_user("other@clinic.test", Role.DOCTOR)
        self.doc = h.headers_for("doc@clinic.test")
        self.specialty = self.post(
            "/specialties", {"name": "General", "defaultSlotLengthMinutes": 20}
        ).json()
        self.doctor = self.make_doctor(self.doc_user.id, "Dr One")
        self.other = self.make_doctor(self.other_user.id, "Dr Two")
        self.asha = self.post("/patients", {"name": "Asha Rao", "phone": "9876543210"}).json()
        self.kiran = self.post("/patients", {"name": "Kiran Rao", "phone": "9876543210"}).json()

    def post(self, path: str, body: dict, headers: dict | None = None):  # type: ignore[no-untyped-def,type-arg]
        return self.c.post(f"{API}{path}", json=body, headers=headers or self.admin)

    def make_doctor(self, user_id: uuid.UUID, name: str) -> dict:  # type: ignore[type-arg]
        doctor = self.post(
            "/doctors", {"userId": str(user_id), "name": name, "specialtyId": self.specialty["id"]}
        ).json()
        rule = {"dayOfWeek": "monday", "startTime": "09:00", "endTime": "10:00"}
        assert self.post(f"/doctors/{doctor['id']}/availability", rule).status_code == 201
        return doctor  # type: ignore[no-any-return]

    def slots(self, **params: str):  # type: ignore[no-untyped-def]
        query = {"date": MONDAY, **params}
        return self.c.get(f"{API}/slots", params=query, headers=self.admin)

    def book(
        self,
        patient: dict,
        start: str,
        doctor: dict | None = None,
        headers: dict | None = None,
        **extra: object,
    ):  # type: ignore[no-untyped-def,type-arg]
        body = {
            "doctorId": (doctor or self.doctor)["id"],
            "patientId": patient["id"],
            "startTime": start,
            **extra,
        }
        return self.post("/appointments", body, headers)


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    return Ctx(booking_harness)


# ---- slot search -------------------------------------------------------------------------------


def test_doctor_slot_search_hides_the_held_back_last_slot_unless_asked(ctx: Ctx) -> None:
    regular = ctx.slots(doctorId=ctx.doctor["id"])
    with_emergency = ctx.slots(doctorId=ctx.doctor["id"], includeEmergency="true")

    assert regular.status_code == 200
    assert [s["startTime"] for s in regular.json()] == [
        "2026-03-02T09:00:00Z",
        "2026-03-02T09:20:00Z",
    ]
    assert [s["isEmergency"] for s in with_emergency.json()] == [False, False, True]
    first = regular.json()[0]
    assert first["doctorId"] == ctx.doctor["id"]
    assert first["specialtyId"] == ctx.specialty["id"]
    assert first["endTime"] == "2026-03-02T09:20:00Z"


def test_specialty_search_returns_every_doctors_slots_as_a_choice(ctx: Ctx) -> None:
    slots = ctx.slots(specialtyId=ctx.specialty["id"]).json()

    assert {s["doctorId"] for s in slots} == {ctx.doctor["id"], ctx.other["id"]}
    assert len(slots) == 4


@pytest.mark.parametrize(
    "params",
    [
        {},  # neither doctor nor specialty
        {"doctorId": "x", "specialtyId": "y"},
        {"doctorId": "not-a-uuid"},
    ],
)
def test_slot_search_input_errors_are_400(ctx: Ctx, params: dict[str, str]) -> None:
    response = ctx.slots(**params)

    assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")


def test_slot_search_requires_a_valid_date_and_known_ids(ctx: Ctx) -> None:
    no_date = ctx.c.get(f"{API}/slots", params={"doctorId": ctx.doctor["id"]}, headers=ctx.admin)
    bad_date = ctx.slots(doctorId=ctx.doctor["id"], date="tomorrow")
    unknown_doctor = ctx.slots(doctorId=str(uuid.uuid4()))
    unknown_specialty = ctx.slots(specialtyId=str(uuid.uuid4()))

    assert no_date.status_code == 400
    assert bad_date.status_code == 400
    assert unknown_doctor.status_code == 404
    assert unknown_specialty.status_code == 404


# ---- booking -----------------------------------------------------------------------------------


def test_booking_a_slot_creates_the_appointment_and_removes_the_slot(ctx: Ctx) -> None:
    response = ctx.book(ctx.asha, z(9, 20), reportedSymptoms="cough")

    assert response.status_code == 201
    body = response.json()
    assert (body["startTime"], body["endTime"]) == (z(9, 20), z(9, 40))
    assert (body["status"], body["source"], body["isEmergencySlot"]) == (
        "booked",
        "scheduled",
        False,
    )
    assert body["reportedSymptoms"] == "cough"
    assert body["cancelledAt"] is None
    remaining = ctx.slots(doctorId=ctx.doctor["id"]).json()
    assert [s["startTime"] for s in remaining] == [z(9, 0)]


def test_a_walk_in_source_is_stored(ctx: Ctx) -> None:
    assert ctx.book(ctx.asha, z(9, 0), source="walk_in").json()["source"] == "walk_in"


def test_booking_the_same_slot_again_is_409_slot_already_booked(ctx: Ctx) -> None:
    ctx.book(ctx.asha, z(9, 0))

    again = ctx.book(ctx.kiran, z(9, 0))

    assert (again.status_code, again.json()["code"]) == (409, "SLOT_ALREADY_BOOKED")


def test_overlapping_the_same_patient_with_another_doctor_is_409_patient_already_booked(
    ctx: Ctx,
) -> None:
    ctx.book(ctx.asha, z(9, 0))

    clash = ctx.book(ctx.asha, z(9, 0), doctor=ctx.other)

    assert (clash.status_code, clash.json()["code"]) == (409, "PATIENT_ALREADY_BOOKED")


@pytest.mark.parametrize("start", [z(9, 5), z(8, 40), z(10, 0), "2026-03-03T09:00:00Z"])
def test_a_time_that_is_not_a_generated_slot_is_422_invalid_slot(ctx: Ctx, start: str) -> None:
    response = ctx.book(ctx.asha, start)

    assert (response.status_code, response.json()["code"]) == (422, "INVALID_SLOT")


def test_a_slot_in_the_past_is_422_invalid_slot(ctx: Ctx) -> None:
    ctx.h.clock.set(datetime(2026, 3, 2, 9, 10, tzinfo=UTC))
    ctx.admin = ctx.h.headers_for("admin@clinic.test")  # the old token has expired by now

    response = ctx.book(ctx.asha, z(9, 0))

    assert (response.status_code, response.json()["code"]) == (422, "INVALID_SLOT")


def test_the_held_back_emergency_slot_needs_a_justification(ctx: Ctx) -> None:
    response = ctx.book(ctx.asha, z(9, 40))

    assert (response.status_code, response.json()["code"]) == (
        422,
        "EMERGENCY_JUSTIFICATION_REQUIRED",
    )


@pytest.mark.parametrize(
    "override",
    [{"startTime": "2026-03-02T09:00:00"}, {"patientId": "nope"}, {"source": "carrier_pigeon"}],
)
def test_malformed_booking_bodies_are_400(ctx: Ctx, override: dict[str, str]) -> None:
    body = {
        "doctorId": ctx.doctor["id"],
        "patientId": ctx.asha["id"],
        "startTime": z(9),
        **override,
    }

    response = ctx.post("/appointments", body)

    assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")


def test_unknown_patient_or_doctor_is_404(ctx: Ctx) -> None:
    ghost = {"id": str(uuid.uuid4())}

    assert ctx.book(ghost, z(9)).status_code == 404
    assert ctx.book(ctx.asha, z(9), doctor=ghost).status_code == 404


def test_a_doctor_books_only_with_themselves(ctx: Ctx) -> None:
    own = ctx.book(ctx.asha, z(9, 0), headers=ctx.doc)
    other = ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other, headers=ctx.doc)

    assert own.status_code == 201
    assert (other.status_code, other.json()["code"]) == (403, "FORBIDDEN")


def test_the_availability_time_zone_follows_clinic_settings(ctx: Ctx) -> None:
    ctx.c.patch(
        f"{API}/clinic-settings", json={"clinicTimezone": "Asia/Kolkata"}, headers=ctx.admin
    )

    slots = ctx.slots(doctorId=ctx.doctor["id"]).json()

    assert slots[0]["startTime"] == "2026-03-02T03:30:00Z"  # 09:00 in Kolkata


# ---- reads -------------------------------------------------------------------------------------


def test_get_and_list_appointments_with_filters_and_pagination(ctx: Ctx) -> None:
    a = ctx.book(ctx.asha, z(9, 0)).json()
    b = ctx.book(ctx.kiran, z(9, 20)).json()
    c = ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other).json()

    assert ctx.c.get(f"{API}/appointments/{a['id']}", headers=ctx.admin).json()["id"] == a["id"]
    everything = ctx.c.get(f"{API}/appointments", headers=ctx.admin).json()
    assert (everything["total"], everything["page"], everything["pageSize"]) == (3, 1, 20)
    starts = [x["startTime"] for x in everything["items"]]
    assert starts == sorted(starts)  # ordered by start time
    assert everything["items"][-1]["id"] == b["id"]  # the 09:20 booking comes last
    assert {x["id"] for x in everything["items"]} == {a["id"], b["id"], c["id"]}
    by_doctor = ctx.c.get(
        f"{API}/appointments", params={"doctorId": ctx.doctor["id"]}, headers=ctx.admin
    ).json()
    assert {x["id"] for x in by_doctor["items"]} == {a["id"], b["id"]}
    by_patient = ctx.c.get(
        f"{API}/appointments", params={"patientId": ctx.kiran["id"]}, headers=ctx.admin
    ).json()
    assert {x["id"] for x in by_patient["items"]} == {b["id"], c["id"]}
    by_day = ctx.c.get(f"{API}/appointments", params={"date": MONDAY}, headers=ctx.admin).json()
    other_day = ctx.c.get(
        f"{API}/appointments", params={"date": "2026-03-03"}, headers=ctx.admin
    ).json()
    assert (by_day["total"], other_day["total"]) == (3, 0)
    by_status = ctx.c.get(
        f"{API}/appointments", params={"status": "cancelled"}, headers=ctx.admin
    ).json()
    assert by_status["total"] == 0
    paged = ctx.c.get(
        f"{API}/appointments", params={"page": 2, "pageSize": 2}, headers=ctx.admin
    ).json()
    assert (paged["total"], len(paged["items"])) == (3, 1)
    assert ctx.c.get(f"{API}/appointments/{uuid.uuid4()}", headers=ctx.admin).status_code == 404
    assert (
        ctx.c.get(f"{API}/appointments", params={"status": "nope"}, headers=ctx.admin).status_code
        == 400
    )


def test_a_doctor_sees_only_their_own_appointments(ctx: Ctx) -> None:
    mine = ctx.book(ctx.asha, z(9, 0)).json()
    theirs = ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other).json()

    listing = ctx.c.get(f"{API}/appointments", headers=ctx.doc).json()
    forbidden_filter = ctx.c.get(
        f"{API}/appointments", params={"doctorId": ctx.other["id"]}, headers=ctx.doc
    )

    assert [x["id"] for x in listing["items"]] == [mine["id"]]
    assert ctx.c.get(f"{API}/appointments/{mine['id']}", headers=ctx.doc).status_code == 200
    assert ctx.c.get(f"{API}/appointments/{theirs['id']}", headers=ctx.doc).status_code == 403
    assert forbidden_filter.status_code == 403


# ---- concurrency through the API ---------------------------------------------------------------


def test_two_simultaneous_requests_for_one_slot_yield_one_201_and_one_409(ctx: Ctx) -> None:
    barrier = threading.Barrier(2)
    statuses: list[int] = [0, 0]
    patients = [ctx.asha, ctx.kiran]

    def worker(i: int) -> None:
        client = TestClient(ctx.h.app, raise_server_exceptions=False)
        body = {"doctorId": ctx.doctor["id"], "patientId": patients[i]["id"], "startTime": z(9, 0)}
        barrier.wait()
        statuses[i] = client.post(f"{API}/appointments", json=body, headers=ctx.admin).status_code

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(statuses) == [201, 409]
    assert ctx.c.get(f"{API}/appointments", headers=ctx.admin).json()["total"] == 1


# ---- availability changes now respect real appointments ---------------------------------------


def rules_url(ctx: Ctx) -> str:
    return f"{API}/doctors/{ctx.doctor['id']}/availability"


def test_removing_availability_that_a_booking_depends_on_is_409(ctx: Ctx) -> None:
    ctx.book(ctx.asha, z(9, 0))
    rule_id = ctx.c.get(rules_url(ctx), headers=ctx.admin).json()[0]["id"]

    response = ctx.c.delete(f"{rules_url(ctx)}/{rule_id}", headers=ctx.admin)

    assert (response.status_code, response.json()["code"]) == (
        409,
        "AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS",
    )
    assert len(ctx.c.get(rules_url(ctx), headers=ctx.admin).json()) == 1


def test_removing_availability_is_fine_when_the_only_appointment_is_cancelled(ctx: Ctx) -> None:
    cancelled = Appointment(
        id=uuid.uuid4(),
        doctor_id=uuid.UUID(ctx.doctor["id"]),
        patient_id=uuid.UUID(ctx.asha["id"]),
        start_time=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
        end_time=datetime(2026, 3, 2, 9, 20, tzinfo=UTC),
        status=AppointmentStatus.CANCELLED,
        source=AppointmentSource.SCHEDULED,
        is_emergency_slot=False,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    with get_session_factory()() as session:
        PostgresAppointmentRepository(session).add(cancelled)
        session.commit()
    rule_id = ctx.c.get(rules_url(ctx), headers=ctx.admin).json()[0]["id"]

    assert ctx.c.delete(f"{rules_url(ctx)}/{rule_id}", headers=ctx.admin).status_code == 204


def test_a_doctor_with_upcoming_appointments_cannot_be_deactivated(ctx: Ctx) -> None:
    ctx.book(ctx.asha, z(9, 0))

    response = ctx.c.patch(
        f"{API}/doctors/{ctx.doctor['id']}", json={"active": False}, headers=ctx.admin
    )

    assert (response.status_code, response.json()["code"]) == (
        409,
        "AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS",
    )
    still_active = ctx.c.get(f"{API}/doctors/{ctx.doctor['id']}", headers=ctx.admin).json()[
        "active"
    ]
    assert still_active is True
    assert ctx.slots(doctorId=ctx.doctor["id"]).json()  # remaining slots stay bookable
