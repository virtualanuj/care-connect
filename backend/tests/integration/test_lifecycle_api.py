import uuid
from datetime import UTC, datetime

import pytest

from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    return Ctx(booking_harness)


def act(
    ctx: Ctx, appointment: dict, action: str, body: dict | None = None, headers: dict | None = None
):  # type: ignore[no-untyped-def,type-arg]
    return ctx.c.post(
        f"{API}/appointments/{appointment['id']}/{action}",
        json=body,
        headers=headers or ctx.admin,
    )


def fetch(ctx: Ctx, appointment: dict) -> dict:  # type: ignore[type-arg]
    return ctx.c.get(f"{API}/appointments/{appointment['id']}", headers=ctx.admin).json()  # type: ignore[no-any-return]


# ---- lifecycle ---------------------------------------------------------------------------------


def test_an_appointment_walks_the_lifecycle_with_timestamps(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()

    checked_in = act(ctx, appointment, "check-in")
    started = act(ctx, appointment, "start-consultation")
    completed = act(ctx, appointment, "complete")

    assert [r.status_code for r in (checked_in, started, completed)] == [200, 200, 200]
    assert checked_in.json()["status"] == "checked_in"
    assert checked_in.json()["checkedInAt"] == "2026-03-01T12:00:00Z"
    assert started.json()["status"] == "in_consultation"
    assert completed.json()["status"] == "completed"
    assert completed.json()["completedAt"] == "2026-03-01T12:00:00Z"


@pytest.mark.parametrize("action", ["start-consultation", "complete"])
def test_out_of_order_actions_are_409_invalid_transition(ctx: Ctx, action: str) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()

    response = act(ctx, appointment, action)

    assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")


def test_no_show_frees_the_slot(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()

    assert act(ctx, appointment, "no-show").json()["status"] == "no_show"
    assert ctx.book(ctx.kiran, z(9, 0)).status_code == 201


def test_a_doctor_acts_only_on_their_own_appointments(ctx: Ctx) -> None:
    mine = ctx.book(ctx.asha, z(9, 0)).json()
    theirs = ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other).json()

    assert act(ctx, mine, "check-in", headers=ctx.doc).status_code == 200
    forbidden = act(ctx, theirs, "check-in", headers=ctx.doc)
    assert (forbidden.status_code, forbidden.json()["code"]) == (403, "FORBIDDEN")
    assert act(ctx, {"id": str(uuid.uuid4())}, "check-in").status_code == 404


# ---- cancel and force-cancel -------------------------------------------------------------------


def test_cancelling_outside_the_cutoff_succeeds_and_records_the_cancellation(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()

    cancelled = act(ctx, appointment, "cancel").json()

    assert (cancelled["status"], cancelled["cancellationType"]) == ("cancelled", "standard")
    assert cancelled["cancelledAt"] == "2026-03-01T12:00:00Z"
    assert cancelled["cancelledBy"] is not None


def test_cancelling_inside_the_cutoff_is_422_and_force_cancel_is_the_way_out(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.h.clock.set(datetime(2026, 3, 2, 8, 30, tzinfo=UTC))
    ctx.admin = ctx.h.headers_for("admin@clinic.test")

    blocked = act(ctx, appointment, "cancel")
    forced = act(ctx, appointment, "force-cancel", {"reason": "Patient hospitalised"})

    assert (blocked.status_code, blocked.json()["code"]) == (422, "CANCELLATION_WINDOW_CLOSED")
    assert forced.status_code == 200
    assert (forced.json()["cancellationType"], forced.json()["cancelReason"]) == (
        "force",
        "Patient hospitalised",
    )
    audit = ctx.c.get(f"{API}/audit-log?action=force_cancel", headers=ctx.admin).json()
    assert audit["total"] == 1
    assert audit["items"][0]["targetId"] == appointment["id"]


def test_a_doctor_cannot_force_cancel_and_a_reason_is_required(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()

    doctor_try = act(ctx, appointment, "force-cancel", {"reason": "x"}, headers=ctx.doc)
    no_reason = act(ctx, appointment, "force-cancel", {"reason": ""})
    missing = act(ctx, appointment, "force-cancel", {})

    assert (doctor_try.status_code, doctor_try.json()["code"]) == (403, "FORBIDDEN")
    assert no_reason.status_code == 400
    assert missing.status_code == 400
    assert fetch(ctx, appointment)["status"] == "booked"


def test_a_cancelled_slot_can_be_booked_again(ctx: Ctx) -> None:
    appointment = ctx.book(ctx.asha, z(9, 0)).json()
    act(ctx, appointment, "cancel")

    assert ctx.book(ctx.kiran, z(9, 0)).status_code == 201
    assert z(9, 0) in [s["startTime"] for s in ctx.slots(doctorId=ctx.other["id"]).json()]


# ---- reschedule --------------------------------------------------------------------------------


def test_reschedule_returns_the_new_appointment_and_links_the_old_one(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0), reportedSymptoms="cough").json()

    response = act(ctx, original, "reschedule", {"newStartTime": z(9, 20)})

    assert response.status_code == 200
    new = response.json()
    assert new["id"] != original["id"]
    assert (new["startTime"], new["status"], new["reportedSymptoms"]) == (
        z(9, 20),
        "booked",
        "cough",
    )
    old = fetch(ctx, original)
    assert (old["status"], old["cancellationType"], old["rescheduledToId"]) == (
        "cancelled",
        "rescheduled",
        new["id"],
    )


def test_reschedule_inside_the_cutoff_is_422_and_changes_nothing(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.h.clock.set(datetime(2026, 3, 2, 8, 0, tzinfo=UTC))
    ctx.admin = ctx.h.headers_for("admin@clinic.test")

    response = act(ctx, original, "reschedule", {"newStartTime": z(9, 20)})

    assert (response.status_code, response.json()["code"]) == (422, "CANCELLATION_WINDOW_CLOSED")
    assert fetch(ctx, original)["status"] == "booked"


def test_reschedule_to_a_taken_or_invalid_slot_leaves_the_original_booked(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.book(ctx.kiran, z(9, 20))

    taken = act(ctx, original, "reschedule", {"newStartTime": z(9, 20)})
    invalid = act(ctx, original, "reschedule", {"newStartTime": z(9, 5)})
    emergency = act(ctx, original, "reschedule", {"newStartTime": z(9, 40)})

    assert (taken.status_code, taken.json()["code"]) == (409, "SLOT_ALREADY_BOOKED")
    assert (invalid.status_code, invalid.json()["code"]) == (422, "INVALID_SLOT")
    assert (emergency.status_code, emergency.json()["code"]) == (422, "INVALID_SLOT")
    assert fetch(ctx, original)["status"] == "booked"


def test_a_reschedule_that_fails_in_the_database_rolls_back_the_cancellation(ctx: Ctx) -> None:
    """The patient already has 09:20 with the other doctor, so the new insert violates the
    patient constraint *after* the old appointment was cancelled: everything must roll back."""
    original = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.book(ctx.asha, z(9, 20), doctor=ctx.other)

    response = act(ctx, original, "reschedule", {"newStartTime": z(9, 20)})

    assert (response.status_code, response.json()["code"]) == (409, "PATIENT_ALREADY_BOOKED")
    after = fetch(ctx, original)
    assert (after["status"], after["cancellationType"], after["rescheduledToId"]) == (
        "booked",
        None,
        None,
    )
    assert ctx.c.get(f"{API}/appointments", headers=ctx.admin).json()["total"] == 2


def test_only_a_booked_appointment_can_be_rescheduled(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0)).json()
    act(ctx, original, "check-in")

    response = act(ctx, original, "reschedule", {"newStartTime": z(9, 20)})

    assert (response.status_code, response.json()["code"]) == (409, "INVALID_TRANSITION")


# ---- follow-up ---------------------------------------------------------------------------------


def complete(ctx: Ctx, appointment: dict) -> None:  # type: ignore[type-arg]
    for step in ("check-in", "start-consultation", "complete"):
        assert act(ctx, appointment, step).status_code == 200


def test_a_follow_up_from_a_completed_visit_is_linked_to_it(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0)).json()
    complete(ctx, original)

    response = act(ctx, original, "follow-up", {"startTime": "2026-03-09T09:00:00Z"})

    assert response.status_code == 201
    follow_up = response.json()
    assert follow_up["followUpOfAppointmentId"] == original["id"]
    assert (follow_up["doctorId"], follow_up["patientId"]) == (
        original["doctorId"],
        original["patientId"],
    )


def test_a_follow_up_needs_a_completed_visit_and_a_real_slot_inside_the_window(ctx: Ctx) -> None:
    original = ctx.book(ctx.asha, z(9, 0)).json()
    early = act(ctx, original, "follow-up", {"startTime": "2026-03-09T09:00:00Z"})
    complete(ctx, original)
    ctx.c.patch(f"{API}/clinic-settings", json={"followUpMaxDays": 5}, headers=ctx.admin)
    too_late = act(ctx, original, "follow-up", {"startTime": "2026-03-09T09:00:00Z"})
    ctx.c.patch(f"{API}/clinic-settings", json={"followUpMaxDays": 30}, headers=ctx.admin)
    off_grid = act(ctx, original, "follow-up", {"startTime": "2026-03-09T09:05:00Z"})

    assert (early.status_code, early.json()["code"]) == (409, "APPOINTMENT_NOT_COMPLETED")
    assert (too_late.status_code, too_late.json()["code"]) == (422, "FOLLOW_UP_WINDOW_EXCEEDED")
    assert (off_grid.status_code, off_grid.json()["code"]) == (422, "INVALID_SLOT")
