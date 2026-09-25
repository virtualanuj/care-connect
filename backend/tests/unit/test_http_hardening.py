import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(**overrides: object) -> TestClient:
    settings = Settings(_env_file=None, **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(settings=settings), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CORS_ALLOWED_ORIGINS", "MAX_REQUEST_BYTES"):
        monkeypatch.delenv(name, raising=False)


# ---- request ids -------------------------------------------------------------------------------


def test_every_response_carries_a_request_id() -> None:
    response = make_client().get("/api/v1/health")

    assert re.fullmatch(r"[0-9a-f-]{36}", response.headers["X-Request-ID"])


def test_a_well_formed_incoming_request_id_is_kept_and_a_malformed_one_replaced() -> None:
    client = make_client()

    kept = client.get("/api/v1/health", headers={"X-Request-ID": "trace-1234-abcd"})
    replaced = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\twith spaces"})

    assert kept.headers["X-Request-ID"] == "trace-1234-abcd"
    assert replaced.headers["X-Request-ID"] != "bad id\twith spaces"


def test_error_responses_also_carry_the_request_id() -> None:
    response = make_client().get("/api/v1/nope")

    assert response.status_code == 404
    assert "X-Request-ID" in response.headers


# ---- security headers --------------------------------------------------------------------------


def test_api_responses_carry_security_headers_and_are_not_cacheable() -> None:
    headers = make_client().get("/api/v1/health").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


# ---- CORS --------------------------------------------------------------------------------------


def test_no_origin_is_allowed_by_default() -> None:
    response = make_client().get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_only_configured_origins_are_allowed() -> None:
    client = make_client(cors_allowed_origins="https://app.clinic.test, https://other.clinic.test")

    allowed = client.get("/api/v1/health", headers={"Origin": "https://other.clinic.test"})
    denied = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    preflight = client.options(
        "/api/v1/patients",
        headers={
            "Origin": "https://app.clinic.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "https://other.clinic.test"
    assert "access-control-allow-origin" not in denied.headers
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://app.clinic.test"


def test_a_wildcard_origin_is_refused_at_startup() -> None:
    with pytest.raises(ValueError, match="CORS"):
        Settings(_env_file=None, cors_allowed_origins="*")  # type: ignore[call-arg]


# ---- request size ------------------------------------------------------------------------------


def test_an_oversized_body_is_rejected_with_the_error_envelope() -> None:
    client = make_client(max_request_bytes=100)

    response = client.post(
        "/api/v1/auth/login", content=b"x" * 500, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "X-Request-ID" in response.headers


def test_a_body_within_the_limit_is_processed() -> None:
    client = make_client(max_request_bytes=1000)

    response = client.post("/api/v1/nope", json={"some": "body"})

    assert response.status_code == 404


# ---- structured access log ---------------------------------------------------------------------


def test_the_access_log_is_one_json_line_per_request_without_query_strings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = make_client()

    with caplog.at_level(logging.INFO, logger="careconnect.access"):
        response = client.get("/api/v1/patients?phone=9876543210")

    record = next(r for r in caplog.records if r.name == "careconnect.access")
    payload = json.loads(record.getMessage())
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/patients"
    assert payload["status"] == 401
    assert payload["requestId"] == response.headers["X-Request-ID"]
    assert isinstance(payload["durationMs"], int | float)
    assert "9876543210" not in json.dumps(payload)


# ---- database rejections of out-of-range values ------------------------------------------------


def test_a_database_data_error_is_a_400_not_a_500_and_leaks_nothing() -> None:
    from sqlalchemy.exc import DataError

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(settings=settings)

    @app.get("/boom")
    def boom() -> None:
        raise DataError(
            "INSERT ... Zephyrina", {"name": "Zephyrina"}, Exception("bigint out of range")
        )

    response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "Zephyrina" not in response.text
