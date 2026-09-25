from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    current_user,
    get_clinic_settings_service,
    require_front_desk,
)
from app.api.schemas.reference import ClinicSettingsOut, ClinicSettingsUpdate
from app.domain.errors import ValidationFailed
from app.domain.models import User
from app.services.clinic_settings_service import ClinicSettingsService

router = APIRouter(tags=["ClinicSettings"])

_NULLABLE = {"default_triage_specialty_id"}


@router.get("/clinic-settings", response_model=ClinicSettingsOut)
def get_settings(
    _: User = Depends(current_user),
    service: ClinicSettingsService = Depends(get_clinic_settings_service),
) -> ClinicSettingsOut:
    return ClinicSettingsOut.from_domain(service.get())


@router.patch("/clinic-settings", response_model=ClinicSettingsOut)
def update_settings(
    body: ClinicSettingsUpdate,
    actor: User = Depends(require_front_desk),
    service: ClinicSettingsService = Depends(get_clinic_settings_service),
) -> ClinicSettingsOut:
    changes: dict[str, Any] = {name: getattr(body, name) for name in body.model_fields_set}
    if any(value is None and name not in _NULLABLE for name, value in changes.items()):
        raise ValidationFailed("Settings values cannot be null")
    return ClinicSettingsOut.from_domain(service.update(actor, changes))
