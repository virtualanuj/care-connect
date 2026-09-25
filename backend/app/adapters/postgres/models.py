import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import (
    AppointmentSource,
    AppointmentStatus,
    AuditAction,
    CancellationType,
    DayOfWeek,
    EmergencyJustification,
    ExceptionType,
    HistoryKind,
    Role,
    TriageSource,
    Urgency,
)


def _enum(enum_class: type, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        create_type=False,  # created by Alembic migrations
        values_callable=lambda e: [member.value for member in e],
    )


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    action: Mapped[AuditAction] = mapped_column(_enum(AuditAction, "audit_action"))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpecialtyRow(Base):
    __tablename__ = "specialties"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    default_slot_length_minutes: Mapped[int] = mapped_column(Integer)


class DoctorRow(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(Text)
    specialty_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("specialties.id"))
    slot_length_minutes: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatientRow(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_normalized: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MedicalHistoryRow(Base):
    __tablename__ = "medical_history_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"))
    kind: Mapped[HistoryKind] = mapped_column(_enum(HistoryKind, "medical_history_kind"))
    amends_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("medical_history_entries.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))


class AvailabilityRow(Base):
    __tablename__ = "availability"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("doctors.id"))
    day_of_week: Mapped[DayOfWeek] = mapped_column(_enum(DayOfWeek, "day_of_week"))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class AvailabilityExceptionRow(Base):
    __tablename__ = "availability_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("doctors.id"))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[ExceptionType] = mapped_column(_enum(ExceptionType, "availability_exception_type"))
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)


class ClinicSettingsRow(Base):
    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    cancellation_cutoff_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    emergency_slots_per_doctor_per_day: Mapped[int] = mapped_column(Integer)
    follow_up_max_days: Mapped[int] = mapped_column(Integer)
    clinic_timezone: Mapped[str] = mapped_column(Text)
    default_triage_specialty_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("specialties.id"), nullable=True
    )


class AppointmentRow(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("doctors.id"))
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        _enum(AppointmentStatus, "appointment_status")
    )
    source: Mapped[AppointmentSource] = mapped_column(
        _enum(AppointmentSource, "appointment_source")
    )
    is_emergency_slot: Mapped[bool] = mapped_column(Boolean)
    emergency_justification: Mapped[EmergencyJustification | None] = mapped_column(
        _enum(EmergencyJustification, "emergency_justification"), nullable=True
    )
    emergency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    reported_symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    triage_result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    follow_up_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    cancellation_type: Mapped[CancellationType | None] = mapped_column(
        _enum(CancellationType, "cancellation_type"), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rescheduled_to_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("appointments.id"), nullable=True
    )


class TriageResultRow(Base):
    __tablename__ = "ai_triage_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id"))
    reported_symptoms: Mapped[str] = mapped_column(Text)
    urgency: Mapped[Urgency] = mapped_column(_enum(Urgency, "urgency"))
    suggested_specialty_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("specialties.id"))
    confidence_score: Mapped[float] = mapped_column(Float)
    source: Mapped[TriageSource] = mapped_column(_enum(TriageSource, "triage_source"))
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclaimer: Mapped[str] = mapped_column(Text)
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overridden_urgency: Mapped[Urgency | None] = mapped_column(
        _enum(Urgency, "urgency"), nullable=True
    )
    overridden_specialty_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("specialties.id"), nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PreVisitSummaryRow(Base):
    __tablename__ = "pre_visit_summaries"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointments.id"), primary_key=True
    )
    summary: Mapped[str] = mapped_column(Text)
    disclaimer: Mapped[str] = mapped_column(Text)
    inputs_hash: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VisitNoteRow(Base):
    __tablename__ = "visit_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("appointments.id"), unique=True
    )
    doctor_notes: Mapped[str] = mapped_column(Text)
    ai_draft_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_draft_disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
