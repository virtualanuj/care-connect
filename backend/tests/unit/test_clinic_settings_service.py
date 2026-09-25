import uuid

import pytest

from app.domain.errors import Forbidden, ValidationFailed
from app.domain.models import AuditAction, Role, Specialty, User
from app.services.audit_service import AuditService
from app.services.clinic_settings_service import ClinicSettingsService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import (
    InMemoryAuditRepository,
    InMemoryClinicSettingsRepository,
    InMemorySpecialtyRepository,
)
from tests.unit.test_audit_service import START


class Setup:
    def __init__(self) -> None:
        self.repo = InMemoryClinicSettingsRepository()
        self.specialties = InMemorySpecialtyRepository()
        self.audit_repo = InMemoryAuditRepository()
        self.service = ClinicSettingsService(
            self.repo, self.specialties, AuditService(self.audit_repo, FixedClock(START))
        )
        self.admin = User(uuid.uuid4(), "a@x.test", "A", Role.FRONT_DESK_ADMIN, "h")
        self.doctor = User(uuid.uuid4(), "d@x.test", "D", Role.DOCTOR, "h")


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_get_returns_the_current_settings(s: Setup) -> None:
    settings = s.service.get()

    assert (settings.cancellation_cutoff_hours, settings.follow_up_max_days) == (2.0, 30)


def test_only_front_desk_can_update(s: Setup) -> None:
    with pytest.raises(Forbidden):
        s.service.update(s.doctor, {"cancellation_cutoff_hours": 3})


def test_update_persists_and_audits_before_and_after_of_changed_fields_only(s: Setup) -> None:
    updated = s.service.update(s.admin, {"cancellation_cutoff_hours": 4, "follow_up_max_days": 30})

    assert updated.cancellation_cutoff_hours == 4
    assert s.repo.get().cancellation_cutoff_hours == 4
    (entry,) = s.audit_repo.entries
    assert entry.action == AuditAction.CLINIC_SETTINGS_CHANGED
    assert entry.reason == "cancellation_cutoff_hours: 2.0 -> 4"
    assert entry.actor_id == s.admin.id


def test_an_update_that_changes_nothing_writes_no_audit_entry(s: Setup) -> None:
    s.service.update(s.admin, {"emergency_slots_per_doctor_per_day": 1})

    assert s.audit_repo.entries == []


@pytest.mark.parametrize(
    "changes",
    [
        {"cancellation_cutoff_hours": -0.5},
        {"emergency_slots_per_doctor_per_day": -1},
        {"follow_up_max_days": 0},
        {"clinic_timezone": "Mars/Olympus_Mons"},
        {"clinic_timezone": ""},
    ],
)
def test_out_of_range_values_are_rejected_and_nothing_is_saved(
    s: Setup, changes: dict[str, object]
) -> None:
    with pytest.raises(ValidationFailed):
        s.service.update(s.admin, changes)

    assert s.repo.get().cancellation_cutoff_hours == 2.0
    assert s.audit_repo.entries == []


@pytest.mark.parametrize(
    "changes",
    [
        {"cancellation_cutoff_hours": 0},
        {"emergency_slots_per_doctor_per_day": 0},
        {"follow_up_max_days": 1},
        {"clinic_timezone": "Asia/Kolkata"},
    ],
)
def test_boundary_values_are_accepted(s: Setup, changes: dict[str, object]) -> None:
    s.service.update(s.admin, changes)


def test_default_triage_specialty_must_exist_and_can_be_cleared(s: Setup) -> None:
    with pytest.raises(ValidationFailed):
        s.service.update(s.admin, {"default_triage_specialty_id": uuid.uuid4()})

    specialty = Specialty(uuid.uuid4(), "General Medicine", 20)
    s.specialties.add(specialty)
    assert (
        s.service.update(
            s.admin, {"default_triage_specialty_id": specialty.id}
        ).default_triage_specialty_id
        == specialty.id
    )

    assert (
        s.service.update(s.admin, {"default_triage_specialty_id": None}).default_triage_specialty_id
        is None
    )
