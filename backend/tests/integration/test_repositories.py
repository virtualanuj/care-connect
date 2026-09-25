import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.adapters.postgres.audit_repository import PostgresAuditRepository
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.db.session import get_session_factory
from app.domain.errors import UserAlreadyExists
from app.domain.models import AuditAction, AuditEntry, Role, User

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
        session.rollback()


def make_user(email: str, role: Role = Role.DOCTOR, active: bool = True) -> User:
    return User(uuid.uuid4(), email, "Name", role, "hash", active)


def test_user_round_trip_by_id_and_case_insensitive_email(session: Session) -> None:
    repo = PostgresUserRepository(session)
    user = make_user("Dr.A@Clinic.test")

    repo.add(user)
    session.commit()

    assert repo.get(user.id) == user
    assert repo.get_by_email("dr.a@clinic.TEST") == user
    assert repo.get(uuid.uuid4()) is None
    assert repo.get_by_email("nobody@clinic.test") is None


def test_adding_a_duplicate_email_raises_domain_error_not_integrity_error(
    session: Session,
) -> None:
    repo = PostgresUserRepository(session)
    repo.add(make_user("dup@clinic.test"))
    session.commit()

    with pytest.raises(UserAlreadyExists):
        repo.add(make_user("DUP@clinic.test"))


def test_update_persists_changes(session: Session) -> None:
    repo = PostgresUserRepository(session)
    user = make_user("u@clinic.test")
    repo.add(user)
    session.commit()

    user.name, user.active, user.role, user.password_hash = (
        "New",
        False,
        Role.FRONT_DESK_ADMIN,
        "h2",
    )
    repo.update(user)
    session.commit()
    session.expire_all()

    assert repo.get(user.id) == user


def test_list_is_ordered_by_email_paginated_and_counts_total(session: Session) -> None:
    repo = PostgresUserRepository(session)
    for email in ["c@x.test", "a@x.test", "b@x.test"]:
        repo.add(make_user(email))
    session.commit()

    first = repo.list(page=1, page_size=2)
    second = repo.list(page=2, page_size=2)

    assert [u.email for u in first.items] == ["a@x.test", "b@x.test"]
    assert [u.email for u in second.items] == ["c@x.test"]
    assert first.total == second.total == 3


def test_audit_entries_are_listed_newest_first_and_filtered(session: Session) -> None:
    users = PostgresUserRepository(session)
    actor = make_user("actor@x.test", Role.FRONT_DESK_ADMIN)
    users.add(actor)
    audit = PostgresAuditRepository(session)
    base = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    target = uuid.uuid4()
    for offset, action in enumerate([AuditAction.USER_CREATED, AuditAction.PASSWORD_RESET]):
        audit.add(
            AuditEntry(
                uuid.uuid4(),
                action,
                actor.id,
                "user",
                target,
                base + timedelta(minutes=offset),
                reason=f"r{offset}",
            )
        )
    session.commit()

    everything = audit.list(None, page=1, page_size=10)
    only_created = audit.list(AuditAction.USER_CREATED, page=1, page_size=10)

    assert [e.action for e in everything.items] == [
        AuditAction.PASSWORD_RESET,
        AuditAction.USER_CREATED,
    ]
    assert everything.total == 2
    assert [e.reason for e in only_created.items] == ["r0"]
    assert everything.items[0].created_at == base + timedelta(minutes=1)
