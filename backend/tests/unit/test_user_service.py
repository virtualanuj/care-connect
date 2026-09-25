import uuid

import pytest

from app.domain.errors import Forbidden, NotFound, UserAlreadyExists, ValidationFailed
from app.domain.models import AuditAction, Role, User
from app.services.audit_service import AuditService
from app.services.user_service import UserService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import InMemoryAuditRepository, InMemoryUserRepository
from tests.fakes.security import FakePasswordHasher
from tests.unit.test_audit_service import START

GOOD_PASSWORD = "correct horse battery"


class Setup:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.audit_repo = InMemoryAuditRepository()
        self.hasher = FakePasswordHasher()
        self.service = UserService(
            self.users, self.hasher, AuditService(self.audit_repo, FixedClock(START))
        )
        self.admin = self.add_user("admin@clinic.test", Role.FRONT_DESK_ADMIN)
        self.doctor = self.add_user("doc@clinic.test", Role.DOCTOR)

    def add_user(self, email: str, role: Role, active: bool = True) -> User:
        user = User(uuid.uuid4(), email, "Name", role, self.hasher.hash(GOOD_PASSWORD), active)
        self.users.add(user)
        return user


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_create_hashes_password_lowercases_email_and_audits(s: Setup) -> None:
    user = s.service.create(s.admin, "New.Doc@Clinic.test", "New Doc", Role.DOCTOR, GOOD_PASSWORD)

    assert user.email == "new.doc@clinic.test"
    assert user.password_hash == s.hasher.hash(GOOD_PASSWORD)
    assert user.active is True
    (entry,) = s.audit_repo.entries
    assert (entry.action, entry.actor_id, entry.target_id) == (
        AuditAction.USER_CREATED,
        s.admin.id,
        user.id,
    )
    assert GOOD_PASSWORD not in (entry.reason or "")


def test_create_rejects_duplicate_email_case_insensitively(s: Setup) -> None:
    with pytest.raises(UserAlreadyExists):
        s.service.create(s.admin, "DOC@clinic.test", "Dup", Role.DOCTOR, GOOD_PASSWORD)


def test_create_rejects_password_shorter_than_12_characters(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.create(s.admin, "x@clinic.test", "X", Role.DOCTOR, "short-pass")


def test_only_front_desk_can_manage_users(s: Setup) -> None:
    with pytest.raises(Forbidden):
        s.service.create(s.doctor, "x@clinic.test", "X", Role.DOCTOR, GOOD_PASSWORD)
    with pytest.raises(Forbidden):
        s.service.list(s.doctor, 1, 10)
    with pytest.raises(Forbidden):
        s.service.update(s.doctor, s.admin.id, active=False)
    with pytest.raises(Forbidden):
        s.service.reset_password(s.doctor, s.admin.id, GOOD_PASSWORD)


def test_list_is_paginated_with_total(s: Setup) -> None:
    page = s.service.list(s.admin, page=1, page_size=1)

    assert len(page.items) == 1
    assert page.total == 2


def test_update_changes_role_name_and_active_and_audits_what_changed(s: Setup) -> None:
    updated = s.service.update(s.admin, s.doctor.id, name="Dr New", active=False)

    assert (updated.name, updated.active, updated.role) == ("Dr New", False, Role.DOCTOR)
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.USER_UPDATED
    assert entry.reason is not None and "active" in entry.reason and "name" in entry.reason


def test_update_unknown_user_is_not_found(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.service.update(s.admin, uuid.uuid4(), name="x")


def test_admin_cannot_deactivate_or_change_the_role_of_their_own_account(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.update(s.admin, s.admin.id, active=False)
    with pytest.raises(ValidationFailed):
        s.service.update(s.admin, s.admin.id, role=Role.DOCTOR)


def test_reset_password_replaces_hash_and_audits_without_the_password(s: Setup) -> None:
    s.service.reset_password(s.admin, s.doctor.id, "a brand new passphrase")

    stored = s.users.get(s.doctor.id)
    assert stored is not None
    assert stored.password_hash == s.hasher.hash("a brand new passphrase")
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.PASSWORD_RESET
    assert "passphrase" not in (entry.reason or "")


def test_reset_password_enforces_minimum_length(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.reset_password(s.admin, s.doctor.id, "tiny")
