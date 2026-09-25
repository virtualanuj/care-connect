import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.postgres._errors import violates
from app.adapters.postgres.models import SpecialtyRow
from app.domain.errors import SpecialtyAlreadyExists
from app.domain.models import Specialty

_NAME_INDEX = "specialties_name_lower_key"


def _to_domain(row: SpecialtyRow) -> Specialty:
    return Specialty(row.id, row.name, row.default_slot_length_minutes)


class PostgresSpecialtyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, specialty: Specialty) -> None:
        try:
            with self._session.begin_nested():
                self._session.add(
                    SpecialtyRow(
                        id=specialty.id,
                        name=specialty.name,
                        default_slot_length_minutes=specialty.default_slot_length_minutes,
                    )
                )
        except IntegrityError as error:
            if violates(error, _NAME_INDEX):
                raise SpecialtyAlreadyExists("A specialty with this name already exists") from error
            raise

    def get(self, specialty_id: uuid.UUID) -> Specialty | None:
        row = self._session.get(SpecialtyRow, specialty_id)
        return _to_domain(row) if row else None

    def list(self) -> list[Specialty]:
        rows = self._session.scalars(select(SpecialtyRow).order_by(func.lower(SpecialtyRow.name)))
        return [_to_domain(r) for r in rows]

    def update(self, specialty: Specialty) -> None:
        row = self._session.get(SpecialtyRow, specialty.id)
        if row is None:
            return
        try:
            with self._session.begin_nested():
                row.name = specialty.name
                row.default_slot_length_minutes = specialty.default_slot_length_minutes
        except IntegrityError as error:
            self._session.expire(row)
            if violates(error, _NAME_INDEX):
                raise SpecialtyAlreadyExists("A specialty with this name already exists") from error
            raise
