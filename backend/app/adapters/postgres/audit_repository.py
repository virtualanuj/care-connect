from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.postgres.models import AuditLogRow
from app.domain.models import AuditAction, AuditEntry, Page


def _to_domain(row: AuditLogRow) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        action=row.action,
        actor_id=row.actor_id,
        target_type=row.target_type,
        target_id=row.target_id,
        created_at=row.created_at,
        reason=row.reason,
    )


class PostgresAuditRepository:
    """Insert and read only: the audit log has no update or delete path."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditLogRow(
                id=entry.id,
                action=entry.action,
                actor_id=entry.actor_id,
                target_type=entry.target_type,
                target_id=entry.target_id,
                reason=entry.reason,
                created_at=entry.created_at,
            )
        )
        self._session.flush()

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        query = select(AuditLogRow)
        count = select(func.count()).select_from(AuditLogRow)
        if action is not None:
            query = query.where(AuditLogRow.action == action)
            count = count.where(AuditLogRow.action == action)
        rows = self._session.scalars(
            query.order_by(AuditLogRow.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return Page(items=[_to_domain(r) for r in rows], total=self._session.scalar(count) or 0)
