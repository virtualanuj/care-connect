import uuid
from datetime import datetime

from pydantic import Field

from app.api.schemas.base import CamelModel
from app.domain.models import VisitNote
from app.services.summary_service import SummaryView


class VisitNotesRequest(CamelModel):
    doctor_notes: str = Field(min_length=1)


class FinalizeRequest(CamelModel):
    final_summary: str = Field(min_length=1)


class VisitNoteOut(CamelModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    doctor_notes: str
    ai_draft_summary: str | None
    ai_draft_disclaimer: str | None
    final_summary: str | None
    finalized_by: uuid.UUID | None
    finalized_at: datetime | None
    locked: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, note: VisitNote) -> "VisitNoteOut":
        return cls(
            id=note.id,
            appointment_id=note.appointment_id,
            doctor_notes=note.doctor_notes,
            ai_draft_summary=note.ai_draft_summary,
            ai_draft_disclaimer=note.ai_draft_disclaimer,
            final_summary=note.final_summary,
            finalized_by=note.finalized_by,
            finalized_at=note.finalized_at,
            locked=note.locked,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )


class PreVisitSummaryOut(CamelModel):
    appointment_id: uuid.UUID
    summary: str
    disclaimer: str
    stale: bool
    generated_at: datetime

    @classmethod
    def from_view(cls, view: SummaryView) -> "PreVisitSummaryOut":
        return cls(
            appointment_id=view.appointment_id,
            summary=view.summary,
            disclaimer=view.disclaimer,
            stale=view.stale,
            generated_at=view.generated_at,
        )
