import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.postgres._errors import violates
from app.adapters.postgres.models import DoctorRow
from app.domain.errors import DoctorAlreadyExists
from app.domain.models import Doctor


def _to_domain(row: DoctorRow) -> Doctor:
    return Doctor(
        row.id, row.user_id, row.name, row.specialty_id, row.slot_length_minutes, row.active
    )


class PostgresDoctorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, doctor: Doctor) -> None:
        try:
            with self._session.begin_nested():
                self._session.add(
                    DoctorRow(
                        id=doctor.id,
                        user_id=doctor.user_id,
                        name=doctor.name,
                        specialty_id=doctor.specialty_id,
                        slot_length_minutes=doctor.slot_length_minutes,
                        active=doctor.active,
                    )
                )
        except IntegrityError as error:
            if violates(error, "doctors_user_id_key"):
                raise DoctorAlreadyExists("This user already has a doctor profile") from error
            raise

    def get(self, doctor_id: uuid.UUID) -> Doctor | None:
        row = self._session.get(DoctorRow, doctor_id)
        return _to_domain(row) if row else None

    def get_by_user_id(self, user_id: uuid.UUID) -> Doctor | None:
        row = self._session.scalars(select(DoctorRow).where(DoctorRow.user_id == user_id)).first()
        return _to_domain(row) if row else None

    def list(self, specialty_id: uuid.UUID | None) -> list[Doctor]:
        query = select(DoctorRow).order_by(func.lower(DoctorRow.name))
        if specialty_id is not None:
            query = query.where(DoctorRow.specialty_id == specialty_id)
        return [_to_domain(r) for r in self._session.scalars(query)]

    def update(self, doctor: Doctor) -> None:
        row = self._session.get(DoctorRow, doctor.id)
        if row is None:
            return
        row.name = doctor.name
        row.specialty_id = doctor.specialty_id
        row.slot_length_minutes = doctor.slot_length_minutes
        row.active = doctor.active
        self._session.flush()
