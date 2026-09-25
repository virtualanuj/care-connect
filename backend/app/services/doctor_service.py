import uuid
from collections.abc import Callable

from app.domain.errors import (
    AvailabilityConflictsWithAppointments,
    Forbidden,
    NotFound,
    ValidationFailed,
)
from app.domain.models import Doctor, Role, Specialty, User
from app.domain.ports import (
    AppointmentQuery,
    Clock,
    DoctorRepository,
    SpecialtyRepository,
    UserRepository,
)
from app.services.user_service import require_front_desk

MIN_SLOT_MINUTES = 5


def _validate_slot_length(minutes: int) -> None:
    if minutes < MIN_SLOT_MINUTES:
        raise ValidationFailed(f"Slot length must be at least {MIN_SLOT_MINUTES} minutes")


class DoctorService:
    """Specialties and doctor profiles."""

    def __init__(
        self,
        users: UserRepository,
        specialties: SpecialtyRepository,
        doctors: DoctorRepository,
        appointments: AppointmentQuery,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._users = users
        self._specialties = specialties
        self._doctors = doctors
        self._appointments = appointments
        self._clock = clock
        self._new_id = new_id

    # ---- specialties ------------------------------------------------------------------------

    def list_specialties(self) -> list[Specialty]:
        return self._specialties.list()

    def create_specialty(
        self, actor: User, name: str, default_slot_length_minutes: int
    ) -> Specialty:
        require_front_desk(actor)
        _validate_slot_length(default_slot_length_minutes)
        specialty = Specialty(self._new_id(), name.strip(), default_slot_length_minutes)
        self._specialties.add(specialty)
        return specialty

    def update_specialty(
        self,
        actor: User,
        specialty_id: uuid.UUID,
        name: str | None = None,
        default_slot_length_minutes: int | None = None,
    ) -> Specialty:
        require_front_desk(actor)
        specialty = self._specialties.get(specialty_id)
        if specialty is None:
            raise NotFound("Specialty not found")
        if name is not None:
            specialty.name = name.strip()
        if default_slot_length_minutes is not None:
            _validate_slot_length(default_slot_length_minutes)
            specialty.default_slot_length_minutes = default_slot_length_minutes
        self._specialties.update(specialty)
        return specialty

    # ---- doctors ----------------------------------------------------------------------------

    def list_doctors(self, specialty_id: uuid.UUID | None) -> list[Doctor]:
        return self._doctors.list(specialty_id)

    def get_doctor(self, doctor_id: uuid.UUID) -> Doctor:
        doctor = self._doctors.get(doctor_id)
        if doctor is None:
            raise NotFound("Doctor not found")
        return doctor

    def create_doctor(
        self,
        actor: User,
        user_id: uuid.UUID,
        name: str,
        specialty_id: uuid.UUID,
        slot_length_minutes: int | None,
    ) -> Doctor:
        require_front_desk(actor)
        user = self._users.get(user_id)
        if user is None or user.role != Role.DOCTOR:
            raise ValidationFailed("userId must belong to an existing doctor account")
        specialty = self._specialties.get(specialty_id)
        if specialty is None:
            raise ValidationFailed("Specialty does not exist")
        slot_length = (
            specialty.default_slot_length_minutes
            if slot_length_minutes is None
            else slot_length_minutes
        )
        _validate_slot_length(slot_length)
        doctor = Doctor(self._new_id(), user_id, name.strip(), specialty_id, slot_length)
        self._doctors.add(doctor)
        return doctor

    def update_doctor(
        self,
        actor: User,
        doctor_id: uuid.UUID,
        name: str | None = None,
        specialty_id: uuid.UUID | None = None,
        slot_length_minutes: int | None = None,
        active: bool | None = None,
    ) -> Doctor:
        doctor = self.get_doctor(doctor_id)
        self.require_can_edit(actor, doctor)
        if active is not None and actor.role != Role.FRONT_DESK_ADMIN:
            raise Forbidden("Only front-desk staff can activate or deactivate a doctor")

        if name is not None:
            doctor.name = name.strip()
        if specialty_id is not None:
            if self._specialties.get(specialty_id) is None:
                raise ValidationFailed("Specialty does not exist")
            doctor.specialty_id = specialty_id
        if slot_length_minutes is not None:
            _validate_slot_length(slot_length_minutes)
            doctor.slot_length_minutes = slot_length_minutes
        if active is not None and active != doctor.active:
            if not active and self._appointments.upcoming_spans(doctor.id, self._clock.now()):
                raise AvailabilityConflictsWithAppointments(
                    "Doctor has upcoming appointments; cancel or reschedule them first"
                )
            doctor.active = active
        self._doctors.update(doctor)
        return doctor

    @staticmethod
    def require_can_edit(actor: User, doctor: Doctor) -> None:
        """Front-desk may edit any doctor; a doctor may edit only their own profile."""
        if actor.role == Role.FRONT_DESK_ADMIN:
            return
        if actor.role == Role.DOCTOR and doctor.user_id == actor.id:
            return
        raise Forbidden("You can only edit your own doctor profile")
