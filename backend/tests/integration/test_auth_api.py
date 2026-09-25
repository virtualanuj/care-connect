import pytest

from app.domain.models import Role
from tests.api_harness import PASSWORD, ApiHarness

pytestmark = pytest.mark.integration


def test_login_returns_token_type_expiry_and_role(harness: ApiHarness) -> None:
    harness.create_user("doc@clinic.test", Role.DOCTOR)

    response = harness.client.post(
        "/api/v1/auth/login", json={"email": "Doc@Clinic.test", "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "tokenType", "expiresIn", "role"}
    assert (body["tokenType"], body["role"]) == ("bearer", "doctor")
    assert body["expiresIn"] == 30 * 60


def test_wrong_password_is_401_invalid_credentials(harness: ApiHarness) -> None:
    harness.create_user("doc@clinic.test")

    response = harness.client.post(
        "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": "nope-nope-nope-1"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_body_missing_password_is_400(harness: ApiHarness) -> None:
    response = harness.client.post("/api/v1/auth/login", json={"email": "doc@clinic.test"})

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_sixth_failed_login_is_429_rate_limited(harness: ApiHarness) -> None:
    harness.create_user("doc@clinic.test")
    attempt = {"email": "doc@clinic.test", "password": "nope-nope-nope-1"}

    codes = [harness.client.post("/api/v1/auth/login", json=attempt).status_code for _ in range(6)]

    assert codes == [401, 401, 401, 401, 401, 429]
    assert (
        harness.client.post(
            "/api/v1/auth/login", json={"email": "doc@clinic.test", "password": PASSWORD}
        ).json()["code"]
        == "RATE_LIMITED"
    )


def test_me_returns_the_authenticated_user_without_secrets(harness: ApiHarness) -> None:
    harness.create_user("doc@clinic.test", Role.DOCTOR, name="Dr Who")

    response = harness.client.get("/api/v1/auth/me", headers=harness.headers_for("doc@clinic.test"))

    assert response.status_code == 200
    body = response.json()
    assert (body["email"], body["name"], body["role"], body["active"]) == (
        "doc@clinic.test",
        "Dr Who",
        "doctor",
        True,
    )
    assert "password" not in response.text.lower()


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}]
)
def test_me_without_a_valid_bearer_token_is_401(
    harness: ApiHarness, headers: dict[str, str]
) -> None:
    response = harness.client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_token_of_a_deactivated_user_stops_working_immediately(harness: ApiHarness) -> None:
    user = harness.create_user("doc@clinic.test")
    headers = harness.headers_for("doc@clinic.test")
    assert harness.client.get("/api/v1/auth/me", headers=headers).status_code == 200

    from app.adapters.postgres.user_repository import PostgresUserRepository
    from app.db.session import get_session_factory

    with get_session_factory()() as session:
        repo = PostgresUserRepository(session)
        user.active = False
        repo.update(user)
        session.commit()

    assert harness.client.get("/api/v1/auth/me", headers=headers).status_code == 401
