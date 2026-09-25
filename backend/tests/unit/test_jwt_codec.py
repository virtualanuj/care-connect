import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.adapters.jwt_codec import JwtTokenCodec
from app.domain.models import Role

SECRET = "s" * 32
NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def test_round_trip_preserves_subject_role_and_expiry() -> None:
    codec = JwtTokenCodec(SECRET)
    user_id = uuid.uuid4()

    claims = codec.decode(codec.encode(user_id, Role.DOCTOR, NOW, ttl_seconds=1800))

    assert claims is not None
    assert (claims.subject, claims.role) == (user_id, Role.DOCTOR)
    assert claims.expires_at == NOW + timedelta(seconds=1800)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = JwtTokenCodec("o" * 32).encode(uuid.uuid4(), Role.DOCTOR, NOW, 60)

    assert JwtTokenCodec(SECRET).decode(token) is None


def test_tampered_or_garbage_tokens_are_rejected() -> None:
    codec = JwtTokenCodec(SECRET)
    token = codec.encode(uuid.uuid4(), Role.DOCTOR, NOW, 60)

    assert codec.decode(token[:-2] + "xx") is None
    assert codec.decode("not-a-token") is None
    assert codec.decode("") is None


def test_unsigned_alg_none_token_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "front_desk_admin", "exp": int(NOW.timestamp()) + 60},
        key="",
        algorithm="none",
    )

    assert JwtTokenCodec(SECRET).decode(forged) is None


def test_token_with_unknown_role_or_missing_claims_is_rejected() -> None:
    bad_role = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "patient", "exp": int(NOW.timestamp()) + 60},
        SECRET,
        algorithm="HS256",
    )
    missing_sub = jwt.encode(
        {"role": "doctor", "exp": int(NOW.timestamp()) + 60}, SECRET, algorithm="HS256"
    )
    codec = JwtTokenCodec(SECRET)

    assert codec.decode(bad_role) is None
    assert codec.decode(missing_sub) is None


def test_expiry_is_reported_not_enforced_by_the_codec() -> None:
    codec = JwtTokenCodec(SECRET)
    token = codec.encode(uuid.uuid4(), Role.DOCTOR, NOW - timedelta(days=1), ttl_seconds=60)

    claims = codec.decode(token)

    assert claims is not None
    assert claims.expires_at < NOW
