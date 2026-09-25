"""appointments with DB-enforced no-overlap constraints

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

STATUSES = ("booked", "checked_in", "in_consultation", "completed", "no_show", "cancelled")
SOURCES = ("scheduled", "walk_in")
CANCELLATION_TYPES = ("standard", "force", "rescheduled")
JUSTIFICATIONS = ("triage", "front_desk_judgment")

status_enum = postgresql.ENUM(*STATUSES, name="appointment_status", create_type=False)
source_enum = postgresql.ENUM(*SOURCES, name="appointment_source", create_type=False)
cancellation_enum = postgresql.ENUM(
    *CANCELLATION_TYPES, name="cancellation_type", create_type=False
)
justification_enum = postgresql.ENUM(
    *JUSTIFICATIONS, name="emergency_justification", create_type=False
)

# Cancelled and no-show appointments release their slot; everything else holds it.
ACTIVE = "status NOT IN ('cancelled', 'no_show')"


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (status_enum, source_enum, cancellation_enum, justification_enum):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doctor_id", sa.Uuid(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="booked"),
        sa.Column("source", source_enum, nullable=False, server_default="scheduled"),
        sa.Column("is_emergency_slot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emergency_justification", justification_enum, nullable=True),
        sa.Column("emergency_reason", sa.Text(), nullable=True),
        sa.Column("emergency_authorized_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reported_symptoms", sa.Text(), nullable=True),
        # FK to ai_triage_results is added in M6 when that table exists.
        sa.Column("triage_result_id", sa.Uuid(), nullable=True),
        sa.Column("follow_up_of_id", sa.Uuid(), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancellation_type", cancellation_enum, nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("rescheduled_to_id", sa.Uuid(), sa.ForeignKey("appointments.id"), nullable=True),
        sa.CheckConstraint("end_time > start_time", name="appointments_end_after_start"),
    )

    # The core guarantee: real overlaps (not just equal start times) are rejected by the
    # database itself, so it holds under concurrent requests.
    op.execute(
        f"ALTER TABLE appointments ADD CONSTRAINT appt_no_doctor_overlap "
        f"EXCLUDE USING gist (doctor_id WITH =, tstzrange(start_time, end_time) WITH &&) "
        f"WHERE ({ACTIVE})"
    )
    op.execute(
        f"ALTER TABLE appointments ADD CONSTRAINT appt_no_patient_overlap "
        f"EXCLUDE USING gist (patient_id WITH =, tstzrange(start_time, end_time) WITH &&) "
        f"WHERE ({ACTIVE})"
    )
    op.create_index("appointments_doctor_start_idx", "appointments", ["doctor_id", "start_time"])
    op.create_index("appointments_patient_start_idx", "appointments", ["patient_id", "start_time"])
    op.create_index("appointments_start_idx", "appointments", ["start_time"])


def downgrade() -> None:
    op.drop_table("appointments")
    bind = op.get_bind()
    for enum in (justification_enum, cancellation_enum, source_enum, status_enum):
        enum.drop(bind, checkfirst=True)
