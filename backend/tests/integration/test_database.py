import pytest
from sqlalchemy import text

from app.db.session import get_engine

pytestmark = pytest.mark.integration


def test_database_is_reachable() -> None:
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_btree_gist_extension_is_installed_by_migrations() -> None:
    with get_engine().connect() as connection:
        found = connection.execute(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'btree_gist'")
        ).scalar_one()
    assert found == 1
