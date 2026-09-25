import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

from app.domain.errors import NotFound, ValidationFailed
from app.domain.models import HistoryKind, MedicalHistoryEntry, Page, Patient, User
from app.domain.patient_identity import normalize_name, normalize_phone
from app.domain.ports import Clock, MedicalHistoryRepository, PatientRepository


class PatientService:
    """Patient records (identity = E.164 phone + normalized name) and their medical history."""

    def __init__(
        self,
        patients: PatientRepository,
        history: MedicalHistoryRepository,
        clock: Clock,
        default_region: str,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._patients = patients
        self._history = history
        self._clock = clock
        self._region = default_region
        self._new_id = new_id

    # ---- patients ---------------------------------------------------------------------------

    def register(
        self, name: str, phone: str, dob: date | None = None, email: str | None = None
    ) -> Patient:
        clean_name = self._require_name(name)
        patient = Patient(
            id=self._new_id(),
            name=clean_name,
            phone=normalize_phone(phone, self._region),
            created_at=self._clock.now(),
            dob=dob,
            email=email,
        )
        self._patients.add(patient)
        return patient

    def search(
        self, phone: str | None, name: str | None, page: int, page_size: int
    ) -> Page[Patient]:
        e164 = normalize_phone(phone, self._region) if phone else None
        prefix = normalize_name(name) if name else None
        return self._patients.find(e164, prefix or None, page, page_size)

    def get(self, patient_id: uuid.UUID) -> Patient:
        patient = self._patients.get(patient_id)
        if patient is None:
            raise NotFound("Patient not found")
        return patient

    def update(self, patient_id: uuid.UUID, changes: dict[str, Any]) -> Patient:
        """Apply only the keys present in `changes` (name, phone, dob, email)."""
        patient = self.get(patient_id)
        if "name" in changes:
            patient.name = self._require_name(changes["name"])
        if "phone" in changes:
            patient.phone = normalize_phone(changes["phone"], self._region)
        if "dob" in changes:
            patient.dob = changes["dob"]
        if "email" in changes:
            patient.email = changes["email"]
        self._patients.update(patient)
        return patient

    # ---- medical history (append-only) ------------------------------------------------------

    def add_history(
        self,
        actor: User,
        patient_id: uuid.UUID,
        kind: HistoryKind,
        description: str,
        amends_entry_id: uuid.UUID | None,
    ) -> MedicalHistoryEntry:
        self.get(patient_id)
        if not description.strip():
            raise ValidationFailed("Description is required")
        if kind == HistoryKind.ENTRY and amends_entry_id is not None:
            raise ValidationFailed("Only an amendment can reference another entry")
        if kind == HistoryKind.AMENDMENT:
            if amends_entry_id is None:
                raise ValidationFailed("An amendment must reference the entry it corrects")
            target = self._history.get(amends_entry_id)
            if target is None or target.patient_id != patient_id:
                raise ValidationFailed("The amended entry must exist for the same patient")
        entry = MedicalHistoryEntry(
            id=self._new_id(),
            patient_id=patient_id,
            kind=kind,
            description=description.strip(),
            recorded_at=self._clock.now(),
            recorded_by=actor.id,
            amends_entry_id=amends_entry_id,
        )
        self._history.add(entry)
        return entry

    def list_history(self, patient_id: uuid.UUID) -> list[MedicalHistoryEntry]:
        self.get(patient_id)
        return self._history.list_for_patient(patient_id)

    @staticmethod
    def _require_name(name: str) -> str:
        clean = name.strip()
        if not clean:
            raise ValidationFailed("Name is required")
        return clean
