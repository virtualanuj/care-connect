"""Idempotent seed data. Run with: uv run python -m app.db.seed"""

import sys
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.adapters.clock import SystemClock
from app.adapters.postgres.appointment_repository import PostgresAppointmentRepository
from app.adapters.postgres.availability_repository import PostgresAvailabilityRepository
from app.adapters.postgres.clinic_settings_repository import PostgresClinicSettingsRepository
from app.adapters.postgres.doctor_repository import PostgresDoctorRepository
from app.adapters.postgres.patient_repository import PostgresPatientRepository
from app.adapters.postgres.specialty_repository import PostgresSpecialtyRepository
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.config import get_settings
from app.db.session import get_session_factory
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Availability,
    CancellationType,
    DayOfWeek,
    Doctor,
    Patient,
    Role,
    Specialty,
    User,
)
from app.domain.patient_identity import normalize_name, normalize_phone
from app.domain.ports import Clock, PasswordHasher
from app.services.user_service import validate_password


def seed_admin(session: Session, hasher: PasswordHasher, email: str, password: str) -> bool:
    """Create the initial front-desk admin if absent. Returns True if a user was created.

    An existing user is never modified (so re-running cannot reset a changed password).
    """
    validate_password(password)
    users = PostgresUserRepository(session)
    if users.get_by_email(email) is not None:
        return False
    users.add(
        User(
            id=uuid.uuid4(),
            email=email.strip().lower(),
            name="Front Desk Admin",
            role=Role.FRONT_DESK_ADMIN,
            password_hash=hasher.hash(password),
        )
    )
    return True


DEV_DOCTOR_EMAIL = "doctor@clinic.test"
DEV_DOCTOR_PASSWORD = "dev doctor passphrase"  # development only; never used outside ENV=dev
_DEV_PATIENTS = [
    ("Asha Rao", "+91 98765 43210"),
    ("Kiran Rao", "+91 98765 43210"),  # same family, same number
    ("Meera Iyer", "+91 91234 56789"),
]


def seed_dev_data(session: Session, hasher: PasswordHasher, clock: Clock) -> bool:
    """Sample reference data for local development. Idempotent; returns True if anything changed."""
    created = False
    users = PostgresUserRepository(session)
    specialties = PostgresSpecialtyRepository(session)
    doctors = PostgresDoctorRepository(session)
    availability = PostgresAvailabilityRepository(session)
    patients = PostgresPatientRepository(session)
    settings_repo = PostgresClinicSettingsRepository(session)

    specialty = next((s for s in specialties.list() if s.name == "General Medicine"), None)
    if specialty is None:
        specialty = Specialty(uuid.uuid4(), "General Medicine", 20)
        specialties.add(specialty)
        created = True

    user = users.get_by_email(DEV_DOCTOR_EMAIL)
    if user is None:
        user = User(
            uuid.uuid4(),
            DEV_DOCTOR_EMAIL,
            "Dev Doctor",
            Role.DOCTOR,
            hasher.hash(DEV_DOCTOR_PASSWORD),
        )
        users.add(user)
        created = True

    doctor = doctors.get_by_user_id(user.id)
    if doctor is None:
        doctor = Doctor(uuid.uuid4(), user.id, "Dr. Dev Doctor", specialty.id, 20)
        doctors.add(doctor)
        created = True

    if not availability.list_rules(doctor.id):
        for day in list(DayOfWeek)[:5]:  # Monday to Friday
            availability.add_rule(Availability(uuid.uuid4(), doctor.id, day, time(9), time(12)))
        created = True

    for name, raw_phone in _DEV_PATIENTS:
        phone = normalize_phone(raw_phone, "IN")
        existing = patients.find(phone, normalize_name(name), 1, 10).items
        if not any(normalize_name(p.name) == normalize_name(name) for p in existing):
            patients.add(Patient(uuid.uuid4(), name, phone, clock.now()))
            created = True

    settings = settings_repo.get()
    if settings.default_triage_specialty_id is None:
        settings.default_triage_specialty_id = specialty.id
        settings_repo.save(settings)
        created = True
    return created


_DEMO_SPECIALTIES = [("General Medicine", 20), ("Cardiology", 30), ("Paediatrics", 20)]
_DEMO_DOCTORS = [
    ("Dr. Anita Sharma", 0),
    ("Dr. Rahul Verma", 0),
    ("Dr. Priya Nair", 1),
    ("Dr. Sanjay Gupta", 1),
    ("Dr. Farah Khan", 2),
    ("Dr. Vikram Singh", 2),
]
_FIRST_NAMES = [
    "Aarav", "Diya", "Ishaan", "Kavya", "Rohan", "Sneha", "Arjun", "Tara", "Neel", "Anika",
]  # fmt: skip
_LAST_NAMES = ["Kapoor", "Menon", "Bose", "Patel"]
# One appointment per status today, each with its own doctor and patient.
_DEMO_QUEUE = [
    (AppointmentStatus.BOOKED, 15),
    (AppointmentStatus.CHECKED_IN, 9),
    (AppointmentStatus.IN_CONSULTATION, 9),
    (AppointmentStatus.COMPLETED, 9),
    (AppointmentStatus.CANCELLED, 10),
    (AppointmentStatus.NO_SHOW, 10),
]


def seed_demo_data(session: Session, hasher: PasswordHasher, clock: Clock) -> bool:
    """A demo clinic: 3 specialties, 6 doctors, 40 patients and today's queue in every status.

    Development only. Idempotent: does nothing once the demo doctors exist.
    """
    users = PostgresUserRepository(session)
    if users.get_by_email("demo.doctor1@clinic.test") is not None:
        return False
    specialties = PostgresSpecialtyRepository(session)
    doctors = PostgresDoctorRepository(session)
    availability = PostgresAvailabilityRepository(session)
    patients = PostgresPatientRepository(session)
    appointments = PostgresAppointmentRepository(session)
    zone = ZoneInfo(PostgresClinicSettingsRepository(session).get().clinic_timezone)

    catalogue = []
    for name, minutes in _DEMO_SPECIALTIES:
        specialty = next((s for s in specialties.list() if s.name == name), None)
        if specialty is None:
            specialty = Specialty(uuid.uuid4(), name, minutes)
            specialties.add(specialty)
        catalogue.append(specialty)

    demo_doctors: list[Doctor] = []
    for index, (name, specialty_index) in enumerate(_DEMO_DOCTORS, start=1):
        user = User(
            uuid.uuid4(),
            f"demo.doctor{index}@clinic.test",
            name.removeprefix("Dr. "),
            Role.DOCTOR,
            hasher.hash(DEV_DOCTOR_PASSWORD),
        )
        users.add(user)
        specialty = catalogue[specialty_index]
        doctor = Doctor(
            uuid.uuid4(), user.id, name, specialty.id, specialty.default_slot_length_minutes
        )
        doctors.add(doctor)
        for day in list(DayOfWeek)[:5]:
            availability.add_rule(Availability(uuid.uuid4(), doctor.id, day, time(9), time(13)))
        demo_doctors.append(doctor)

    demo_patients: list[Patient] = []
    for number in range(40):
        first = _FIRST_NAMES[number % len(_FIRST_NAMES)]
        last = _LAST_NAMES[number // len(_FIRST_NAMES)]
        patient = Patient(
            uuid.uuid4(), f"{first} {last}", normalize_phone(f"+91 90000 {number:05d}", "IN"),
            clock.now(),
        )  # fmt: skip
        patients.add(patient)
        demo_patients.append(patient)

    today = clock.now().astimezone(zone).date()
    for index, (status, hour) in enumerate(_DEMO_QUEUE):
        doctor, patient = demo_doctors[index], demo_patients[index]
        start = datetime.combine(today, time(hour), tzinfo=zone)
        slot = timedelta(minutes=doctor.slot_length_minutes)
        appointment = Appointment(
            uuid.uuid4(), doctor.id, patient.id, start, start + slot, status,
            AppointmentSource.SCHEDULED, False, clock.now(),
        )  # fmt: skip
        if status in (
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.IN_CONSULTATION,
            AppointmentStatus.COMPLETED,
        ):
            appointment.checked_in_at = clock.now()
        if status == AppointmentStatus.COMPLETED:
            appointment.completed_at = clock.now()
        if status == AppointmentStatus.CANCELLED:
            appointment.cancelled_at = clock.now()
            appointment.cancellation_type = CancellationType.STANDARD
            appointment.cancel_reason = "Patient called to cancel"
        appointments.add(appointment)
    # A walk-in already waiting with the first doctor.
    walk_in_start = datetime.combine(today, time(11), tzinfo=zone)
    walk_in = Appointment(
        uuid.uuid4(), demo_doctors[0].id, demo_patients[6].id, walk_in_start,
        walk_in_start + timedelta(minutes=demo_doctors[0].slot_length_minutes),
        AppointmentStatus.CHECKED_IN, AppointmentSource.WALK_IN, False, clock.now(),
    )  # fmt: skip
    walk_in.checked_in_at = clock.now()
    appointments.add(walk_in)
    return True


def main() -> int:
    settings = get_settings()
    if not settings.seed_admin_email or not settings.seed_admin_password:
        print("Set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD to seed the admin user.")
        return 1
    with get_session_factory()() as session:
        created = seed_admin(
            session, Argon2PasswordHasher(), settings.seed_admin_email, settings.seed_admin_password
        )
        print("Admin user created." if created else "Admin user already exists; nothing changed.")
        if settings.env == "dev":
            changed = seed_dev_data(session, Argon2PasswordHasher(), SystemClock())
            print("Dev data created." if changed else "Dev data already present.")
            if "--demo" in sys.argv[1:]:
                demo = seed_demo_data(session, Argon2PasswordHasher(), SystemClock())
                print("Demo data created." if demo else "Demo data already present.")
        session.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
