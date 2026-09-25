import pytest
from alembic.config import Config

from alembic import command


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database to the latest schema once per test session."""
    command.upgrade(Config("alembic.ini"), "head")
