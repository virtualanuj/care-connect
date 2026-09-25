import uuid

import pytest

from app.domain.models import Role
from tests.api_harness import PASSWORD, ApiHarness

pytestmark = pytest.mark.integration

NEW_USER = {
    "email": "new.doc@clinic.test",
    "name": "New Doc",
    "role": "doctor",
    "password": "a long enough passphrase",
}


def test_admin_creates_a_user_who_can_then_log_in(harness: ApiHarness) -> None:
    headers = harness.admin_headers()

    created = harness.client.post("/api/v1/users", json=NEW_USER, headers=headers)

    assert created.status_code == 201
    body = created.json()
    assert (body["email"], body["role"], body["active"]) == ("new.doc@clinic.test", "doctor", True)
    assert "password" not in created.text.lower()
    login = harness.client.post(
        "/api/v1/auth/login",
        json={"email": NEW_USER["email"], "password": NEW_USER["password"]},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "doctor"


def test_duplicate_email_is_409_user_already_exists(harness: ApiHarness) -> None:
    headers = harness.admin_headers()
    harness.client.post("/api/v1/users", json=NEW_USER, headers=headers)

    again = harness.client.post(
        "/api/v1/users", json={**NEW_USER, "email": "NEW.DOC@clinic.test"}, headers=headers
    )

    assert again.status_code == 409
    assert again.json()["code"] == "USER_ALREADY_EXISTS"


@pytest.mark.parametrize(
    "override",
    [{"password": "short"}, {"role": "patient"}, {"email": "not-an-email"}, {"name": ""}],
)
def test_invalid_create_bodies_are_400(harness: ApiHarness, override: dict[str, str]) -> None:
    response = harness.client.post(
        "/api/v1/users", json={**NEW_USER, **override}, headers=harness.admin_headers()
    )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_list_is_paginated_and_never_exposes_password_hashes(harness: ApiHarness) -> None:
    headers = harness.admin_headers()
    for i in range(3):
        harness.create_user(f"user{i}@clinic.test")

    page = harness.client.get("/api/v1/users?page=1&pageSize=2", headers=headers)

    body = page.json()
    assert page.status_code == 200
    assert (body["page"], body["pageSize"], body["total"]) == (1, 2, 4)
    assert len(body["items"]) == 2
    assert "hash" not in page.text.lower()


def test_page_size_above_100_is_400(harness: ApiHarness) -> None:
    response = harness.client.get("/api/v1/users?pageSize=101", headers=harness.admin_headers())

    assert response.status_code == 400


def test_deactivating_a_user_blocks_their_login_and_live_session(harness: ApiHarness) -> None:
    admin = harness.admin_headers()
    doctor = harness.create_user("doc@clinic.test")
    doctor_headers = harness.headers_for("doc@clinic.test")

    patched = harness.client.patch(
        f"/api/v1/users/{doctor.id}", json={"active": False}, headers=admin
    )

    assert patched.status_code == 200
    assert patched.json()["active"] is False
    assert harness.client.get("/api/v1/auth/me", headers=doctor_headers).status_code == 401
    relogin = harness.client.post(
        "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": PASSWORD}
    )
    assert relogin.status_code == 401


def test_admin_cannot_deactivate_themselves(harness: ApiHarness) -> None:
    headers = harness.admin_headers()
    me = harness.client.get("/api/v1/auth/me", headers=headers).json()

    response = harness.client.patch(
        f"/api/v1/users/{me['id']}", json={"active": False}, headers=headers
    )

    assert response.status_code == 400


def test_role_change_takes_effect_on_existing_tokens(harness: ApiHarness) -> None:
    admin = harness.admin_headers()
    doctor = harness.create_user("doc@clinic.test", Role.DOCTOR)
    doctor_headers = harness.headers_for("doc@clinic.test")
    assert harness.client.get("/api/v1/users", headers=doctor_headers).status_code == 403

    harness.client.patch(
        f"/api/v1/users/{doctor.id}", json={"role": "front_desk_admin"}, headers=admin
    )

    assert harness.client.get("/api/v1/users", headers=doctor_headers).status_code == 200


def test_patch_unknown_user_is_404(harness: ApiHarness) -> None:
    response = harness.client.patch(
        f"/api/v1/users/{uuid.uuid4()}", json={"name": "x"}, headers=harness.admin_headers()
    )

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_reset_password_swaps_the_working_password(harness: ApiHarness) -> None:
    admin = harness.admin_headers()
    doctor = harness.create_user("doc@clinic.test")

    reset = harness.client.post(
        f"/api/v1/users/{doctor.id}/reset-password",
        json={"newPassword": "brand new passphrase"},
        headers=admin,
    )

    assert reset.status_code == 204
    old = harness.client.post(
        "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": PASSWORD}
    )
    new = harness.client.post(
        "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": "brand new passphrase"}
    )
    assert (old.status_code, new.status_code) == (401, 200)


def test_audit_log_records_user_events_without_secrets_and_can_be_filtered(
    harness: ApiHarness,
) -> None:
    admin = harness.admin_headers()
    created = harness.client.post("/api/v1/users", json=NEW_USER, headers=admin).json()
    harness.client.post(
        f"/api/v1/users/{created['id']}/reset-password",
        json={"newPassword": "another long passphrase"},
        headers=admin,
    )

    everything = harness.client.get("/api/v1/audit-log", headers=admin).json()
    resets = harness.client.get("/api/v1/audit-log?action=password_reset", headers=admin).json()

    assert [e["action"] for e in everything["items"]] == ["password_reset", "user_created"]
    assert everything["total"] == 2
    assert [e["action"] for e in resets["items"]] == ["password_reset"]
    assert resets["items"][0]["targetId"] == created["id"]
    assert "passphrase" not in str(everything)


def test_audit_log_rejects_unknown_action_filter(harness: ApiHarness) -> None:
    response = harness.client.get("/api/v1/audit-log?action=nope", headers=harness.admin_headers())

    assert response.status_code == 400
