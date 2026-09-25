"""Permission matrix: every registered route x role -> expected status.

Extended by every milestone. The completeness test fails when a route is added
without a row here.
"""

import json
import re
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
        {"email": "{role}@new.test", "name": "N", "role": "doctor", "password": "long enough pass"},
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


FORBIDDEN_FOR_DOCTOR_404 = {"anonymous": 401, "doctor": 403, "front_desk": 404}
# Unknown ids: authentication and role gates are checked before the resource lookup, so an
# authorized role gets 404. Ownership rules (doctor edits only own data) are covered in
# test_reference_api.py against real records.
NOT_FOUND = {"anonymous": 401, "doctor": 404, "front_desk": 404}
AUTHENTICATED_OK = {"anonymous": 401, "doctor": 200, "front_desk": 200}
RULE = {"dayOfWeek": "monday", "startTime": "09:00", "endTime": "12:00"}
EXCEPTION = {"date": "2026-03-09", "type": "unavailable"}
REFERENCE_MATRIX: list[tuple[str, str, dict[str, object] | None, dict[str, int]]] = [
    ("GET", "/clinic-settings", None, AUTHENTICATED_OK),
    (
        "PATCH",
        "/clinic-settings",
        {"followUpMaxDays": 30},
        {**FORBIDDEN_FOR_DOCTOR, "front_desk": 200},
    ),
    ("GET", "/specialties", None, AUTHENTICATED_OK),
    (
        "POST",
        "/specialties",
        {"name": "Spec {role}", "defaultSlotLengthMinutes": 20},
        {**FORBIDDEN_FOR_DOCTOR, "front_desk": 201},
    ),
    ("PATCH", f"/specialties/{ID}", {"name": "x"}, FORBIDDEN_FOR_DOCTOR_404),
    ("GET", "/doctors", None, AUTHENTICATED_OK),
    (
        "POST",
        "/doctors",
        {"userId": ID, "name": "x", "specialtyId": ID},
        {**FORBIDDEN_FOR_DOCTOR, "front_desk": 400},
    ),
    ("GET", f"/doctors/{ID}", None, NOT_FOUND),
    ("PATCH", f"/doctors/{ID}", {"name": "x"}, NOT_FOUND),
    ("GET", f"/doctors/{ID}/availability", None, NOT_FOUND),
    ("POST", f"/doctors/{ID}/availability", RULE, NOT_FOUND),
    ("PATCH", f"/doctors/{ID}/availability/{ID}", {"endTime": "13:00"}, NOT_FOUND),
    ("DELETE", f"/doctors/{ID}/availability/{ID}", None, NOT_FOUND),
    ("GET", f"/doctors/{ID}/availability-exceptions", None, NOT_FOUND),
    ("POST", f"/doctors/{ID}/availability-exceptions", EXCEPTION, NOT_FOUND),
    ("PATCH", f"/doctors/{ID}/availability-exceptions/{ID}", {"endTime": "13:00"}, NOT_FOUND),
    ("DELETE", f"/doctors/{ID}/availability-exceptions/{ID}", None, NOT_FOUND),
    ("GET", "/patients", None, AUTHENTICATED_OK),
    (
        "POST",
        "/patients",
        {"name": "Patient {role}", "phone": "9876543210"},
        {"anonymous": 401, "doctor": 201, "front_desk": 201},
    ),
    ("GET", f"/patients/{ID}", None, NOT_FOUND),
    ("PATCH", f"/patients/{ID}", {"name": "x"}, NOT_FOUND),
    ("GET", f"/patients/{ID}/medical-history", None, NOT_FOUND),
    ("POST", f"/patients/{ID}/medical-history", {"description": "x"}, NOT_FOUND),
]
MATRIX.extend(REFERENCE_MATRIX)

BOOKING_MATRIX: list[tuple[str, str, dict[str, object] | None, dict[str, int]]] = [
    ("GET", f"/slots?date=2026-03-02&doctorId={ID}", None, NOT_FOUND),
    ("GET", "/appointments", None, AUTHENTICATED_OK),
    (
        "POST",
        "/appointments",
        {"doctorId": ID, "patientId": ID, "startTime": "2026-03-02T09:00:00Z"},
        NOT_FOUND,
    ),
    ("GET", f"/appointments/{ID}", None, NOT_FOUND),
]
MATRIX.extend(BOOKING_MATRIX)

LIFECYCLE_MATRIX: list[tuple[str, str, dict[str, object] | None, dict[str, int]]] = [
    ("POST", f"/appointments/{ID}/check-in", None, NOT_FOUND),
    ("POST", f"/appointments/{ID}/start-consultation", None, NOT_FOUND),
    ("POST", f"/appointments/{ID}/complete", None, NOT_FOUND),
    ("POST", f"/appointments/{ID}/no-show", None, NOT_FOUND),
    ("POST", f"/appointments/{ID}/cancel", None, NOT_FOUND),
    (
        "POST",
        f"/appointments/{ID}/force-cancel",
        {"reason": "why"},
        {"anonymous": 401, "doctor": 403, "front_desk": 404},  # role gate precedes the lookup
    ),
    (
        "POST",
        f"/appointments/{ID}/reschedule",
        {"newStartTime": "2026-03-02T09:00:00Z"},
        NOT_FOUND,
    ),
    ("POST", f"/appointments/{ID}/follow-up", {"startTime": "2026-03-09T09:00:00Z"}, NOT_FOUND),
]
MATRIX.extend(LIFECYCLE_MATRIX)
MATRIX.append(("GET", "/queue?date=2026-03-02", None, AUTHENTICATED_OK))

TRIAGE_MATRIX: list[tuple[str, str, dict[str, object] | None, dict[str, int]]] = [
    ("POST", f"/patients/{ID}/triage", {"reportedSymptoms": "cough"}, NOT_FOUND),
    ("GET", f"/patients/{ID}/triage", None, NOT_FOUND),
    ("GET", f"/appointments/{ID}/triage", None, NOT_FOUND),
    (
        "PATCH",
        f"/triage-results/{ID}/override",
        {"overriddenUrgency": "routine", "overrideReason": "why"},
        NOT_FOUND,
    ),
]
MATRIX.extend(TRIAGE_MATRIX)


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
        # Creating routes need unique values per role: "{role}" is substituted in the body.
        payload = json.loads(json.dumps(body).replace("{role}", role)) if body else body
        response = harness.client.request(
            method, f"{API_PREFIX}{path}", json=payload, headers=headers_by_role[role]
        )
        assert response.status_code == status, f"{role} {method} {path}: {response.text}"


def test_every_registered_route_is_in_the_permission_matrix() -> None:
    documented = {(method, path.split("?")[0]) for method, path, _, _ in MATRIX}
    # FastAPI's generated schema lists every registered operation.
    registered = {
        (method.upper(), re.sub(r"\{[a-z_]+\}", ID, path.removeprefix(API_PREFIX)))
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
    }

    assert registered == documented
