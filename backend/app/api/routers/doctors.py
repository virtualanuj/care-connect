import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_doctor_service
from app.api.schemas.reference import DoctorCreate, DoctorOut, DoctorUpdate
from app.domain.models import User
from app.services.doctor_service import DoctorService

router = APIRouter(tags=["Doctors"])


@router.get("/doctors", response_model=list[DoctorOut])
def list_doctors(
    specialty_id: uuid.UUID | None = Query(None, alias="specialtyId"),
    _: User = Depends(current_user),
    service: DoctorService = Depends(get_doctor_service),
) -> list[DoctorOut]:
    return [DoctorOut.from_domain(d) for d in service.list_doctors(specialty_id)]


@router.post("/doctors", response_model=DoctorOut, status_code=201)
def create_doctor(
    body: DoctorCreate,
    actor: User = Depends(current_user),
    service: DoctorService = Depends(get_doctor_service),
) -> DoctorOut:
    doctor = service.create_doctor(
        actor, body.user_id, body.name, body.specialty_id, body.slot_length_minutes
    )
    return DoctorOut.from_domain(doctor)


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(
    doctor_id: uuid.UUID,
    _: User = Depends(current_user),
    service: DoctorService = Depends(get_doctor_service),
) -> DoctorOut:
    return DoctorOut.from_domain(service.get_doctor(doctor_id))


@router.patch("/doctors/{doctor_id}", response_model=DoctorOut)
def update_doctor(
    doctor_id: uuid.UUID,
    body: DoctorUpdate,
    actor: User = Depends(current_user),
    service: DoctorService = Depends(get_doctor_service),
) -> DoctorOut:
    doctor = service.update_doctor(
        actor,
        doctor_id,
        name=body.name,
        specialty_id=body.specialty_id,
        slot_length_minutes=body.slot_length_minutes,
        active=body.active,
    )
    return DoctorOut.from_domain(doctor)
