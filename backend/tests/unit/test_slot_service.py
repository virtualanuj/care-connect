import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.domain.errors import NotFound, ValidationFailed
from app.domain.models import (
    Availability,
    DayOfWeek,
    Doctor,
    Specialty,
)
from app.services.slot_service import SlotService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    InMemoryAppointmentRepository,
    InMemoryAvailabilityRepository,
    InMemoryClinicSettingsRepository,
    InMemoryDoctorRepository,
    InMemorySpecialtyRepository,
)

SUNDAY_NOON = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
MONDAY = date(2026, 3, 2)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, 2, hour, minute, tzinfo=UTC)


class Setup:
    def __init__(self) -> None:
        self.specialties = InMemorySpecialtyRepository()
        self.doctors = InMemoryDoctorRepository()
        self.availability = InMemoryAvailabilityRepository()
        self.appointments = InMemoryAppointmentRepository()
        self.settings = InMemoryClinicSettingsRepository()
        self.clock = FixedClock(SUNDAY_NOON)
        self.service = SlotService(
            self.specialties,
            self.doctors,
            self.availability,
            self.appointments,
            self.settings,
            self.clock,
        )
        self.general = Specialty(uuid.uuid4(), "General", 20)
        self.cardio = Specialty(uuid.uuid4(), "Cardiology", 30)
        self.specialties.add(self.general)
        self.specialties.add(self.cardio)
        self.d1 = self.add_doctor("Dr A", self.general, 20)
        self.d2 = self.add_doctor("Dr B", self.general, 20)
        self.cardiologist = self.add_doctor("Dr C", self.cardio, 30)
        self.inactive = self.add_doctor("Dr Off", self.general, 20, active=False)

    def add_doctor(
        self, name: str, specialty: Specialty, minutes: int, active: bool = True
    ) -> Doctor:
        doctor = Doctor(uuid.uuid4(), uuid.uuid4(), name, specialty.id, minutes, active)
        self.doctors.add(doctor)
        self.availability.add_rule(
            Availability(uuid.uuid4(), doctor.id, DayOfWeek.MONDAY, time(9), time(10))
        )
        return doctor

    def search(self, **kwargs):  # type: ignore[no-untyped-def]
        params = {
            "doctor_id": None,
            "specialty_id": None,
            "day": MONDAY,
            "include_emergency": False,
        }
        return self.service.search(**{**params, **kwargs})


@pytest.fixture
def s() -> Setup:
    return Setup()


def start_hm(slots) -> list[str]:  # type: ignore[no-untyped-def]
    return [x.start_time.strftime("%H:%M") for x in slots]


def test_a_doctor_search_hides_the_held_back_last_slot_by_default(s: Setup) -> None:
    slots = s.search(doctor_id=s.d1.id)

    assert start_hm(slots) == ["09:00", "09:20"]
    assert all(not x.is_emergency for x in slots)


def test_include_emergency_returns_the_held_slot_flagged_as_emergency(s: Setup) -> None:
    slots = s.search(doctor_id=s.d1.id, include_emergency=True)

    assert start_hm(slots) == ["09:00", "09:20", "09:40"]
    assert [x.is_emergency for x in slots] == [False, False, True]


def test_slots_carry_the_doctor_specialty_and_utc_times(s: Setup) -> None:
    (first, *_) = s.search(doctor_id=s.d1.id)

    assert (first.doctor_id, first.specialty_id) == (s.d1.id, s.general.id)
    assert (first.start_time, first.end_time) == (at(9), at(9, 20))


def test_exactly_one_of_doctor_or_specialty_is_required(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.search()
    with pytest.raises(ValidationFailed):
        s.search(doctor_id=s.d1.id, specialty_id=s.general.id)


def test_specialty_search_returns_every_active_doctors_slots_as_a_choice(s: Setup) -> None:
    slots = s.search(specialty_id=s.general.id)

    assert {x.doctor_id for x in slots} == {s.d1.id, s.d2.id}  # both doctors offered
    assert s.inactive.id not in {x.doctor_id for x in slots}
    assert s.cardiologist.id not in {x.doctor_id for x in slots}
    assert len(slots) == 4  # two regular slots per doctor; nothing was auto-selected


def test_specialty_results_are_ordered_by_start_time_then_doctor(s: Setup) -> None:
    slots = s.search(specialty_id=s.general.id)

    keys = [(x.start_time, str(x.doctor_id)) for x in slots]
    assert keys == sorted(keys)
    assert slots[0].start_time == slots[1].start_time  # same start, two doctors


def test_doctors_use_their_own_slot_length(s: Setup) -> None:
    slots = s.search(doctor_id=s.cardiologist.id, include_emergency=True)

    assert start_hm(slots) == ["09:00", "09:30"]
    assert [x.is_emergency for x in slots] == [False, True]


def test_booked_slots_disappear_from_results(s: Setup) -> None:
    from tests.unit.test_appointment_service import book_directly

    book_directly(s.appointments, s.d1.id, at(9, 20), at(9, 40))

    assert start_hm(s.search(doctor_id=s.d1.id)) == ["09:00"]
    assert start_hm(s.search(doctor_id=s.d2.id)) == ["09:00", "09:20"]


def test_a_cancelled_appointment_frees_its_slot_again(s: Setup) -> None:
    from app.domain.models import AppointmentStatus
    from tests.unit.test_appointment_service import book_directly

    book_directly(s.appointments, s.d1.id, at(9, 0), at(9, 20), status=AppointmentStatus.CANCELLED)

    assert start_hm(s.search(doctor_id=s.d1.id)) == ["09:00", "09:20"]


def test_the_held_slot_is_released_within_sixty_minutes_of_its_start(s: Setup) -> None:
    s.clock.set(at(8, 40))  # 09:40 is exactly 60 minutes away

    slots = s.search(doctor_id=s.d1.id)

    assert start_hm(slots) == ["09:00", "09:20", "09:40"]
    assert all(not x.is_emergency for x in slots)


def test_past_slots_are_never_returned(s: Setup) -> None:
    s.clock.set(at(9, 20))

    assert start_hm(s.search(doctor_id=s.d1.id, include_emergency=True)) == ["09:40"]
    s.clock.set(at(9) + timedelta(days=1))
    assert s.search(doctor_id=s.d1.id) == []


def test_the_holdback_count_comes_from_clinic_settings(s: Setup) -> None:
    s.settings.settings.emergency_slots_per_doctor_per_day = 0
    assert start_hm(s.search(doctor_id=s.d1.id)) == ["09:00", "09:20", "09:40"]

    s.settings.settings.emergency_slots_per_doctor_per_day = 2
    assert start_hm(s.search(doctor_id=s.d1.id)) == ["09:00"]


def test_the_clinic_time_zone_shifts_slots_and_defines_the_date(s: Setup) -> None:
    s.settings.settings.clinic_timezone = "Asia/Kolkata"

    slots = s.search(doctor_id=s.d1.id, include_emergency=True)

    assert slots[0].start_time == datetime(2026, 3, 2, 3, 30, tzinfo=UTC)  # 09:00 IST


def test_an_inactive_doctor_has_no_slots_and_unknown_ids_are_not_found(s: Setup) -> None:
    assert s.search(doctor_id=s.inactive.id) == []
    with pytest.raises(NotFound):
        s.search(doctor_id=uuid.uuid4())
    with pytest.raises(NotFound):
        s.search(specialty_id=uuid.uuid4())
