import contextlib
import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from app.domain.appointment_lifecycle import Action, next_status
from app.domain.errors import (
    AppointmentNotCompleted,
    CancellationWindowClosed,
    DomainError,
    EmergencyJustificationRequired,
    EmergencyNotAuthorized,
    FollowUpWindowExceeded,
    Forbidden,
    InvalidSlot,
    InvalidTransition,
    NotFound,
    SlotAlreadyBooked,
    ValidationFailed,
)
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    AuditAction,
    CancellationType,
    Doctor,
    EmergencyJustification,
    Page,
    Role,
    Slot,
    User,
)
from app.domain.ports import (
    AppointmentRepository,
    ClinicSettingsRepository,
    Clock,
    DoctorRepository,
    PatientRepository,
)
from app.services.audit_service import AuditService
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
        audit: AuditService,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._appointments = appointments
        self._doctors = doctors
        self._patients = patients
        self._slots = slots
        self._settings = settings
        self._clock = clock
        self._audit = audit
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

        slot = self._open_slot(doctor, start_time)
        emergency = (
            self._authorize_emergency(actor, emergency_justification, emergency_reason)
            if slot.is_emergency
            else None  # a justification sent for a regular slot is ignored
        )

        appointment = self._create(
            doctor,
            patient_id,
            slot,
            source=source,
            reported_symptoms=reported_symptoms,
            triage_result_id=triage_result_id,
            emergency=emergency,
            authorized_by=actor.id,
        )
        if emergency is not None:
            self._audit.record(
                AuditAction.EMERGENCY_AUTHORIZATION,
                actor.id,
                "appointment",
                appointment.id,
                emergency[1] or emergency[0].value,
            )
        return appointment

    @staticmethod
    def _authorize_emergency(
        actor: User,
        justification: EmergencyJustification | None,
        reason: str | None,
    ) -> tuple[EmergencyJustification, str | None]:
        """Decide whether the actor may draw on held-back emergency capacity.

        Front-desk judgment needs a stated reason and a front-desk actor. Authorization by an AI
        triage result arrives with the triage milestone (M6).
        """
        if justification is None:
            raise EmergencyJustificationRequired(
                "This slot is held for emergencies and needs a justification"
            )
        if justification == EmergencyJustification.FRONT_DESK_JUDGMENT:
            if actor.role != Role.FRONT_DESK_ADMIN:
                raise Forbidden("Only front-desk staff can authorize emergency capacity")
            if reason is None or not reason.strip():
                raise EmergencyJustificationRequired(
                    "Front-desk judgment needs a reason for using emergency capacity"
                )
            return justification, reason.strip()
        raise EmergencyNotAuthorized("The triage result does not authorize an emergency slot")

    def _open_slot(self, doctor: Doctor, start_time: datetime) -> Slot:
        """The currently open slot starting at `start_time`, or the reason there is none."""
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
        return slot

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

    def _create(
        self,
        doctor: Doctor,
        patient_id: uuid.UUID,
        slot: Slot,
        source: AppointmentSource,
        reported_symptoms: str | None = None,
        triage_result_id: uuid.UUID | None = None,
        follow_up_of_id: uuid.UUID | None = None,
        emergency: tuple[EmergencyJustification, str | None] | None = None,
        authorized_by: uuid.UUID | None = None,
    ) -> Appointment:
        appointment = Appointment(
            id=self._new_id(),
            doctor_id=doctor.id,
            patient_id=patient_id,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=AppointmentStatus.BOOKED,
            source=source,
            is_emergency_slot=emergency is not None,
            created_at=self._clock.now(),
            reported_symptoms=reported_symptoms,
            triage_result_id=triage_result_id,
            follow_up_of_id=follow_up_of_id,
            emergency_justification=emergency[0] if emergency else None,
            emergency_reason=emergency[1] if emergency else None,
            emergency_authorized_by=authorized_by if emergency else None,
        )
        self._appointments.add(appointment)
        return appointment

    # ---- reads ------------------------------------------------------------------------------

    def get(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        return self._load(actor, appointment_id)

    def _load(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        """Fetch an appointment the actor may see or act on (doctors: their own only)."""
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or own.id != appointment.doctor_id:
                raise Forbidden("You can only access your own appointments")
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

    # ---- lifecycle --------------------------------------------------------------------------

    def check_in(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        appointment = self._transition(actor, appointment_id, Action.CHECK_IN)
        appointment.checked_in_at = self._clock.now()
        self._appointments.update(appointment)
        return appointment

    def start_consultation(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        return self._transition(actor, appointment_id, Action.START_CONSULTATION)

    def complete(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        appointment = self._transition(actor, appointment_id, Action.COMPLETE)
        appointment.completed_at = self._clock.now()
        self._appointments.update(appointment)
        return appointment

    def mark_no_show(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        return self._transition(actor, appointment_id, Action.MARK_NO_SHOW)

    def _transition(self, actor: User, appointment_id: uuid.UUID, action: Action) -> Appointment:
        appointment = self._load(actor, appointment_id)
        appointment.status = next_status(appointment.status, action)
        self._appointments.update(appointment)
        return appointment

    # ---- cancellation -----------------------------------------------------------------------

    def _inside_cutoff(self, appointment: Appointment) -> bool:
        """True when the appointment starts within the cancellation cutoff (inclusive)."""
        cutoff = timedelta(hours=self._settings.get().cancellation_cutoff_hours)
        return appointment.start_time - self._clock.now() <= cutoff

    def _apply_cancellation(
        self,
        appointment: Appointment,
        actor: User,
        kind: CancellationType,
        reason: str | None = None,
    ) -> None:
        appointment.status = next_status(appointment.status, Action.CANCEL)
        appointment.cancelled_at = self._clock.now()
        appointment.cancelled_by = actor.id
        appointment.cancellation_type = kind
        appointment.cancel_reason = reason
        self._appointments.update(appointment)

    def cancel(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        """Standard cancellation: blocked inside the cutoff window (use force-cancel)."""
        appointment = self._load(actor, appointment_id)
        next_status(appointment.status, Action.CANCEL)  # InvalidTransition takes precedence
        if self._inside_cutoff(appointment):
            raise CancellationWindowClosed(
                "This appointment is inside the cancellation window; front-desk can force-cancel it"
            )
        self._apply_cancellation(appointment, actor, CancellationType.STANDARD)
        return appointment

    def force_cancel(self, actor: User, appointment_id: uuid.UUID, reason: str) -> Appointment:
        """Front-desk only: cancel regardless of the cutoff, with a reason, audited."""
        if actor.role != Role.FRONT_DESK_ADMIN:
            raise Forbidden("Only front-desk staff can force-cancel an appointment")
        if not reason.strip():
            raise ValidationFailed("A reason is required to force-cancel")
        appointment = self._load(actor, appointment_id)
        self._apply_cancellation(appointment, actor, CancellationType.FORCE, reason.strip())
        self._audit.record(
            AuditAction.FORCE_CANCEL, actor.id, "appointment", appointment.id, reason.strip()
        )
        return appointment

    # ---- reschedule -------------------------------------------------------------------------

    def reschedule(
        self, actor: User, appointment_id: uuid.UUID, new_start_time: datetime
    ) -> Appointment:
        """Move a booked appointment to another regular slot of the same doctor.

        Atomic: if the new slot cannot be booked the original stays booked. The old appointment
        is cancelled *first* so that it no longer holds its slot when the new one is inserted.
        """
        original = self._load(actor, appointment_id)
        if original.status != AppointmentStatus.BOOKED:
            raise InvalidTransition("Only a booked appointment can be rescheduled")
        if self._inside_cutoff(original):
            raise CancellationWindowClosed(
                "This appointment is inside the cancellation window and cannot be rescheduled"
            )
        doctor = self._doctors.get(original.doctor_id)
        if doctor is None:
            raise NotFound("Doctor not found")
        slot = self._open_slot(doctor, new_start_time)
        if slot.is_emergency:
            raise InvalidSlot("Held-back emergency slots cannot be used to reschedule")

        snapshot = Appointment(**vars(original))
        self._apply_cancellation(original, actor, CancellationType.RESCHEDULED)
        try:
            new = self._create(
                doctor,
                original.patient_id,
                slot,
                source=original.source,
                reported_symptoms=original.reported_symptoms,
                triage_result_id=original.triage_result_id,
            )
        except DomainError:
            # Restore the original; never mask the real error (the request's database
            # transaction is rolled back anyway).
            with contextlib.suppress(Exception):
                self._appointments.update(snapshot)
            raise
        original.rescheduled_to_id = new.id
        self._appointments.update(original)
        return new

    # ---- follow-up --------------------------------------------------------------------------

    def book_follow_up(
        self, actor: User, original_id: uuid.UUID, start_time: datetime
    ) -> Appointment:
        """Book a follow-up for a completed visit, within the follow-up window of the root visit."""
        original = self._load(actor, original_id)
        if original.status != AppointmentStatus.COMPLETED:
            raise AppointmentNotCompleted("A follow-up can only be booked from a completed visit")

        root = original
        while root.follow_up_of_id is not None:
            parent = self._appointments.get(root.follow_up_of_id)
            if parent is None:
                break
            root = parent
        window = timedelta(days=self._settings.get().follow_up_max_days)
        if start_time > root.start_time + window:
            raise FollowUpWindowExceeded("The follow-up is too long after the original visit")

        doctor = self._doctors.get(original.doctor_id)
        if doctor is None:
            raise NotFound("Doctor not found")
        slot = self._open_slot(doctor, start_time)
        if slot.is_emergency:
            raise InvalidSlot("Follow-ups cannot use held-back emergency slots")
        return self._create(
            doctor,
            original.patient_id,
            slot,
            source=AppointmentSource.SCHEDULED,
            follow_up_of_id=original.id,
        )
