"""Permission matrix: every registered route x role -> expected status.

Extended by every milestone. The completeness test fails when a route is added
without a row here.
"""

import uuid

import pytest

from app.main import API_PREFIX, create_app
from tests.api_harness import ApiHarness

pytestmark = pytest.mark.integration

ID = str(uuid.uuid4())
PUBLIC = {"/health", "/auth/login"}

# (method, path template, body, {role: expected status}); roles: anonymous, doctor, front_desk
FORBIDDEN_FOR_DOCTOR = {"anonymous": 401, "doctor": 403}
MATRIX: list[tuple[str, str, dict[str, object] | None, dict[str, int]]] = [
    ("GET", "/health", None, {"anonymous": 200, "doctor": 200, "front_desk": 200}),
    (
        "POST",
        "/auth/login",
        {"email": "nobody@clinic.test", "password": "x"},
        {"anonymous": 401, "doctor": 401, "front_desk": 401},
    ),
    ("GET", "/auth/me", None, {"anonymous": 401, "doctor": 200, "front_desk": 200}),
    ("GET", "/users", None, {**FORBIDDEN_FOR_DOCTOR, "front_desk": 200}),
    (
        "POST",
        "/users",
        {"email": "n@clinic.test", "name": "N", "role": "doctor", "password": "long enough pass"},
        {**FORBIDDEN_FOR_DOCTOR, "front_desk": 201},
    ),
    ("PATCH", f"/users/{ID}", {"name": "x"}, {**FORBIDDEN_FOR_DOCTOR, "front_desk": 404}),
    (
        "POST",
        f"/users/{ID}/reset-password",
        {"newPassword": "long enough pass"},
        {**FORBIDDEN_FOR_DOCTOR, "front_desk": 404},
    ),
    ("GET", "/audit-log", None, {**FORBIDDEN_FOR_DOCTOR, "front_desk": 200}),
]


@pytest.mark.parametrize(("method", "path", "body", "expected"), MATRIX)
def test_route_permissions(
    harness: ApiHarness,
    method: str,
    path: str,
    body: dict[str, object] | None,
    expected: dict[str, int],
) -> None:
    headers_by_role = {
        "anonymous": {},
        "doctor": harness.doctor_headers(),
        "front_desk": harness.admin_headers(),
    }
    for role, status in expected.items():
        # POST /users creates a row, so give every role its own email.
        payload = body
        if path == "/users" and method == "POST" and body is not None:
            payload = {**body, "email": f"{role}@new.test"}
        response = harness.client.request(
            method, f"{API_PREFIX}{path}", json=payload, headers=headers_by_role[role]
        )
        assert response.status_code == status, f"{role} {method} {path}: {response.text}"


def test_every_registered_route_is_in_the_permission_matrix() -> None:
    documented = {(method, path) for method, path, _, _ in MATRIX}
    # FastAPI's generated schema lists every registered operation.
    registered = {
        (method.upper(), path.removeprefix(API_PREFIX).replace("{user_id}", ID))
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
    }

    assert registered == documented
