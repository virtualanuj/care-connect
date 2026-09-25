import pytest
from sqlalchemy import text

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.adapters.clock import SystemClock
from app.db.seed import seed_dev_data
from app.db.session import get_engine, get_session_factory

pytestmark = pytest.mark.integration


def run() -> bool:
    with get_session_factory()() as session:
        created = seed_dev_data(session, Argon2PasswordHasher(), SystemClock())
        session.commit()
        return created


def count(table: str) -> int:
    with get_engine().connect() as connection:
        return int(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def test_dev_seed_creates_a_specialty_doctor_availability_and_patients() -> None:
    assert run() is True

    assert count("specialties") == 1
    assert count("doctors") == 1
    assert count("availability") == 5  # Monday to Friday
    assert count("patients") == 3
    with get_engine().connect() as connection:
        slot = connection.execute(
            text("SELECT s.name, s.default_slot_length_minutes FROM specialties s")
        ).one()
        window = connection.execute(
            text("SELECT DISTINCT start_time, end_time FROM availability")
        ).all()
        shared_phone = connection.execute(
            text(
                "SELECT count(*) FROM (SELECT phone FROM patients GROUP BY phone HAVING count(*) > 1) t"
            )
        ).scalar_one()
        triage = connection.execute(
            text("SELECT default_triage_specialty_id IS NOT NULL FROM clinic_settings")
        ).scalar_one()
    assert tuple(slot) == ("General Medicine", 20)
    assert [(str(a), str(b)) for a, b in window] == [("09:00:00", "12:00:00")]
    assert shared_phone == 1  # a family sharing one number
    assert triage is True


def test_running_the_dev_seed_twice_changes_nothing_the_second_time() -> None:
    assert run() is True
    before = {t: count(t) for t in ("users", "specialties", "doctors", "availability", "patients")}

    assert run() is False

    assert {t: count(t) for t in before} == before


def test_the_seeded_doctor_can_log_in(harness) -> None:  # type: ignore[no-untyped-def]
    run()

    response = harness.client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@clinic.test", "password": "dev doctor passphrase"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "doctor"
