import uuid
from datetime import date, datetime

from pydantic import AwareDatetime, Field

from app.api.schemas.base import CamelModel
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    CancellationType,
    DailyQueue,
    EmergencyJustification,
    Page,
    QueueItem,
    Slot,
)


class SlotOut(CamelModel):
    doctor_id: uuid.UUID
    specialty_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    is_emergency: bool

    @classmethod
    def from_domain(cls, slot: Slot) -> "SlotOut":
        return cls(
            doctor_id=slot.doctor_id,
            specialty_id=slot.specialty_id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            is_emergency=slot.is_emergency,
        )


class AppointmentOut(CamelModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    source: AppointmentSource
    is_emergency_slot: bool
    emergency_justification: EmergencyJustification | None
    emergency_reason: str | None
    emergency_authorized_by: uuid.UUID | None
    reported_symptoms: str | None
    triage_result_id: uuid.UUID | None
    follow_up_of_appointment_id: uuid.UUID | None
    created_at: datetime
    checked_in_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: uuid.UUID | None
    cancellation_type: CancellationType | None
    cancel_reason: str | None
    rescheduled_to_id: uuid.UUID | None

    @classmethod
    def from_domain(cls, a: Appointment) -> "AppointmentOut":
        return cls(
            id=a.id,
            doctor_id=a.doctor_id,
            patient_id=a.patient_id,
            start_time=a.start_time,
            end_time=a.end_time,
            status=a.status,
            source=a.source,
            is_emergency_slot=a.is_emergency_slot,
            emergency_justification=a.emergency_justification,
            emergency_reason=a.emergency_reason,
            emergency_authorized_by=a.emergency_authorized_by,
            reported_symptoms=a.reported_symptoms,
            triage_result_id=a.triage_result_id,
            follow_up_of_appointment_id=a.follow_up_of_id,
            created_at=a.created_at,
            checked_in_at=a.checked_in_at,
            completed_at=a.completed_at,
            cancelled_at=a.cancelled_at,
            cancelled_by=a.cancelled_by,
            cancellation_type=a.cancellation_type,
            cancel_reason=a.cancel_reason,
            rescheduled_to_id=a.rescheduled_to_id,
        )


class AppointmentCreate(CamelModel):
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_time: AwareDatetime
    source: AppointmentSource = AppointmentSource.SCHEDULED
    reported_symptoms: str | None = Field(default=None, max_length=4000)
    triage_result_id: uuid.UUID | None = None
    emergency_justification: EmergencyJustification | None = None
    emergency_reason: str | None = None


class RescheduleRequest(CamelModel):
    new_start_time: AwareDatetime


class ForceCancelRequest(CamelModel):
    reason: str = Field(min_length=1)


class FollowUpRequest(CamelModel):
    start_time: AwareDatetime


class AppointmentPage(CamelModel):
    items: list[AppointmentOut]
    page: int
    page_size: int
    total: int

    @classmethod
    def from_domain(cls, result: Page[Appointment], page: int, page_size: int) -> "AppointmentPage":
        return cls(
            items=[AppointmentOut.from_domain(a) for a in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
        )


__all__ = [
    "AppointmentCreate",
    "DailyQueueOut",
    "AppointmentOut",
    "AppointmentPage",
    "FollowUpRequest",
    "ForceCancelRequest",
    "RescheduleRequest",
    "SlotOut",
]


class QueueItemOut(AppointmentOut):
    patient_name: str
    doctor_name: str


class DailyQueueOut(CamelModel):
    date: date
    booked: list[QueueItemOut]
    checked_in: list[QueueItemOut]
    in_progress: list[QueueItemOut]
    completed: list[QueueItemOut]
    no_shows: list[QueueItemOut]
    cancelled: list[QueueItemOut]

    @classmethod
    def from_domain(cls, queue: DailyQueue) -> "DailyQueueOut":
        def items(rows: list[QueueItem]) -> list[QueueItemOut]:
            return [
                QueueItemOut(
                    **AppointmentOut.from_domain(r.appointment).model_dump(),
                    patient_name=r.patient_name,
                    doctor_name=r.doctor_name,
                )
                for r in rows
            ]

        return cls(
            date=queue.day,
            booked=items(queue.booked),
            checked_in=items(queue.checked_in),
            in_progress=items(queue.in_progress),
            completed=items(queue.completed),
            no_shows=items(queue.no_shows),
            cancelled=items(queue.cancelled),
        )
