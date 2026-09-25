from __future__ import annotations

import uuid

from app.domain.errors import UserAlreadyExists
from app.domain.models import AuditAction, AuditEntry, Page, User


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    def add(self, user: User) -> None:
        if self.get_by_email(user.email) is not None:
            raise UserAlreadyExists("A user with this email already exists")
        self.users[user.id] = user

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def list(self, page: int, page_size: int) -> Page[User]:
        ordered = sorted(self.users.values(), key=lambda u: u.email.lower())
        start = (page - 1) * page_size
        return Page(items=ordered[start : start + page_size], total=len(ordered))

    def update(self, user: User) -> None:
        self.users[user.id] = user


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        matching = [e for e in self.entries if action is None or e.action == action]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        start = (page - 1) * page_size
        return Page(items=matching[start : start + page_size], total=len(matching))


# ---- M2 reference data ------------------------------------------------------------------------
from datetime import datetime  # noqa: E402

from app.domain.errors import (  # noqa: E402
    DoctorAlreadyExists,
    PatientAlreadyExists,
    SpecialtyAlreadyExists,
)
from app.domain.models import (  # noqa: E402
    AppointmentSpan,
    Availability,
    AvailabilityException,
    ClinicSettings,
    Doctor,
    MedicalHistoryEntry,
    Patient,
    Specialty,
)


class InMemorySpecialtyRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Specialty] = {}

    def _name_taken(self, name: str, except_id: uuid.UUID | None = None) -> bool:
        return any(
            s.name.lower() == name.lower() and s.id != except_id for s in self.items.values()
        )

    def add(self, specialty: Specialty) -> None:
        if self._name_taken(specialty.name):
            raise SpecialtyAlreadyExists("A specialty with this name already exists")
        self.items[specialty.id] = specialty

    def get(self, specialty_id: uuid.UUID) -> Specialty | None:
        return self.items.get(specialty_id)

    def list(self) -> list[Specialty]:
        return sorted(self.items.values(), key=lambda s: s.name.lower())

    def update(self, specialty: Specialty) -> None:
        if self._name_taken(specialty.name, specialty.id):
            raise SpecialtyAlreadyExists("A specialty with this name already exists")
        self.items[specialty.id] = specialty


class InMemoryDoctorRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Doctor] = {}

    def add(self, doctor: Doctor) -> None:
        if self.get_by_user_id(doctor.user_id) is not None:
            raise DoctorAlreadyExists("This user already has a doctor profile")
        self.items[doctor.id] = doctor

    def get(self, doctor_id: uuid.UUID) -> Doctor | None:
        return self.items.get(doctor_id)

    def get_by_user_id(self, user_id: uuid.UUID) -> Doctor | None:
        return next((d for d in self.items.values() if d.user_id == user_id), None)

    def list(self, specialty_id: uuid.UUID | None) -> list[Doctor]:
        matching = [d for d in self.items.values() if specialty_id in (None, d.specialty_id)]
        return sorted(matching, key=lambda d: d.name.lower())

    def update(self, doctor: Doctor) -> None:
        self.items[doctor.id] = doctor


class InMemoryPatientRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Patient] = {}

    def _identity_taken(self, patient: Patient) -> bool:
        from app.domain.patient_identity import normalize_name

        return any(
            p.id != patient.id
            and p.phone == patient.phone
            and normalize_name(p.name) == normalize_name(patient.name)
            for p in self.items.values()
        )

    def add(self, patient: Patient) -> None:
        if self._identity_taken(patient):
            raise PatientAlreadyExists("A patient with this name and phone already exists")
        self.items[patient.id] = patient

    def get(self, patient_id: uuid.UUID) -> Patient | None:
        return self.items.get(patient_id)

    def get_many(self, ids) -> dict[uuid.UUID, Patient]:  # type: ignore[no-untyped-def]
        return {i: self.items[i] for i in ids if i in self.items}

    def find(
        self, phone: str | None, name_prefix: str | None, page: int, page_size: int
    ) -> Page[Patient]:
        from app.domain.patient_identity import normalize_name

        matching = [
            p
            for p in self.items.values()
            if (phone is None or p.phone == phone)
            and (name_prefix is None or normalize_name(p.name).startswith(name_prefix))
        ]
        matching.sort(key=lambda p: normalize_name(p.name))
        start = (page - 1) * page_size
        return Page(items=matching[start : start + page_size], total=len(matching))

    def update(self, patient: Patient) -> None:
        if self._identity_taken(patient):
            raise PatientAlreadyExists("A patient with this name and phone already exists")
        self.items[patient.id] = patient


class InMemoryMedicalHistoryRepository:
    def __init__(self) -> None:
        self.items: list[MedicalHistoryEntry] = []

    def add(self, entry: MedicalHistoryEntry) -> None:
        self.items.append(entry)

    def get(self, entry_id: uuid.UUID) -> MedicalHistoryEntry | None:
        return next((e for e in self.items if e.id == entry_id), None)

    def list_for_patient(self, patient_id: uuid.UUID) -> list[MedicalHistoryEntry]:
        return sorted(
            (e for e in self.items if e.patient_id == patient_id), key=lambda e: e.recorded_at
        )


class InMemoryAvailabilityRepository:
    def __init__(self) -> None:
        self.rules: dict[uuid.UUID, Availability] = {}
        self.exceptions: dict[uuid.UUID, AvailabilityException] = {}

    def add_rule(self, rule: Availability) -> None:
        self.rules[rule.id] = rule

    def get_rule(self, rule_id: uuid.UUID) -> Availability | None:
        return self.rules.get(rule_id)

    def list_rules(self, doctor_id: uuid.UUID) -> list[Availability]:
        found = [r for r in self.rules.values() if r.doctor_id == doctor_id]
        return sorted(found, key=lambda r: (r.day_of_week.value, r.start_time))

    def update_rule(self, rule: Availability) -> None:
        self.rules[rule.id] = rule

    def delete_rule(self, rule_id: uuid.UUID) -> None:
        self.rules.pop(rule_id, None)

    def add_exception(self, exception: AvailabilityException) -> None:
        self.exceptions[exception.id] = exception

    def get_exception(self, exception_id: uuid.UUID) -> AvailabilityException | None:
        return self.exceptions.get(exception_id)

    def list_exceptions(self, doctor_id: uuid.UUID) -> list[AvailabilityException]:
        found = [e for e in self.exceptions.values() if e.doctor_id == doctor_id]
        return sorted(found, key=lambda e: e.date)

    def update_exception(self, exception: AvailabilityException) -> None:
        self.exceptions[exception.id] = exception

    def delete_exception(self, exception_id: uuid.UUID) -> None:
        self.exceptions.pop(exception_id, None)


class InMemoryClinicSettingsRepository:
    def __init__(self) -> None:
        self.settings = ClinicSettings(2.0, 1, 30, "UTC", None)

    def get(self) -> ClinicSettings:
        return ClinicSettings(**vars(self.settings))

    def save(self, settings: ClinicSettings) -> None:
        self.settings = ClinicSettings(**vars(settings))


class FakeAppointmentQuery:
    """Fake for the appointments table (arrives in M3): tests add spans per doctor."""

    def __init__(self) -> None:
        self.spans: dict[uuid.UUID, list[AppointmentSpan]] = {}

    def add(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> None:
        self.spans.setdefault(doctor_id, []).append(AppointmentSpan(start, end))

    def upcoming_spans(self, doctor_id: uuid.UUID, after: datetime) -> list[AppointmentSpan]:
        return [s for s in self.spans.get(doctor_id, []) if s.end_time > after]

    def spans_between(
        self, doctor_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[AppointmentSpan]:
        return [
            s for s in self.spans.get(doctor_id, []) if s.start_time < end and start < s.end_time
        ]


# ---- M3 appointments --------------------------------------------------------------------------
from app.domain.errors import PatientAlreadyBooked, SlotAlreadyBooked  # noqa: E402
from app.domain.models import Appointment, AppointmentStatus  # noqa: E402


class InMemoryAppointmentRepository:
    """Emulates the database's overlap constraints so services can be tested without Postgres."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Appointment] = {}

    def _holding(self) -> list[Appointment]:
        return [a for a in self.items.values() if a.status.holds_slot]

    def add(self, appointment: Appointment) -> None:
        if appointment.status.holds_slot:
            for other in self._holding():
                overlaps = (
                    other.start_time < appointment.end_time
                    and appointment.start_time < other.end_time
                )
                if overlaps and other.doctor_id == appointment.doctor_id:
                    raise SlotAlreadyBooked("That time is already booked for this doctor")
                if overlaps and other.patient_id == appointment.patient_id:
                    raise PatientAlreadyBooked(
                        "This patient already has an overlapping appointment"
                    )
        self.items[appointment.id] = appointment

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self.items.get(appointment_id)

    def update(self, appointment: Appointment) -> None:
        self.items[appointment.id] = appointment

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
        matching = [
            a
            for a in self.items.values()
            if (doctor_id is None or a.doctor_id == doctor_id)
            and (patient_id is None or a.patient_id == patient_id)
            and (starts_from is None or a.start_time >= starts_from)
            and (starts_before is None or a.start_time < starts_before)
            and (status is None or a.status == status)
        ]
        matching.sort(key=lambda a: a.start_time)
        start = (page - 1) * page_size
        return Page(items=matching[start : start + page_size], total=len(matching))

    def upcoming_spans(self, doctor_id: uuid.UUID, after: datetime) -> list[AppointmentSpan]:
        return [
            AppointmentSpan(a.start_time, a.end_time)
            for a in self._holding()
            if a.doctor_id == doctor_id and a.end_time > after
        ]

    def spans_between(
        self, doctor_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[AppointmentSpan]:
        return [
            AppointmentSpan(a.start_time, a.end_time)
            for a in self._holding()
            if a.doctor_id == doctor_id and a.start_time < end and start < a.end_time
        ]
