import pytest
from sqlalchemy import text

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.db.seed import seed_admin
from app.db.session import get_engine, get_session_factory
from app.domain.errors import ValidationFailed
from app.domain.models import Role
from tests.api_harness import ApiHarness

pytestmark = pytest.mark.integration

PASSWORD = "seed admin passphrase"


def run_seed(email: str = "Admin@Clinic.test", password: str = PASSWORD) -> bool:
    with get_session_factory()() as session:
        created = seed_admin(session, Argon2PasswordHasher(), email, password)
        session.commit()
        return created


def count_users() -> int:
    with get_engine().connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


def test_seed_creates_one_front_desk_admin_who_can_log_in(harness: ApiHarness) -> None:
    assert run_seed() is True

    response = harness.client.post(
        "/api/v1/auth/login", json={"email": "admin@clinic.test", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["role"] == Role.FRONT_DESK_ADMIN.value


def test_running_the_seed_twice_leaves_exactly_one_row() -> None:
    assert run_seed() is True
    assert run_seed() is False

    assert count_users() == 1


def test_seed_does_not_overwrite_an_existing_admin_password() -> None:
    run_seed()

    run_seed(password="a different passphrase!")

    with get_session_factory()() as session:
        from app.adapters.postgres.user_repository import PostgresUserRepository

        user = PostgresUserRepository(session).get_by_email("admin@clinic.test")
    assert user is not None
    assert Argon2PasswordHasher().verify(PASSWORD, user.password_hash)


def test_seed_rejects_a_weak_password() -> None:
    with pytest.raises(ValidationFailed):
        run_seed(password="short")
    assert count_users() == 0
