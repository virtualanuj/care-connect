import uuid
from datetime import date
from zoneinfo import ZoneInfo

from app.domain.errors import NotFound, ValidationFailed
from app.domain.models import Doctor, Slot
from app.domain.ports import (
    AppointmentQuery,
    AvailabilityRepository,
    ClinicSettingsRepository,
    Clock,
    DoctorRepository,
    SpecialtyRepository,
)
from app.domain.slots import TimeSlot, generate_day_slots, plan_day


class SlotService:
    """Bookable slots. Holds no rules of its own beyond composing the pure slot logic."""

    def __init__(
        self,
        specialties: SpecialtyRepository,
        doctors: DoctorRepository,
        availability: AvailabilityRepository,
        appointments: AppointmentQuery,
        settings: ClinicSettingsRepository,
        clock: Clock,
    ) -> None:
        self._specialties = specialties
        self._doctors = doctors
        self._availability = availability
        self._appointments = appointments
        self._settings = settings
        self._clock = clock

    def zone(self) -> ZoneInfo:
        return ZoneInfo(self._settings.get().clinic_timezone)

    def search(
        self,
        doctor_id: uuid.UUID | None,
        specialty_id: uuid.UUID | None,
        day: date,
        include_emergency: bool,
    ) -> list[Slot]:
        """Open slots for one doctor, or for every active doctor of a specialty.

        A specialty search returns *all* options (never auto-selects one) so front-desk can
        offer the patient a choice.
        """
        if (doctor_id is None) == (specialty_id is None):
            raise ValidationFailed("Provide exactly one of doctorId or specialtyId")

        if doctor_id is not None:
            doctor = self._doctors.get(doctor_id)
            if doctor is None:
                raise NotFound("Doctor not found")
            doctors = [doctor]
        else:
            assert specialty_id is not None
            if self._specialties.get(specialty_id) is None:
                raise NotFound("Specialty not found")
            doctors = self._doctors.list(specialty_id)

        slots = [
            slot for doctor in doctors for slot in self.day_slots(doctor, day, include_emergency)
        ]
        return sorted(slots, key=lambda s: (s.start_time, str(s.doctor_id)))

    def day_grid(self, doctor: Doctor, day: date) -> list[TimeSlot]:
        """The doctor's full slot grid for a date, ignoring bookings, holdback and the clock."""
        return generate_day_slots(
            self._availability.list_rules(doctor.id),
            self._availability.list_exceptions(doctor.id),
            day,
            doctor.slot_length_minutes,
            self.zone(),
        )

    def day_slots(self, doctor: Doctor, day: date, include_emergency: bool) -> list[Slot]:
        """The doctor's currently bookable slots on a clinic-local date."""
        if not doctor.active:
            return []
        settings = self._settings.get()
        grid = generate_day_slots(
            self._availability.list_rules(doctor.id),
            self._availability.list_exceptions(doctor.id),
            day,
            doctor.slot_length_minutes,
            ZoneInfo(settings.clinic_timezone),
        )
        if not grid:
            return []
        booked = [
            (span.start_time, span.end_time)
            for span in self._appointments.spans_between(
                doctor.id, grid[0].start_time, grid[-1].end_time
            )
        ]
        planned = plan_day(
            grid,
            settings.emergency_slots_per_doctor_per_day,
            booked,
            self._clock.now(),
        )
        return [
            Slot(doctor.id, doctor.specialty_id, p.start_time, p.end_time, p.is_emergency)
            for p in planned
            if include_emergency or not p.is_emergency
        ]
