import uuid
from datetime import UTC, datetime, timedelta

from app.domain.models import AuditAction
from app.services.audit_service import AuditService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.repositories import InMemoryAuditRepository

START = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def make() -> tuple[AuditService, InMemoryAuditRepository, FixedClock]:
    clock = FixedClock(START)
    repo = InMemoryAuditRepository()
    return AuditService(repo, clock), repo, clock


def test_record_stores_actor_target_reason_and_clock_time() -> None:
    service, repo, _ = make()
    actor, target = uuid.uuid4(), uuid.uuid4()

    service.record(AuditAction.USER_CREATED, actor, "user", target, reason="role=doctor")

    (entry,) = repo.entries
    assert (entry.action, entry.actor_id, entry.target_type, entry.target_id) == (
        AuditAction.USER_CREATED,
        actor,
        "user",
        target,
    )
    assert entry.reason == "role=doctor"
    assert entry.created_at == START


def test_list_returns_newest_first_and_filters_by_action() -> None:
    service, _, clock = make()
    actor = uuid.uuid4()
    service.record(AuditAction.USER_CREATED, actor, "user", uuid.uuid4())
    clock.advance(timedelta(minutes=1))
    service.record(AuditAction.PASSWORD_RESET, actor, "user", uuid.uuid4())

    everything = service.list(None, page=1, page_size=10)
    resets = service.list(AuditAction.PASSWORD_RESET, page=1, page_size=10)

    assert [e.action for e in everything.items] == [
        AuditAction.PASSWORD_RESET,
        AuditAction.USER_CREATED,
    ]
    assert everything.total == 2
    assert [e.action for e in resets.items] == [AuditAction.PASSWORD_RESET]


def test_audit_service_exposes_no_way_to_change_or_delete_entries() -> None:
    public = {name for name in dir(AuditService) if not name.startswith("_")}

    assert public == {"record", "list"}
