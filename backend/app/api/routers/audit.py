from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, require_front_desk
from app.api.schemas.users import AuditLogEntryOut, AuditLogPage
from app.domain.models import AuditAction, User
from app.services.audit_service import AuditService

router = APIRouter(tags=["Audit"])


@router.get("/audit-log", response_model=AuditLogPage)
def list_audit_log(
    action: AuditAction | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    _: User = Depends(require_front_desk),
    audit: AuditService = Depends(get_audit_service),
) -> AuditLogPage:
    result = audit.list(action, page, page_size)
    return AuditLogPage(
        items=[AuditLogEntryOut.from_domain(e) for e in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )
