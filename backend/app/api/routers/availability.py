import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response

from app.api.deps import current_user, get_availability_service
from app.api.schemas.reference import (
    AvailabilityCreate,
    AvailabilityExceptionCreate,
    AvailabilityExceptionOut,
    AvailabilityExceptionUpdate,
    AvailabilityOut,
    AvailabilityUpdate,
)
from app.domain.errors import ValidationFailed
from app.domain.models import User
from app.services.availability_service import AvailabilityService

router = APIRouter(tags=["Availability"])


@router.get("/doctors/{doctor_id}/availability", response_model=list[AvailabilityOut])
def list_rules(
    doctor_id: uuid.UUID,
    _: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityOut]:
    return [AvailabilityOut.from_domain(r) for r in service.list_rules(doctor_id)]


@router.post("/doctors/{doctor_id}/availability", response_model=AvailabilityOut, status_code=201)
def add_rule(
    doctor_id: uuid.UUID,
    body: AvailabilityCreate,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityOut:
    rule = service.add_rule(actor, doctor_id, body.day_of_week, body.start_time, body.end_time)
    return AvailabilityOut.from_domain(rule)


@router.patch("/doctors/{doctor_id}/availability/{availability_id}", response_model=AvailabilityOut)
def update_rule(
    doctor_id: uuid.UUID,
    availability_id: uuid.UUID,
    body: AvailabilityUpdate,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityOut:
    rule = service.update_rule(
        actor,
        doctor_id,
        availability_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    return AvailabilityOut.from_domain(rule)


@router.delete("/doctors/{doctor_id}/availability/{availability_id}", status_code=204)
def delete_rule(
    doctor_id: uuid.UUID,
    availability_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> Response:
    service.delete_rule(actor, doctor_id, availability_id)
    return Response(status_code=204)


@router.get(
    "/doctors/{doctor_id}/availability-exceptions", response_model=list[AvailabilityExceptionOut]
)
def list_exceptions(
    doctor_id: uuid.UUID,
    _: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityExceptionOut]:
    return [AvailabilityExceptionOut.from_domain(e) for e in service.list_exceptions(doctor_id)]


@router.post(
    "/doctors/{doctor_id}/availability-exceptions",
    response_model=AvailabilityExceptionOut,
    status_code=201,
)
def add_exception(
    doctor_id: uuid.UUID,
    body: AvailabilityExceptionCreate,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityExceptionOut:
    exception = service.add_exception(
        actor, doctor_id, body.date, body.type, body.start_time, body.end_time
    )
    return AvailabilityExceptionOut.from_domain(exception)


@router.patch(
    "/doctors/{doctor_id}/availability-exceptions/{exception_id}",
    response_model=AvailabilityExceptionOut,
)
def update_exception(
    doctor_id: uuid.UUID,
    exception_id: uuid.UUID,
    body: AvailabilityExceptionUpdate,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityExceptionOut:
    changes: dict[str, Any] = {name: getattr(body, name) for name in body.model_fields_set}
    if changes.get("date", 0) is None or changes.get("type", 0) is None:
        raise ValidationFailed("date and type cannot be null")
    exception = service.update_exception(actor, doctor_id, exception_id, **changes)
    return AvailabilityExceptionOut.from_domain(exception)


@router.delete("/doctors/{doctor_id}/availability-exceptions/{exception_id}", status_code=204)
def delete_exception(
    doctor_id: uuid.UUID,
    exception_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: AvailabilityService = Depends(get_availability_service),
) -> Response:
    service.delete_exception(actor, doctor_id, exception_id)
    return Response(status_code=204)
