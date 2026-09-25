import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.domain.errors import (
    AvailabilityConflictsWithAppointments,
    AvailabilityOverlap,
    Forbidden,
    NotFound,
    ValidationFailed,
)
from app.domain.models import DayOfWeek, Doctor, ExceptionType, Role, User
from app.services.availability_service import AvailabilityService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    FakeAppointmentQuery,
    InMemoryAvailabilityRepository,
    InMemoryClinicSettingsRepository,
    InMemoryDoctorRepository,
)

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)  # a Sunday
MONDAY = date(2026, 3, 2)
T = time.fromisoformat


class Setup:
    def __init__(self) -> None:
        self.doctors = InMemoryDoctorRepository()
        self.repo = InMemoryAvailabilityRepository()
        self.appointments = FakeAppointmentQuery()
        self.settings = InMemoryClinicSettingsRepository()
        self.service = AvailabilityService(
            self.doctors, self.repo, self.appointments, self.settings, FixedClock(NOW)
        )
        self.admin = User(uuid.uuid4(), "a@x.test", "A", Role.FRONT_DESK_ADMIN, "h")
        self.doc_user = User(uuid.uuid4(), "d@x.test", "D", Role.DOCTOR, "h")
        self.other_user = User(uuid.uuid4(), "o@x.test", "O", Role.DOCTOR, "h")
        self.doctor = Doctor(uuid.uuid4(), self.doc_user.id, "Dr D", uuid.uuid4(), 20)
        self.other = Doctor(uuid.uuid4(), self.other_user.id, "Dr O", uuid.uuid4(), 20)
        self.doctors.add(self.doctor)
        self.doctors.add(self.other)

    def book_monday(self, hour: int, minute: int = 0) -> None:
        start = datetime(2026, 3, 2, hour, minute, tzinfo=UTC)
        self.appointments.add(self.doctor.id, start, start + timedelta(minutes=20))

    def add_monday_rule(self, start: str = "09:00", end: str = "12:00"):  # type: ignore[no-untyped-def]
        return self.service.add_rule(self.admin, self.doctor.id, DayOfWeek.MONDAY, T(start), T(end))


@pytest.fixture
def s() -> Setup:
    return Setup()


# ---- rules: validation, overlap, permissions ---------------------------------------------------


def test_add_and_list_rules_round_trip(s: Setup) -> None:
    rule = s.add_monday_rule()

    assert s.service.list_rules(s.doctor.id) == [rule]
    assert (rule.start_time, rule.end_time) == (T("09:00"), T("12:00"))


def test_start_must_be_before_end(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.add_monday_rule("12:00", "09:00")
    with pytest.raises(ValidationFailed):
        s.add_monday_rule("09:00", "09:00")


def test_overlapping_rules_on_the_same_day_are_rejected_but_adjacent_and_other_days_are_fine(
    s: Setup,
) -> None:
    s.add_monday_rule("09:00", "12:00")

    with pytest.raises(AvailabilityOverlap):
        s.add_monday_rule("11:00", "13:00")
    s.add_monday_rule("12:00", "14:00")  # adjacent
    s.service.add_rule(s.admin, s.doctor.id, DayOfWeek.TUESDAY, T("09:00"), T("12:00"))


def test_updating_a_rule_may_not_overlap_another_but_may_overlap_itself(s: Setup) -> None:
    morning = s.add_monday_rule("09:00", "12:00")
    afternoon = s.add_monday_rule("13:00", "16:00")

    grown = s.service.update_rule(s.admin, s.doctor.id, morning.id, end_time=T("12:30"))
    assert grown.end_time == T("12:30")
    with pytest.raises(AvailabilityOverlap):
        s.service.update_rule(s.admin, s.doctor.id, afternoon.id, start_time=T("12:00"))


def test_doctor_manages_their_own_availability_but_not_another_doctors(s: Setup) -> None:
    own = s.service.add_rule(s.doc_user, s.doctor.id, DayOfWeek.MONDAY, T("09:00"), T("12:00"))

    assert own.doctor_id == s.doctor.id
    with pytest.raises(Forbidden):
        s.service.add_rule(s.doc_user, s.other.id, DayOfWeek.MONDAY, T("09:00"), T("12:00"))
    with pytest.raises(Forbidden):
        s.service.delete_rule(s.other_user, s.doctor.id, own.id)


def test_unknown_doctor_or_a_rule_of_a_different_doctor_is_not_found(s: Setup) -> None:
    rule = s.add_monday_rule()

    with pytest.raises(NotFound):
        s.service.list_rules(uuid.uuid4())
    with pytest.raises(NotFound):
        s.service.delete_rule(s.admin, s.other.id, rule.id)
    with pytest.raises(NotFound):
        s.service.update_rule(s.admin, s.doctor.id, uuid.uuid4(), end_time=T("10:00"))


# ---- exceptions --------------------------------------------------------------------------------


def test_extra_hours_need_both_times_and_a_whole_day_exception_needs_neither(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.add_exception(s.admin, s.doctor.id, MONDAY, ExceptionType.EXTRA_HOURS, None, None)
    with pytest.raises(ValidationFailed):
        s.service.add_exception(
            s.admin, s.doctor.id, MONDAY, ExceptionType.EXTRA_HOURS, T("09:00"), None
        )
    with pytest.raises(ValidationFailed):
        s.service.add_exception(
            s.admin, s.doctor.id, MONDAY, ExceptionType.UNAVAILABLE, T("09:00"), None
        )
    with pytest.raises(ValidationFailed):
        s.service.add_exception(
            s.admin, s.doctor.id, MONDAY, ExceptionType.EXTRA_HOURS, T("12:00"), T("09:00")
        )

    whole_day = s.service.add_exception(
        s.admin, s.doctor.id, MONDAY, ExceptionType.UNAVAILABLE, None, None
    )
    assert (whole_day.start_time, whole_day.end_time) == (None, None)
    assert s.service.list_exceptions(s.doctor.id) == [whole_day]


def test_exceptions_are_permission_checked_and_can_be_updated_and_deleted(s: Setup) -> None:
    extra = s.service.add_exception(
        s.doc_user, s.doctor.id, MONDAY, ExceptionType.EXTRA_HOURS, T("13:00"), T("15:00")
    )

    moved = s.service.update_exception(s.doc_user, s.doctor.id, extra.id, end_time=T("16:00"))
    assert moved.end_time == T("16:00")
    with pytest.raises(Forbidden):
        s.service.delete_exception(s.other_user, s.doctor.id, extra.id)
    s.service.delete_exception(s.doc_user, s.doctor.id, extra.id)
    assert s.service.list_exceptions(s.doctor.id) == []
    with pytest.raises(NotFound):
        s.service.delete_exception(s.doc_user, s.doctor.id, extra.id)


# ---- conflicts with existing appointments ------------------------------------------------------


def test_deleting_the_only_rule_covering_an_appointment_is_rejected_and_changes_nothing(
    s: Setup,
) -> None:
    rule = s.add_monday_rule()
    s.book_monday(9, 30)

    with pytest.raises(AvailabilityConflictsWithAppointments, match="1"):
        s.service.delete_rule(s.admin, s.doctor.id, rule.id)

    assert s.service.list_rules(s.doctor.id) == [rule]


def test_deleting_a_rule_is_fine_when_no_appointment_depends_on_it(s: Setup) -> None:
    rule = s.add_monday_rule()

    s.service.delete_rule(s.admin, s.doctor.id, rule.id)

    assert s.service.list_rules(s.doctor.id) == []


def test_deleting_a_rule_is_fine_when_another_rule_still_covers_the_appointment(s: Setup) -> None:
    s.add_monday_rule("09:00", "12:00")
    other = s.service.add_rule(s.admin, s.doctor.id, DayOfWeek.MONDAY, T("12:00"), T("13:00"))
    s.book_monday(9, 30)

    s.service.delete_rule(s.admin, s.doctor.id, other.id)


def test_narrowing_or_moving_a_rule_that_would_orphan_an_appointment_is_rejected(s: Setup) -> None:
    rule = s.add_monday_rule("09:00", "12:00")
    s.book_monday(11, 30)

    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.update_rule(s.admin, s.doctor.id, rule.id, end_time=T("11:00"))
    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.update_rule(s.admin, s.doctor.id, rule.id, day_of_week=DayOfWeek.TUESDAY)
    assert s.service.update_rule(s.admin, s.doctor.id, rule.id, end_time=T("13:00")).end_time == T(
        "13:00"
    )


def test_a_whole_day_unavailable_exception_conflicts_with_that_days_appointments(s: Setup) -> None:
    s.add_monday_rule()
    s.book_monday(9, 30)

    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.add_exception(s.admin, s.doctor.id, MONDAY, ExceptionType.UNAVAILABLE, None, None)
    s.service.add_exception(
        s.admin, s.doctor.id, date(2026, 3, 9), ExceptionType.UNAVAILABLE, None, None
    )


def test_a_partial_unavailable_exception_only_conflicts_if_it_hits_an_appointment(s: Setup) -> None:
    s.add_monday_rule()
    s.book_monday(9, 30)

    s.service.add_exception(
        s.admin, s.doctor.id, MONDAY, ExceptionType.UNAVAILABLE, T("11:00"), T("12:00")
    )
    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.add_exception(
            s.admin, s.doctor.id, MONDAY, ExceptionType.UNAVAILABLE, T("09:00"), T("10:00")
        )


def test_removing_extra_hours_that_cover_an_appointment_is_rejected(s: Setup) -> None:
    extra = s.service.add_exception(
        s.admin, s.doctor.id, MONDAY, ExceptionType.EXTRA_HOURS, T("13:00"), T("15:00")
    )
    s.book_monday(13, 30)

    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.delete_exception(s.admin, s.doctor.id, extra.id)
    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.update_exception(s.admin, s.doctor.id, extra.id, end_time=T("13:10"))


def test_appointments_already_outside_availability_do_not_block_unrelated_edits(s: Setup) -> None:
    s.book_monday(20, 0)  # never covered by anything
    rule = s.add_monday_rule()

    s.service.delete_rule(s.admin, s.doctor.id, rule.id)


def test_appointments_in_the_past_never_conflict(s: Setup) -> None:
    rule = s.add_monday_rule()
    start = datetime(2026, 2, 23, 9, 30, tzinfo=UTC)  # a past Monday
    s.appointments.add(s.doctor.id, start, start + timedelta(minutes=20))

    s.service.delete_rule(s.admin, s.doctor.id, rule.id)


def test_conflict_checks_use_the_clinic_time_zone(s: Setup) -> None:
    s.settings.settings.clinic_timezone = "Asia/Kolkata"
    rule = s.add_monday_rule("09:00", "12:00")
    s.appointments.add(
        s.doctor.id,
        datetime(2026, 3, 2, 4, 0, tzinfo=UTC),  # 09:30 in Kolkata
        datetime(2026, 3, 2, 4, 20, tzinfo=UTC),
    )

    with pytest.raises(AvailabilityConflictsWithAppointments):
        s.service.delete_rule(s.admin, s.doctor.id, rule.id)
