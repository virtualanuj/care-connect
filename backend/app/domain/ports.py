"""Ports: interfaces the service layer depends on (implemented by adapters)."""

import uuid
from datetime import datetime
from typing import Protocol

from app.domain.models import AuditAction, AuditEntry, Page, Role, User


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time as a timezone-aware UTC datetime."""
        ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenClaims(Protocol):
    subject: uuid.UUID
    role: Role
    expires_at: datetime


class TokenCodec(Protocol):
    def encode(self, subject: uuid.UUID, role: Role, issued_at: datetime, ttl_seconds: int) -> str:
        """Create a signed token."""
        ...

    def decode(self, token: str) -> "TokenClaims | None":
        """Return the claims if the signature and structure are valid, else None.

        Expiry is NOT checked here: the service compares `expires_at` against the Clock.
        """
        ...


class RateLimiter(Protocol):
    def is_blocked(self, key: str) -> bool: ...

    def record_failure(self, key: str) -> None: ...

    def reset(self, key: str) -> None: ...


class UserRepository(Protocol):
    def add(self, user: User) -> None:
        """Insert a user. Raises `UserAlreadyExists` if the email is taken (case-insensitive)."""
        ...

    def get(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def list(self, page: int, page_size: int) -> Page[User]: ...

    def update(self, user: User) -> None: ...


class AuditRepository(Protocol):
    def add(self, entry: AuditEntry) -> None: ...

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        """Newest first."""
        ...
