"""Fixtures for suites that use the real Postgres (integration and contract)."""

from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database to the latest schema once per test session."""
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    """Every test leaves the application tables empty."""
    yield
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE audit_log, medical_history_entries, availability_exceptions, "
                "availability, doctors, patients, specialties, users CASCADE"
            )
        )
        # TRUNCATE ... CASCADE also empties clinic_settings (it references specialties).
        connection.execute(
            text(
                "INSERT INTO clinic_settings (id, cancellation_cutoff_hours, "
                "emergency_slots_per_doctor_per_day, follow_up_max_days, clinic_timezone) "
                "VALUES (1, 2, 1, 30, 'UTC') ON CONFLICT (id) DO UPDATE SET "
                "cancellation_cutoff_hours = 2, emergency_slots_per_doctor_per_day = 1, "
                "follow_up_max_days = 30, clinic_timezone = 'UTC', "
                "default_triage_specialty_id = NULL"
            )
        )
