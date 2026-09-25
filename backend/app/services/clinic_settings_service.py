import uuid
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.errors import ValidationFailed
from app.domain.models import AuditAction, ClinicSettings, User
from app.domain.ports import ClinicSettingsRepository, SpecialtyRepository
from app.services.audit_service import AuditService
from app.services.user_service import require_front_desk

# Settings are a singleton, but audit entries need a target id.
SETTINGS_TARGET_ID = uuid.UUID(int=1)


class ClinicSettingsService:
    def __init__(
        self,
        repository: ClinicSettingsRepository,
        specialties: SpecialtyRepository,
        audit: AuditService,
    ) -> None:
        self._repository = repository
        self._specialties = specialties
        self._audit = audit

    def get(self) -> ClinicSettings:
        return self._repository.get()

    def update(self, actor: User, changes: dict[str, Any]) -> ClinicSettings:
        """Apply only the keys present in `changes` (snake_case ClinicSettings field names)."""
        require_front_desk(actor)
        current = self._repository.get()
        updated = ClinicSettings(**vars(current))
        for field, value in changes.items():
            setattr(updated, field, value)
        self._validate(updated)

        diffs = [
            f"{field}: {getattr(current, field)} -> {getattr(updated, field)}"
            for field in changes
            if getattr(current, field) != getattr(updated, field)
        ]
        if diffs:
            self._repository.save(updated)
            self._audit.record(
                AuditAction.CLINIC_SETTINGS_CHANGED,
                actor.id,
                "clinic_settings",
                SETTINGS_TARGET_ID,
                "; ".join(diffs),
            )
        return updated

    def _validate(self, settings: ClinicSettings) -> None:
        if settings.cancellation_cutoff_hours < 0:
            raise ValidationFailed("Cancellation cutoff cannot be negative")
        if settings.emergency_slots_per_doctor_per_day < 0:
            raise ValidationFailed("Emergency slots per day cannot be negative")
        if settings.follow_up_max_days < 1:
            raise ValidationFailed("Follow-up window must be at least 1 day")
        try:
            ZoneInfo(settings.clinic_timezone)
        except (ZoneInfoNotFoundError, ValueError, OSError) as error:
            raise ValidationFailed("Unknown time zone") from error
        triage_specialty = settings.default_triage_specialty_id
        if triage_specialty is not None and self._specialties.get(triage_specialty) is None:
            raise ValidationFailed("Default triage specialty does not exist")
