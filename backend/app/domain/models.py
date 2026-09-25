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


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"

    @property
    def holds_slot(self) -> bool:
        """Cancelled and no-show appointments release their slot; all others hold it."""
        return self not in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)


class AppointmentSource(StrEnum):
    SCHEDULED = "scheduled"
    WALK_IN = "walk_in"


class CancellationType(StrEnum):
    STANDARD = "standard"
    FORCE = "force"
    RESCHEDULED = "rescheduled"


class EmergencyJustification(StrEnum):
    TRIAGE = "triage"
    FRONT_DESK_JUDGMENT = "front_desk_judgment"


@dataclass
class Appointment:
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    source: AppointmentSource
    is_emergency_slot: bool
    created_at: datetime
    emergency_justification: EmergencyJustification | None = None
    emergency_reason: str | None = None
    emergency_authorized_by: uuid.UUID | None = None
    reported_symptoms: str | None = None
    triage_result_id: uuid.UUID | None = None
    follow_up_of_id: uuid.UUID | None = None
    checked_in_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by: uuid.UUID | None = None
    cancellation_type: CancellationType | None = None
    cancel_reason: str | None = None
    rescheduled_to_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Slot:
    """A bookable slot returned by search. `is_emergency` marks held-back emergency capacity."""

    doctor_id: uuid.UUID
    specialty_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    is_emergency: bool


@dataclass(frozen=True)
class QueueItem:
    appointment: Appointment
    patient_name: str
    doctor_name: str


@dataclass(frozen=True)
class DailyQueue:
    """One clinic-local day's appointments in mutually exclusive status buckets."""

    day: date
    booked: list[QueueItem]
    checked_in: list[QueueItem]
    in_progress: list[QueueItem]
    completed: list[QueueItem]
    no_shows: list[QueueItem]
    cancelled: list[QueueItem]


class Urgency(StrEnum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"


class TriageSource(StrEnum):
    MODEL = "model"
    RED_FLAG = "red_flag"


@dataclass(frozen=True)
class PatientIdentifiers:
    """Direct identifiers known about a patient; scrubbed from text before any AI call."""

    name: str
    phone: str | None = None
    email: str | None = None
    dob: date | None = None


@dataclass(frozen=True)
class TriageModelOutput:
    urgency: Urgency
    suggested_specialty: str
    confidence: float


@dataclass
class TriageResult:
    id: uuid.UUID
    patient_id: uuid.UUID
    reported_symptoms: str
    urgency: Urgency
    suggested_specialty_id: uuid.UUID
    confidence_score: float
    source: TriageSource
    disclaimer: str
    created_at: datetime
    model_version: str | None = None
    prompt_version: str | None = None
    overridden_by: uuid.UUID | None = None
    overridden_at: datetime | None = None
    overridden_urgency: Urgency | None = None
    overridden_specialty_id: uuid.UUID | None = None
    override_reason: str | None = None

    @property
    def effective_urgency(self) -> Urgency:
        """The staff override if there is one (it always wins), otherwise the original."""
        return self.overridden_urgency or self.urgency
