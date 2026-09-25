import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.postgres.models import MedicalHistoryRow
from app.domain.models import MedicalHistoryEntry


def _to_domain(row: MedicalHistoryRow) -> MedicalHistoryEntry:
    return MedicalHistoryEntry(
        id=row.id,
        patient_id=row.patient_id,
        kind=row.kind,
        description=row.description,
        recorded_at=row.recorded_at,
        recorded_by=row.recorded_by,
        amends_entry_id=row.amends_entry_id,
    )


class PostgresMedicalHistoryRepository:
    """Insert and read only: medical history is append-only."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: MedicalHistoryEntry) -> None:
        self._session.add(
            MedicalHistoryRow(
                id=entry.id,
                patient_id=entry.patient_id,
                kind=entry.kind,
                amends_entry_id=entry.amends_entry_id,
                description=entry.description,
                recorded_at=entry.recorded_at,
                recorded_by=entry.recorded_by,
            )
        )
        self._session.flush()

    def get(self, entry_id: uuid.UUID) -> MedicalHistoryEntry | None:
        row = self._session.get(MedicalHistoryRow, entry_id)
        return _to_domain(row) if row else None

    def list_for_patient(self, patient_id: uuid.UUID) -> list[MedicalHistoryEntry]:
        rows = self._session.scalars(
            select(MedicalHistoryRow)
            .where(MedicalHistoryRow.patient_id == patient_id)
            .order_by(MedicalHistoryRow.recorded_at, MedicalHistoryRow.id)
        )
        return [_to_domain(r) for r in rows]
