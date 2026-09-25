import uuid
from datetime import timedelta

import pytest

from app.domain.errors import (
    AvailabilityConflictsWithAppointments,
    DoctorAlreadyExists,
    Forbidden,
    NotFound,
    SpecialtyAlreadyExists,
    ValidationFailed,
)
from app.domain.models import Role, Specialty, User
from app.services.doctor_service import DoctorService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    FakeAppointmentQuery,
    InMemoryDoctorRepository,
    InMemorySpecialtyRepository,
    InMemoryUserRepository,
)
from tests.unit.test_audit_service import START


class Setup:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.specialties = InMemorySpecialtyRepository()
        self.doctors = InMemoryDoctorRepository()
        self.appointments = FakeAppointmentQuery()
        self.clock = FixedClock(START)
        self.service = DoctorService(
            self.users, self.specialties, self.doctors, self.appointments, self.clock
        )
        self.admin = self.add_user("admin@x.test", Role.FRONT_DESK_ADMIN)
        self.doc_user = self.add_user("doc@x.test", Role.DOCTOR)
        self.other_user = self.add_user("other@x.test", Role.DOCTOR)
        self.general = Specialty(uuid.uuid4(), "General Medicine", 20)
        self.cardio = Specialty(uuid.uuid4(), "Cardiology", 30)
        self.specialties.add(self.general)
        self.specialties.add(self.cardio)

    def add_user(self, email: str, role: Role) -> User:
        user = User(uuid.uuid4(), email, email, role, "h")
        self.users.add(user)
        return user


@pytest.fixture
def s() -> Setup:
    return Setup()


# ---- specialties -------------------------------------------------------------------------------


def test_front_desk_creates_and_lists_specialties_but_doctors_cannot_create(s: Setup) -> None:
    created = s.service.create_specialty(s.admin, "Dermatology", 15)

    assert created.default_slot_length_minutes == 15
    assert "Dermatology" in [x.name for x in s.service.list_specialties()]
    with pytest.raises(Forbidden):
        s.service.create_specialty(s.doc_user, "Nope", 15)


def test_specialty_name_must_be_unique_ignoring_case_and_slot_length_at_least_5(s: Setup) -> None:
    with pytest.raises(SpecialtyAlreadyExists):
        s.service.create_specialty(s.admin, "cardiology", 20)
    with pytest.raises(ValidationFailed):
        s.service.create_specialty(s.admin, "Tiny", 4)


def test_front_desk_updates_a_specialty_and_doctors_cannot(s: Setup) -> None:
    updated = s.service.update_specialty(s.admin, s.general.id, name="Family Medicine")

    assert updated.name == "Family Medicine"
    with pytest.raises(Forbidden):
        s.service.update_specialty(s.doc_user, s.general.id, name="X")
    with pytest.raises(NotFound):
        s.service.update_specialty(s.admin, uuid.uuid4(), name="X")


# ---- doctors -----------------------------------------------------------------------------------


def test_created_doctor_inherits_the_specialty_default_slot_length(s: Setup) -> None:
    doctor = s.service.create_doctor(s.admin, s.doc_user.id, "Dr Doc", s.cardio.id, None)

    assert doctor.slot_length_minutes == 30
    assert doctor.active is True


def test_explicit_slot_length_overrides_the_default(s: Setup) -> None:
    doctor = s.service.create_doctor(s.admin, s.doc_user.id, "Dr Doc", s.cardio.id, 45)

    assert doctor.slot_length_minutes == 45


def test_only_front_desk_creates_doctors(s: Setup) -> None:
    with pytest.raises(Forbidden):
        s.service.create_doctor(s.doc_user, s.doc_user.id, "Self", s.general.id, None)


def test_doctor_requires_an_existing_doctor_role_user_and_specialty(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.create_doctor(s.admin, uuid.uuid4(), "Ghost", s.general.id, None)
    with pytest.raises(ValidationFailed):
        s.service.create_doctor(s.admin, s.admin.id, "Admin as doctor", s.general.id, None)
    with pytest.raises(ValidationFailed):
        s.service.create_doctor(s.admin, s.doc_user.id, "No specialty", uuid.uuid4(), None)
    with pytest.raises(ValidationFailed):
        s.service.create_doctor(s.admin, s.doc_user.id, "Tiny", s.general.id, 4)


def test_a_user_can_have_only_one_doctor_profile(s: Setup) -> None:
    s.service.create_doctor(s.admin, s.doc_user.id, "Dr Doc", s.general.id, None)

    with pytest.raises(DoctorAlreadyExists):
        s.service.create_doctor(s.admin, s.doc_user.id, "Dr Doc 2", s.general.id, None)


def test_list_filters_by_specialty_and_get_raises_not_found(s: Setup) -> None:
    a = s.service.create_doctor(s.admin, s.doc_user.id, "A", s.general.id, None)
    s.service.create_doctor(s.admin, s.other_user.id, "B", s.cardio.id, None)

    assert [d.id for d in s.service.list_doctors(s.cardio.id)] != [a.id]
    assert [d.id for d in s.service.list_doctors(s.general.id)] == [a.id]
    assert len(s.service.list_doctors(None)) == 2
    with pytest.raises(NotFound):
        s.service.get_doctor(uuid.uuid4())


def test_doctor_edits_their_own_profile_but_not_another_doctors(s: Setup) -> None:
    mine = s.service.create_doctor(s.admin, s.doc_user.id, "Mine", s.general.id, None)
    theirs = s.service.create_doctor(s.admin, s.other_user.id, "Theirs", s.general.id, None)

    updated = s.service.update_doctor(
        s.doc_user, mine.id, name="Dr Mine", specialty_id=s.cardio.id, slot_length_minutes=25
    )

    assert (updated.name, updated.specialty_id, updated.slot_length_minutes) == (
        "Dr Mine",
        s.cardio.id,
        25,
    )
    with pytest.raises(Forbidden):
        s.service.update_doctor(s.doc_user, theirs.id, name="Hacked")


def test_only_front_desk_can_change_active_and_front_desk_can_edit_anyone(s: Setup) -> None:
    mine = s.service.create_doctor(s.admin, s.doc_user.id, "Mine", s.general.id, None)

    with pytest.raises(Forbidden):
        s.service.update_doctor(s.doc_user, mine.id, active=False)
    updated = s.service.update_doctor(s.admin, mine.id, active=False, name="Renamed")

    assert (updated.active, updated.name) == (False, "Renamed")


def test_update_validates_specialty_and_slot_length_and_missing_doctor(s: Setup) -> None:
    mine = s.service.create_doctor(s.admin, s.doc_user.id, "Mine", s.general.id, None)

    with pytest.raises(ValidationFailed):
        s.service.update_doctor(s.admin, mine.id, specialty_id=uuid.uuid4())
    with pytest.raises(ValidationFailed):
        s.service.update_doctor(s.admin, mine.id, slot_length_minutes=1)
    with pytest.raises(NotFound):
        s.service.update_doctor(s.admin, uuid.uuid4(), name="x")


def test_deactivating_a_doctor_with_future_appointments_is_rejected(s: Setup) -> None:
    mine = s.service.create_doctor(s.admin, s.doc_user.id, "Mine", s.general.id, None)
    s.appointments.add(mine.id, START + timedelta(days=1), START + timedelta(days=1, minutes=20))

    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.update_doctor(s.admin, mine.id, active=False)

    assert s.doctors.get(mine.id).active is True  # type: ignore[union-attr]


def test_deactivating_a_doctor_whose_appointments_are_all_in_the_past_is_allowed(s: Setup) -> None:
    mine = s.service.create_doctor(s.admin, s.doc_user.id, "Mine", s.general.id, None)
    s.appointments.add(mine.id, START - timedelta(days=2), START - timedelta(days=2, minutes=-20))

    assert s.service.update_doctor(s.admin, mine.id, active=False).active is False
