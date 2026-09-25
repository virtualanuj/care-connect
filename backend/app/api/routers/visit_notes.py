import uuid

from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_summary_service, get_visit_note_service
from app.api.schemas.visit_notes import (
    FinalizeRequest,
    PreVisitSummaryOut,
    VisitNoteOut,
    VisitNotesRequest,
)
from app.domain.models import User
from app.services.summary_service import SummaryService
from app.services.visit_note_service import VisitNoteService

router = APIRouter(tags=["Summary", "VisitNotes"])


@router.get("/appointments/{appointment_id}/summary", response_model=PreVisitSummaryOut)
def get_summary(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: SummaryService = Depends(get_summary_service),
) -> PreVisitSummaryOut:
    return PreVisitSummaryOut.from_view(service.get(actor, appointment_id))


@router.post("/appointments/{appointment_id}/summary", response_model=PreVisitSummaryOut)
def generate_summary(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: SummaryService = Depends(get_summary_service),
) -> PreVisitSummaryOut:
    service.generate(actor, appointment_id)
    return PreVisitSummaryOut.from_view(service.get(actor, appointment_id))


@router.get("/appointments/{appointment_id}/visit-note", response_model=VisitNoteOut)
def get_visit_note(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: VisitNoteService = Depends(get_visit_note_service),
) -> VisitNoteOut:
    return VisitNoteOut.from_domain(service.get(actor, appointment_id))


@router.put("/appointments/{appointment_id}/visit-note", response_model=VisitNoteOut)
def put_visit_note(
    appointment_id: uuid.UUID,
    body: VisitNotesRequest,
    actor: User = Depends(current_user),
    service: VisitNoteService = Depends(get_visit_note_service),
) -> VisitNoteOut:
    return VisitNoteOut.from_domain(service.put_notes(actor, appointment_id, body.doctor_notes))


@router.post("/appointments/{appointment_id}/visit-note/draft", response_model=VisitNoteOut)
def draft_visit_note(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: VisitNoteService = Depends(get_visit_note_service),
) -> VisitNoteOut:
    return VisitNoteOut.from_domain(service.draft(actor, appointment_id))


@router.post("/appointments/{appointment_id}/visit-note/finalize", response_model=VisitNoteOut)
def finalize_visit_note(
    appointment_id: uuid.UUID,
    body: FinalizeRequest,
    actor: User = Depends(current_user),
    service: VisitNoteService = Depends(get_visit_note_service),
) -> VisitNoteOut:
    return VisitNoteOut.from_domain(service.finalize(actor, appointment_id, body.final_summary))
