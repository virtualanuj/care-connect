import uuid
from collections.abc import Callable

from app.domain.errors import (
    Forbidden,
    NoNotesToDraft,
    NotFound,
    ValidationFailed,
    VisitNoteLocked,
    VisitNoteNotWritable,
)
from app.domain.models import Appointment, AppointmentStatus, Role, User, VisitNote
from app.domain.ports import AppointmentRepository, Clock, DoctorRepository, VisitNoteRepository
from app.domain.triage import AI_TEXT_DISCLAIMER
from app.services.summary_service import SummaryService

_WRITABLE = (AppointmentStatus.IN_CONSULTATION, AppointmentStatus.COMPLETED)


class VisitNoteService:
    """A doctor's notes for an appointment: raw notes, an AI draft, and the final summary."""

    def __init__(
        self,
        appointments: AppointmentRepository,
        doctors: DoctorRepository,
        notes: VisitNoteRepository,
        summaries: SummaryService,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._appointments = appointments
        self._doctors = doctors
        self._notes = notes
        self._summaries = summaries
        self._clock = clock
        self._new_id = new_id

    # ---- helpers ----------------------------------------------------------------------------

    def _appointment(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        """The appointment, if the actor may work with it (front-desk, or its own doctor)."""
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or own.id != appointment.doctor_id:
                raise Forbidden("You can only access your own appointments")
        return appointment

    @staticmethod
    def _require_writable_status(appointment: Appointment) -> None:
        if appointment.status not in _WRITABLE:
            raise VisitNoteNotWritable("Notes can be written once the consultation has started")

    # ---- operations -------------------------------------------------------------------------

    def get(self, actor: User, appointment_id: uuid.UUID) -> VisitNote:
        appointment = self._appointment(actor, appointment_id)
        note = self._notes.get_by_appointment(appointment.id)
        if note is None:
            raise NotFound("No visit note yet")
        return note

    def put_notes(self, actor: User, appointment_id: uuid.UUID, doctor_notes: str) -> VisitNote:
        appointment = self._appointment(actor, appointment_id)
        text = doctor_notes.strip()
        if not text:
            raise ValidationFailed("Notes cannot be empty")
        existing = self._notes.get_by_appointment(appointment.id)
        if existing is not None and existing.locked:
            raise VisitNoteLocked("This visit summary has been finalized")
        self._require_writable_status(appointment)

        now = self._clock.now()
        if existing is None:
            note = VisitNote(self._new_id(), appointment.id, text, created_at=now, updated_at=now)
            self._notes.add(note)
            return note
        existing.doctor_notes = text
        existing.updated_at = now
        self._notes.update(existing)
        return existing

    def draft(self, actor: User, appointment_id: uuid.UUID) -> VisitNote:
        """Generate an AI draft from the raw notes. Writes the draft only, never the final."""
        appointment = self._appointment(actor, appointment_id)
        note = self._notes.get_by_appointment(appointment.id)
        if note is None or not note.doctor_notes.strip():
            raise NoNotesToDraft("Write some notes before requesting an AI draft")
        if note.locked:
            raise VisitNoteLocked("This visit summary has been finalized")

        draft = self._summaries.draft_from_notes(appointment, note.doctor_notes)  # may raise
        note.ai_draft_summary = draft
        note.ai_draft_disclaimer = AI_TEXT_DISCLAIMER
        note.updated_at = self._clock.now()
        self._notes.update(note)
        return note

    def finalize(self, actor: User, appointment_id: uuid.UUID, final_summary: str) -> VisitNote:
        """Only the appointment's own doctor finalizes; this locks the note."""
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        own = self._doctors.get_by_user_id(actor.id) if actor.role == Role.DOCTOR else None
        if own is None or own.id != appointment.doctor_id:
            raise Forbidden("Only the appointment's doctor can finalize the visit summary")
        note = self._notes.get_by_appointment(appointment.id)
        if note is None:
            raise NotFound("No visit note yet")
        if note.locked:
            raise VisitNoteLocked("This visit summary has already been finalized")
        self._require_writable_status(appointment)
        text = final_summary.strip()
        if not text:
            raise ValidationFailed("The final summary cannot be empty")

        now = self._clock.now()
        note.final_summary = text
        note.finalized_by = actor.id
        note.finalized_at = now
        note.updated_at = now
        self._notes.update(note)
        return note
