"""Real responses of the auth, users and audit endpoints must match docs/openapi.yaml."""

import uuid

from app.domain.models import Role
from tests.api_harness import PASSWORD, ApiHarness
from tests.contract.conftest import ContractCheck

NEW_USER = {
    "email": "new.doc@clinic.test",
    "name": "New Doc",
    "role": "doctor",
    "password": "a long enough passphrase",
}


def test_login_and_me_responses(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    harness.create_user("doc@clinic.test", Role.DOCTOR)
    client = harness.client

    login = client.post(
        "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": PASSWORD}
    )
    assert_contract(login)
    token = login.json()["accessToken"]
    assert_contract(client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}))


def test_auth_error_responses(harness: ApiHarness, assert_contract: ContractCheck) -> None:
    harness.create_user("doc@clinic.test")
    client = harness.client

    assert_contract(client.post("/api/v1/auth/login", json={"email": "doc@clinic.test"}))  # 400
    bad = {"email": "doc@clinic.test", "password": "wrong-password-1"}
    assert_contract(client.post("/api/v1/auth/login", json=bad))  # 401
    assert_contract(client.get("/api/v1/auth/me"))  # 401
    for _ in range(5):
        client.post("/api/v1/auth/login", json=bad)
    assert_contract(client.post("/api/v1/auth/login", json=bad))  # 429


def test_users_endpoints_match_the_contract(
    harness: ApiHarness, assert_contract: ContractCheck
) -> None:
    admin = harness.admin_headers()
    doctor_headers = harness.doctor_headers()
    client = harness.client

    created = client.post("/api/v1/users", json=NEW_USER, headers=admin)
    assert_contract(created)  # 201
    user_id = created.json()["id"]
    assert_contract(client.get("/api/v1/users", headers=admin))  # 200
    assert_contract(
        client.patch(f"/api/v1/users/{user_id}", json={"name": "Renamed"}, headers=admin)
    )
    reset = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        json={"newPassword": "another long passphrase"},
        headers=admin,
    )
    assert_contract(reset)  # 204

    assert_contract(client.post("/api/v1/users", json=NEW_USER, headers=admin))  # 409
    assert_contract(client.post("/api/v1/users", json={**NEW_USER, "password": "x"}, headers=admin))
    assert_contract(
        client.patch(f"/api/v1/users/{uuid.uuid4()}", json={"name": "x"}, headers=admin)
    )
    assert_contract(client.get("/api/v1/users", headers=doctor_headers))  # 403
    assert_contract(client.get("/api/v1/users"))  # 401


def test_audit_log_endpoint_matches_the_contract(
    harness: ApiHarness, assert_contract: ContractCheck
) -> None:
    admin = harness.admin_headers()
    harness.client.post("/api/v1/users", json=NEW_USER, headers=admin)

    assert_contract(harness.client.get("/api/v1/audit-log", headers=admin))
    assert_contract(harness.client.get("/api/v1/audit-log?action=user_created", headers=admin))
    assert_contract(harness.client.get("/api/v1/audit-log", headers=harness.doctor_headers()))
