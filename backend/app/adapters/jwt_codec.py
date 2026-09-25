import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.domain.models import Role

_ALGORITHM = "HS256"


@dataclass(frozen=True)
class DecodedToken:
    subject: uuid.UUID
    role: Role
    expires_at: datetime


class JwtTokenCodec:
    """HS256 JWTs. Expiry is reported, not enforced: the service checks it against the Clock."""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def encode(self, subject: uuid.UUID, role: Role, issued_at: datetime, ttl_seconds: int) -> str:
        payload = {
            "sub": str(subject),
            "role": role.value,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + timedelta(seconds=ttl_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def decode(self, token: str) -> DecodedToken | None:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={"verify_exp": False, "require": ["sub", "role", "exp"]},
            )
            return DecodedToken(
                subject=uuid.UUID(payload["sub"]),
                role=Role(payload["role"]),
                expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
            )
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            return None
