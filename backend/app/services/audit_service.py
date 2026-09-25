import uuid
from collections.abc import Callable

from app.domain.models import AuditAction, AuditEntry, Page
from app.domain.ports import AuditRepository, Clock


class AuditService:
    """Append-only record of sensitive actions. Deliberately has no update or delete."""

    def __init__(
        self,
        repository: AuditRepository,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def record(
        self,
        action: AuditAction,
        actor_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        reason: str | None = None,
    ) -> None:
        self._repository.add(
            AuditEntry(
                id=self._new_id(),
                action=action,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                created_at=self._clock.now(),
                reason=reason,
            )
        )

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        return self._repository.list(action, page, page_size)
