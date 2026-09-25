"""Helpers for API tests: create users directly and log in through the real endpoint."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.db.session import get_session_factory
from app.domain.models import Role, User
from app.main import create_app
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.llm import FakeLLMProvider

PASSWORD = "correct horse battery"


class ApiHarness:
    app: FastAPI
    clock: FixedClock
    llm: FakeLLMProvider

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self._hasher = Argon2PasswordHasher()
        self._password_hash = self._hasher.hash(PASSWORD)

    def create_user(
        self, email: str, role: Role = Role.DOCTOR, active: bool = True, name: str = "Test User"
    ) -> User:
        user = User(uuid.uuid4(), email, name, role, self._password_hash, active)
        with get_session_factory()() as session:
            PostgresUserRepository(session).add(user)
            session.commit()
        return user

    def login(self, email: str, password: str = PASSWORD) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return str(response.json()["accessToken"])

    def headers_for(self, email: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.login(email)}"}

    def admin_headers(self) -> dict[str, str]:
        self.create_user("admin@clinic.test", Role.FRONT_DESK_ADMIN, name="Admin")
        return self.headers_for("admin@clinic.test")

    def doctor_headers(self) -> dict[str, str]:
        self.create_user("doctor@clinic.test", Role.DOCTOR, name="Doctor")
        return self.headers_for("doctor@clinic.test")


@pytest.fixture
def harness() -> Iterator[ApiHarness]:
    yield ApiHarness(TestClient(create_app(), raise_server_exceptions=False))


# A Sunday noon; the following Monday (2026-03-02) is the day booking tests work with.
BOOKING_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def booking_harness() -> Iterator[ApiHarness]:
    """A harness whose server clock is fixed and whose AI provider is a scripted fake."""
    clock = FixedClock(BOOKING_NOW)
    llm = FakeLLMProvider()
    app = create_app(clock=clock, llm=llm)
    harness = ApiHarness(TestClient(app, raise_server_exceptions=False))
    harness.app = app
    harness.clock = clock
    harness.llm = llm
    yield harness
