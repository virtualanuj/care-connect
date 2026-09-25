from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.models import (
    Appointment,
    AppointmentStatus,
    DailyQueue,
    QueueItem,
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

_MISSING_NAME = "—"
_ALL = 10_000  # one clinic, one day: never paginate the dashboard


class QueueService:
    """The front-desk daily dashboard: a day's appointments bucketed by status."""

    def __init__(
        self,
        appointments: AppointmentRepository,
        patients: PatientRepository,
        doctors: DoctorRepository,
        settings: ClinicSettingsRepository,
        clock: Clock,
    ) -> None:
        self._appointments = appointments
        self._patients = patients
        self._doctors = doctors
        self._settings = settings
        self._clock = clock

    def get(self, actor: User, day: date | None) -> DailyQueue:
        zone = ZoneInfo(self._settings.get().clinic_timezone)
        day = day or self._clock.now().astimezone(zone).date()

        doctor_id = None
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None:
                return self._bucket(day, [], {}, {})
            doctor_id = own.id

        starts_from = datetime.combine(day, time.min, tzinfo=zone)
        starts_before = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
        appointments = self._appointments.list(
            doctor_id, None, starts_from, starts_before, None, 1, _ALL
        ).items

        # Two batched lookups regardless of how many appointments there are (no N+1).
        patient_names = {
            pid: p.name
            for pid, p in self._patients.get_many({a.patient_id for a in appointments}).items()
        }
        doctor_names = {d.id: d.name for d in self._doctors.list(None)}
        return self._bucket(day, appointments, patient_names, doctor_names)

    @staticmethod
    def _bucket(
        day: date,
        appointments: list[Appointment],
        patient_names: dict,  # type: ignore[type-arg]
        doctor_names: dict,  # type: ignore[type-arg]
    ) -> DailyQueue:
        def in_status(*statuses: AppointmentStatus) -> list[QueueItem]:
            return [
                QueueItem(
                    a,
                    patient_names.get(a.patient_id, _MISSING_NAME),
                    doctor_names.get(a.doctor_id, _MISSING_NAME),
                )
                for a in sorted(appointments, key=lambda a: a.start_time)
                if a.status in statuses
            ]

        S = AppointmentStatus
        return DailyQueue(
            day=day,
            booked=in_status(S.BOOKED),
            checked_in=in_status(S.CHECKED_IN),
            in_progress=in_status(S.IN_CONSULTATION),
            completed=in_status(S.COMPLETED),
            no_shows=in_status(S.NO_SHOW),
            cancelled=in_status(S.CANCELLED),
        )
