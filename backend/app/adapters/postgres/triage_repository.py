import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.postgres.models import TriageResultRow
from app.domain.models import TriageResult

_FIELDS = (
    "id",
    "patient_id",
    "reported_symptoms",
    "urgency",
    "suggested_specialty_id",
    "confidence_score",
    "source",
    "disclaimer",
    "created_at",
    "model_version",
    "prompt_version",
    "overridden_by",
    "overridden_at",
    "overridden_urgency",
    "overridden_specialty_id",
    "override_reason",
)


def _to_domain(row: TriageResultRow) -> TriageResult:
    return TriageResult(**{name: getattr(row, name) for name in _FIELDS})


class PostgresTriageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, result: TriageResult) -> None:
        self._session.add(TriageResultRow(**{n: getattr(result, n) for n in _FIELDS}))
        self._session.flush()

    def get(self, triage_id: uuid.UUID) -> TriageResult | None:
        row = self._session.get(TriageResultRow, triage_id)
        return _to_domain(row) if row else None

    def list_for_patient(self, patient_id: uuid.UUID) -> list[TriageResult]:
        rows = self._session.scalars(
            select(TriageResultRow)
            .where(TriageResultRow.patient_id == patient_id)
            .order_by(TriageResultRow.created_at.desc(), TriageResultRow.id)
        )
        return [_to_domain(r) for r in rows]

    def update(self, result: TriageResult) -> None:
        row = self._session.get(TriageResultRow, result.id)
        if row is None:
            return
        for name in _FIELDS:
            if name != "id":
                setattr(row, name, getattr(result, name))
        self._session.flush()
