"""Ports: interfaces the service layer depends on (implemented by adapters)."""

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Protocol

from app.domain.models import (
    Appointment,
    AppointmentSpan,
    AppointmentStatus,
    AuditAction,
    AuditEntry,
    Availability,
    AvailabilityException,
    ClinicSettings,
    Doctor,
    MedicalHistoryEntry,
    Page,
    Patient,
    PatientIdentifiers,
    Role,
    Specialty,
    TriageModelOutput,
    TriageResult,
    User,
)


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as a timezone-aware UTC datetime."""
        ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenClaims(Protocol):
    subject: uuid.UUID
    role: Role
    expires_at: datetime


class TokenCodec(Protocol):
    def encode(self, subject: uuid.UUID, role: Role, issued_at: datetime, ttl_seconds: int) -> str:
        """Create a signed token."""
        ...

    def decode(self, token: str) -> "TokenClaims | None":
        """Return the claims if the signature and structure are valid, else None.

        Expiry is NOT checked here: the service compares `expires_at` against the Clock.
        """
        ...


class RateLimiter(Protocol):
    def is_blocked(self, key: str) -> bool: ...

    def record_failure(self, key: str) -> None: ...

    def reset(self, key: str) -> None: ...


class UserRepository(Protocol):
    def add(self, user: User) -> None:
        """Insert a user. Raises `UserAlreadyExists` if the email is taken (case-insensitive)."""
        ...

    def get(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def list(self, page: int, page_size: int) -> Page[User]: ...

    def update(self, user: User) -> None: ...


class AuditRepository(Protocol):
    def add(self, entry: AuditEntry) -> None: ...

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        """Newest first."""
        ...


class SpecialtyRepository(Protocol):
    def add(self, specialty: Specialty) -> None:
        """Raises `SpecialtyAlreadyExists` if the name is taken (case-insensitive)."""
        ...

    def get(self, specialty_id: uuid.UUID) -> Specialty | None: ...

    def list(self) -> list[Specialty]: ...

    def update(self, specialty: Specialty) -> None:
        """Raises `SpecialtyAlreadyExists` on a name collision."""
        ...


class DoctorRepository(Protocol):
    def add(self, doctor: Doctor) -> None:
        """Raises `DoctorAlreadyExists` if the user already has a doctor profile."""
        ...

    def get(self, doctor_id: uuid.UUID) -> Doctor | None: ...

    def get_by_user_id(self, user_id: uuid.UUID) -> Doctor | None: ...

    def list(self, specialty_id: uuid.UUID | None) -> list[Doctor]: ...

    def update(self, doctor: Doctor) -> None: ...


class PatientRepository(Protocol):
    def add(self, patient: Patient) -> None:
        """Raises `PatientAlreadyExists` on a (phone, normalized name) collision."""
        ...

    def get(self, patient_id: uuid.UUID) -> Patient | None: ...

    def get_many(self, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, Patient]:
        """Load several patients with one query."""
        ...

    def find(
        self, phone: str | None, name_prefix: str | None, page: int, page_size: int
    ) -> Page[Patient]:
        """`phone` is E.164; `name_prefix` matches the normalized name. Ordered by name."""
        ...

    def update(self, patient: Patient) -> None:
        """Raises `PatientAlreadyExists` on a (phone, normalized name) collision."""
        ...


class MedicalHistoryRepository(Protocol):
    """Append-only: there is intentionally no update or delete."""

    def add(self, entry: MedicalHistoryEntry) -> None: ...

    def get(self, entry_id: uuid.UUID) -> MedicalHistoryEntry | None: ...

    def list_for_patient(self, patient_id: uuid.UUID) -> list[MedicalHistoryEntry]:
        """Oldest first."""
        ...


class AvailabilityRepository(Protocol):
    def add_rule(self, rule: Availability) -> None: ...

    def get_rule(self, rule_id: uuid.UUID) -> Availability | None: ...

    def list_rules(self, doctor_id: uuid.UUID) -> list[Availability]: ...

    def update_rule(self, rule: Availability) -> None: ...

    def delete_rule(self, rule_id: uuid.UUID) -> None: ...

    def add_exception(self, exception: AvailabilityException) -> None: ...

    def get_exception(self, exception_id: uuid.UUID) -> AvailabilityException | None: ...

    def list_exceptions(self, doctor_id: uuid.UUID) -> list[AvailabilityException]: ...

    def update_exception(self, exception: AvailabilityException) -> None: ...

    def delete_exception(self, exception_id: uuid.UUID) -> None: ...


class ClinicSettingsRepository(Protocol):
    def get(self) -> ClinicSettings: ...

    def save(self, settings: ClinicSettings) -> None: ...


class AppointmentQuery(Protocol):
    def upcoming_spans(self, doctor_id: uuid.UUID, after: datetime) -> list[AppointmentSpan]:
        """Slot-holding appointments of the doctor that end after `after`."""
        ...

    def spans_between(
        self, doctor_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[AppointmentSpan]:
        """Slot-holding appointments of the doctor overlapping [start, end)."""
        ...


class AppointmentRepository(AppointmentQuery, Protocol):
    def add(self, appointment: Appointment) -> None:
        """Insert. Raises `SlotAlreadyBooked` / `PatientAlreadyBooked` on an overlap."""
        ...

    def get(self, appointment_id: uuid.UUID) -> Appointment | None: ...

    def triage_used_by(self, triage_id: uuid.UUID, doctor_id: uuid.UUID) -> bool:
        """True if one of the doctor's appointments references this triage result."""
        ...

    def update(self, appointment: Appointment) -> None:
        """Persist changes to an existing appointment (status, cancellation fields, links)."""
        ...

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
        """Filter on start time in [starts_from, starts_before). Ordered by start time."""
        ...


class TriageRepository(Protocol):
    def add(self, result: TriageResult) -> None: ...

    def get(self, triage_id: uuid.UUID) -> TriageResult | None: ...

    def list_for_patient(self, patient_id: uuid.UUID) -> list[TriageResult]:
        """Newest first; every run is kept for audit."""
        ...

    def update(self, result: TriageResult) -> None: ...


class LLMProvider(Protocol):
    """The only door to an external AI service (implemented by the Gemini adapter).

    Implementations must scrub `identifiers` from every outbound payload themselves, validate the
    response, and raise `AiServiceUnavailable` on any failure or invalid answer.
    """

    model_version: str
    prompt_version: str

    def classify_triage(
        self,
        symptoms: str,
        history: Sequence[str],
        specialties: Sequence[str],
        identifiers: PatientIdentifiers,
    ) -> TriageModelOutput: ...

    def generate_text(self, task: str, text: str, identifiers: PatientIdentifiers) -> str:
        """Free-text generation (pre-visit summary, note draft) - used from M7."""
        ...
