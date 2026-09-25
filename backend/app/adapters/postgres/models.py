import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import AuditAction, Role


def _enum(enum_class: type, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        create_type=False,  # created by Alembic migrations
        values_callable=lambda e: [member.value for member in e],
    )


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    action: Mapped[AuditAction] = mapped_column(_enum(AuditAction, "audit_action"))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
