from __future__ import annotations

import builtins
import time
import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.adapters.postgres._errors import violates
from app.adapters.postgres.models import AppointmentRow
from app.domain.errors import PatientAlreadyBooked, SlotAlreadyBooked
from app.domain.models import Appointment, AppointmentSpan, AppointmentStatus, Page

DOCTOR_OVERLAP = "appt_no_doctor_overlap"
PATIENT_OVERLAP = "appt_no_patient_overlap"

# Bookings that share a doctor or a patient are queued with transaction-level advisory locks,
# always taken in sorted key order, so concurrent inserts cannot deadlock on the exclusion
# constraints. The constraints remain the actual guarantee; the locks only order the attempts.
# Under heavy concurrency Postgres may still abort one of several racing inserts with a deadlock
# (40P01) or serialization failure (40001) instead of an exclusion violation. Retrying lets the
# loser see the winner's committed row and fail with the proper overlap error.
_RETRYABLE_SQLSTATES = ("40P01", "40001")
_MAX_ATTEMPTS = 5

# Statuses that free their slot (mirrors the WHERE clause of the exclusion constraints).
_RELEASED = (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)

_FIELDS = (
    "id",
    "doctor_id",
    "patient_id",
    "start_time",
    "end_time",
    "status",
    "source",
    "is_emergency_slot",
    "created_at",
    "emergency_justification",
    "emergency_reason",
    "emergency_authorized_by",
    "reported_symptoms",
    "triage_result_id",
    "follow_up_of_id",
    "checked_in_at",
    "completed_at",
    "cancelled_at",
    "cancelled_by",
    "cancellation_type",
    "cancel_reason",
    "rescheduled_to_id",
)


def _lock_key(identifier: uuid.UUID) -> int:
    """A stable signed 64-bit key for pg_advisory_xact_lock."""
    return int.from_bytes(identifier.bytes[:8], "big", signed=True)


def _to_domain(row: AppointmentRow) -> Appointment:
    return Appointment(**{name: getattr(row, name) for name in _FIELDS})


class PostgresAppointmentRepository:
    """Appointments. Overlaps are enforced by the database's exclusion constraints."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _lock_participants(self, appointment: Appointment) -> None:
        keys = sorted({_lock_key(appointment.doctor_id), _lock_key(appointment.patient_id)})
        for key in keys:
            self._session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def add(self, appointment: Appointment) -> None:
        self._lock_participants(appointment)
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            row = AppointmentRow(**{name: getattr(appointment, name) for name in _FIELDS})
            try:
                with self._session.begin_nested():
                    self._session.add(row)
                return
            except IntegrityError as error:
                if violates(error, DOCTOR_OVERLAP):
                    raise SlotAlreadyBooked(
                        "That time is already booked for this doctor"
                    ) from error
                if violates(error, PATIENT_OVERLAP):
                    raise PatientAlreadyBooked(
                        "This patient already has an overlapping appointment"
                    ) from error
                raise
            except OperationalError as error:
                retryable = getattr(error.orig, "sqlstate", None) in _RETRYABLE_SQLSTATES
                if not retryable or attempt == _MAX_ATTEMPTS:
                    raise
                time.sleep(0.02 * attempt)  # let the winning transaction finish

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        row = self._session.get(AppointmentRow, appointment_id)
        return _to_domain(row) if row else None

    def triage_used_by(self, triage_id: uuid.UUID, doctor_id: uuid.UUID) -> bool:
        found = self._session.scalar(
            select(func.count())
            .select_from(AppointmentRow)
            .where(
                AppointmentRow.triage_result_id == triage_id,
                AppointmentRow.doctor_id == doctor_id,
            )
        )
        return bool(found)

    def update(self, appointment: Appointment) -> None:
        row = self._session.get(AppointmentRow, appointment.id)
        if row is None:
            return
        for name in _FIELDS:
            if name != "id":
                setattr(row, name, getattr(appointment, name))
        self._session.flush()

    def list(
        self,
        doctor_id: uuid.UUID | None,
        patient_id: uuid.UUID | None,
        starts_from: datetime | None,
        starts_before: datetime | None,
        status: AppointmentStatus | None,
        page: int,
        page_size: int,
    ) -> Page[Appointment]:
        conditions = []
        if doctor_id is not None:
            conditions.append(AppointmentRow.doctor_id == doctor_id)
        if patient_id is not None:
            conditions.append(AppointmentRow.patient_id == patient_id)
        if starts_from is not None:
            conditions.append(AppointmentRow.start_time >= starts_from)
        if starts_before is not None:
            conditions.append(AppointmentRow.start_time < starts_before)
        if status is not None:
            conditions.append(AppointmentRow.status == status)
        rows = self._session.scalars(
            select(AppointmentRow)
            .where(*conditions)
            .order_by(AppointmentRow.start_time, AppointmentRow.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        total = self._session.scalar(
            select(func.count()).select_from(AppointmentRow).where(*conditions)
        )
        return Page(items=[_to_domain(r) for r in rows], total=total or 0)

    def upcoming_spans(
        self, doctor_id: uuid.UUID, after: datetime
    ) -> builtins.list[AppointmentSpan]:
        rows = self._session.execute(
            select(AppointmentRow.start_time, AppointmentRow.end_time).where(
                AppointmentRow.doctor_id == doctor_id,
                AppointmentRow.status.not_in(_RELEASED),
                AppointmentRow.end_time > after,
            )
        )
        return [AppointmentSpan(start, end) for start, end in rows]

    def spans_between(
        self, doctor_id: uuid.UUID, start: datetime, end: datetime
    ) -> builtins.list[AppointmentSpan]:
        rows = self._session.execute(
            select(AppointmentRow.start_time, AppointmentRow.end_time).where(
                AppointmentRow.doctor_id == doctor_id,
                AppointmentRow.status.not_in(_RELEASED),
                AppointmentRow.start_time < end,
                AppointmentRow.end_time > start,
            )
        )
        return [AppointmentSpan(s, e) for s, e in rows]
