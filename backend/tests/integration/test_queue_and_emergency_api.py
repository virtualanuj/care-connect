import pytest

from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z

pytestmark = pytest.mark.integration

LAST_SLOT = z(9, 40)  # the held-back emergency slot (N = 1)


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    return Ctx(booking_harness)


def queue(ctx: Ctx, headers: dict | None = None, day: str = "2026-03-02"):  # type: ignore[no-untyped-def,type-arg]
    return ctx.c.get(f"{API}/queue", params={"date": day}, headers=headers or ctx.admin)


# ---- emergency booking by front-desk judgment --------------------------------------------------


def test_front_desk_books_the_held_slot_with_a_reason_and_it_is_recorded_and_audited(
    ctx: Ctx,
) -> None:
    response = ctx.book(
        ctx.asha,
        LAST_SLOT,
        emergencyJustification="front_desk_judgment",
        emergencyReason="Chest pain, walked in",
        source="walk_in",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["isEmergencySlot"] is True
    assert (body["emergencyJustification"], body["emergencyReason"]) == (
        "front_desk_judgment",
        "Chest pain, walked in",
    )
    assert body["emergencyAuthorizedBy"] is not None
    audit = ctx.c.get(f"{API}/audit-log?action=emergency_authorization", headers=ctx.admin).json()
    assert audit["total"] == 1
    assert audit["items"][0]["targetId"] == body["id"]
    assert audit["items"][0]["reason"] == "Chest pain, walked in"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_a_missing_or_blank_reason_is_422(ctx: Ctx, reason: str | None) -> None:
    extra = {"emergencyReason": reason} if reason is not None else {}

    response = ctx.book(ctx.asha, LAST_SLOT, emergencyJustification="front_desk_judgment", **extra)

    assert (response.status_code, response.json()["code"]) == (
        422,
        "EMERGENCY_JUSTIFICATION_REQUIRED",
    )


def test_a_doctor_cannot_use_front_desk_judgment(ctx: Ctx) -> None:
    response = ctx.book(
        ctx.asha,
        LAST_SLOT,
        headers=ctx.doc,
        emergencyJustification="front_desk_judgment",
        emergencyReason="urgent",
    )

    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


def test_a_triage_justification_is_rejected_until_triage_exists(ctx: Ctx) -> None:
    response = ctx.book(ctx.asha, LAST_SLOT, emergencyJustification="triage")

    assert (response.status_code, response.json()["code"]) == (422, "EMERGENCY_NOT_AUTHORIZED")


def test_the_emergency_slot_stays_hidden_from_regular_search_even_after_use_elsewhere(
    ctx: Ctx,
) -> None:
    ctx.book(ctx.asha, LAST_SLOT, emergencyJustification="front_desk_judgment", emergencyReason="x")

    regular = ctx.slots(doctorId=ctx.doctor["id"]).json()
    with_emergency = ctx.slots(doctorId=ctx.doctor["id"], includeEmergency="true").json()

    assert LAST_SLOT not in [s["startTime"] for s in regular]
    assert LAST_SLOT not in [s["startTime"] for s in with_emergency]  # now booked


# ---- queue -------------------------------------------------------------------------------------


def test_the_queue_groups_the_days_appointments_by_status_with_names(ctx: Ctx) -> None:
    waiting = ctx.book(ctx.asha, z(9, 0)).json()
    walk_in = ctx.book(ctx.kiran, z(9, 20), source="walk_in").json()
    ctx.c.post(f"{API}/appointments/{walk_in['id']}/check-in", headers=ctx.admin)

    body = queue(ctx).json()

    assert body["date"] == "2026-03-02"
    assert [i["id"] for i in body["booked"]] == [waiting["id"]]
    assert [i["id"] for i in body["checkedIn"]] == [walk_in["id"]]
    assert body["inProgress"] == body["completed"] == body["noShows"] == body["cancelled"] == []
    item = body["checkedIn"][0]
    assert (item["patientName"], item["doctorName"], item["source"]) == (
        "Kiran Rao",
        "Dr One",
        "walk_in",
    )
    assert body["booked"][0]["patientName"] == "Asha Rao"


def test_cancelled_and_no_show_appointments_stay_visible_in_their_buckets(ctx: Ctx) -> None:
    a = ctx.book(ctx.asha, z(9, 0)).json()
    b = ctx.book(ctx.kiran, z(9, 20)).json()
    ctx.c.post(f"{API}/appointments/{a['id']}/cancel", headers=ctx.admin)
    ctx.c.post(f"{API}/appointments/{b['id']}/no-show", headers=ctx.admin)

    body = queue(ctx).json()

    assert [i["id"] for i in body["cancelled"]] == [a["id"]]
    assert [i["id"] for i in body["noShows"]] == [b["id"]]


def test_the_queue_defaults_to_today_in_the_clinic_zone_and_rejects_a_bad_date(ctx: Ctx) -> None:
    ctx.h.clock.set(
        __import__("datetime").datetime(2026, 3, 2, 8, 0, tzinfo=__import__("datetime").UTC)
    )
    ctx.admin = ctx.h.headers_for("admin@clinic.test")
    ctx.book(ctx.asha, z(9, 0))

    today = ctx.c.get(f"{API}/queue", headers=ctx.admin).json()

    assert today["date"] == "2026-03-02"
    assert len(today["booked"]) == 1
    assert ctx.c.get(f"{API}/queue", params={"date": "soon"}, headers=ctx.admin).status_code == 400


def test_a_doctor_sees_only_their_own_queue(ctx: Ctx) -> None:
    mine = ctx.book(ctx.asha, z(9, 0)).json()
    ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other)

    body = queue(ctx, headers=ctx.doc).json()

    assert [i["id"] for i in body["booked"]] == [mine["id"]]
