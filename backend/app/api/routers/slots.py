import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_slot_service
from app.api.schemas.appointments import SlotOut
from app.domain.models import User
from app.services.slot_service import SlotService

router = APIRouter(tags=["Slots"])


@router.get("/slots", response_model=list[SlotOut])
def search_slots(
    day: date = Query(alias="date"),
    doctor_id: uuid.UUID | None = Query(None, alias="doctorId"),
    specialty_id: uuid.UUID | None = Query(None, alias="specialtyId"),
    include_emergency: bool = Query(False, alias="includeEmergency"),
    _: User = Depends(current_user),
    service: SlotService = Depends(get_slot_service),
) -> list[SlotOut]:
    slots = service.search(doctor_id, specialty_id, day, include_emergency)
    return [SlotOut.from_domain(s) for s in slots]
