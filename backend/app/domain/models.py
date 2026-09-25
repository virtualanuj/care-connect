"""Domain entities and enums (framework-free)."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum


class Role(StrEnum):
    DOCTOR = "doctor"
    FRONT_DESK_ADMIN = "front_desk_admin"


class AuditAction(StrEnum):
    FORCE_CANCEL = "force_cancel"
    TRIAGE_OVERRIDE = "triage_override"
    EMERGENCY_AUTHORIZATION = "emergency_authorization"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    PASSWORD_RESET = "password_reset"
    CLINIC_SETTINGS_CHANGED = "clinic_settings_changed"


@dataclass
class User:
    id: uuid.UUID
    email: str
    name: str
    role: Role
    password_hash: str
    active: bool = True


@dataclass(frozen=True)
class AuditEntry:
    id: uuid.UUID
    action: AuditAction
    actor_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    created_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class Page[T]:
    items: list[T] = field(default_factory=list)
    total: int = 0


class DayOfWeek(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @classmethod
    def from_date(cls, value: date) -> "DayOfWeek":
        return list(cls)[value.weekday()]


class ExceptionType(StrEnum):
    UNAVAILABLE = "unavailable"
    EXTRA_HOURS = "extra_hours"


class HistoryKind(StrEnum):
    ENTRY = "entry"
    AMENDMENT = "amendment"


@dataclass
class Specialty:
    id: uuid.UUID
    name: str
    default_slot_length_minutes: int


@dataclass
class Doctor:
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    specialty_id: uuid.UUID
    slot_length_minutes: int
    active: bool = True


@dataclass
class Patient:
    id: uuid.UUID
    name: str
    phone: str  # E.164
    created_at: datetime
    dob: date | None = None
    email: str | None = None


@dataclass(frozen=True)
class MedicalHistoryEntry:
    id: uuid.UUID
    patient_id: uuid.UUID
    kind: HistoryKind
    description: str
    recorded_at: datetime
    recorded_by: uuid.UUID
    amends_entry_id: uuid.UUID | None = None


@dataclass
class Availability:
    id: uuid.UUID
    doctor_id: uuid.UUID
    day_of_week: DayOfWeek
    start_time: time
    end_time: time


@dataclass
class AvailabilityException:
    id: uuid.UUID
    doctor_id: uuid.UUID
    date: date
    type: ExceptionType
    start_time: time | None = None
    end_time: time | None = None


@dataclass
class ClinicSettings:
    cancellation_cutoff_hours: float
    emergency_slots_per_doctor_per_day: int
    follow_up_max_days: int
    clinic_timezone: str
    default_triage_specialty_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AppointmentSpan:
    """Time range of a non-cancelled appointment (used for availability conflict checks)."""

    start_time: datetime
    end_time: datetime
