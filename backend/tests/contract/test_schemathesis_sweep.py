"""Fuzz every operation in docs/openapi.yaml against a running app, as both roles.

Fails on any response whose status, content type or body is not what the contract documents (and
on any 5xx). This is the "every operation" backstop behind the hand-written contract tests.
"""

import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import schemathesis
import uvicorn
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

from app.domain.models import Role
from app.main import create_app
from tests.api_harness import ApiHarness
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.llm import FakeLLMProvider

SPEC = Path(__file__).resolve().parents[3] / "docs" / "openapi.yaml"
schema = schemathesis.openapi.from_path(str(SPEC))

CHECKS = (
    schemathesis.checks.not_a_server_error,
    schemathesis.checks.status_code_conformance,
    schemathesis.checks.content_type_conformance,
    schemathesis.checks.response_schema_conformance,
)


@pytest.fixture(scope="session")
def live_app() -> Iterator[tuple[str, object]]:
    app = create_app(
        clock=FixedClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC)), llm=FakeLLMProvider()
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/api/v1", app
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def auth_headers(live_app: tuple[str, object]) -> dict[str, dict[str, str]]:
    """Tokens for both roles; users are recreated per test because tables are cleaned between."""
    harness = ApiHarness(TestClient(live_app[1]))  # type: ignore[arg-type]
    harness.create_user("sweep.doctor@clinic.test", Role.DOCTOR)
    return {
        "front_desk": harness.admin_headers(),
        "doctor": harness.headers_for("sweep.doctor@clinic.test"),
    }


@schema.parametrize()
@settings(max_examples=10, deadline=None, suppress_health_check=list(HealthCheck))
def test_every_operation_conforms_to_the_contract(
    case: schemathesis.Case,
    live_app: tuple[str, object],
    auth_headers: dict[str, dict[str, str]],
) -> None:
    for headers in (*auth_headers.values(), {}):
        case.call_and_validate(base_url=live_app[0], headers=headers, checks=CHECKS)
