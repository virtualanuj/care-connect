from decimal import Decimal

from sqlalchemy.orm import Session

from app.adapters.postgres.models import ClinicSettingsRow
from app.domain.models import ClinicSettings


class PostgresClinicSettingsRepository:
    """The single settings row (id = 1) is created by the migration."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _row(self) -> ClinicSettingsRow:
        row = self._session.get(ClinicSettingsRow, 1)
        if row is None:
            raise RuntimeError("clinic_settings row is missing; run `alembic upgrade head`")
        return row

    def get(self) -> ClinicSettings:
        row = self._row()
        return ClinicSettings(
            cancellation_cutoff_hours=float(row.cancellation_cutoff_hours),
            emergency_slots_per_doctor_per_day=row.emergency_slots_per_doctor_per_day,
            follow_up_max_days=row.follow_up_max_days,
            clinic_timezone=row.clinic_timezone,
            default_triage_specialty_id=row.default_triage_specialty_id,
        )

    def save(self, settings: ClinicSettings) -> None:
        row = self._row()
        row.cancellation_cutoff_hours = Decimal(str(settings.cancellation_cutoff_hours))
        row.emergency_slots_per_doctor_per_day = settings.emergency_slots_per_doctor_per_day
        row.follow_up_max_days = settings.follow_up_max_days
        row.clinic_timezone = settings.clinic_timezone
        row.default_triage_specialty_id = settings.default_triage_specialty_id
        self._session.flush()
