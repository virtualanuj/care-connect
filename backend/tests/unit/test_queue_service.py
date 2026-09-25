import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Doctor,
    Patient,
    Role,
    Specialty,
    User,
)
from app.services.queue_service import QueueService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    InMemoryAppointmentRepository,
    InMemoryClinicSettingsRepository,
    InMemoryDoctorRepository,
    InMemoryPatientRepository,
)

S = AppointmentStatus
# Late evening UTC on 2026-03-01 is already 2026-03-02 in Asia/Kolkata (UTC+05:30).
CLOCK_NOW = datetime(2026, 3, 1, 20, 0, tzinfo=UTC)


class CountingAppointments(InMemoryAppointmentRepository):
    def __init__(self) -> None:
        super().__init__()
        self.list_calls = 0

    def list(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.list_calls += 1
        return super().list(*args, **kwargs)


class CountingPatients(InMemoryPatientRepository):
    def __init__(self) -> None:
        super().__init__()
        self.get_many_calls = 0
        self.get_calls = 0

    def get(self, patient_id):  # type: ignore[no-untyped-def]
        self.get_calls += 1
        return super().get(patient_id)

    def get_many(self, ids):  # type: ignore[no-untyped-def]
        self.get_many_calls += 1
        return super().get_many(ids)


class Setup:
    def __init__(self) -> None:
        self.appointments = CountingAppointments()
        self.patients = CountingPatients()
        self.doctors = InMemoryDoctorRepository()
        self.settings = InMemoryClinicSettingsRepository()
        self.settings.settings.clinic_timezone = "Asia/Kolkata"
        self.clock = FixedClock(CLOCK_NOW)
        self.service = QueueService(
            self.appointments, self.patients, self.doctors, self.settings, self.clock
        )
        specialty = Specialty(uuid.uuid4(), "General", 20)
        self.admin = User(uuid.uuid4(), "fd@x.test", "FD", Role.FRONT_DESK_ADMIN, "h")
        self.doc_user = User(uuid.uuid4(), "d@x.test", "D", Role.DOCTOR, "h")
        self.other_user = User(uuid.uuid4(), "o@x.test", "O", Role.DOCTOR, "h")
        self.dan = Doctor(uuid.uuid4(), self.doc_user.id, "Dr Dan", specialty.id, 20)
        self.eve = Doctor(uuid.uuid4(), self.other_user.id, "Dr Eve", specialty.id, 20)
        self.doctors.add(self.dan)
        self.doctors.add(self.eve)
        self.asha = self.patient("Asha Rao", "+911")
        self.kiran = self.patient("Kiran Rao", "+912")

    def patient(self, name: str, phone: str) -> Patient:
        patient = Patient(uuid.uuid4(), name, phone, CLOCK_NOW)
        self.patients.add(patient)
        return patient

    def add(
        self,
        status: S,
        start: datetime,
        doctor: Doctor | None = None,
        patient: Patient | None = None,
        source: AppointmentSource = AppointmentSource.SCHEDULED,
    ) -> Appointment:
        appointment = Appointment(
            id=uuid.uuid4(),
            doctor_id=(doctor or self.dan).id,
            patient_id=(patient or self.asha).id,
            start_time=start,
            end_time=start + timedelta(minutes=20),
            status=status,
            source=source,
            is_emergency_slot=False,
            created_at=CLOCK_NOW,
        )
        self.appointments.items[appointment.id] = appointment
        return appointment


@pytest.fixture
def s() -> Setup:
    return Setup()


def at(hour: int, minute: int = 0, day: int = 2) -> datetime:
    """A UTC instant; 03:30 UTC on the 2nd is 09:00 in Kolkata."""
    return datetime(2026, 3, day, hour, 0, tzinfo=UTC) + timedelta(minutes=minute)


def ids(items) -> list[uuid.UUID]:  # type: ignore[no-untyped-def]
    return [i.appointment.id for i in items]


def test_each_status_lands_in_exactly_one_bucket(s: Setup) -> None:
    rows = {
        status: s.add(status, at(4, index * 20), patient=p)
        for index, (status, p) in enumerate(
            [
                (S.BOOKED, s.asha),
                (S.CHECKED_IN, s.kiran),
                (S.IN_CONSULTATION, s.patient("P3", "+913")),
                (S.COMPLETED, s.patient("P4", "+914")),
                (S.NO_SHOW, s.patient("P5", "+915")),
                (S.CANCELLED, s.patient("P6", "+916")),
            ]
        )
    }

    queue = s.service.get(s.admin, date(2026, 3, 2))

    assert ids(queue.booked) == [rows[S.BOOKED].id]
    assert ids(queue.checked_in) == [rows[S.CHECKED_IN].id]
    assert ids(queue.in_progress) == [rows[S.IN_CONSULTATION].id]
    assert ids(queue.completed) == [rows[S.COMPLETED].id]
    assert ids(queue.no_shows) == [rows[S.NO_SHOW].id]
    assert ids(queue.cancelled) == [rows[S.CANCELLED].id]
    every = [
        *queue.booked,
        *queue.checked_in,
        *queue.in_progress,
        *queue.completed,
        *queue.no_shows,
        *queue.cancelled,
    ]
    assert len(every) == len({i.appointment.id for i in every}) == 6  # no overlap between buckets


def test_walk_ins_appear_in_the_bucket_for_their_status_and_are_flagged(s: Setup) -> None:
    walk_in = s.add(S.CHECKED_IN, at(4, 0), source=AppointmentSource.WALK_IN)
    scheduled = s.add(S.CHECKED_IN, at(4, 20), patient=s.kiran)

    queue = s.service.get(s.admin, date(2026, 3, 2))

    flagged = {i.appointment.id: i.appointment.source for i in queue.checked_in}
    assert flagged == {
        walk_in.id: AppointmentSource.WALK_IN,
        scheduled.id: AppointmentSource.SCHEDULED,
    }
    assert queue.booked == []


def test_items_carry_patient_and_doctor_names_and_are_sorted_by_start_time(s: Setup) -> None:
    late = s.add(S.BOOKED, at(5, 0), doctor=s.eve, patient=s.kiran)
    early = s.add(S.BOOKED, at(4, 0))

    queue = s.service.get(s.admin, date(2026, 3, 2))

    assert ids(queue.booked) == [early.id, late.id]
    assert (queue.booked[0].patient_name, queue.booked[0].doctor_name) == ("Asha Rao", "Dr Dan")
    assert (queue.booked[1].patient_name, queue.booked[1].doctor_name) == ("Kiran Rao", "Dr Eve")


def test_the_day_is_the_clinic_local_day_not_the_utc_day(s: Setup) -> None:
    # 2026-03-01 20:00 UTC = 2026-03-02 01:30 in Kolkata -> belongs to the 2nd, not the 1st.
    after_local_midnight = s.add(S.BOOKED, datetime(2026, 3, 1, 20, 0, tzinfo=UTC))
    before_local_midnight = s.add(
        S.BOOKED, datetime(2026, 3, 1, 18, 0, tzinfo=UTC), patient=s.kiran
    )

    second = s.service.get(s.admin, date(2026, 3, 2))
    first = s.service.get(s.admin, date(2026, 3, 1))

    assert ids(second.booked) == [after_local_midnight.id]
    assert ids(first.booked) == [before_local_midnight.id]


def test_the_default_date_is_today_in_the_clinic_time_zone(s: Setup) -> None:
    s.add(S.BOOKED, at(4, 0))  # 2026-03-02 local

    queue = s.service.get(s.admin, None)

    assert queue.day == date(2026, 3, 2)  # UTC clock says the 1st, the clinic says the 2nd
    assert len(queue.booked) == 1


def test_a_doctor_sees_only_their_own_appointments_and_a_doctor_without_a_profile_none(
    s: Setup,
) -> None:
    mine = s.add(S.BOOKED, at(4, 0))
    s.add(S.BOOKED, at(4, 20), doctor=s.eve, patient=s.kiran)
    stranger = User(uuid.uuid4(), "s@x.test", "S", Role.DOCTOR, "h")

    scoped = s.service.get(s.doc_user, date(2026, 3, 2))
    nothing = s.service.get(stranger, date(2026, 3, 2))

    assert ids(scoped.booked) == [mine.id]
    assert nothing.booked == []


def test_names_are_loaded_in_batches_not_one_query_per_appointment(s: Setup) -> None:
    for index in range(8):
        s.add(S.BOOKED, at(4, index * 2), patient=s.patient(f"P{index}", f"+9{index}00"))

    s.service.get(s.admin, date(2026, 3, 2))

    assert s.appointments.list_calls == 1
    assert s.patients.get_many_calls == 1
    assert s.patients.get_calls == 0


def test_an_empty_day_returns_six_empty_buckets(s: Setup) -> None:
    queue = s.service.get(s.admin, date(2026, 3, 2))

    assert (queue.booked, queue.checked_in, queue.in_progress) == ([], [], [])
    assert (queue.completed, queue.no_shows, queue.cancelled) == ([], [], [])
