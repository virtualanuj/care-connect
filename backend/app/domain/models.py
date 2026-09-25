"""Domain entities and enums (framework-free)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Role(StrEnum):
    DOCTOR = "doctor"
    FRONT_DESK_ADMIN = "front_desk_admin"


class AuditAction(StrEnum):
    FORCE_CANCEL = "force_cancel"
    TRIAGE_OVERRIDE = "triage_override"
    EMERGENCY_AUTHORIZATION = "emergency_authorization"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    PASSWORD_RESET = "password_reset"
    CLINIC_SETTINGS_CHANGED = "clinic_settings_changed"


@dataclass
class User:
    id: uuid.UUID
    email: str
    name: str
    role: Role
    password_hash: str
    active: bool = True


@dataclass(frozen=True)
class AuditEntry:
    id: uuid.UUID
    action: AuditAction
    actor_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    created_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class Page[T]:
    items: list[T] = field(default_factory=list)
    total: int = 0
