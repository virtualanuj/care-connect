import uuid
from datetime import timedelta

import pytest

from app.adapters.jwt_codec import JwtTokenCodec
from app.adapters.rate_limiter import InMemoryRateLimiter
from app.domain.errors import InvalidCredentials, RateLimited, Unauthenticated
from app.domain.models import Role, User
from app.services.auth_service import AuthService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import InMemoryUserRepository
from tests.fakes.security import FakePasswordHasher
from tests.unit.test_audit_service import START

PASSWORD = "correct horse battery"
TTL = 1800


class SpyHasher(FakePasswordHasher):
    def __init__(self) -> None:
        self.verify_calls = 0

    def verify(self, password: str, password_hash: str) -> bool:
        self.verify_calls += 1
        return super().verify(password, password_hash)


class Setup:
    def __init__(self) -> None:
        self.clock = FixedClock(START)
        self.users = InMemoryUserRepository()
        self.hasher = SpyHasher()
        self.codec = JwtTokenCodec("s" * 32)
        self.limiter = InMemoryRateLimiter(self.clock, max_failures=5, window=timedelta(minutes=15))
        self.service = AuthService(
            self.users, self.hasher, self.codec, self.clock, self.limiter, ttl_seconds=TTL
        )
        self.doctor = User(
            uuid.uuid4(), "doc@clinic.test", "Doc", Role.DOCTOR, self.hasher.hash(PASSWORD)
        )
        self.users.add(self.doctor)


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_correct_credentials_issue_a_token_carrying_the_role(s: Setup) -> None:
    result = s.service.login("Doc@Clinic.test", PASSWORD, "1.2.3.4")

    assert result.role == Role.DOCTOR
    assert result.expires_in == TTL
    claims = s.codec.decode(result.token)
    assert claims is not None
    assert (claims.subject, claims.role) == (s.doctor.id, Role.DOCTOR)


def test_wrong_password_unknown_email_and_inactive_user_are_indistinguishable(s: Setup) -> None:
    s.doctor.active = False
    s.users.add(User(uuid.uuid4(), "b@clinic.test", "B", Role.DOCTOR, s.hasher.hash(PASSWORD)))

    messages = set()
    for email, password in [
        ("b@clinic.test", "wrong-password-123"),
        ("nobody@clinic.test", PASSWORD),
        ("doc@clinic.test", PASSWORD),
    ]:
        with pytest.raises(InvalidCredentials) as caught:
            s.service.login(email, password, "1.2.3.4")
        messages.add(caught.value.message)

    assert len(messages) == 1


def test_unknown_email_still_performs_a_password_verification(s: Setup) -> None:
    before = s.hasher.verify_calls

    with pytest.raises(InvalidCredentials):
        s.service.login("nobody@clinic.test", "whatever-password", "1.2.3.4")

    assert s.hasher.verify_calls == before + 1


def test_sixth_attempt_is_rate_limited_even_with_the_correct_password(s: Setup) -> None:
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            s.service.login("doc@clinic.test", "wrong-password-123", "1.2.3.4")

    with pytest.raises(RateLimited):
        s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4")

    s.clock.advance(timedelta(minutes=15, seconds=1))
    assert s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token


def test_rate_limit_is_per_ip_and_email(s: Setup) -> None:
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            s.service.login("doc@clinic.test", "wrong-password-123", "1.2.3.4")

    assert s.service.login("doc@clinic.test", PASSWORD, "9.9.9.9").token


def test_successful_login_resets_the_failure_counter(s: Setup) -> None:
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            s.service.login("doc@clinic.test", "wrong-password-123", "1.2.3.4")
    s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4")

    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            s.service.login("doc@clinic.test", "wrong-password-123", "1.2.3.4")
    assert s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token


def test_authenticate_returns_the_current_user_from_the_repository(s: Setup) -> None:
    token = s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token
    s.doctor.name = "Renamed"

    assert s.service.authenticate(token).name == "Renamed"


def test_authenticate_rejects_expired_tokens(s: Setup) -> None:
    token = s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token

    s.clock.advance(timedelta(seconds=TTL))

    with pytest.raises(Unauthenticated):
        s.service.authenticate(token)


def test_authenticate_rejects_garbage_and_deactivated_and_deleted_users(s: Setup) -> None:
    token = s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token

    with pytest.raises(Unauthenticated):
        s.service.authenticate("garbage")

    s.doctor.active = False
    with pytest.raises(Unauthenticated):
        s.service.authenticate(token)

    del s.users.users[s.doctor.id]
    with pytest.raises(Unauthenticated):
        s.service.authenticate(token)


def test_role_in_a_token_is_ignored_in_favour_of_the_current_database_role(s: Setup) -> None:
    token = s.service.login("doc@clinic.test", PASSWORD, "1.2.3.4").token
    s.doctor.role = Role.FRONT_DESK_ADMIN

    assert s.service.authenticate(token).role == Role.FRONT_DESK_ADMIN
