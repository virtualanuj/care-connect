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
        connection.execute(text("TRUNCATE audit_log, users CASCADE"))
