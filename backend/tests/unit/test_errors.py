from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.errors import register_error_handlers
from app.domain import errors
from app.domain.errors import ErrorCode

OPENAPI = Path(__file__).resolve().parents[3] / "docs" / "openapi.yaml"

EXPECTED_STATUS = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.SLOT_ALREADY_BOOKED: 409,
    ErrorCode.PATIENT_ALREADY_BOOKED: 409,
    ErrorCode.INVALID_SLOT: 422,
    ErrorCode.EMERGENCY_JUSTIFICATION_REQUIRED: 422,
    ErrorCode.EMERGENCY_NOT_AUTHORIZED: 422,
    ErrorCode.CANCELLATION_WINDOW_CLOSED: 422,
    ErrorCode.INVALID_TRANSITION: 409,
    ErrorCode.FOLLOW_UP_WINDOW_EXCEEDED: 422,
    ErrorCode.APPOINTMENT_NOT_COMPLETED: 409,
    ErrorCode.PATIENT_ALREADY_EXISTS: 409,
    ErrorCode.USER_ALREADY_EXISTS: 409,
    ErrorCode.AVAILABILITY_OVERLAP: 409,
    ErrorCode.AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS: 409,
    ErrorCode.VISIT_NOTE_NOT_WRITABLE: 409,
    ErrorCode.VISIT_NOTE_LOCKED: 409,
    ErrorCode.NO_NOTES_TO_DRAFT: 422,
    ErrorCode.AI_SERVICE_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class Payload(BaseModel):
    name: str
    age: int


def build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/domain")
    def domain() -> None:
        raise errors.SlotAlreadyBooked("Doctor already booked at that time")

    @app.get("/not-found")
    def not_found() -> None:
        raise HTTPException(status_code=404, detail="nope")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise HTTPException(status_code=403, detail="nope")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail: patient Asha Rao 555-0102")

    @app.post("/validate")
    def validate(payload: Payload) -> Payload:
        return payload

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app(), raise_server_exceptions=False)


def test_every_error_code_has_a_domain_error_with_the_documented_status() -> None:
    assert set(EXPECTED_STATUS) == set(ErrorCode)
    for code, status in EXPECTED_STATUS.items():
        error_class = errors.ERROR_CLASSES[code]
        assert issubclass(error_class, errors.DomainError)
        assert error_class.code == code
        assert error_class.status_code == status


def test_error_codes_match_the_openapi_catalog() -> None:
    spec = yaml.safe_load(OPENAPI.read_text())
    catalog = set(spec["components"]["schemas"]["ErrorCode"]["enum"])

    assert catalog == {code.value for code in ErrorCode}


def test_domain_error_is_serialized_as_code_and_message_only(client: TestClient) -> None:
    response = client.get("/domain")

    assert response.status_code == 409
    assert response.json() == {
        "code": "SLOT_ALREADY_BOOKED",
        "message": "Doctor already booked at that time",
    }


def test_malformed_body_returns_400_validation_error_not_422(client: TestClient) -> None:
    response = client.post("/validate", json={"name": "Asha Rao", "age": "not-a-number"})

    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == "VALIDATION_ERROR"
    assert "age" in body["message"]


def test_validation_message_does_not_echo_submitted_values(client: TestClient) -> None:
    response = client.post("/validate", json={"name": "Asha Rao 555-0102", "age": "x"})

    assert "555-0102" not in response.text
    assert "Asha" not in response.text


def test_http_404_and_403_map_to_error_envelope(client: TestClient) -> None:
    missing = client.get("/not-found")
    forbidden = client.get("/forbidden")
    unknown_route = client.get("/no-such-route")

    assert (missing.status_code, missing.json()["code"]) == (404, "NOT_FOUND")
    assert (forbidden.status_code, forbidden.json()["code"]) == (403, "FORBIDDEN")
    assert (unknown_route.status_code, unknown_route.json()["code"]) == (404, "NOT_FOUND")


def test_unhandled_exception_returns_generic_500_without_details(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL_ERROR", "message": "Internal server error"}
    assert "secret" not in response.text
    assert "Traceback" not in response.text
