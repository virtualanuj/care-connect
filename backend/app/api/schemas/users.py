import uuid

from pydantic import Field

from app.api.schemas.base import CamelModel
from app.api.schemas.types import Email
from app.domain.models import AuditAction, AuditEntry, Page, Role, User
from app.services.user_service import MIN_PASSWORD_LENGTH


class UserOut(CamelModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role
    active: bool

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        return cls(id=user.id, email=user.email, name=user.name, role=user.role, active=user.active)


class UserCreate(CamelModel):
    email: Email
    name: str = Field(min_length=1)
    role: Role
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class UserUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1)
    role: Role | None = None
    active: bool | None = None


class ResetPasswordRequest(CamelModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class UserPage(CamelModel):
    items: list[UserOut]
    page: int
    page_size: int
    total: int

    @classmethod
    def from_domain(cls, result: Page[User], page: int, page_size: int) -> "UserPage":
        return cls(
            items=[UserOut.from_domain(u) for u in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
        )


class AuditLogEntryOut(CamelModel):
    id: uuid.UUID
    action: AuditAction
    actor_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: str | None
    created_at: str

    @classmethod
    def from_domain(cls, entry: AuditEntry) -> "AuditLogEntryOut":
        return cls(
            id=entry.id,
            action=entry.action,
            actor_id=entry.actor_id,
            target_type=entry.target_type,
            target_id=entry.target_id,
            reason=entry.reason,
            created_at=entry.created_at.isoformat(),
        )


class AuditLogPage(CamelModel):
    items: list[AuditLogEntryOut]
    page: int
    page_size: int
    total: int
