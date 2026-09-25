import pytest

from app.domain.errors import AiServiceUnavailable
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z
from tests.integration.test_lifecycle_api import act

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    return Ctx(booking_harness)


def note_url(appointment: dict) -> str:  # type: ignore[type-arg]
    return f"{API}/appointments/{appointment['id']}/visit-note"


def put(ctx: Ctx, appointment: dict, text: str, headers: dict | None = None):  # type: ignore[no-untyped-def,type-arg]
    return ctx.c.put(note_url(appointment), json={"doctorNotes": text}, headers=headers or ctx.doc)


def in_consultation(ctx: Ctx) -> dict:  # type: ignore[type-arg]
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    act(ctx, appointment, "check-in")
    act(ctx, appointment, "start-consultation")
    return appointment  # type: ignore[no-any-return]


# ---- visit notes -------------------------------------------------------------------------------


def test_notes_are_written_read_back_and_updated_in_place(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    missing = ctx.c.get(note_url(appointment), headers=ctx.doc)

    created = put(ctx, appointment, "Cough for a week.")
    updated = put(ctx, appointment, "Cough for a week. Chest clear.")
    fetched = ctx.c.get(note_url(appointment), headers=ctx.admin)

    assert missing.status_code == 404
    assert created.status_code == 200
    assert updated.json()["id"] == created.json()["id"]
    assert fetched.json()["doctorNotes"] == "Cough for a week. Chest clear."
    body = fetched.json()
    assert (body["aiDraftSummary"], body["finalSummary"], body["locked"]) == (None, None, False)
    assert body["appointmentId"] == appointment["id"]


def test_notes_need_a_started_consultation(ctx: Ctx) -> None:
    booked = ctx.book(ctx.asha, z(9, 0)).json()

    response = put(ctx, booked, "too early")

    assert (response.status_code, response.json()["code"]) == (409, "VISIT_NOTE_NOT_WRITABLE")


def test_another_doctor_cannot_touch_the_note_but_front_desk_can_write(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    other = ctx.h.headers_for("other@clinic.test")

    assert put(ctx, appointment, "x", headers=other).status_code == 403
    assert ctx.c.get(note_url(appointment), headers=other).status_code == 403
    assert put(ctx, appointment, "front desk wrote this", headers=ctx.admin).status_code == 200


def test_blank_notes_are_rejected(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)

    assert put(ctx, appointment, "").status_code == 400
    assert put(ctx, appointment, "   ").status_code in (400, 422)


# ---- AI draft ----------------------------------------------------------------------------------


def test_a_draft_fills_only_the_ai_fields_with_a_disclaimer(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    put(ctx, appointment, "Cough for a week.")
    ctx.h.llm.text_output = "Week-long cough."

    response = ctx.c.post(f"{note_url(appointment)}/draft", headers=ctx.doc)

    body = response.json()
    assert response.status_code == 200
    assert body["aiDraftSummary"] == "Week-long cough."
    assert body["aiDraftDisclaimer"]
    assert body["finalSummary"] is None and body["locked"] is False
    assert ctx.h.llm.text_calls[-1][1] == "Cough for a week."


def test_a_draft_without_notes_is_unprocessable(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)

    response = ctx.c.post(f"{note_url(appointment)}/draft", headers=ctx.doc)

    assert (response.status_code, response.json()["code"]) == (422, "NO_NOTES_TO_DRAFT")


def test_an_ai_outage_returns_503_and_keeps_the_notes(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    put(ctx, appointment, "notes")
    ctx.h.llm.text_output = AiServiceUnavailable("down")

    response = ctx.c.post(f"{note_url(appointment)}/draft", headers=ctx.doc)

    assert (response.status_code, response.json()["code"]) == (503, "AI_SERVICE_UNAVAILABLE")
    assert ctx.c.get(note_url(appointment), headers=ctx.doc).json()["doctorNotes"] == "notes"


# ---- finalize ----------------------------------------------------------------------------------


def test_the_doctor_finalizes_and_the_note_is_locked(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    put(ctx, appointment, "notes")

    final = ctx.c.post(
        f"{note_url(appointment)}/finalize", json={"finalSummary": "Viral cough."}, headers=ctx.doc
    )
    again = ctx.c.post(
        f"{note_url(appointment)}/finalize", json={"finalSummary": "Again."}, headers=ctx.doc
    )

    body = final.json()
    assert final.status_code == 200
    assert (body["finalSummary"], body["locked"], body["finalizedBy"]) == (
        "Viral cough.",
        True,
        str(ctx.doc_user.id),
    )
    assert body["finalizedAt"]
    assert (again.status_code, again.json()["code"]) == (409, "VISIT_NOTE_LOCKED")
    edit = put(ctx, appointment, "edit after")
    assert (edit.status_code, edit.json()["code"]) == (409, "VISIT_NOTE_LOCKED")


def test_front_desk_cannot_finalize(ctx: Ctx) -> None:
    appointment = in_consultation(ctx)
    put(ctx, appointment, "notes")

    response = ctx.c.post(
        f"{note_url(appointment)}/finalize", json={"finalSummary": "x"}, headers=ctx.admin
    )

    assert response.status_code == 403


# ---- pre-visit summary -------------------------------------------------------------------------


def summary_url(appointment: dict) -> str:  # type: ignore[type-arg]
    return f"{API}/appointments/{appointment['id']}/summary"


def test_the_summary_is_generated_stored_and_marked_stale_when_history_changes(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    none_yet = ctx.c.get(summary_url(appointment), headers=ctx.doc)
    ctx.h.llm.text_output = "Summary v1."

    generated = ctx.c.post(summary_url(appointment), headers=ctx.doc)
    calls = len(ctx.h.llm.text_calls)
    fresh = ctx.c.get(summary_url(appointment), headers=ctx.doc)
    ctx.c.post(
        f"{API}/patients/{ctx.asha['id']}/medical-history",
        json={"description": "Penicillin allergy"},
        headers=ctx.admin,
    )
    stale = ctx.c.get(summary_url(appointment), headers=ctx.doc)

    assert none_yet.status_code == 404
    assert generated.status_code == 200 and generated.json()["summary"] == "Summary v1."
    assert generated.json()["stale"] is False and generated.json()["disclaimer"]
    assert fresh.json()["stale"] is False
    assert len(ctx.h.llm.text_calls) == calls  # GET never calls the AI
    assert stale.json()["stale"] is True


def test_summary_outage_is_503_and_other_doctors_are_forbidden(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.h.llm.text_output = AiServiceUnavailable("down")

    down = ctx.c.post(summary_url(appointment), headers=ctx.doc)
    other = ctx.c.post(summary_url(appointment), headers=ctx.h.headers_for("other@clinic.test"))

    assert (down.status_code, down.json()["code"]) == (503, "AI_SERVICE_UNAVAILABLE")
    assert other.status_code == 403
