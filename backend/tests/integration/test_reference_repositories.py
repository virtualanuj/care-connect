import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.adapters.postgres.availability_repository import PostgresAvailabilityRepository
from app.adapters.postgres.clinic_settings_repository import PostgresClinicSettingsRepository
from app.adapters.postgres.doctor_repository import PostgresDoctorRepository
from app.adapters.postgres.history_repository import PostgresMedicalHistoryRepository
from app.adapters.postgres.patient_repository import PostgresPatientRepository
from app.adapters.postgres.specialty_repository import PostgresSpecialtyRepository
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.db.session import get_session_factory
from app.domain.errors import DoctorAlreadyExists, PatientAlreadyExists, SpecialtyAlreadyExists
from app.domain.models import (
    Availability,
    AvailabilityException,
    ClinicSettings,
    DayOfWeek,
    Doctor,
    ExceptionType,
    HistoryKind,
    MedicalHistoryEntry,
    Patient,
    Role,
    Specialty,
    User,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
        session.rollback()


def make_doctor(session: Session, email: str = "d@x.test") -> tuple[User, Specialty, Doctor]:
    user = User(uuid.uuid4(), email, "D", Role.DOCTOR, "h")
    PostgresUserRepository(session).add(user)
    specialty = Specialty(uuid.uuid4(), f"Spec {uuid.uuid4().hex[:6]}", 20)
    PostgresSpecialtyRepository(session).add(specialty)
    doctor = Doctor(uuid.uuid4(), user.id, "Dr D", specialty.id, 20)
    PostgresDoctorRepository(session).add(doctor)
    session.commit()
    return user, specialty, doctor


def make_patient(name: str = "Asha Rao", phone: str = "+919876543210") -> Patient:
    return Patient(uuid.uuid4(), name, phone, NOW, date(1990, 1, 1), "a@x.test")


def test_specialties_round_trip_list_update_and_unique_name(session: Session) -> None:
    repo = PostgresSpecialtyRepository(session)
    general = Specialty(uuid.uuid4(), "General Medicine", 20)
    repo.add(general)
    repo.add(Specialty(uuid.uuid4(), "Cardiology", 30))
    session.commit()

    assert repo.get(general.id) == general
    assert [s.name for s in repo.list()] == ["Cardiology", "General Medicine"]
    with pytest.raises(SpecialtyAlreadyExists):
        repo.add(Specialty(uuid.uuid4(), "cardiology", 15))

    general.name, general.default_slot_length_minutes = "Family Medicine", 25
    repo.update(general)
    session.commit()
    session.expire_all()
    assert repo.get(general.id) == general
    with pytest.raises(SpecialtyAlreadyExists):
        general.name = "CARDIOLOGY"
        repo.update(general)


def test_doctors_round_trip_filter_update_and_one_profile_per_user(session: Session) -> None:
    user, specialty, doctor = make_doctor(session)
    repo = PostgresDoctorRepository(session)

    assert repo.get(doctor.id) == doctor
    assert repo.get_by_user_id(user.id) == doctor
    assert repo.list(specialty.id) == [doctor]
    assert repo.list(uuid.uuid4()) == []
    assert [d.id for d in repo.list(None)] == [doctor.id]
    with pytest.raises(DoctorAlreadyExists):
        repo.add(Doctor(uuid.uuid4(), user.id, "Second", specialty.id, 20))

    doctor.name, doctor.slot_length_minutes, doctor.active = "Dr Renamed", 30, False
    repo.update(doctor)
    session.commit()
    session.expire_all()
    assert repo.get(doctor.id) == doctor


def test_patients_are_unique_on_phone_and_normalized_name_and_searchable(session: Session) -> None:
    repo = PostgresPatientRepository(session)
    asha, kiran = make_patient("Asha Rao"), make_patient("Kiran Rao")
    other_phone = make_patient("Bina Shah", "+919123456789")
    for p in (asha, kiran, other_phone):
        repo.add(p)
    session.commit()

    with pytest.raises(PatientAlreadyExists):
        repo.add(make_patient("  ASHA   rao "))

    by_phone = repo.find("+919876543210", None, 1, 10)
    assert [p.name for p in by_phone.items] == ["Asha Rao", "Kiran Rao"]
    assert by_phone.total == 2
    assert repo.find(None, "bin", 1, 10).items == [other_phone]
    assert repo.find("+919876543210", "kir", 1, 10).items == [kiran]
    paged = repo.find(None, None, 2, 2)
    assert paged.total == 3
    assert [p.name for p in paged.items] == ["Kiran Rao"]
    assert repo.get(asha.id) == asha
    assert repo.get(uuid.uuid4()) is None


def test_patient_update_persists_and_detects_collisions(session: Session) -> None:
    repo = PostgresPatientRepository(session)
    asha, kiran = make_patient("Asha Rao"), make_patient("Kiran Rao")
    repo.add(asha)
    repo.add(kiran)
    session.commit()

    kiran.name, kiran.dob, kiran.email = "Kiran R. Rao", None, None
    repo.update(kiran)
    session.commit()
    session.expire_all()
    assert repo.get(kiran.id) == kiran

    kiran.name = "asha rao"
    with pytest.raises(PatientAlreadyExists):
        repo.update(kiran)


def test_medical_history_is_stored_in_order_with_amendment_links(session: Session) -> None:
    user, _, _ = make_doctor(session)
    patient = make_patient()
    PostgresPatientRepository(session).add(patient)
    repo = PostgresMedicalHistoryRepository(session)
    original = MedicalHistoryEntry(
        uuid.uuid4(), patient.id, HistoryKind.ENTRY, "Allergic to X", NOW, user.id
    )
    amendment = MedicalHistoryEntry(
        uuid.uuid4(),
        patient.id,
        HistoryKind.AMENDMENT,
        "Actually Y",
        NOW.replace(minute=5),
        user.id,
        amends_entry_id=original.id,
    )
    repo.add(original)
    repo.add(amendment)
    session.commit()

    assert repo.list_for_patient(patient.id) == [original, amendment]
    assert repo.get(amendment.id) == amendment
    assert repo.get(uuid.uuid4()) is None
    assert repo.list_for_patient(uuid.uuid4()) == []


def test_availability_rules_and_exceptions_round_trip_update_delete(session: Session) -> None:
    _, _, doctor = make_doctor(session)
    repo = PostgresAvailabilityRepository(session)
    rule = Availability(uuid.uuid4(), doctor.id, DayOfWeek.MONDAY, time(9), time(12))
    repo.add_rule(rule)
    extra = AvailabilityException(
        uuid.uuid4(), doctor.id, date(2026, 3, 2), ExceptionType.EXTRA_HOURS, time(13), time(15)
    )
    holiday = AvailabilityException(
        uuid.uuid4(), doctor.id, date(2026, 3, 9), ExceptionType.UNAVAILABLE
    )
    repo.add_exception(extra)
    repo.add_exception(holiday)
    session.commit()

    assert repo.list_rules(doctor.id) == [rule]
    assert repo.get_rule(rule.id) == rule
    assert repo.list_exceptions(doctor.id) == [extra, holiday]
    assert repo.get_exception(holiday.id) == holiday

    rule.end_time = time(13)
    repo.update_rule(rule)
    extra.end_time = time(16)
    repo.update_exception(extra)
    session.commit()
    session.expire_all()
    assert repo.get_rule(rule.id) == rule
    assert repo.get_exception(extra.id) == extra

    repo.delete_rule(rule.id)
    repo.delete_exception(holiday.id)
    session.commit()
    assert repo.list_rules(doctor.id) == []
    assert repo.list_exceptions(doctor.id) == [extra]
    assert repo.get_rule(rule.id) is None


def test_clinic_settings_read_and_save(session: Session) -> None:
    repo = PostgresClinicSettingsRepository(session)
    specialty = Specialty(uuid.uuid4(), "General", 20)
    PostgresSpecialtyRepository(session).add(specialty)

    assert repo.get() == ClinicSettings(2.0, 1, 30, "UTC", None)

    repo.save(ClinicSettings(3.5, 2, 14, "Asia/Kolkata", specialty.id))
    session.commit()
    session.expire_all()

    assert repo.get() == ClinicSettings(3.5, 2, 14, "Asia/Kolkata", specialty.id)
