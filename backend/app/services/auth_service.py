from dataclasses import dataclass

from app.domain.errors import InvalidCredentials, RateLimited, Unauthenticated
from app.domain.models import Role, User
from app.domain.ports import Clock, PasswordHasher, RateLimiter, TokenCodec, UserRepository

_BAD_CREDENTIALS = "Incorrect email or password"


@dataclass(frozen=True)
class LoginResult:
    token: str
    expires_in: int
    role: Role


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenCodec,
        clock: Clock,
        limiter: RateLimiter,
        ttl_seconds: int,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._limiter = limiter
        self._ttl_seconds = ttl_seconds
        # Verified against for unknown emails so response time does not reveal which exist.
        self._dummy_hash = hasher.hash("timing-equalisation-password")

    def login(self, email: str, password: str, client_id: str) -> LoginResult:
        normalized = email.strip().lower()
        key = f"{client_id}|{normalized}"
        if self._limiter.is_blocked(key):
            raise RateLimited("Too many failed attempts. Try again later.")

        user = self._users.get_by_email(normalized)
        password_ok = self._hasher.verify(
            password, user.password_hash if user else self._dummy_hash
        )
        if user is None or not user.active or not password_ok:
            self._limiter.record_failure(key)
            raise InvalidCredentials(_BAD_CREDENTIALS)

        self._limiter.reset(key)
        token = self._tokens.encode(user.id, user.role, self._clock.now(), self._ttl_seconds)
        return LoginResult(token=token, expires_in=self._ttl_seconds, role=user.role)

    def authenticate(self, token: str) -> User:
        """Resolve a bearer token to the *current* active user (role comes from the database)."""
        claims = self._tokens.decode(token)
        if claims is None or claims.expires_at <= self._clock.now():
            raise Unauthenticated("Authentication required")
        user = self._users.get(claims.subject)
        if user is None or not user.active:
            raise Unauthenticated("Authentication required")
        return user
