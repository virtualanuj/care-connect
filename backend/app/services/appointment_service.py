import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from app.domain.errors import (
    EmergencyJustificationRequired,
    EmergencyNotAuthorized,
    Forbidden,
    InvalidSlot,
    NotFound,
    SlotAlreadyBooked,
)
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Doctor,
    EmergencyJustification,
    Page,
    Role,
    User,
)
from app.domain.ports import (
    AppointmentRepository,
    ClinicSettingsRepository,
    Clock,
    DoctorRepository,
    PatientRepository,
)
from app.services.slot_service import SlotService


class AppointmentService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        doctors: DoctorRepository,
        patients: PatientRepository,
        slots: SlotService,
        settings: ClinicSettingsRepository,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._appointments = appointments
        self._doctors = doctors
        self._patients = patients
        self._slots = slots
        self._settings = settings
        self._clock = clock
        self._new_id = new_id

    # ---- booking ----------------------------------------------------------------------------

    def book(
        self,
        actor: User,
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        start_time: datetime,
        reported_symptoms: str | None = None,
        source: AppointmentSource = AppointmentSource.SCHEDULED,
        emergency_justification: EmergencyJustification | None = None,
        emergency_reason: str | None = None,
        triage_result_id: uuid.UUID | None = None,
    ) -> Appointment:
        """Book a real, currently open slot. Overlaps are finally rejected by the database."""
        if self._patients.get(patient_id) is None:
            raise NotFound("Patient not found")
        doctor = self._doctors.get(doctor_id)
        if doctor is None:
            raise NotFound("Doctor not found")
        if not doctor.active:
            raise InvalidSlot("That doctor is not taking appointments")
        if actor.role == Role.DOCTOR and doctor.user_id != actor.id:
            raise Forbidden("Doctors can only book appointments with themselves")

        local_day = start_time.astimezone(self._slots.zone()).date()
        slot = next(
            (
                s
                for s in self._slots.day_slots(doctor, local_day, include_emergency=True)
                if s.start_time == start_time
            ),
            None,
        )
        if slot is None:
            raise self._why_unavailable(doctor, local_day, start_time)

        if slot.is_emergency:
            # Full authorization (triage result or front-desk judgment) arrives in M5/M6.
            if emergency_justification is None:
                raise EmergencyJustificationRequired(
                    "This slot is held for emergencies and needs a justification"
                )
            raise EmergencyNotAuthorized("Emergency booking is not available yet")

        appointment = Appointment(
            id=self._new_id(),
            doctor_id=doctor.id,
            patient_id=patient_id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=AppointmentStatus.BOOKED,
            source=source,
            is_emergency_slot=False,
            created_at=self._clock.now(),
            reported_symptoms=reported_symptoms,
        )
        self._appointments.add(appointment)
        return appointment

    def _why_unavailable(
        self, doctor: Doctor, day: date, start_time: datetime
    ) -> SlotAlreadyBooked | InvalidSlot:
        """Explain why `start_time` is not open: already taken, or simply not a slot."""
        on_grid = any(g.start_time == start_time for g in self._slots.day_grid(doctor, day))
        taken = self._appointments.spans_between(
            doctor.id, start_time, start_time + timedelta(minutes=1)
        )
        if on_grid and taken:
            return SlotAlreadyBooked("That time is already booked for this doctor")
        return InvalidSlot("That time is not an available slot")

    # ---- reads ------------------------------------------------------------------------------

    def get(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or own.id != appointment.doctor_id:
                raise Forbidden("You can only view your own appointments")
        return appointment

    def list(
        self,
        actor: User,
        doctor_id: uuid.UUID | None,
        patient_id: uuid.UUID | None,
        day: date | None,
        status: AppointmentStatus | None,
        page: int,
        page_size: int,
    ) -> Page[Appointment]:
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None:
                return Page(items=[], total=0)
            if doctor_id is not None and doctor_id != own.id:
                raise Forbidden("You can only view your own appointments")
            doctor_id = own.id

        starts_from = starts_before = None
        if day is not None:
            zone = self._slots.zone()
            starts_from = datetime.combine(day, time.min, tzinfo=zone)
            starts_before = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
        return self._appointments.list(
            doctor_id, patient_id, starts_from, starts_before, status, page, page_size
        )
