import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.postgres._errors import violates
from app.adapters.postgres.models import PatientRow
from app.domain.errors import PatientAlreadyExists
from app.domain.models import Page, Patient
from app.domain.patient_identity import normalize_name

_IDENTITY_KEY = "patients_phone_name_key"
_DUPLICATE = "A patient with this name and phone number already exists"


def _to_domain(row: PatientRow) -> Patient:
    return Patient(row.id, row.name, row.phone, row.created_at, row.dob, row.email)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PostgresPatientRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, patient: Patient) -> None:
        row = PatientRow(
            id=patient.id,
            name=patient.name,
            name_normalized=normalize_name(patient.name),
            phone=patient.phone,
            dob=patient.dob,
            email=patient.email,
            created_at=patient.created_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as error:
            if violates(error, _IDENTITY_KEY):
                raise PatientAlreadyExists(_DUPLICATE) from error
            raise

    def get(self, patient_id: uuid.UUID) -> Patient | None:
        row = self._session.get(PatientRow, patient_id)
        return _to_domain(row) if row else None

    def find(
        self, phone: str | None, name_prefix: str | None, page: int, page_size: int
    ) -> Page[Patient]:
        query = select(PatientRow)
        count = select(func.count()).select_from(PatientRow)
        if phone is not None:
            query = query.where(PatientRow.phone == phone)
            count = count.where(PatientRow.phone == phone)
        if name_prefix:
            pattern = _escape_like(name_prefix) + "%"
            query = query.where(PatientRow.name_normalized.like(pattern, escape="\\"))
            count = count.where(PatientRow.name_normalized.like(pattern, escape="\\"))
        rows = self._session.scalars(
            query.order_by(PatientRow.name_normalized, PatientRow.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return Page(items=[_to_domain(r) for r in rows], total=self._session.scalar(count) or 0)

    def update(self, patient: Patient) -> None:
        row = self._session.get(PatientRow, patient.id)
        if row is None:
            return
        try:
            with self._session.begin_nested():
                row.name = patient.name
                row.name_normalized = normalize_name(patient.name)
                row.phone = patient.phone
                row.dob = patient.dob
                row.email = patient.email
        except IntegrityError as error:
            self._session.expire(row)
            if violates(error, _IDENTITY_KEY):
                raise PatientAlreadyExists(_DUPLICATE) from error
            raise
