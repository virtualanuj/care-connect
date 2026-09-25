import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine

pytestmark = pytest.mark.integration


def run(sql: str, **params: object) -> None:
    with get_engine().connect() as connection:
        try:
            connection.execute(text(sql), params)
        finally:
            connection.rollback()


def test_clinic_settings_has_a_single_row_with_the_documented_defaults() -> None:
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                "SELECT cancellation_cutoff_hours, emergency_slots_per_doctor_per_day, "
                "follow_up_max_days, clinic_timezone, default_triage_specialty_id "
                "FROM clinic_settings"
            )
        ).all()

    assert len(row) == 1
    cutoff, emergency, follow_up, timezone, triage_specialty = row[0]
    assert (float(cutoff), emergency, follow_up) == (2.0, 1, 30)
    assert timezone
    assert triage_specialty is None


def test_a_second_clinic_settings_row_is_rejected() -> None:
    with pytest.raises(IntegrityError):
        run(
            "INSERT INTO clinic_settings (id, cancellation_cutoff_hours, "
            "emergency_slots_per_doctor_per_day, follow_up_max_days, clinic_timezone) "
            "VALUES (2, 1, 1, 1, 'UTC')"
        )


def test_patient_identity_is_unique_on_phone_and_normalized_name() -> None:
    with get_engine().connect() as connection:
        insert = text(
            "INSERT INTO patients (id, name, name_normalized, phone) VALUES (:id, :n, :nn, :p)"
        )
        connection.execute(
            insert, {"id": uuid.uuid4(), "n": "Asha Rao", "nn": "asha rao", "p": "+911"}
        )
        connection.execute(
            insert, {"id": uuid.uuid4(), "n": "Kiran Rao", "nn": "kiran rao", "p": "+911"}
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert, {"id": uuid.uuid4(), "n": "ASHA  rao", "nn": "asha rao", "p": "+911"}
            )
        connection.rollback()


def test_specialty_names_are_unique_case_insensitively_and_slot_length_has_a_floor() -> None:
    with get_engine().connect() as connection:
        insert = text(
            "INSERT INTO specialties (id, name, default_slot_length_minutes) VALUES (:id, :n, :m)"
        )
        connection.execute(insert, {"id": uuid.uuid4(), "n": "Cardiology", "m": 20})
        with pytest.raises(IntegrityError):
            connection.execute(insert, {"id": uuid.uuid4(), "n": "cardiology", "m": 20})
        connection.rollback()
    with pytest.raises(IntegrityError):
        run(
            "INSERT INTO specialties (id, name, default_slot_length_minutes) VALUES (:id, 'X', 4)",
            id=uuid.uuid4(),
        )


def test_availability_requires_start_before_end() -> None:
    with get_engine().connect() as connection:
        user_id, specialty_id, doctor_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO users (id, email, name, role, password_hash, active) "
                "VALUES (:u, 'd@x.test', 'D', 'doctor', 'h', true)"
            ),
            {"u": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO specialties (id, name, default_slot_length_minutes) VALUES (:s, 'S', 20)"
            ),
            {"s": specialty_id},
        )
        connection.execute(
            text(
                "INSERT INTO doctors (id, user_id, name, specialty_id, slot_length_minutes, active) "
                "VALUES (:d, :u, 'D', :s, 20, true)"
            ),
            {"d": doctor_id, "u": user_id, "s": specialty_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO availability (id, doctor_id, day_of_week, start_time, end_time) "
                    "VALUES (:id, :d, 'monday', '10:00', '09:00')"
                ),
                {"id": uuid.uuid4(), "d": doctor_id},
            )
        connection.rollback()


def test_amendment_entries_must_reference_an_entry_and_plain_entries_must_not() -> None:
    with get_engine().connect() as connection:
        user_id, patient_id = uuid.uuid4(), uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO users (id, email, name, role, password_hash, active) "
                "VALUES (:u, 'a@x.test', 'A', 'doctor', 'h', true)"
            ),
            {"u": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO patients (id, name, name_normalized, phone) VALUES (:p, 'P', 'p', '+1')"
            ),
            {"p": patient_id},
        )
        insert = text(
            "INSERT INTO medical_history_entries (id, patient_id, kind, amends_entry_id, "
            "description, recorded_at, recorded_by) VALUES (:id, :p, :k, :a, 'd', now(), :u)"
        )
        first = uuid.uuid4()
        connection.execute(
            insert, {"id": first, "p": patient_id, "k": "entry", "a": None, "u": user_id}
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert,
                {"id": uuid.uuid4(), "p": patient_id, "k": "amendment", "a": None, "u": user_id},
            )
        connection.rollback()
    with get_engine().connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO medical_history_entries (id, patient_id, kind, amends_entry_id, "
                    "description, recorded_at, recorded_by) VALUES (:id, :p, 'entry', :a, 'd', now(), :u)"
                ),
                {"id": uuid.uuid4(), "p": uuid.uuid4(), "a": uuid.uuid4(), "u": uuid.uuid4()},
            )
        connection.rollback()
