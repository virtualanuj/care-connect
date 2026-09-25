"""Pre-visit summaries and visit notes

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_visit_summaries",
        sa.Column("appointment_id", sa.Uuid(), sa.ForeignKey("appointments.id"), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("inputs_hash", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "visit_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "appointment_id",
            sa.Uuid(),
            sa.ForeignKey("appointments.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("doctor_notes", sa.Text(), nullable=False),
        sa.Column("ai_draft_summary", sa.Text(), nullable=True),
        sa.Column("ai_draft_disclaimer", sa.Text(), nullable=True),
        sa.Column("final_summary", sa.Text(), nullable=True),
        sa.Column("finalized_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Finalizing always records who, when and what.
        sa.CheckConstraint(
            "(final_summary IS NULL) = (finalized_at IS NULL) "
            "AND (final_summary IS NULL) = (finalized_by IS NULL)",
            name="visit_note_final_complete",
        ),
    )


def downgrade() -> None:
    op.drop_table("visit_notes")
    op.drop_table("pre_visit_summaries")
