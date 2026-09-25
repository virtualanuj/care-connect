"""users and audit_log

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

USER_ROLES = ("doctor", "front_desk_admin")
# All actions from docs/openapi.yaml `AuditAction`, so later milestones need no enum migration.
AUDIT_ACTIONS = (
    "force_cancel",
    "triage_override",
    "emergency_authorization",
    "user_created",
    "user_updated",
    "password_reset",
    "clinic_settings_changed",
)

user_role = postgresql.ENUM(*USER_ROLES, name="user_role", create_type=False)
audit_action = postgresql.ENUM(*AUDIT_ACTIONS, name="audit_action", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    audit_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("users_email_lower_key", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("audit_log_created_at_idx", "audit_log", ["created_at"])
    op.create_index("audit_log_action_idx", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("users")
    audit_action.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
