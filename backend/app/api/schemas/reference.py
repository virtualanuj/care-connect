import uuid
from datetime import date as Date
from datetime import datetime

from pydantic import Field

from app.api.schemas.base import CamelModel
from app.api.schemas.types import ClockTime, Email
from app.domain.models import (
    Availability,
    AvailabilityException,
    ClinicSettings,
    DayOfWeek,
    Doctor,
    ExceptionType,
    HistoryKind,
    MedicalHistoryEntry,
    Page,
    Patient,
    Specialty,
)

# ---- clinic settings ---------------------------------------------------------------------------


class ClinicSettingsOut(CamelModel):
    cancellation_cutoff_hours: float
    emergency_slots_per_doctor_per_day: int
    follow_up_max_days: int
    clinic_timezone: str
    default_triage_specialty_id: uuid.UUID | None

    @classmethod
    def from_domain(cls, s: ClinicSettings) -> "ClinicSettingsOut":
        return cls(**vars(s))


class ClinicSettingsUpdate(CamelModel):
    cancellation_cutoff_hours: float | None = Field(default=None, ge=0)
    emergency_slots_per_doctor_per_day: int | None = Field(default=None, ge=0)
    follow_up_max_days: int | None = Field(default=None, ge=1)
    clinic_timezone: str | None = None
    default_triage_specialty_id: uuid.UUID | None = None


# ---- specialties and doctors -------------------------------------------------------------------


class SpecialtyOut(CamelModel):
    id: uuid.UUID
    name: str
    default_slot_length_minutes: int

    @classmethod
    def from_domain(cls, s: Specialty) -> "SpecialtyOut":
        return cls(id=s.id, name=s.name, default_slot_length_minutes=s.default_slot_length_minutes)


class SpecialtyCreate(CamelModel):
    name: str = Field(min_length=1)
    default_slot_length_minutes: int = Field(ge=5)


class SpecialtyUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1)
    default_slot_length_minutes: int | None = Field(default=None, ge=5)


class DoctorOut(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    specialty_id: uuid.UUID
    slot_length_minutes: int
    active: bool

    @classmethod
    def from_domain(cls, d: Doctor) -> "DoctorOut":
        return cls(
            id=d.id,
            user_id=d.user_id,
            name=d.name,
            specialty_id=d.specialty_id,
            slot_length_minutes=d.slot_length_minutes,
            active=d.active,
        )


class DoctorCreate(CamelModel):
    user_id: uuid.UUID
    name: str = Field(min_length=1)
    specialty_id: uuid.UUID
    slot_length_minutes: int | None = Field(default=None, ge=5)


class DoctorUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1)
    specialty_id: uuid.UUID | None = None
    slot_length_minutes: int | None = Field(default=None, ge=5)
    active: bool | None = None


# ---- patients and history ----------------------------------------------------------------------


class PatientOut(CamelModel):
    id: uuid.UUID
    name: str
    phone: str
    dob: Date | None
    email: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, p: Patient) -> "PatientOut":
        return cls(
            id=p.id, name=p.name, phone=p.phone, dob=p.dob, email=p.email, created_at=p.created_at
        )


class PatientCreate(CamelModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    dob: Date | None = None
    email: Email | None = None


class PatientUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, min_length=1)
    dob: Date | None = None
    email: Email | None = None


class PatientPage(CamelModel):
    items: list[PatientOut]
    page: int
    page_size: int
    total: int

    @classmethod
    def from_domain(cls, result: Page[Patient], page: int, page_size: int) -> "PatientPage":
        return cls(
            items=[PatientOut.from_domain(p) for p in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
        )


class MedicalHistoryEntryOut(CamelModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    kind: HistoryKind
    amends_entry_id: uuid.UUID | None
    description: str
    recorded_at: datetime
    recorded_by: uuid.UUID

    @classmethod
    def from_domain(cls, e: MedicalHistoryEntry) -> "MedicalHistoryEntryOut":
        return cls(
            id=e.id,
            patient_id=e.patient_id,
            kind=e.kind,
            amends_entry_id=e.amends_entry_id,
            description=e.description,
            recorded_at=e.recorded_at,
            recorded_by=e.recorded_by,
        )


class MedicalHistoryEntryCreate(CamelModel):
    kind: HistoryKind = HistoryKind.ENTRY
    amends_entry_id: uuid.UUID | None = None
    description: str = Field(min_length=1)


# ---- availability ------------------------------------------------------------------------------


class AvailabilityOut(CamelModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    day_of_week: DayOfWeek
    start_time: ClockTime
    end_time: ClockTime

    @classmethod
    def from_domain(cls, a: Availability) -> "AvailabilityOut":
        return cls(
            id=a.id,
            doctor_id=a.doctor_id,
            day_of_week=a.day_of_week,
            start_time=a.start_time,
            end_time=a.end_time,
        )


class AvailabilityCreate(CamelModel):
    day_of_week: DayOfWeek
    start_time: ClockTime
    end_time: ClockTime


class AvailabilityUpdate(CamelModel):
    day_of_week: DayOfWeek | None = None
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None


class AvailabilityExceptionOut(CamelModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    date: Date
    type: ExceptionType
    start_time: ClockTime | None
    end_time: ClockTime | None

    @classmethod
    def from_domain(cls, e: AvailabilityException) -> "AvailabilityExceptionOut":
        return cls(
            id=e.id,
            doctor_id=e.doctor_id,
            date=e.date,
            type=e.type,
            start_time=e.start_time,
            end_time=e.end_time,
        )


class AvailabilityExceptionCreate(CamelModel):
    date: Date
    type: ExceptionType
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None


class AvailabilityExceptionUpdate(CamelModel):
    date: Date | None = None
    type: ExceptionType | None = None
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None
