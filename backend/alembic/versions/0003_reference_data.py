"""reference data: clinic settings, specialties, doctors, patients, history, availability

Revision ID: 0003
Revises: 0002
"""

import os

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
EXCEPTION_TYPES = ("unavailable", "extra_hours")
HISTORY_KINDS = ("entry", "amendment")

day_of_week = postgresql.ENUM(*DAYS, name="day_of_week", create_type=False)
exception_type = postgresql.ENUM(
    *EXCEPTION_TYPES, name="availability_exception_type", create_type=False
)
history_kind = postgresql.ENUM(*HISTORY_KINDS, name="medical_history_kind", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (day_of_week, exception_type, history_kind):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "specialties",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("default_slot_length_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("default_slot_length_minutes >= 5", name="specialties_slot_min"),
    )
    op.create_index(
        "specialties_name_lower_key", "specialties", [sa.text("lower(name)")], unique=True
    )

    op.create_table(
        "clinic_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True, server_default="1"),
        sa.Column("cancellation_cutoff_hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("emergency_slots_per_doctor_per_day", sa.Integer(), nullable=False),
        sa.Column("follow_up_max_days", sa.Integer(), nullable=False),
        sa.Column("clinic_timezone", sa.Text(), nullable=False),
        sa.Column(
            "default_triage_specialty_id",
            sa.Uuid(),
            sa.ForeignKey("specialties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("id = 1", name="clinic_settings_singleton"),
        sa.CheckConstraint("cancellation_cutoff_hours >= 0", name="clinic_settings_cutoff"),
        sa.CheckConstraint(
            "emergency_slots_per_doctor_per_day >= 0", name="clinic_settings_emergency"
        ),
        sa.CheckConstraint("follow_up_max_days >= 1", name="clinic_settings_follow_up"),
    )
    op.execute(
        sa.text(
            "INSERT INTO clinic_settings (id, cancellation_cutoff_hours, "
            "emergency_slots_per_doctor_per_day, follow_up_max_days, clinic_timezone) "
            "VALUES (1, 2, 1, 30, :tz)"
        ).bindparams(tz=os.environ.get("SEED_CLINIC_TIMEZONE", "UTC"))
    )

    op.create_table(
        "doctors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("specialty_id", sa.Uuid(), sa.ForeignKey("specialties.id"), nullable=False),
        sa.Column("slot_length_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("slot_length_minutes >= 5", name="doctors_slot_min"),
    )
    op.create_index("doctors_specialty_idx", "doctors", ["specialty_id"])

    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("phone", "name_normalized", name="patients_phone_name_key"),
    )
    op.create_index("patients_name_normalized_idx", "patients", ["name_normalized"])

    op.create_table(
        "medical_history_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("kind", history_kind, nullable=False),
        sa.Column(
            "amends_entry_id", sa.Uuid(), sa.ForeignKey("medical_history_entries.id"), nullable=True
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint(
            "(kind = 'amendment') = (amends_entry_id IS NOT NULL)", name="history_amendment_link"
        ),
    )
    op.create_index("history_patient_idx", "medical_history_entries", ["patient_id", "recorded_at"])

    op.create_table(
        "availability",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doctor_id", sa.Uuid(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("day_of_week", day_of_week, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="availability_start_before_end"),
    )
    op.create_index("availability_doctor_idx", "availability", ["doctor_id"])

    op.create_table(
        "availability_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doctor_id", sa.Uuid(), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("type", exception_type, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.CheckConstraint(
            "(start_time IS NULL) = (end_time IS NULL)", name="exception_times_together"
        ),
        sa.CheckConstraint(
            "start_time IS NULL OR start_time < end_time", name="exception_start_before_end"
        ),
        sa.CheckConstraint(
            "type = 'unavailable' OR start_time IS NOT NULL", name="extra_hours_needs_times"
        ),
    )
    op.create_index("exceptions_doctor_date_idx", "availability_exceptions", ["doctor_id", "date"])


def downgrade() -> None:
    for table in (
        "availability_exceptions",
        "availability",
        "medical_history_entries",
        "patients",
        "doctors",
        "clinic_settings",
        "specialties",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for enum in (history_kind, exception_type, day_of_week):
        enum.drop(bind, checkfirst=True)
