import uuid

from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_doctor_service, require_front_desk
from app.api.schemas.reference import SpecialtyCreate, SpecialtyOut, SpecialtyUpdate
from app.domain.models import User
from app.services.doctor_service import DoctorService

router = APIRouter(tags=["Specialties"])


@router.get("/specialties", response_model=list[SpecialtyOut])
def list_specialties(
    _: User = Depends(current_user), service: DoctorService = Depends(get_doctor_service)
) -> list[SpecialtyOut]:
    return [SpecialtyOut.from_domain(s) for s in service.list_specialties()]


@router.post("/specialties", response_model=SpecialtyOut, status_code=201)
def create_specialty(
    body: SpecialtyCreate,
    actor: User = Depends(require_front_desk),
    service: DoctorService = Depends(get_doctor_service),
) -> SpecialtyOut:
    return SpecialtyOut.from_domain(
        service.create_specialty(actor, body.name, body.default_slot_length_minutes)
    )


@router.patch("/specialties/{specialty_id}", response_model=SpecialtyOut)
def update_specialty(
    specialty_id: uuid.UUID,
    body: SpecialtyUpdate,
    actor: User = Depends(require_front_desk),
    service: DoctorService = Depends(get_doctor_service),
) -> SpecialtyOut:
    return SpecialtyOut.from_domain(
        service.update_specialty(
            actor,
            specialty_id,
            name=body.name,
            default_slot_length_minutes=body.default_slot_length_minutes,
        )
    )
