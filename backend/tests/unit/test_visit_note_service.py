import uuid
from datetime import timedelta

import pytest

from app.domain.errors import (
    AiServiceUnavailable,
    Forbidden,
    NoNotesToDraft,
    NotFound,
    ValidationFailed,
    VisitNoteLocked,
    VisitNoteNotWritable,
)
from app.domain.models import AppointmentStatus as S
from app.domain.triage import AI_TEXT_DISCLAIMER
from app.services.summary_service import SummaryService
from app.services.visit_note_service import VisitNoteService
from tests.fakes.repositories import InMemoryVisitNoteRepository
from tests.unit.test_summary_service import Setup as SummarySetup


class Setup(SummarySetup):
    def __init__(self) -> None:
        super().__init__()
        self.notes = InMemoryVisitNoteRepository()
        summaries: SummaryService = self.service
        self.notes_service = VisitNoteService(
            self.appointments, self.doctors, self.notes, summaries, self.clock
        )
        self.appointment.status = S.IN_CONSULTATION

    def write(self, text: str = "Cough, no fever.", actor=None):  # type: ignore[no-untyped-def]
        return self.notes_service.put_notes(actor or self.doc_user, self.appointment.id, text)


@pytest.fixture
def s() -> Setup:
    return Setup()


# ---- writing notes -----------------------------------------------------------------------------


def test_notes_are_created_then_updated_in_place(s: Setup) -> None:
    created = s.write("first draft")
    s.clock.advance(timedelta(minutes=10))
    updated = s.write("second version")

    assert updated.id == created.id
    assert updated.doctor_notes == "second version"
    assert (created.created_at, updated.created_at) == (updated.created_at, updated.created_at)
    assert updated.updated_at > updated.created_at
    assert len(s.notes.items) == 1
    assert (updated.ai_draft_summary, updated.final_summary, updated.locked) == (None, None, False)


@pytest.mark.parametrize("status", [S.IN_CONSULTATION, S.COMPLETED])
def test_notes_can_be_written_during_or_after_the_consultation(s: Setup, status: S) -> None:
    s.appointment.status = status

    assert s.write().doctor_notes


@pytest.mark.parametrize("status", [S.BOOKED, S.CHECKED_IN, S.NO_SHOW, S.CANCELLED])
def test_notes_cannot_be_written_before_the_consultation_or_for_dead_appointments(
    s: Setup, status: S
) -> None:
    s.appointment.status = status

    with pytest.raises(VisitNoteNotWritable):
        s.write()
    assert s.notes.items == {}


def test_front_desk_and_the_owning_doctor_may_write_but_not_another_doctor(s: Setup) -> None:
    s.write(actor=s.admin)
    s.write(actor=s.doc_user)
    with pytest.raises(Forbidden):
        s.write(actor=s.other_user)


def test_blank_notes_are_rejected_and_unknown_appointments_are_not_found(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.write("   ")
    with pytest.raises(NotFound):
        s.notes_service.put_notes(s.admin, uuid.uuid4(), "x")


def test_get_returns_the_note_or_not_found_with_doctor_scoping(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.notes_service.get(s.admin, s.appointment.id)
    note = s.write()

    assert s.notes_service.get(s.doc_user, s.appointment.id) == note
    with pytest.raises(Forbidden):
        s.notes_service.get(s.other_user, s.appointment.id)


# ---- AI draft ----------------------------------------------------------------------------------


def test_a_draft_writes_the_ai_draft_only_and_never_the_final_summary(s: Setup) -> None:
    s.write("Cough for a week. Chest clear.")
    s.provider.text_output = "Draft: week-long cough, chest clear."

    drafted = s.notes_service.draft(s.doc_user, s.appointment.id)

    assert drafted.ai_draft_summary == "Draft: week-long cough, chest clear."
    assert drafted.ai_draft_disclaimer == AI_TEXT_DISCLAIMER
    assert drafted.final_summary is None and drafted.finalized_at is None
    assert drafted.doctor_notes == "Cough for a week. Chest clear."
    task, text, identifiers = s.provider.text_calls[-1]
    assert (task, text) == ("draft", "Cough for a week. Chest clear.")
    assert identifiers.name == "Asha Rao"


def test_a_draft_needs_notes_first(s: Setup) -> None:
    with pytest.raises(NoNotesToDraft):
        s.notes_service.draft(s.doc_user, s.appointment.id)
    assert s.provider.text_calls == []


def test_an_ai_failure_leaves_the_note_unchanged(s: Setup) -> None:
    s.write("notes")
    s.provider.text_output = AiServiceUnavailable("down")

    with pytest.raises(AiServiceUnavailable):
        s.notes_service.draft(s.doc_user, s.appointment.id)

    note = s.notes.get_by_appointment(s.appointment.id)
    assert note is not None and note.ai_draft_summary is None


def test_drafting_is_limited_to_front_desk_and_the_owner(s: Setup) -> None:
    s.write()

    with pytest.raises(Forbidden):
        s.notes_service.draft(s.other_user, s.appointment.id)
    assert s.notes_service.draft(s.admin, s.appointment.id).ai_draft_summary


# ---- finalize ----------------------------------------------------------------------------------


def test_only_the_appointments_doctor_can_finalize_and_it_locks_the_note(s: Setup) -> None:
    s.write()
    s.clock.advance(timedelta(minutes=5))

    final = s.notes_service.finalize(s.doc_user, s.appointment.id, "Final: viral cough.")

    assert final.final_summary == "Final: viral cough."
    assert (final.finalized_by, final.finalized_at) == (s.doc_user.id, s.clock.now())
    assert final.locked is True


def test_front_desk_and_other_doctors_cannot_finalize(s: Setup) -> None:
    s.write()

    with pytest.raises(Forbidden):
        s.notes_service.finalize(s.admin, s.appointment.id, "Final.")
    with pytest.raises(Forbidden):
        s.notes_service.finalize(s.other_user, s.appointment.id, "Final.")
    note = s.notes.get_by_appointment(s.appointment.id)
    assert note is not None and note.locked is False


def test_finalize_needs_an_existing_note_and_a_non_blank_summary(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.notes_service.finalize(s.doc_user, s.appointment.id, "Final.")
    s.write()
    with pytest.raises(ValidationFailed):
        s.notes_service.finalize(s.doc_user, s.appointment.id, "  ")


def test_a_second_finalize_and_any_edit_after_finalize_are_rejected(s: Setup) -> None:
    s.write()
    s.notes_service.finalize(s.doc_user, s.appointment.id, "Final.")

    with pytest.raises(VisitNoteLocked):
        s.notes_service.finalize(s.doc_user, s.appointment.id, "Again.")
    with pytest.raises(VisitNoteLocked):
        s.write("edited afterwards")
    with pytest.raises(VisitNoteLocked):
        s.notes_service.draft(s.doc_user, s.appointment.id)
    note = s.notes.get_by_appointment(s.appointment.id)
    assert (
        note is not None
        and note.final_summary == "Final."
        and note.doctor_notes != "edited afterwards"
    )


def test_finalizing_requires_a_started_consultation(s: Setup) -> None:
    s.write()
    s.appointment.status = S.CANCELLED

    with pytest.raises(VisitNoteNotWritable):
        s.notes_service.finalize(s.doc_user, s.appointment.id, "Final.")
