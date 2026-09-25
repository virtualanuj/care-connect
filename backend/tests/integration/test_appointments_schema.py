import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine

pytestmark = pytest.mark.integration

BASE = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)


class World:
    """Two doctors and two patients inserted with plain SQL."""

    def __init__(self, connection: Connection) -> None:
        self.c = connection
        specialty = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO specialties (id, name, default_slot_length_minutes) VALUES (:i, 'S', 20)"
            ),
            {"i": specialty},
        )
        self.doctors = []
        for n in range(2):
            user = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO users (id, email, name, role, password_hash, active) "
                    "VALUES (:i, :e, 'D', 'doctor', 'h', true)"
                ),
                {"i": user, "e": f"d{n}@x.test"},
            )
            doctor = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO doctors (id, user_id, name, specialty_id, slot_length_minutes, active) "
                    "VALUES (:i, :u, 'Dr', :s, 20, true)"
                ),
                {"i": doctor, "u": user, "s": specialty},
            )
            self.doctors.append(doctor)
        self.patients = []
        for n in range(2):
            patient = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO patients (id, name, name_normalized, phone) "
                    "VALUES (:i, :n, :n, :p)"
                ),
                {"i": patient, "n": f"p{n}", "p": f"+91{n}"},
            )
            self.patients.append(patient)

    def book(
        self, doctor: int, patient: int, start: datetime, minutes: int = 20, status: str = "booked"
    ) -> None:
        self.c.execute(
            text(
                "INSERT INTO appointments (id, doctor_id, patient_id, start_time, end_time, status) "
                "VALUES (:i, :d, :p, :s, :e, :st)"
            ),
            {
                "i": uuid.uuid4(),
                "d": self.doctors[doctor],
                "p": self.patients[patient],
                "s": start,
                "e": start + timedelta(minutes=minutes),
                "st": status,
            },
        )


@pytest.fixture
def world():  # type: ignore[no-untyped-def]
    with get_engine().connect() as connection:
        yield World(connection)
        connection.rollback()


def test_a_booking_overlapping_the_same_doctors_appointment_is_rejected(world: World) -> None:
    world.book(0, 0, BASE)  # 10:00-10:20

    with pytest.raises(IntegrityError, match="appt_no_doctor_overlap"):
        world.book(0, 1, BASE + timedelta(minutes=10))  # 10:10-10:30, a different patient


def test_identical_start_times_for_the_same_doctor_are_rejected(world: World) -> None:
    world.book(0, 0, BASE)

    with pytest.raises(IntegrityError, match="appt_no_doctor_overlap"):
        world.book(0, 1, BASE)


def test_back_to_back_appointments_do_not_overlap(world: World) -> None:
    world.book(0, 0, BASE)

    world.book(0, 1, BASE + timedelta(minutes=20))  # 10:20-10:40


def test_the_same_patient_cannot_hold_overlapping_appointments_with_two_doctors(
    world: World,
) -> None:
    world.book(0, 0, BASE)

    with pytest.raises(IntegrityError, match="appt_no_patient_overlap"):
        world.book(1, 0, BASE + timedelta(minutes=10))


def test_different_doctors_and_patients_may_book_the_same_time(world: World) -> None:
    world.book(0, 0, BASE)

    world.book(1, 1, BASE)


@pytest.mark.parametrize("status", ["cancelled", "no_show"])
def test_cancelled_and_no_show_appointments_do_not_block_rebooking(
    world: World, status: str
) -> None:
    world.book(0, 0, BASE, status=status)

    world.book(0, 0, BASE)  # same doctor, same patient, same time


@pytest.mark.parametrize("status", ["booked", "checked_in", "in_consultation", "completed"])
def test_active_statuses_block_overlapping_bookings(world: World, status: str) -> None:
    world.book(0, 0, BASE, status=status)

    with pytest.raises(IntegrityError):
        world.book(0, 1, BASE)


def test_end_must_be_after_start(world: World) -> None:
    with pytest.raises(IntegrityError, match="appointments_end_after_start"):
        world.book(0, 0, BASE, minutes=0)


def test_unknown_status_is_rejected_and_default_status_is_booked(world: World) -> None:
    with pytest.raises(Exception, match="appointment_status"):
        world.book(0, 0, BASE, status="teleported")


def test_new_appointments_default_to_booked_scheduled_and_not_emergency(world: World) -> None:
    world.book(0, 0, BASE)

    row = world.c.execute(text("SELECT status, source, is_emergency_slot FROM appointments")).one()

    assert tuple(row) == ("booked", "scheduled", False)
