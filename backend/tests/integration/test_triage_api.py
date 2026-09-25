import uuid
from datetime import timedelta

import pytest

from app.domain.errors import AiServiceUnavailable
from app.domain.models import TriageModelOutput, Urgency
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API, Ctx, z

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx(booking_harness: ApiHarness) -> Ctx:
    # The scripted AI answers with the specialty this setup actually has.
    booking_harness.llm.output = TriageModelOutput(Urgency.ROUTINE, "General", 0.8)
    return Ctx(booking_harness)


def run_triage(ctx: Ctx, symptoms: str, patient: dict | None = None, headers: dict | None = None):  # type: ignore[no-untyped-def,type-arg]
    who = patient or ctx.asha
    return ctx.c.post(
        f"{API}/patients/{who['id']}/triage",
        json={"reportedSymptoms": symptoms},
        headers=headers or ctx.admin,
    )


def script(ctx: Ctx, urgency: Urgency, specialty: str = "General", confidence: float = 0.8) -> None:
    ctx.h.llm.output = TriageModelOutput(urgency, specialty, confidence)


# ---- running triage ----------------------------------------------------------------------------


def test_triage_returns_the_result_with_disclaimer_versions_and_effective_urgency(ctx: Ctx) -> None:
    script(ctx, Urgency.URGENT, confidence=0.66)

    response = run_triage(ctx, "high fever for three days")

    assert response.status_code == 201
    body = response.json()
    assert (body["urgency"], body["effectiveUrgency"], body["source"]) == (
        "urgent",
        "urgent",
        "model",
    )
    assert body["suggestedSpecialtyId"] == ctx.specialty["id"]
    assert body["confidenceScore"] == 0.66
    assert body["patientId"] == ctx.asha["id"]
    assert body["reportedSymptoms"] == "high fever for three days"
    assert "not a diagnosis" in body["disclaimer"]
    assert (body["modelVersion"], body["promptVersion"]) == ("fake-model-1", "fake-prompt-1")
    assert body["overriddenUrgency"] is None and body["overrideReason"] is None


def test_the_provider_is_given_the_patients_identifiers_to_scrub_and_the_specialty_names(
    ctx: Ctx,
) -> None:
    run_triage(ctx, "cough")

    (call,) = ctx.h.llm.calls
    assert call.identifiers.name == "Asha Rao"
    assert call.identifiers.phone == "+919876543210"
    assert call.specialties == ["General"]


def test_a_doctor_can_run_triage_too(ctx: Ctx) -> None:
    assert run_triage(ctx, "cough", headers=ctx.doc).status_code == 201


def test_each_run_is_kept_and_listed_newest_first(ctx: Ctx) -> None:
    first = run_triage(ctx, "cough").json()
    ctx.h.clock.advance(timedelta(minutes=5))
    ctx.admin = ctx.h.headers_for("admin@clinic.test")
    second = run_triage(ctx, "cough is worse").json()

    listing = ctx.c.get(f"{API}/patients/{ctx.asha['id']}/triage", headers=ctx.admin).json()

    assert [r["id"] for r in listing] == [second["id"], first["id"]]


# ---- safety net --------------------------------------------------------------------------------


def test_a_red_flag_forces_emergency_even_when_the_model_says_routine(ctx: Ctx) -> None:
    script(ctx, Urgency.ROUTINE)

    body = run_triage(ctx, "crushing chest pain").json()

    assert (body["urgency"], body["effectiveUrgency"], body["source"]) == (
        "emergency",
        "emergency",
        "red_flag",
    )


def test_a_red_flag_is_still_answered_with_201_when_the_ai_is_down(ctx: Ctx) -> None:
    ctx.h.llm.output = AiServiceUnavailable("down")
    ctx.c.patch(
        f"{API}/clinic-settings",
        json={"defaultTriageSpecialtyId": ctx.specialty["id"]},
        headers=ctx.admin,
    )

    response = run_triage(ctx, "she is having a seizure")

    assert response.status_code == 201
    body = response.json()
    assert (body["urgency"], body["source"], body["modelVersion"]) == (
        "emergency",
        "red_flag",
        None,
    )
    assert body["suggestedSpecialtyId"] == ctx.specialty["id"]


def test_without_a_red_flag_an_ai_outage_is_503_and_nothing_is_stored(ctx: Ctx) -> None:
    ctx.h.llm.output = AiServiceUnavailable("down")

    response = run_triage(ctx, "sore throat")

    assert (response.status_code, response.json()["code"]) == (503, "AI_SERVICE_UNAVAILABLE")
    assert ctx.c.get(f"{API}/patients/{ctx.asha['id']}/triage", headers=ctx.admin).json() == []


def test_an_answer_naming_an_unknown_specialty_is_503(ctx: Ctx) -> None:
    script(ctx, Urgency.ROUTINE, specialty="Astrology")

    assert run_triage(ctx, "sore throat").status_code == 503


@pytest.mark.parametrize("symptoms", ["", "   ", "x" * 4001])
def test_invalid_symptom_text_is_400(ctx: Ctx, symptoms: str) -> None:
    assert run_triage(ctx, symptoms).status_code == 400


def test_unknown_patient_is_404(ctx: Ctx) -> None:
    response = run_triage(ctx, "cough", patient={"id": str(uuid.uuid4())})

    assert response.status_code == 404


# ---- override ----------------------------------------------------------------------------------


def override(ctx: Ctx, triage: dict, body: dict, headers: dict | None = None):  # type: ignore[no-untyped-def,type-arg]
    return ctx.c.patch(
        f"{API}/triage-results/{triage['id']}/override", json=body, headers=headers or ctx.admin
    )


def test_an_override_is_stored_beside_the_original_and_audited(ctx: Ctx) -> None:
    triage = run_triage(ctx, "severe chest pain").json()

    response = override(
        ctx,
        triage,
        {
            "overriddenUrgency": "routine",
            "overriddenSpecialtyId": ctx.specialty["id"],
            "overrideReason": "Known anxiety, ECG normal",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["urgency"], body["overriddenUrgency"], body["effectiveUrgency"]) == (
        "emergency",
        "routine",
        "routine",
    )
    assert body["overrideReason"] == "Known anxiety, ECG normal"
    assert body["overriddenBy"] is not None and body["overriddenAt"] is not None
    audit = ctx.c.get(f"{API}/audit-log?action=triage_override", headers=ctx.admin).json()
    assert audit["total"] == 1
    assert audit["items"][0]["targetId"] == triage["id"]


@pytest.mark.parametrize(
    "body",
    [
        {"overriddenUrgency": "routine"},  # no reason
        {"overriddenUrgency": "routine", "overrideReason": ""},
        {"overrideReason": "why"},  # no urgency
        {"overriddenUrgency": "dire", "overrideReason": "why"},
    ],
)
def test_an_override_needs_an_urgency_and_a_reason(ctx: Ctx, body: dict) -> None:  # type: ignore[type-arg]
    triage = run_triage(ctx, "cough").json()

    assert override(ctx, triage, body).status_code == 400
    assert (
        ctx.c.get(f"{API}/patients/{ctx.asha['id']}/triage", headers=ctx.admin).json()[0][
            "overriddenUrgency"
        ]
        is None
    )


def test_unknown_triage_or_specialty_in_an_override(ctx: Ctx) -> None:
    triage = run_triage(ctx, "cough").json()

    unknown = override(
        ctx, {"id": str(uuid.uuid4())}, {"overriddenUrgency": "urgent", "overrideReason": "x"}
    )
    bad_specialty = override(
        ctx,
        triage,
        {
            "overriddenUrgency": "urgent",
            "overrideReason": "x",
            "overriddenSpecialtyId": str(uuid.uuid4()),
        },
    )

    assert unknown.status_code == 404
    assert bad_specialty.status_code == 400


def test_a_doctor_may_override_only_triage_used_by_their_own_appointments(ctx: Ctx) -> None:
    script(ctx, Urgency.URGENT)
    triage = run_triage(ctx, "fever").json()
    body = {"overriddenUrgency": "routine", "overrideReason": "reviewed"}

    assert override(ctx, triage, body, headers=ctx.doc).status_code == 403
    ctx.book(ctx.asha, z(9, 0), triageResultId=triage["id"])  # the doctor's own appointment
    assert override(ctx, triage, body, headers=ctx.doc).status_code == 200


# ---- booking against triage --------------------------------------------------------------------


def test_an_emergency_triage_authorizes_the_held_back_slot(ctx: Ctx) -> None:
    script(ctx, Urgency.EMERGENCY)
    triage = run_triage(ctx, "collapsed at home").json()

    response = ctx.book(
        ctx.asha, z(9, 40), triageResultId=triage["id"], emergencyJustification="triage"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["isEmergencySlot"] is True
    assert (body["emergencyJustification"], body["triageResultId"]) == ("triage", triage["id"])
    audit = ctx.c.get(f"{API}/audit-log?action=emergency_authorization", headers=ctx.admin).json()
    assert audit["total"] == 1


def test_a_routine_or_downgraded_triage_does_not_authorize_and_an_upgrade_does(ctx: Ctx) -> None:
    script(ctx, Urgency.ROUTINE)
    routine = run_triage(ctx, "sore throat").json()
    script(ctx, Urgency.EMERGENCY)
    downgraded = run_triage(ctx, "dizzy spells").json()
    override(ctx, downgraded, {"overriddenUrgency": "urgent", "overrideReason": "reviewed"})

    for triage in (routine, downgraded):
        response = ctx.book(
            ctx.asha, z(9, 40), triageResultId=triage["id"], emergencyJustification="triage"
        )
        assert (response.status_code, response.json()["code"]) == (422, "EMERGENCY_NOT_AUTHORIZED")

    override(ctx, routine, {"overriddenUrgency": "emergency", "overrideReason": "clinical concern"})
    upgraded = ctx.book(
        ctx.asha, z(9, 40), triageResultId=routine["id"], emergencyJustification="triage"
    )
    assert upgraded.status_code == 201


def test_another_patients_triage_cannot_authorize_and_a_bad_reference_on_a_regular_slot_is_400(
    ctx: Ctx,
) -> None:
    script(ctx, Urgency.EMERGENCY)
    kirans = run_triage(ctx, "collapsed", patient=ctx.kiran).json()

    stolen = ctx.book(
        ctx.asha, z(9, 40), triageResultId=kirans["id"], emergencyJustification="triage"
    )
    bad_regular = ctx.book(ctx.asha, z(9, 0), triageResultId=str(uuid.uuid4()))

    assert (stolen.status_code, stolen.json()["code"]) == (422, "EMERGENCY_NOT_AUTHORIZED")
    assert bad_regular.status_code == 400


def test_the_triage_an_appointment_was_booked_against_can_be_read_and_404s_otherwise(
    ctx: Ctx,
) -> None:
    triage = run_triage(ctx, "cough").json()
    with_triage = ctx.book(ctx.asha, z(9, 0), triageResultId=triage["id"]).json()
    without = ctx.book(ctx.kiran, z(9, 20)).json()

    found = ctx.c.get(f"{API}/appointments/{with_triage['id']}/triage", headers=ctx.admin)
    missing = ctx.c.get(f"{API}/appointments/{without['id']}/triage", headers=ctx.admin)

    assert found.status_code == 200 and found.json()["id"] == triage["id"]
    assert missing.status_code == 404
    other_doctor = ctx.book(ctx.kiran, z(9, 0), doctor=ctx.other).json()
    assert (
        ctx.c.get(f"{API}/appointments/{other_doctor['id']}/triage", headers=ctx.doc).status_code
        == 403
    )
