import uuid

from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_triage_service
from app.api.schemas.triage import OverrideRequest, TriageRequest, TriageResultOut
from app.domain.models import User
from app.services.triage_service import TriageService

router = APIRouter(tags=["Triage"])


@router.post("/patients/{patient_id}/triage", response_model=TriageResultOut, status_code=201)
def run_triage(
    patient_id: uuid.UUID,
    body: TriageRequest,
    actor: User = Depends(current_user),
    service: TriageService = Depends(get_triage_service),
) -> TriageResultOut:
    return TriageResultOut.from_domain(service.run(actor, patient_id, body.reported_symptoms))


@router.get("/patients/{patient_id}/triage", response_model=list[TriageResultOut])
def list_triage(
    patient_id: uuid.UUID,
    _: User = Depends(current_user),
    service: TriageService = Depends(get_triage_service),
) -> list[TriageResultOut]:
    return [TriageResultOut.from_domain(r) for r in service.for_patient(patient_id)]


@router.get("/appointments/{appointment_id}/triage", response_model=TriageResultOut)
def appointment_triage(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: TriageService = Depends(get_triage_service),
) -> TriageResultOut:
    return TriageResultOut.from_domain(service.for_appointment(actor, appointment_id))


@router.patch("/triage-results/{triage_result_id}/override", response_model=TriageResultOut)
def override_triage(
    triage_result_id: uuid.UUID,
    body: OverrideRequest,
    actor: User = Depends(current_user),
    service: TriageService = Depends(get_triage_service),
) -> TriageResultOut:
    result = service.override(
        actor,
        triage_result_id,
        body.overridden_urgency,
        body.override_reason,
        body.overridden_specialty_id,
    )
    return TriageResultOut.from_domain(result)
