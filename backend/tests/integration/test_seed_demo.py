from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.db.seed import seed_demo_data
from app.db.session import get_engine, get_session_factory
from tests.fakes.fixed_clock import FixedClock

pytestmark = pytest.mark.integration

NOW = datetime(2026, 3, 4, 8, 0, tzinfo=UTC)


def run() -> bool:
    with get_session_factory()() as session:
        created = seed_demo_data(session, Argon2PasswordHasher(), FixedClock(NOW))
        session.commit()
        return created


def scalar(sql: str) -> int:
    with get_engine().connect() as connection:
        return int(connection.execute(text(sql)).scalar_one())


def test_the_demo_seed_builds_a_realistic_clinic_with_a_queue_in_every_status() -> None:
    assert run() is True

    assert scalar("SELECT count(*) FROM specialties") == 3
    assert scalar("SELECT count(*) FROM doctors") == 6
    assert scalar("SELECT count(*) FROM patients") >= 40
    assert scalar("SELECT count(DISTINCT doctor_id) FROM availability") == 6
    with get_engine().connect() as connection:
        statuses = {
            row[0] for row in connection.execute(text("SELECT status::text FROM appointments"))
        }
        walk_ins = connection.execute(
            text("SELECT count(*) FROM appointments WHERE source = 'walk_in'")
        ).scalar_one()
    assert statuses == {
        "booked",
        "checked_in",
        "in_consultation",
        "completed",
        "cancelled",
        "no_show",
    }
    assert walk_ins >= 1


def test_the_demo_seed_is_idempotent() -> None:
    run()
    counts = [
        scalar(f"SELECT count(*) FROM {table}")
        for table in ("users", "doctors", "patients", "appointments", "specialties")
    ]

    assert run() is False

    assert counts == [
        scalar(f"SELECT count(*) FROM {table}")
        for table in ("users", "doctors", "patients", "appointments", "specialties")
    ]
