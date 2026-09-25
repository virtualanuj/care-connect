import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.postgres.models import PreVisitSummaryRow, VisitNoteRow
from app.domain.models import PreVisitSummary, VisitNote

_SUMMARY_FIELDS = ("appointment_id", "summary", "disclaimer", "inputs_hash", "generated_at")
_NOTE_FIELDS = (
    "id",
    "appointment_id",
    "doctor_notes",
    "created_at",
    "updated_at",
    "ai_draft_summary",
    "ai_draft_disclaimer",
    "final_summary",
    "finalized_by",
    "finalized_at",
)


class PostgresSummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, appointment_id: uuid.UUID) -> PreVisitSummary | None:
        row = self._session.get(PreVisitSummaryRow, appointment_id)
        return PreVisitSummary(**{n: getattr(row, n) for n in _SUMMARY_FIELDS}) if row else None

    def save(self, summary: PreVisitSummary) -> None:
        row = self._session.get(PreVisitSummaryRow, summary.appointment_id)
        if row is None:
            self._session.add(
                PreVisitSummaryRow(**{n: getattr(summary, n) for n in _SUMMARY_FIELDS})
            )
        else:
            for name in _SUMMARY_FIELDS:
                setattr(row, name, getattr(summary, name))
        self._session.flush()


class PostgresVisitNoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_appointment(self, appointment_id: uuid.UUID) -> VisitNote | None:
        row = self._session.scalars(
            select(VisitNoteRow).where(VisitNoteRow.appointment_id == appointment_id)
        ).first()
        return VisitNote(**{n: getattr(row, n) for n in _NOTE_FIELDS}) if row else None

    def add(self, note: VisitNote) -> None:
        self._session.add(VisitNoteRow(**{n: getattr(note, n) for n in _NOTE_FIELDS}))
        self._session.flush()

    def update(self, note: VisitNote) -> None:
        row = self._session.get(VisitNoteRow, note.id)
        if row is None:
            return
        for name in _NOTE_FIELDS:
            if name != "id":
                setattr(row, name, getattr(note, name))
        self._session.flush()
