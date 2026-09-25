"""Booking rules. Written before AppointmentService."""

import uuid
from datetime import UTC, date, datetime, time

import pytest

from app.domain.errors import (
    EmergencyJustificationRequired,
    EmergencyNotAuthorized,
    Forbidden,
    InvalidSlot,
    NotFound,
    PatientAlreadyBooked,
    SlotAlreadyBooked,
    ValidationFailed,
)
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    AuditAction,
    Availability,
    DayOfWeek,
    Doctor,
    EmergencyJustification,
    Patient,
    Role,
    Specialty,
    TriageResult,
    TriageSource,
    Urgency,
    User,
)
from app.services.appointment_service import AppointmentService
from app.services.audit_service import AuditService
from app.services.slot_service import SlotService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    InMemoryAppointmentRepository,
    InMemoryAuditRepository,
    InMemoryAvailabilityRepository,
    InMemoryClinicSettingsRepository,
    InMemoryDoctorRepository,
    InMemoryPatientRepository,
    InMemorySpecialtyRepository,
    InMemoryTriageRepository,
)

SUNDAY_NOON = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def at(hour: int, minute: int = 0, day: int = 2) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def book_directly(
    repo: InMemoryAppointmentRepository,
    doctor_id: uuid.UUID,
    start: datetime,
    end: datetime,
    patient_id: uuid.UUID | None = None,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
) -> Appointment:
    appointment = Appointment(
        id=uuid.uuid4(),
        doctor_id=doctor_id,
        patient_id=patient_id or uuid.uuid4(),
        start_time=start,
        end_time=end,
        status=status,
        source=AppointmentSource.SCHEDULED,
        is_emergency_slot=False,
        created_at=SUNDAY_NOON,
    )
    repo.add(appointment)
    return appointment


class Setup:
    def __init__(self) -> None:
        self.specialties = InMemorySpecialtyRepository()
        self.doctors = InMemoryDoctorRepository()
        self.availability = InMemoryAvailabilityRepository()
        self.appointments = InMemoryAppointmentRepository()
        self.patients = InMemoryPatientRepository()
        self.settings = InMemoryClinicSettingsRepository()
        self.clock = FixedClock(SUNDAY_NOON)
        slots = SlotService(
            self.specialties,
            self.doctors,
            self.availability,
            self.appointments,
            self.settings,
            self.clock,
        )
        self.audit_repo = InMemoryAuditRepository()
        self.triage = InMemoryTriageRepository()
        self.service = AppointmentService(
            self.appointments,
            self.doctors,
            self.patients,
            slots,
            self.settings,
            self.clock,
            AuditService(self.audit_repo, self.clock),
            self.triage,
        )
        self.specialty = Specialty(uuid.uuid4(), "General", 20)
        self.specialties.add(self.specialty)
        self.admin = User(uuid.uuid4(), "fd@x.test", "FD", Role.FRONT_DESK_ADMIN, "h")
        self.doc_user = User(uuid.uuid4(), "d1@x.test", "D1", Role.DOCTOR, "h")
        self.other_user = User(uuid.uuid4(), "d2@x.test", "D2", Role.DOCTOR, "h")
        self.doctor = self.add_doctor(self.doc_user, "Dr One")
        self.other_doctor = self.add_doctor(self.other_user, "Dr Two")
        self.asha = self.add_patient("Asha Rao", "+919876543210")
        self.kiran = self.add_patient("Kiran Rao", "+919876543210")

    def add_doctor(self, user: User, name: str, active: bool = True) -> Doctor:
        doctor = Doctor(uuid.uuid4(), user.id, name, self.specialty.id, 20, active)
        self.doctors.add(doctor)
        self.availability.add_rule(
            Availability(uuid.uuid4(), doctor.id, DayOfWeek.MONDAY, time(9), time(10))
        )
        return doctor

    def add_patient(self, name: str, phone: str) -> Patient:
        patient = Patient(uuid.uuid4(), name, phone, SUNDAY_NOON)
        self.patients.add(patient)
        return patient

    def book(self, actor: User | None = None, doctor: Doctor | None = None, **kwargs):  # type: ignore[no-untyped-def]
        params = {
            "actor": actor or self.admin,
            "doctor_id": (doctor or self.doctor).id,
            "patient_id": self.asha.id,
            "start_time": at(9),
        }
        return self.service.book(**{**params, **kwargs})


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_booking_a_generated_slot_derives_the_end_time_and_defaults(s: Setup) -> None:
    appointment = s.book(start_time=at(9, 20), reported_symptoms="cough")

    assert appointment.end_time == at(9, 40)
    assert appointment.status == AppointmentStatus.BOOKED
    assert appointment.source == AppointmentSource.SCHEDULED
    assert appointment.is_emergency_slot is False
    assert appointment.reported_symptoms == "cough"
    assert appointment.created_at == SUNDAY_NOON
    assert s.appointments.get(appointment.id) == appointment


def test_walk_in_source_is_stored(s: Setup) -> None:
    assert s.book(source=AppointmentSource.WALK_IN).source == AppointmentSource.WALK_IN


def test_double_booking_the_doctor_is_rejected_with_a_doctor_specific_error(s: Setup) -> None:
    s.book()

    with pytest.raises(SlotAlreadyBooked):
        s.book(patient_id=s.kiran.id)


def test_the_same_patient_cannot_be_booked_with_two_doctors_at_once(s: Setup) -> None:
    s.book()

    with pytest.raises(PatientAlreadyBooked):
        s.book(doctor=s.other_doctor)


def test_a_cancelled_slot_can_be_rebooked(s: Setup) -> None:
    first = s.book()
    first.status = AppointmentStatus.CANCELLED

    assert s.book(patient_id=s.kiran.id).id != first.id


@pytest.mark.parametrize(
    "start",
    [
        at(9, 5),  # off the slot grid
        at(8, 40),  # before the working window
        at(10, 0),  # after the last slot
        at(9, 0, day=3),  # a day without availability
        at(9, 0, day=1),  # in the past (yesterday relative to a Monday clock)
    ],
)
def test_a_start_time_that_is_not_a_generated_slot_is_invalid(s: Setup, start: datetime) -> None:
    with pytest.raises(InvalidSlot):
        s.book(start_time=start)


def test_a_slot_that_has_already_started_is_invalid(s: Setup) -> None:
    s.clock.set(at(9, 10))

    with pytest.raises(InvalidSlot):
        s.book(start_time=at(9, 0))


def test_an_inactive_doctor_cannot_be_booked(s: Setup) -> None:
    inactive = s.add_doctor(User(uuid.uuid4(), "x@x.test", "X", Role.DOCTOR, "h"), "Dr Off", False)

    with pytest.raises(InvalidSlot):
        s.book(doctor=inactive)


def test_unknown_patient_or_doctor_is_not_found(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.book(patient_id=uuid.uuid4())
    with pytest.raises(NotFound):
        s.book(doctor_id=uuid.uuid4())


def test_a_doctor_may_book_only_with_themselves(s: Setup) -> None:
    assert s.book(actor=s.doc_user, doctor=s.doctor).doctor_id == s.doctor.id
    with pytest.raises(Forbidden):
        s.book(actor=s.doc_user, doctor=s.other_doctor, start_time=at(9, 20))


def test_front_desk_may_book_with_any_doctor(s: Setup) -> None:
    assert s.book(actor=s.admin, doctor=s.other_doctor).doctor_id == s.other_doctor.id


def test_the_held_back_last_slot_needs_an_emergency_justification(s: Setup) -> None:
    with pytest.raises(EmergencyJustificationRequired):
        s.book(start_time=at(9, 40))  # the last slot is held back (N = 1)


def test_front_desk_judgment_with_a_reason_books_the_held_slot_and_records_who_and_why(
    s: Setup,
) -> None:
    appointment = s.book(
        start_time=at(9, 40),
        emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
        emergency_reason="chest pain, walked in",
    )

    assert appointment.is_emergency_slot is True
    assert appointment.emergency_justification == EmergencyJustification.FRONT_DESK_JUDGMENT
    assert appointment.emergency_reason == "chest pain, walked in"
    assert appointment.emergency_authorized_by == s.admin.id
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.EMERGENCY_AUTHORIZATION
    assert (entry.actor_id, entry.target_id, entry.reason) == (
        s.admin.id,
        appointment.id,
        "chest pain, walked in",
    )


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_front_desk_judgment_needs_a_non_blank_reason(s: Setup, reason: str | None) -> None:
    with pytest.raises(EmergencyJustificationRequired):
        s.book(
            start_time=at(9, 40),
            emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
            emergency_reason=reason,
        )

    assert s.appointments.items == {}
    assert s.audit_repo.entries == []


def test_a_doctor_cannot_authorize_emergency_capacity_by_judgment(s: Setup) -> None:
    with pytest.raises(Forbidden):
        s.book(
            actor=s.doc_user,
            doctor=s.doctor,
            start_time=at(9, 40),
            emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
            emergency_reason="urgent",
        )


def add_triage(
    s: Setup,
    urgency: Urgency,
    patient: Patient | None = None,
    override: Urgency | None = None,
) -> TriageResult:
    result = TriageResult(
        id=uuid.uuid4(),
        patient_id=(patient or s.asha).id,
        reported_symptoms="symptoms",
        urgency=urgency,
        suggested_specialty_id=s.specialty.id,
        confidence_score=0.9,
        source=TriageSource.MODEL,
        disclaimer="d",
        created_at=SUNDAY_NOON,
        overridden_urgency=override,
    )
    s.triage.add(result)
    return result


def book_by_triage(s: Setup, triage: TriageResult | None, **kwargs):  # type: ignore[no-untyped-def]
    return s.book(
        start_time=at(9, 40),
        emergency_justification=EmergencyJustification.TRIAGE,
        triage_result_id=triage.id if triage else None,
        **kwargs,
    )


def test_an_emergency_triage_result_authorizes_the_held_back_slot(s: Setup) -> None:
    triage = add_triage(s, Urgency.EMERGENCY)

    appointment = book_by_triage(s, triage)

    assert appointment.is_emergency_slot is True
    assert appointment.emergency_justification == EmergencyJustification.TRIAGE
    assert appointment.triage_result_id == triage.id
    assert appointment.emergency_authorized_by == s.admin.id
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.EMERGENCY_AUTHORIZATION
    assert entry.target_id == appointment.id


@pytest.mark.parametrize(
    ("urgency", "override", "allowed"),
    [
        (Urgency.ROUTINE, None, False),
        (Urgency.URGENT, None, False),
        (Urgency.EMERGENCY, None, True),
        (Urgency.EMERGENCY, Urgency.ROUTINE, False),  # the override always wins: a downgrade blocks
        (Urgency.ROUTINE, Urgency.EMERGENCY, True),  # ...and an upgrade allows
        (Urgency.EMERGENCY, Urgency.EMERGENCY, True),
    ],
)
def test_authorization_follows_the_effective_urgency_including_overrides(
    s: Setup, urgency: Urgency, override: Urgency | None, allowed: bool
) -> None:
    triage = add_triage(s, urgency, override=override)

    if allowed:
        assert book_by_triage(s, triage).is_emergency_slot is True
    else:
        with pytest.raises(EmergencyNotAuthorized):
            book_by_triage(s, triage)
        assert s.appointments.items == {}


def test_a_triage_result_of_another_patient_never_authorizes_the_booking(s: Setup) -> None:
    others = add_triage(s, Urgency.EMERGENCY, patient=s.kiran)

    with pytest.raises(EmergencyNotAuthorized):
        book_by_triage(s, others)  # booking Asha with Kiran's emergency triage


def test_a_triage_justification_needs_a_result_that_exists(s: Setup) -> None:
    with pytest.raises(EmergencyNotAuthorized):
        book_by_triage(s, None)
    with pytest.raises(EmergencyNotAuthorized):
        s.book(
            start_time=at(9, 40),
            emergency_justification=EmergencyJustification.TRIAGE,
            triage_result_id=uuid.uuid4(),
        )


def test_a_doctor_may_book_their_own_slot_on_the_strength_of_triage(s: Setup) -> None:
    triage = add_triage(s, Urgency.EMERGENCY)

    appointment = book_by_triage(s, triage, actor=s.doc_user, doctor=s.doctor)

    assert appointment.emergency_authorized_by == s.doc_user.id


def test_a_triage_reference_on_a_regular_booking_is_validated_and_stored(s: Setup) -> None:
    triage = add_triage(s, Urgency.ROUTINE)

    stored = s.book(start_time=at(9, 0), triage_result_id=triage.id)

    assert stored.triage_result_id == triage.id and stored.is_emergency_slot is False
    with pytest.raises(ValidationFailed):
        s.book(start_time=at(9, 20), triage_result_id=uuid.uuid4())
    with pytest.raises(ValidationFailed):
        s.book(
            start_time=at(9, 20),
            triage_result_id=add_triage(s, Urgency.ROUTINE, patient=s.kiran).id,
        )


def test_an_emergency_booking_still_blocks_double_booking_of_that_slot(s: Setup) -> None:
    s.book(
        start_time=at(9, 40),
        emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
        emergency_reason="first",
    )

    with pytest.raises(SlotAlreadyBooked):
        s.book(
            patient_id=s.kiran.id,
            start_time=at(9, 40),
            emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
            emergency_reason="second",
        )


def test_the_held_slot_is_bookable_as_a_regular_slot_once_released(s: Setup) -> None:
    s.clock.set(at(8, 40))  # 60 minutes before 09:40

    appointment = s.book(start_time=at(9, 40))

    assert appointment.is_emergency_slot is False


def test_a_justification_sent_for_a_regular_slot_is_ignored(s: Setup) -> None:
    appointment = s.book(
        start_time=at(9),
        emergency_justification=EmergencyJustification.FRONT_DESK_JUDGMENT,
        emergency_reason="not needed",
    )

    assert appointment.is_emergency_slot is False
    assert appointment.emergency_justification is None


def test_the_clinic_time_zone_decides_which_instants_are_slots(s: Setup) -> None:
    s.settings.settings.clinic_timezone = "Asia/Kolkata"  # 09:00 local = 03:30 UTC

    assert s.book(start_time=at(3, 30)).end_time == at(3, 50)
    with pytest.raises(InvalidSlot):
        s.book(start_time=at(9, 0), patient_id=s.kiran.id)  # 09:00 UTC is 14:30 local


# ---- reads -------------------------------------------------------------------------------------


def test_get_returns_the_appointment_or_not_found(s: Setup) -> None:
    appointment = s.book()

    assert s.service.get(s.admin, appointment.id) == appointment
    with pytest.raises(NotFound):
        s.service.get(s.admin, uuid.uuid4())


def test_a_doctor_can_read_only_their_own_appointments(s: Setup) -> None:
    mine = s.book(doctor=s.doctor)
    theirs = s.book(doctor=s.other_doctor, patient_id=s.kiran.id)

    assert s.service.get(s.doc_user, mine.id) == mine
    with pytest.raises(Forbidden):
        s.service.get(s.doc_user, theirs.id)


def test_list_filters_by_doctor_patient_status_and_paginates(s: Setup) -> None:
    a = s.book(start_time=at(9))
    b = s.book(start_time=at(9, 20), patient_id=s.kiran.id)
    c = s.book(doctor=s.other_doctor, start_time=at(9), patient_id=s.kiran.id)
    b.status = AppointmentStatus.CANCELLED

    everything = s.service.list(s.admin, None, None, None, None, 1, 10)
    by_doctor = s.service.list(s.admin, s.doctor.id, None, None, None, 1, 10)
    by_patient = s.service.list(s.admin, None, s.kiran.id, None, None, 1, 10)
    cancelled = s.service.list(s.admin, None, None, None, AppointmentStatus.CANCELLED, 1, 10)
    page_two = s.service.list(s.admin, None, None, None, None, 2, 2)

    assert everything.total == 3
    assert [x.id for x in by_doctor.items] == [a.id, b.id]
    assert {x.id for x in by_patient.items} == {b.id, c.id}
    assert [x.id for x in cancelled.items] == [b.id]
    assert (page_two.total, len(page_two.items)) == (3, 1)


def test_list_by_date_uses_the_clinic_local_day(s: Setup) -> None:
    s.settings.settings.clinic_timezone = "Asia/Kolkata"
    s.book(start_time=at(3, 30))  # 09:00 IST on Monday the 2nd (03:30 UTC)

    assert s.service.list(s.admin, None, None, date(2026, 3, 2), None, 1, 10).total == 1
    assert s.service.list(s.admin, None, None, date(2026, 3, 3), None, 1, 10).total == 0
    assert s.service.list(s.admin, None, None, date(2026, 3, 1), None, 1, 10).total == 0


def test_a_doctors_list_is_scoped_to_their_own_appointments(s: Setup) -> None:
    mine = s.book(doctor=s.doctor)
    s.book(doctor=s.other_doctor, patient_id=s.kiran.id)

    scoped = s.service.list(s.doc_user, None, None, None, None, 1, 10)

    assert [x.id for x in scoped.items] == [mine.id]
    assert scoped.total == 1


def test_a_doctor_asking_for_another_doctors_appointments_is_forbidden(s: Setup) -> None:
    with pytest.raises(Forbidden):
        s.service.list(s.doc_user, s.other_doctor.id, None, None, None, 1, 10)


def test_a_doctor_without_a_profile_sees_nothing(s: Setup) -> None:
    stranger = User(uuid.uuid4(), "s@x.test", "S", Role.DOCTOR, "h")
    s.book()

    assert s.service.list(stranger, None, None, None, None, 1, 10).total == 0
