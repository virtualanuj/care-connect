import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_patient_service
from app.api.schemas.reference import (
    MedicalHistoryEntryCreate,
    MedicalHistoryEntryOut,
    PatientCreate,
    PatientOut,
    PatientPage,
    PatientUpdate,
)
from app.domain.errors import ValidationFailed
from app.domain.models import User
from app.services.patient_service import PatientService

router = APIRouter(tags=["Patients"])


@router.get("/patients", response_model=PatientPage)
def search_patients(
    phone: str | None = None,
    name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    _: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> PatientPage:
    result = service.search(phone, name, page, page_size)
    return PatientPage.from_domain(result, page, page_size)


@router.post("/patients", response_model=PatientOut, status_code=201)
def register_patient(
    body: PatientCreate,
    _: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> PatientOut:
    return PatientOut.from_domain(service.register(body.name, body.phone, body.dob, body.email))


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: uuid.UUID,
    _: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> PatientOut:
    return PatientOut.from_domain(service.get(patient_id))


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: uuid.UUID,
    body: PatientUpdate,
    _: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> PatientOut:
    changes: dict[str, Any] = {name: getattr(body, name) for name in body.model_fields_set}
    if changes.get("name", 0) is None or changes.get("phone", 0) is None:
        raise ValidationFailed("name and phone cannot be null")
    return PatientOut.from_domain(service.update(patient_id, changes))


@router.get("/patients/{patient_id}/medical-history", response_model=list[MedicalHistoryEntryOut])
def list_history(
    patient_id: uuid.UUID,
    _: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> list[MedicalHistoryEntryOut]:
    return [MedicalHistoryEntryOut.from_domain(e) for e in service.list_history(patient_id)]


@router.post(
    "/patients/{patient_id}/medical-history", response_model=MedicalHistoryEntryOut, status_code=201
)
def add_history(
    patient_id: uuid.UUID,
    body: MedicalHistoryEntryCreate,
    actor: User = Depends(current_user),
    service: PatientService = Depends(get_patient_service),
) -> MedicalHistoryEntryOut:
    entry = service.add_history(
        actor, patient_id, body.kind, body.description, body.amends_entry_id
    )
    return MedicalHistoryEntryOut.from_domain(entry)
