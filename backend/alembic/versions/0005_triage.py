"""AI triage results (patient-keyed, append-only history with staff overrides)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

URGENCIES = ("emergency", "urgent", "routine")
SOURCES = ("model", "red_flag")

urgency_enum = postgresql.ENUM(*URGENCIES, name="urgency", create_type=False)
source_enum = postgresql.ENUM(*SOURCES, name="triage_source", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (urgency_enum, source_enum):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "ai_triage_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("reported_symptoms", sa.Text(), nullable=False),
        sa.Column("urgency", urgency_enum, nullable=False),
        sa.Column(
            "suggested_specialty_id", sa.Uuid(), sa.ForeignKey("specialties.id"), nullable=False
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("overridden_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overridden_urgency", urgency_enum, nullable=True),
        sa.Column(
            "overridden_specialty_id", sa.Uuid(), sa.ForeignKey("specialties.id"), nullable=True
        ),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="triage_conf"),
        # An override always comes with who, when and why.
        sa.CheckConstraint(
            "(overridden_urgency IS NULL) = (overridden_by IS NULL) "
            "AND (overridden_urgency IS NULL) = (override_reason IS NULL) "
            "AND (overridden_urgency IS NULL) = (overridden_at IS NULL)",
            name="triage_override_complete",
        ),
    )
    op.create_index("triage_patient_created_idx", "ai_triage_results", ["patient_id", "created_at"])
    op.create_foreign_key(
        "appointments_triage_result_fk",
        "appointments",
        "ai_triage_results",
        ["triage_result_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("appointments_triage_result_fk", "appointments", type_="foreignkey")
    op.drop_table("ai_triage_results")
    bind = op.get_bind()
    source_enum.drop(bind, checkfirst=True)
    urgency_enum.drop(bind, checkfirst=True)
