import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_appointment_service
from app.api.schemas.appointments import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentPage,
    FollowUpRequest,
    ForceCancelRequest,
    RescheduleRequest,
)
from app.domain.models import AppointmentStatus, User
from app.services.appointment_service import AppointmentService

router = APIRouter(tags=["Appointments"])


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
def book_appointment(
    body: AppointmentCreate,
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentOut:
    appointment = service.book(
        actor,
        body.doctor_id,
        body.patient_id,
        body.start_time,
        reported_symptoms=body.reported_symptoms,
        source=body.source,
        emergency_justification=body.emergency_justification,
        emergency_reason=body.emergency_reason,
        triage_result_id=body.triage_result_id,
    )
    return AppointmentOut.from_domain(appointment)


@router.get("/appointments", response_model=AppointmentPage)
def list_appointments(
    doctor_id: uuid.UUID | None = Query(None, alias="doctorId"),
    patient_id: uuid.UUID | None = Query(None, alias="patientId"),
    day: date | None = Query(None, alias="date"),
    status: AppointmentStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentPage:
    result = service.list(actor, doctor_id, patient_id, day, status, page, page_size)
    return AppointmentPage.from_domain(result, page, page_size)


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: uuid.UUID,
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentOut:
    return AppointmentOut.from_domain(service.get(actor, appointment_id))


def _lifecycle(action: str, path: str, summary: str) -> None:
    """Register a POST /appointments/{id}/<path> endpoint that calls the named service method."""

    def endpoint(
        appointment_id: uuid.UUID,
        actor: User = Depends(current_user),
        service: AppointmentService = Depends(get_appointment_service),
    ) -> AppointmentOut:
        return AppointmentOut.from_domain(getattr(service, action)(actor, appointment_id))

    endpoint.__name__ = action
    router.post(
        f"/appointments/{{appointment_id}}/{path}", response_model=AppointmentOut, summary=summary
    )(endpoint)


_lifecycle("check_in", "check-in", "Transition Booked → Checked-in")
_lifecycle("start_consultation", "start-consultation", "Transition Checked-in → In-consultation")
_lifecycle("complete", "complete", "Transition In-consultation → Completed")
_lifecycle("mark_no_show", "no-show", "Mark Booked or Checked-in → No-show")
_lifecycle("cancel", "cancel", "Cancel an appointment (standard)")


@router.post("/appointments/{appointment_id}/force-cancel", response_model=AppointmentOut)
def force_cancel(
    appointment_id: uuid.UUID,
    body: ForceCancelRequest,
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentOut:
    return AppointmentOut.from_domain(service.force_cancel(actor, appointment_id, body.reason))


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(
    appointment_id: uuid.UUID,
    body: RescheduleRequest,
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentOut:
    return AppointmentOut.from_domain(
        service.reschedule(actor, appointment_id, body.new_start_time)
    )


@router.post(
    "/appointments/{appointment_id}/follow-up", response_model=AppointmentOut, status_code=201
)
def follow_up(
    appointment_id: uuid.UUID,
    body: FollowUpRequest,
    actor: User = Depends(current_user),
    service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentOut:
    return AppointmentOut.from_domain(
        service.book_follow_up(actor, appointment_id, body.start_time)
    )
