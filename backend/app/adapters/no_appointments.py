import uuid
from datetime import datetime

from app.domain.models import AppointmentSpan


class NoAppointments:
    """AppointmentQuery for milestones before the appointments table exists (replaced in M3)."""

    def upcoming_spans(self, doctor_id: uuid.UUID, after: datetime) -> list[AppointmentSpan]:
        return []
