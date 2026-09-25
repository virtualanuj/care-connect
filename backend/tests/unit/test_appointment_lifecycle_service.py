"""Lifecycle actions, cancellation cutoff, force-cancel, reschedule and follow-up."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.errors import (
    AppointmentNotCompleted,
    CancellationWindowClosed,
    FollowUpWindowExceeded,
    Forbidden,
    InvalidSlot,
    InvalidTransition,
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
    CancellationType,
)
from tests.unit.test_appointment_service import SUNDAY_NOON, Setup, at

S = AppointmentStatus
NEXT_MONDAY = 9  # 2026-03-09, seven days after the booking Monday (2026-03-02)


@pytest.fixture
def s() -> Setup:
    return Setup()


def booked(s: Setup, hour: int = 9, minute: int = 0, **kwargs) -> Appointment:  # type: ignore[no-untyped-def]
    return s.book(start_time=at(hour, minute), **kwargs)


# ---- check-in, start, complete, no-show --------------------------------------------------------


def test_the_happy_path_walks_the_whole_lifecycle_and_stamps_times(s: Setup) -> None:
    appointment = booked(s)
    s.clock.set(at(9, 0))

    checked_in = s.service.check_in(s.admin, appointment.id)
    assert (checked_in.status, checked_in.checked_in_at) == (S.CHECKED_IN, at(9, 0))
    started = s.service.start_consultation(s.admin, appointment.id)
    assert started.status == S.IN_CONSULTATION
    s.clock.set(at(9, 15))
    done = s.service.complete(s.admin, appointment.id)
    assert (done.status, done.completed_at) == (S.COMPLETED, at(9, 15))
    assert s.appointments.get(appointment.id) == done  # persisted


@pytest.mark.parametrize(
    "action",
    ["start_consultation", "complete"],
)
def test_actions_out_of_order_are_invalid_transitions(s: Setup, action: str) -> None:
    appointment = booked(s)

    with pytest.raises(InvalidTransition):
        getattr(s.service, action)(s.admin, appointment.id)


def test_checking_in_twice_is_an_invalid_transition(s: Setup) -> None:
    appointment = booked(s)
    s.service.check_in(s.admin, appointment.id)

    with pytest.raises(InvalidTransition):
        s.service.check_in(s.admin, appointment.id)


@pytest.mark.parametrize("check_in_first", [False, True])
def test_no_show_is_allowed_before_or_after_check_in_and_frees_the_slot(
    s: Setup, check_in_first: bool
) -> None:
    appointment = booked(s)
    if check_in_first:
        s.service.check_in(s.admin, appointment.id)

    marked = s.service.mark_no_show(s.admin, appointment.id)

    assert marked.status == S.NO_SHOW
    assert s.book(start_time=at(9), patient_id=s.kiran.id).id != appointment.id  # slot free again


def test_no_show_is_invalid_once_the_consultation_started(s: Setup) -> None:
    appointment = booked(s)
    s.service.check_in(s.admin, appointment.id)
    s.service.start_consultation(s.admin, appointment.id)

    with pytest.raises(InvalidTransition):
        s.service.mark_no_show(s.admin, appointment.id)


def test_a_doctor_acts_only_on_their_own_appointments_and_front_desk_on_any(s: Setup) -> None:
    mine = booked(s, doctor=s.doctor)
    theirs = booked(s, doctor=s.other_doctor, patient_id=s.kiran.id)

    assert s.service.check_in(s.doc_user, mine.id).status == S.CHECKED_IN
    with pytest.raises(Forbidden):
        s.service.check_in(s.doc_user, theirs.id)
    assert s.service.check_in(s.admin, theirs.id).status == S.CHECKED_IN


def test_actions_on_an_unknown_appointment_are_not_found(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.service.check_in(s.admin, uuid.uuid4())


def test_there_is_no_time_based_gating_on_lifecycle_actions(s: Setup) -> None:
    appointment = booked(s)  # Monday 09:00; the clock is Sunday noon, a day early

    assert s.service.check_in(s.admin, appointment.id).status == S.CHECKED_IN


# ---- standard cancellation and the cutoff ------------------------------------------------------


def test_cancelling_outside_the_cutoff_succeeds_and_records_who_and_when(s: Setup) -> None:
    appointment = booked(s)  # 21 hours away from Sunday noon

    cancelled = s.service.cancel(s.admin, appointment.id)

    assert cancelled.status == S.CANCELLED
    assert cancelled.cancellation_type == CancellationType.STANDARD
    assert (cancelled.cancelled_at, cancelled.cancelled_by) == (SUNDAY_NOON, s.admin.id)


def test_cancelling_exactly_at_the_cutoff_is_rejected_and_one_second_earlier_succeeds(
    s: Setup,
) -> None:
    appointment = booked(s)  # starts Monday 09:00
    s.clock.set(at(7, 0))  # exactly 2 hours before: inside the (inclusive) cutoff

    with pytest.raises(CancellationWindowClosed):
        s.service.cancel(s.admin, appointment.id)

    s.clock.set(at(7, 0) - timedelta(seconds=1))  # 2 h + 1 s away
    assert s.service.cancel(s.admin, appointment.id).status == S.CANCELLED


def test_the_cutoff_is_read_from_clinic_settings_not_hardcoded(s: Setup) -> None:
    appointment = booked(s)
    s.settings.settings.cancellation_cutoff_hours = 5
    s.clock.set(at(5, 0))  # 4 hours away: fine for a 2 h cutoff, blocked by 5 h

    with pytest.raises(CancellationWindowClosed):
        s.service.cancel(s.admin, appointment.id)


def test_a_cancelled_appointment_frees_its_slot(s: Setup) -> None:
    appointment = booked(s)

    s.service.cancel(s.admin, appointment.id)

    assert s.book(start_time=at(9), patient_id=s.kiran.id).id != appointment.id


def test_cancel_works_on_checked_in_but_not_completed_appointments(s: Setup) -> None:
    checked_in = booked(s, 9, 0)
    s.service.check_in(s.admin, checked_in.id)
    completed = booked(s, 9, 20, patient_id=s.kiran.id)
    completed.status = S.COMPLETED

    assert s.service.cancel(s.admin, checked_in.id).status == S.CANCELLED
    with pytest.raises(InvalidTransition):
        s.service.cancel(s.admin, completed.id)


def test_a_doctor_may_cancel_only_their_own_appointments(s: Setup) -> None:
    mine = booked(s, doctor=s.doctor)
    theirs = booked(s, doctor=s.other_doctor, patient_id=s.kiran.id)

    assert s.service.cancel(s.doc_user, mine.id).status == S.CANCELLED
    with pytest.raises(Forbidden):
        s.service.cancel(s.doc_user, theirs.id)


# ---- force-cancel ------------------------------------------------------------------------------


def test_front_desk_can_force_cancel_inside_the_cutoff_and_it_is_recorded_and_audited(
    s: Setup,
) -> None:
    appointment = booked(s)
    s.clock.set(at(8, 30))  # well inside the cutoff

    with pytest.raises(CancellationWindowClosed):
        s.service.cancel(s.admin, appointment.id)
    forced = s.service.force_cancel(s.admin, appointment.id, "Patient hospitalised")

    assert forced.status == S.CANCELLED
    assert forced.cancellation_type == CancellationType.FORCE
    assert forced.cancel_reason == "Patient hospitalised"
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.FORCE_CANCEL
    assert (entry.actor_id, entry.target_id, entry.reason) == (
        s.admin.id,
        appointment.id,
        "Patient hospitalised",
    )


def test_a_doctor_cannot_force_cancel(s: Setup) -> None:
    appointment = booked(s, doctor=s.doctor)

    with pytest.raises(Forbidden):
        s.service.force_cancel(s.doc_user, appointment.id, "reason")
    assert s.appointments.get(appointment.id).status == S.BOOKED  # type: ignore[union-attr]


def test_force_cancel_requires_a_reason_and_a_cancellable_status(s: Setup) -> None:
    appointment = booked(s)

    with pytest.raises(ValidationFailed):
        s.service.force_cancel(s.admin, appointment.id, "   ")
    appointment.status = S.COMPLETED
    with pytest.raises(InvalidTransition):
        s.service.force_cancel(s.admin, appointment.id, "too late")


# ---- reschedule --------------------------------------------------------------------------------


def test_reschedule_books_the_new_slot_and_cancels_the_old_one_linking_them(s: Setup) -> None:
    original = booked(s, 9, 0, reported_symptoms="cough", source=AppointmentSource.WALK_IN)

    new = s.service.reschedule(s.admin, original.id, at(9, 20))

    assert new.id != original.id
    assert (new.doctor_id, new.patient_id, new.start_time) == (
        original.doctor_id,
        original.patient_id,
        at(9, 20),
    )
    assert (new.reported_symptoms, new.source, new.status) == (
        "cough",
        AppointmentSource.WALK_IN,
        S.BOOKED,
    )
    old = s.appointments.get(original.id)
    assert old is not None
    assert (old.status, old.cancellation_type, old.rescheduled_to_id) == (
        S.CANCELLED,
        CancellationType.RESCHEDULED,
        new.id,
    )
    assert (old.cancelled_by, old.cancelled_at) == (s.admin.id, SUNDAY_NOON)


def test_reschedule_is_blocked_inside_the_cancellation_cutoff_and_changes_nothing(s: Setup) -> None:
    original = booked(s)
    s.clock.set(at(8, 0))  # an hour before

    with pytest.raises(CancellationWindowClosed):
        s.service.reschedule(s.admin, original.id, at(9, 20))

    assert s.appointments.get(original.id).status == S.BOOKED  # type: ignore[union-attr]
    assert len(s.appointments.items) == 1


def test_only_a_booked_appointment_can_be_rescheduled(s: Setup) -> None:
    original = booked(s)
    s.service.check_in(s.admin, original.id)

    with pytest.raises(InvalidTransition):
        s.service.reschedule(s.admin, original.id, at(9, 20))


def test_a_failed_reschedule_leaves_the_original_booked(s: Setup) -> None:
    original = booked(s, 9, 0)
    booked(s, 9, 20, patient_id=s.kiran.id)  # the target slot is taken

    with pytest.raises(SlotAlreadyBooked):
        s.service.reschedule(s.admin, original.id, at(9, 20))

    kept = s.appointments.get(original.id)
    assert kept is not None
    assert (kept.status, kept.rescheduled_to_id, kept.cancelled_at) == (S.BOOKED, None, None)


@pytest.mark.parametrize("target", [at(9, 5), at(9, 0, day=3)])
def test_rescheduling_to_a_time_that_is_not_a_slot_is_invalid_and_atomic(
    s: Setup, target: datetime
) -> None:
    original = booked(s)

    with pytest.raises(InvalidSlot):
        s.service.reschedule(s.admin, original.id, target)

    assert s.appointments.get(original.id).status == S.BOOKED  # type: ignore[union-attr]


def test_a_reschedule_cannot_target_the_held_back_emergency_slot(s: Setup) -> None:
    original = booked(s)

    with pytest.raises(InvalidSlot):
        s.service.reschedule(s.admin, original.id, at(9, 40))  # the held last slot

    assert s.appointments.get(original.id).status == S.BOOKED  # type: ignore[union-attr]


def test_rescheduling_into_a_time_the_patient_already_has_elsewhere_is_rejected_atomically(
    s: Setup,
) -> None:
    original = booked(s, 9, 0)
    s.book(doctor=s.other_doctor, start_time=at(9, 20))  # the patient's other appointment

    with pytest.raises(PatientAlreadyBooked):
        s.service.reschedule(s.admin, original.id, at(9, 20))

    assert s.appointments.get(original.id).status == S.BOOKED  # type: ignore[union-attr]


def test_a_doctor_may_reschedule_only_their_own_appointments(s: Setup) -> None:
    mine = booked(s, doctor=s.doctor)
    theirs = booked(s, doctor=s.other_doctor, patient_id=s.kiran.id)

    assert s.service.reschedule(s.doc_user, mine.id, at(9, 20)).doctor_id == s.doctor.id
    with pytest.raises(Forbidden):
        s.service.reschedule(s.doc_user, theirs.id, at(9, 20))


# ---- follow-up ---------------------------------------------------------------------------------


def completed(s: Setup, hour: int = 9, minute: int = 0, **kwargs) -> Appointment:  # type: ignore[no-untyped-def]
    appointment = booked(s, hour, minute, **kwargs)
    appointment.status = S.COMPLETED
    return appointment


def monday(day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def test_a_follow_up_is_booked_for_the_same_doctor_and_patient_and_linked(s: Setup) -> None:
    original = completed(s)

    follow_up = s.service.book_follow_up(s.admin, original.id, monday(9))

    assert (follow_up.doctor_id, follow_up.patient_id) == (original.doctor_id, original.patient_id)
    assert (follow_up.follow_up_of_id, follow_up.status) == (original.id, S.BOOKED)
    assert follow_up.start_time == monday(9)


def test_only_a_completed_appointment_can_have_a_follow_up(s: Setup) -> None:
    original = booked(s)

    with pytest.raises(AppointmentNotCompleted):
        s.service.book_follow_up(s.admin, original.id, monday(9))


def test_the_follow_up_window_is_inclusive_at_the_boundary_and_rejects_one_second_beyond(
    s: Setup,
) -> None:
    original = completed(s)  # Monday 2026-03-02 09:00
    s.settings.settings.follow_up_max_days = 7

    ok = s.service.book_follow_up(s.admin, original.id, monday(9))  # exactly 7 days later
    assert ok.start_time == monday(9)

    s.settings.settings.follow_up_max_days = 6
    other = completed(s, 9, 20, patient_id=s.kiran.id)
    with pytest.raises(FollowUpWindowExceeded):
        s.service.book_follow_up(s.admin, other.id, monday(9, 9, 20))  # 7 days > 6


def test_a_follow_up_of_a_follow_up_is_measured_from_the_root_visit(s: Setup) -> None:
    root = completed(s)  # 03-02
    s.settings.settings.follow_up_max_days = 14
    first = s.service.book_follow_up(s.admin, root.id, monday(9))  # 7 days from root
    first.status = S.COMPLETED

    second = s.service.book_follow_up(s.admin, first.id, monday(16))  # 14 days from root
    assert second.follow_up_of_id == first.id

    s.settings.settings.follow_up_max_days = 10
    third_source = completed(s, 9, 20, patient_id=s.kiran.id)
    chained = s.service.book_follow_up(s.admin, third_source.id, monday(9, 9, 20))
    chained.status = S.COMPLETED
    with pytest.raises(FollowUpWindowExceeded):  # 7 days from its parent, but 14 from the root
        s.service.book_follow_up(s.admin, chained.id, monday(16, 9, 20))


def test_a_follow_up_must_be_a_regular_open_slot(s: Setup) -> None:
    original = completed(s)

    with pytest.raises(InvalidSlot):  # the held-back last slot of that day
        s.service.book_follow_up(s.admin, original.id, monday(9, 9, 40))
    with pytest.raises(InvalidSlot):  # not a slot at all
        s.service.book_follow_up(s.admin, original.id, monday(9, 9, 5))
    s.service.book_follow_up(s.admin, original.id, monday(9))
    with pytest.raises(SlotAlreadyBooked):  # now taken
        s.service.book_follow_up(s.admin, completed(s, 9, 20, patient_id=s.kiran.id).id, monday(9))


def test_a_doctor_books_follow_ups_only_for_their_own_appointments(s: Setup) -> None:
    mine = completed(s, doctor=s.doctor)
    theirs = completed(s, doctor=s.other_doctor, patient_id=s.kiran.id)

    assert s.service.book_follow_up(s.doc_user, mine.id, monday(9)).doctor_id == s.doctor.id
    with pytest.raises(Forbidden):
        s.service.book_follow_up(s.doc_user, theirs.id, monday(9))
