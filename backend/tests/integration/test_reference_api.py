import uuid

import pytest

from app.domain.models import Role
from tests.api_harness import ApiHarness

pytestmark = pytest.mark.integration
API = "/api/v1"


class Ctx:
    """Common setup: an admin, a doctor account with a profile, and a second doctor."""

    def __init__(self, h: ApiHarness) -> None:
        self.h = h
        self.c = h.client
        self.admin = h.admin_headers()
        self.doc_user = h.create_user("doc@clinic.test", Role.DOCTOR, name="Doc")
        self.other_user = h.create_user("other@clinic.test", Role.DOCTOR, name="Other")
        self.doc = h.headers_for("doc@clinic.test")
        self.general = self.c.post(
            f"{API}/specialties",
            json={"name": "General Medicine", "defaultSlotLengthMinutes": 20},
            headers=self.admin,
        ).json()
        self.doctor = self.make_doctor(self.doc_user.id, "Dr Doc")
        self.other = self.make_doctor(self.other_user.id, "Dr Other")

    def make_doctor(self, user_id: uuid.UUID, name: str, **extra: object) -> dict:  # type: ignore[type-arg]
        response = self.c.post(
            f"{API}/doctors",
            json={"userId": str(user_id), "name": name, "specialtyId": self.general["id"], **extra},
            headers=self.admin,
        )
        assert response.status_code == 201, response.text
        return response.json()  # type: ignore[no-any-return]


@pytest.fixture
def ctx(harness: ApiHarness) -> Ctx:
    return Ctx(harness)


# ---- clinic settings ---------------------------------------------------------------------------


def test_settings_are_readable_by_any_staff_and_updatable_by_front_desk_with_audit(
    ctx: Ctx,
) -> None:
    got = ctx.c.get(f"{API}/clinic-settings", headers=ctx.doc)
    assert got.status_code == 200
    assert got.json()["cancellationCutoffHours"] == 2
    assert got.json()["followUpMaxDays"] == 30

    patched = ctx.c.patch(
        f"{API}/clinic-settings",
        json={"cancellationCutoffHours": 4.5, "clinicTimezone": "Asia/Kolkata"},
        headers=ctx.admin,
    )
    assert patched.status_code == 200
    assert (patched.json()["cancellationCutoffHours"], patched.json()["clinicTimezone"]) == (
        4.5,
        "Asia/Kolkata",
    )
    assert (
        ctx.c.get(f"{API}/clinic-settings", headers=ctx.doc).json()["clinicTimezone"]
        == "Asia/Kolkata"
    )
    audit = ctx.c.get(f"{API}/audit-log?action=clinic_settings_changed", headers=ctx.admin).json()
    assert audit["total"] == 1


def test_settings_updates_by_a_doctor_are_forbidden_and_bad_values_are_400(ctx: Ctx) -> None:
    assert (
        ctx.c.patch(
            f"{API}/clinic-settings", json={"followUpMaxDays": 5}, headers=ctx.doc
        ).status_code
        == 403
    )
    for body in (
        {"followUpMaxDays": 0},
        {"cancellationCutoffHours": -1},
        {"clinicTimezone": "Mars/X"},
    ):
        r = ctx.c.patch(f"{API}/clinic-settings", json=body, headers=ctx.admin)
        assert (r.status_code, r.json()["code"]) == (400, "VALIDATION_ERROR"), body


def test_default_triage_specialty_can_be_set_and_cleared(ctx: Ctx) -> None:
    set_ = ctx.c.patch(
        f"{API}/clinic-settings",
        json={"defaultTriageSpecialtyId": ctx.general["id"]},
        headers=ctx.admin,
    )
    cleared = ctx.c.patch(
        f"{API}/clinic-settings", json={"defaultTriageSpecialtyId": None}, headers=ctx.admin
    )

    assert set_.json()["defaultTriageSpecialtyId"] == ctx.general["id"]
    assert cleared.json()["defaultTriageSpecialtyId"] is None


# ---- specialties and doctors -------------------------------------------------------------------


def test_specialty_crud_rules(ctx: Ctx) -> None:
    dup = ctx.c.post(
        f"{API}/specialties",
        json={"name": "general medicine", "defaultSlotLengthMinutes": 20},
        headers=ctx.admin,
    )
    assert (dup.status_code, dup.json()["code"]) == (409, "SPECIALTY_ALREADY_EXISTS")
    assert (
        ctx.c.post(
            f"{API}/specialties",
            json={"name": "X", "defaultSlotLengthMinutes": 20},
            headers=ctx.doc,
        ).status_code
        == 403
    )
    assert (
        ctx.c.post(
            f"{API}/specialties",
            json={"name": "Tiny", "defaultSlotLengthMinutes": 4},
            headers=ctx.admin,
        ).status_code
        == 400
    )
    patched = ctx.c.patch(
        f"{API}/specialties/{ctx.general['id']}",
        json={"name": "Family Medicine"},
        headers=ctx.admin,
    )
    assert patched.json()["name"] == "Family Medicine"
    assert [s["name"] for s in ctx.c.get(f"{API}/specialties", headers=ctx.doc).json()] == [
        "Family Medicine"
    ]
    assert (
        ctx.c.patch(
            f"{API}/specialties/{uuid.uuid4()}", json={"name": "x"}, headers=ctx.admin
        ).status_code
        == 404
    )


def test_doctor_inherits_specialty_slot_length_and_lists_and_filters(ctx: Ctx) -> None:
    assert ctx.doctor["slotLengthMinutes"] == 20
    assert ctx.doctor["active"] is True
    assert len(ctx.c.get(f"{API}/doctors", headers=ctx.doc).json()) == 2
    assert len(ctx.c.get(f"{API}/doctors?specialtyId={uuid.uuid4()}", headers=ctx.doc).json()) == 0
    assert (
        ctx.c.get(f"{API}/doctors/{ctx.doctor['id']}", headers=ctx.doc).json()["name"] == "Dr Doc"
    )
    assert ctx.c.get(f"{API}/doctors/{uuid.uuid4()}", headers=ctx.doc).status_code == 404


def test_doctor_creation_rules(ctx: Ctx) -> None:
    payload = {"userId": str(ctx.doc_user.id), "name": "Again", "specialtyId": ctx.general["id"]}
    dup = ctx.c.post(f"{API}/doctors", json=payload, headers=ctx.admin)
    assert (dup.status_code, dup.json()["code"]) == (409, "DOCTOR_ALREADY_EXISTS")
    ghost = ctx.c.post(
        f"{API}/doctors", json={**payload, "userId": str(uuid.uuid4())}, headers=ctx.admin
    )
    assert ghost.status_code == 400
    assert ctx.c.post(f"{API}/doctors", json=payload, headers=ctx.doc).status_code == 403


def test_doctor_edits_only_their_own_profile_and_never_active(ctx: Ctx) -> None:
    own = ctx.c.patch(
        f"{API}/doctors/{ctx.doctor['id']}", json={"slotLengthMinutes": 25}, headers=ctx.doc
    )
    other = ctx.c.patch(
        f"{API}/doctors/{ctx.other['id']}", json={"name": "Hacked"}, headers=ctx.doc
    )
    active = ctx.c.patch(
        f"{API}/doctors/{ctx.doctor['id']}", json={"active": False}, headers=ctx.doc
    )
    by_admin = ctx.c.patch(
        f"{API}/doctors/{ctx.other['id']}", json={"active": False}, headers=ctx.admin
    )

    assert (own.status_code, own.json()["slotLengthMinutes"]) == (200, 25)
    assert other.status_code == 403
    assert active.status_code == 403
    assert (by_admin.status_code, by_admin.json()["active"]) == (200, False)


# ---- patients and medical history --------------------------------------------------------------


def test_patients_register_search_by_phone_and_reject_duplicates(ctx: Ctx) -> None:
    created = ctx.c.post(
        f"{API}/patients",
        json={"name": "Asha Rao", "phone": "98765 43210", "dob": "1990-05-01"},
        headers=ctx.doc,  # doctors may register patients
    )
    assert created.status_code == 201
    assert created.json()["phone"] == "+919876543210"
    ctx.c.post(
        f"{API}/patients", json={"name": "Kiran Rao", "phone": "+91 98765 43210"}, headers=ctx.admin
    )

    dup = ctx.c.post(
        f"{API}/patients", json={"name": "  asha  RAO", "phone": "09876543210"}, headers=ctx.admin
    )
    assert (dup.status_code, dup.json()["code"]) == (409, "PATIENT_ALREADY_EXISTS")

    found = ctx.c.get(f"{API}/patients?phone=098765-43210", headers=ctx.doc).json()
    assert sorted(p["name"] for p in found["items"]) == ["Asha Rao", "Kiran Rao"]
    assert (found["total"], found["page"], found["pageSize"]) == (2, 1, 20)
    by_name = ctx.c.get(f"{API}/patients?name=kir", headers=ctx.doc).json()
    assert [p["name"] for p in by_name["items"]] == ["Kiran Rao"]
    paged = ctx.c.get(f"{API}/patients?page=2&pageSize=1", headers=ctx.doc).json()
    assert (paged["total"], len(paged["items"])) == (2, 1)


def test_patient_validation_errors(ctx: Ctx) -> None:
    for body in (
        {"name": "A", "phone": "12345"},
        {"name": "", "phone": "9876543210"},
        {"phone": "9876543210"},
    ):
        assert ctx.c.post(f"{API}/patients", json=body, headers=ctx.admin).status_code == 400, body
    assert ctx.c.get(f"{API}/patients?phone=nope", headers=ctx.admin).status_code == 400
    assert ctx.c.get(f"{API}/patients/{uuid.uuid4()}", headers=ctx.admin).status_code == 404


def test_patient_update_can_clear_fields_and_detects_collisions(ctx: Ctx) -> None:
    asha = ctx.c.post(
        f"{API}/patients",
        json={"name": "Asha Rao", "phone": "9876543210", "dob": "1990-05-01", "email": "a@x.com"},
        headers=ctx.admin,
    ).json()
    kiran = ctx.c.post(
        f"{API}/patients", json={"name": "Kiran Rao", "phone": "9876543210"}, headers=ctx.admin
    ).json()

    cleared = ctx.c.patch(
        f"{API}/patients/{asha['id']}", json={"dob": None, "email": None}, headers=ctx.doc
    )
    assert (cleared.json()["dob"], cleared.json()["email"]) == (None, None)
    assert cleared.json()["name"] == "Asha Rao"
    collision = ctx.c.patch(
        f"{API}/patients/{kiran['id']}", json={"name": "asha rao"}, headers=ctx.admin
    )
    assert (collision.status_code, collision.json()["code"]) == (409, "PATIENT_ALREADY_EXISTS")
    assert ctx.c.get(f"{API}/patients/{asha['id']}", headers=ctx.doc).json()["name"] == "Asha Rao"


def test_medical_history_is_append_only_with_amendments(ctx: Ctx) -> None:
    patient = ctx.c.post(
        f"{API}/patients", json={"name": "Asha Rao", "phone": "9876543210"}, headers=ctx.admin
    ).json()
    url = f"{API}/patients/{patient['id']}/medical-history"

    first = ctx.c.post(url, json={"description": "Allergic to X"}, headers=ctx.admin)
    assert first.status_code == 201
    assert (first.json()["kind"], first.json()["amendsEntryId"]) == ("entry", None)
    amendment = ctx.c.post(
        url,
        json={
            "kind": "amendment",
            "amendsEntryId": first.json()["id"],
            "description": "Actually Y",
        },
        headers=ctx.doc,
    )
    assert amendment.status_code == 201

    listing = ctx.c.get(url, headers=ctx.doc).json()
    assert [e["description"] for e in listing] == ["Allergic to X", "Actually Y"]
    assert listing[1]["amendsEntryId"] == first.json()["id"]
    admin_id = ctx.c.get(f"{API}/auth/me", headers=ctx.admin).json()["id"]
    assert listing[0]["recordedBy"] == admin_id
    assert listing[1]["recordedBy"] == str(ctx.doc_user.id)

    bad = ctx.c.post(url, json={"kind": "amendment", "description": "no target"}, headers=ctx.admin)
    assert bad.status_code == 400
    assert (
        ctx.c.post(
            f"{API}/patients/{uuid.uuid4()}/medical-history",
            json={"description": "x"},
            headers=ctx.admin,
        ).status_code
        == 404
    )
    for verb in ("put", "patch", "delete"):
        assert getattr(ctx.c, verb)(
            f"{url}/{first.json()['id']}", headers=ctx.admin
        ).status_code in (404, 405)


# ---- availability ------------------------------------------------------------------------------


def rule_url(ctx: Ctx, doctor: dict, suffix: str = "") -> str:  # type: ignore[type-arg]
    return f"{API}/doctors/{doctor['id']}/availability{suffix}"


def test_weekly_rules_crud_overlap_and_permissions(ctx: Ctx) -> None:
    body = {"dayOfWeek": "monday", "startTime": "09:00", "endTime": "12:00"}
    created = ctx.c.post(rule_url(ctx, ctx.doctor), json=body, headers=ctx.doc)
    assert created.status_code == 201
    assert (created.json()["startTime"], created.json()["endTime"]) == ("09:00", "12:00")

    overlap = ctx.c.post(
        rule_url(ctx, ctx.doctor),
        json={**body, "startTime": "11:00", "endTime": "13:00"},
        headers=ctx.admin,
    )
    assert (overlap.status_code, overlap.json()["code"]) == (409, "AVAILABILITY_OVERLAP")
    assert ctx.c.post(rule_url(ctx, ctx.other), json=body, headers=ctx.doc).status_code == 403
    for bad in (
        {**body, "startTime": "12:00", "endTime": "09:00"},
        {**body, "startTime": "9am"},
        {**body, "dayOfWeek": "funday"},
    ):
        assert (
            ctx.c.post(rule_url(ctx, ctx.doctor), json=bad, headers=ctx.admin).status_code == 400
        ), bad

    rid = created.json()["id"]
    patched = ctx.c.patch(
        rule_url(ctx, ctx.doctor, f"/{rid}"), json={"endTime": "13:00"}, headers=ctx.doc
    )
    assert patched.json()["endTime"] == "13:00"
    listing = ctx.c.get(rule_url(ctx, ctx.doctor), headers=ctx.doc).json()
    assert [r["id"] for r in listing] == [rid]
    assert ctx.c.delete(rule_url(ctx, ctx.doctor, f"/{rid}"), headers=ctx.doc).status_code == 204
    assert ctx.c.delete(rule_url(ctx, ctx.doctor, f"/{rid}"), headers=ctx.doc).status_code == 404
    assert (
        ctx.c.get(f"{API}/doctors/{uuid.uuid4()}/availability", headers=ctx.doc).status_code == 404
    )


def test_exceptions_crud_and_validation(ctx: Ctx) -> None:
    url = f"{API}/doctors/{ctx.doctor['id']}/availability-exceptions"
    holiday = ctx.c.post(url, json={"date": "2026-03-09", "type": "unavailable"}, headers=ctx.doc)
    assert holiday.status_code == 201
    assert (holiday.json()["startTime"], holiday.json()["endTime"]) == (None, None)
    extra = ctx.c.post(
        url,
        json={
            "date": "2026-03-10",
            "type": "extra_hours",
            "startTime": "13:00",
            "endTime": "15:00",
        },
        headers=ctx.admin,
    )
    assert extra.status_code == 201
    for bad in (
        {"date": "2026-03-10", "type": "extra_hours"},
        {"date": "2026-03-10", "type": "unavailable", "startTime": "09:00"},
        {"date": "2026-03-10", "type": "extra_hours", "startTime": "15:00", "endTime": "13:00"},
    ):
        assert ctx.c.post(url, json=bad, headers=ctx.admin).status_code == 400, bad

    assert len(ctx.c.get(url, headers=ctx.doc).json()) == 2
    moved = ctx.c.patch(f"{url}/{extra.json()['id']}", json={"endTime": "16:00"}, headers=ctx.doc)
    assert moved.json()["endTime"] == "16:00"
    assert (
        ctx.c.patch(
            f"{url}/{extra.json()['id']}",
            json={"endTime": "16:00"},
            headers=ctx.h.headers_for("other@clinic.test"),
        ).status_code
        == 403
    )
    assert ctx.c.delete(f"{url}/{holiday.json()['id']}", headers=ctx.doc).status_code == 204
