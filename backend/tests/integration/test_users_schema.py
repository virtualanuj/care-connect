import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine

pytestmark = pytest.mark.integration


def insert_user(connection, email: str) -> None:  # type: ignore[no-untyped-def]
    connection.execute(
        text(
            "INSERT INTO users (id, email, name, role, password_hash, active) "
            "VALUES (:id, :email, 'N', 'doctor', 'h', true)"
        ),
        {"id": uuid.uuid4(), "email": email},
    )


def test_email_is_unique_regardless_of_case() -> None:
    with get_engine().connect() as connection:
        insert_user(connection, "Dr.A@clinic.test")
        with pytest.raises(IntegrityError):
            insert_user(connection, "dr.a@CLINIC.test")
        connection.rollback()


def test_role_only_accepts_known_values() -> None:
    with get_engine().connect() as connection:
        with pytest.raises(Exception, match="user_role"):
            connection.execute(
                text(
                    "INSERT INTO users (id, email, name, role, password_hash, active) "
                    "VALUES (:id, 'x@y.test', 'N', 'patient', 'h', true)"
                ),
                {"id": uuid.uuid4()},
            )
        connection.rollback()


def test_audit_log_table_exists_with_expected_columns() -> None:
    with get_engine().connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'audit_log'"
                )
            )
        }
    assert columns == {
        "id",
        "action",
        "actor_id",
        "target_type",
        "target_id",
        "reason",
        "created_at",
    }
