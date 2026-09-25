import dataclasses
import uuid
from collections.abc import Callable, Sequence
from datetime import date as Date
from datetime import time
from zoneinfo import ZoneInfo

from app.domain.availability import covers
from app.domain.errors import (
    AvailabilityConflictsWithAppointments,
    AvailabilityOverlap,
    NotFound,
    ValidationFailed,
)
from app.domain.models import (
    Availability,
    AvailabilityException,
    DayOfWeek,
    Doctor,
    ExceptionType,
    User,
)
from app.domain.ports import (
    AppointmentQuery,
    AvailabilityRepository,
    ClinicSettingsRepository,
    Clock,
    DoctorRepository,
)
from app.services.doctor_service import DoctorService


class _Unset:
    """Marks a PATCH field that was not sent (distinct from an explicit null)."""


UNSET = _Unset()


class AvailabilityService:
    """Weekly availability rules and one-off exceptions, with appointment-conflict protection."""

    def __init__(
        self,
        doctors: DoctorRepository,
        availability: AvailabilityRepository,
        appointments: AppointmentQuery,
        settings: ClinicSettingsRepository,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._doctors = doctors
        self._availability = availability
        self._appointments = appointments
        self._settings = settings
        self._clock = clock
        self._new_id = new_id

    # ---- helpers ----------------------------------------------------------------------------

    def _doctor(self, doctor_id: uuid.UUID) -> Doctor:
        doctor = self._doctors.get(doctor_id)
        if doctor is None:
            raise NotFound("Doctor not found")
        return doctor

    def _editable_doctor(self, actor: User, doctor_id: uuid.UUID) -> Doctor:
        doctor = self._doctor(doctor_id)
        DoctorService.require_can_edit(actor, doctor)
        return doctor

    def _rule(self, doctor_id: uuid.UUID, rule_id: uuid.UUID) -> Availability:
        rule = self._availability.get_rule(rule_id)
        if rule is None or rule.doctor_id != doctor_id:
            raise NotFound("Availability rule not found")
        return rule

    def _exception(self, doctor_id: uuid.UUID, exception_id: uuid.UUID) -> AvailabilityException:
        exception = self._availability.get_exception(exception_id)
        if exception is None or exception.doctor_id != doctor_id:
            raise NotFound("Availability exception not found")
        return exception

    def _ensure_no_orphans(
        self,
        doctor: Doctor,
        before: tuple[Sequence[Availability], Sequence[AvailabilityException]],
        after: tuple[Sequence[Availability], Sequence[AvailabilityException]],
    ) -> None:
        """Reject a change that leaves an upcoming appointment outside the doctor's availability.

        Appointments that were already uncovered before the change are ignored.
        """
        zone = ZoneInfo(self._settings.get().clinic_timezone)
        orphaned = [
            span
            for span in self._appointments.upcoming_spans(doctor.id, self._clock.now())
            if covers(*before, zone, span.start_time, span.end_time)
            and not covers(*after, zone, span.start_time, span.end_time)
        ]
        if orphaned:
            raise AvailabilityConflictsWithAppointments(
                f"{len(orphaned)} upcoming appointment(s) would be outside the doctor's "
                "availability; cancel or reschedule them first"
            )

    @staticmethod
    def _validate_window(start: time | None, end: time | None) -> None:
        if start is not None and end is not None and start >= end:
            raise ValidationFailed("Start time must be before end time")

    # ---- weekly rules -----------------------------------------------------------------------

    def list_rules(self, doctor_id: uuid.UUID) -> list[Availability]:
        self._doctor(doctor_id)
        return self._availability.list_rules(doctor_id)

    def add_rule(
        self, actor: User, doctor_id: uuid.UUID, day: DayOfWeek, start: time, end: time
    ) -> Availability:
        self._editable_doctor(actor, doctor_id)
        rule = Availability(self._new_id(), doctor_id, day, start, end)
        self._validate_rule(rule, self._availability.list_rules(doctor_id))
        self._availability.add_rule(rule)
        return rule

    def update_rule(
        self,
        actor: User,
        doctor_id: uuid.UUID,
        rule_id: uuid.UUID,
        day_of_week: DayOfWeek | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> Availability:
        doctor = self._editable_doctor(actor, doctor_id)
        current = self._rule(doctor_id, rule_id)
        changed = dataclasses.replace(
            current,
            day_of_week=day_of_week or current.day_of_week,
            start_time=start_time or current.start_time,
            end_time=end_time or current.end_time,
        )
        rules = self._availability.list_rules(doctor_id)
        others = [r for r in rules if r.id != rule_id]
        self._validate_rule(changed, others)
        exceptions = self._availability.list_exceptions(doctor_id)
        self._ensure_no_orphans(doctor, (rules, exceptions), ([*others, changed], exceptions))
        self._availability.update_rule(changed)
        return changed

    def delete_rule(self, actor: User, doctor_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        doctor = self._editable_doctor(actor, doctor_id)
        self._rule(doctor_id, rule_id)
        rules = self._availability.list_rules(doctor_id)
        exceptions = self._availability.list_exceptions(doctor_id)
        remaining = [r for r in rules if r.id != rule_id]
        self._ensure_no_orphans(doctor, (rules, exceptions), (remaining, exceptions))
        self._availability.delete_rule(rule_id)

    def _validate_rule(self, rule: Availability, others: Sequence[Availability]) -> None:
        self._validate_window(rule.start_time, rule.end_time)
        for other in others:
            if (
                other.day_of_week == rule.day_of_week
                and rule.start_time < other.end_time
                and other.start_time < rule.end_time
            ):
                raise AvailabilityOverlap("That time overlaps another rule for the same day")

    # ---- one-off exceptions -----------------------------------------------------------------

    def list_exceptions(self, doctor_id: uuid.UUID) -> list[AvailabilityException]:
        self._doctor(doctor_id)
        return self._availability.list_exceptions(doctor_id)

    def add_exception(
        self,
        actor: User,
        doctor_id: uuid.UUID,
        date: Date,
        type: ExceptionType,
        start_time: time | None,
        end_time: time | None,
    ) -> AvailabilityException:
        doctor = self._editable_doctor(actor, doctor_id)
        exception = AvailabilityException(
            self._new_id(), doctor_id, date, type, start_time, end_time
        )
        self._validate_exception(exception)
        rules = self._availability.list_rules(doctor_id)
        exceptions = self._availability.list_exceptions(doctor_id)
        self._ensure_no_orphans(doctor, (rules, exceptions), (rules, [*exceptions, exception]))
        self._availability.add_exception(exception)
        return exception

    def update_exception(
        self,
        actor: User,
        doctor_id: uuid.UUID,
        exception_id: uuid.UUID,
        date: Date | _Unset = UNSET,
        type: ExceptionType | _Unset = UNSET,
        start_time: time | None | _Unset = UNSET,
        end_time: time | None | _Unset = UNSET,
    ) -> AvailabilityException:
        doctor = self._editable_doctor(actor, doctor_id)
        current = self._exception(doctor_id, exception_id)
        changes = {
            name: value
            for name, value in (
                ("date", date),
                ("type", type),
                ("start_time", start_time),
                ("end_time", end_time),
            )
            if not isinstance(value, _Unset)
        }
        changed = dataclasses.replace(current, **changes)  # type: ignore[arg-type]
        self._validate_exception(changed)
        rules = self._availability.list_rules(doctor_id)
        exceptions = self._availability.list_exceptions(doctor_id)
        others = [e for e in exceptions if e.id != exception_id]
        self._ensure_no_orphans(doctor, (rules, exceptions), (rules, [*others, changed]))
        self._availability.update_exception(changed)
        return changed

    def delete_exception(self, actor: User, doctor_id: uuid.UUID, exception_id: uuid.UUID) -> None:
        doctor = self._editable_doctor(actor, doctor_id)
        self._exception(doctor_id, exception_id)
        rules = self._availability.list_rules(doctor_id)
        exceptions = self._availability.list_exceptions(doctor_id)
        remaining = [e for e in exceptions if e.id != exception_id]
        self._ensure_no_orphans(doctor, (rules, exceptions), (rules, remaining))
        self._availability.delete_exception(exception_id)

    def _validate_exception(self, exception: AvailabilityException) -> None:
        start, end = exception.start_time, exception.end_time
        if (start is None) != (end is None):
            raise ValidationFailed("Provide both start and end time, or neither")
        if exception.type == ExceptionType.EXTRA_HOURS and start is None:
            raise ValidationFailed("Extra hours need a start and end time")
        self._validate_window(start, end)
