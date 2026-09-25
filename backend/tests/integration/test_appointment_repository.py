import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.adapters.postgres.appointment_repository import PostgresAppointmentRepository
from app.adapters.postgres.patient_repository import PostgresPatientRepository
from app.adapters.postgres.triage_repository import PostgresTriageRepository
from app.db.session import get_session_factory
from app.domain.errors import PatientAlreadyBooked, SlotAlreadyBooked
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    CancellationType,
    Doctor,
    EmergencyJustification,
    Patient,
    TriageResult,
    TriageSource,
    Urgency,
)
from tests.integration.test_reference_repositories import make_doctor, make_patient

pytestmark = pytest.mark.integration

BASE = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
        session.rollback()


def appointment(
    doctor: Doctor,
    patient: Patient,
    start: datetime = BASE,
    minutes: int = 20,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
) -> Appointment:
    return Appointment(
        id=uuid.uuid4(),
        doctor_id=doctor.id,
        patient_id=patient.id,
        start_time=start,
        end_time=start + timedelta(minutes=minutes),
        status=status,
        source=AppointmentSource.SCHEDULED,
        is_emergency_slot=False,
        created_at=BASE - timedelta(days=1),
    )


class Env:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = PostgresAppointmentRepository(session)
        _, self.specialty, self.doctor = make_doctor(session)
        self.patients: list[Patient] = []
        patients = PostgresPatientRepository(session)
        for name, phone in [("Asha Rao", "+911"), ("Kiran Rao", "+912")]:
            patient = make_patient(name, phone)
            patients.add(patient)
            self.patients.append(patient)
        session.commit()


@pytest.fixture
def env(session: Session) -> Env:
    return Env(session)


def test_every_field_round_trips(env: Env) -> None:
    full = appointment(env.doctor, env.patients[0])
    full.is_emergency_slot = True
    full.source = AppointmentSource.WALK_IN
    full.emergency_justification = EmergencyJustification.FRONT_DESK_JUDGMENT
    full.emergency_reason = "chest pain"
    full.reported_symptoms = "cough"
    triage = TriageResult(
        id=uuid.uuid4(),
        patient_id=env.patients[0].id,
        reported_symptoms="cough",
        urgency=Urgency.URGENT,
        suggested_specialty_id=env.specialty.id,
        confidence_score=0.7,
        source=TriageSource.MODEL,
        disclaimer="d",
        created_at=BASE,
    )
    PostgresTriageRepository(env.session).add(triage)
    full.triage_result_id = triage.id
    full.checked_in_at = BASE
    full.cancellation_type = CancellationType.STANDARD
    full.cancel_reason = "moved"

    env.repo.add(full)
    env.session.commit()
    env.session.expire_all()

    assert env.repo.get(full.id) == full
    assert env.repo.get(uuid.uuid4()) is None


def test_overlaps_map_to_doctor_and_patient_specific_errors(env: Env) -> None:
    other_doctor = make_doctor(env.session, "second@x.test")[2]
    env.repo.add(appointment(env.doctor, env.patients[0]))
    env.session.commit()

    with pytest.raises(SlotAlreadyBooked):
        env.repo.add(appointment(env.doctor, env.patients[1], BASE + timedelta(minutes=10)))
    with pytest.raises(PatientAlreadyBooked):
        env.repo.add(appointment(other_doctor, env.patients[0], BASE + timedelta(minutes=10)))
    env.repo.add(appointment(env.doctor, env.patients[1], BASE + timedelta(minutes=20)))  # adjacent


def test_a_failed_add_leaves_the_session_usable(env: Env) -> None:
    env.repo.add(appointment(env.doctor, env.patients[0]))

    with pytest.raises(SlotAlreadyBooked):
        env.repo.add(appointment(env.doctor, env.patients[1]))

    env.repo.add(appointment(env.doctor, env.patients[1], BASE + timedelta(hours=1)))
    env.session.commit()
    assert env.repo.list(None, None, None, None, None, 1, 10).total == 2


@pytest.mark.parametrize("status", [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
def test_released_appointments_do_not_block_and_are_not_reported_as_spans(
    env: Env, status: AppointmentStatus
) -> None:
    env.repo.add(appointment(env.doctor, env.patients[0], status=status))
    env.session.commit()

    env.repo.add(appointment(env.doctor, env.patients[0]))  # rebooking the same slot works
    env.session.commit()

    spans = env.repo.spans_between(
        env.doctor.id, BASE - timedelta(hours=1), BASE + timedelta(hours=1)
    )
    assert len(spans) == 1


def test_spans_between_and_upcoming_spans(env: Env) -> None:
    env.repo.add(appointment(env.doctor, env.patients[0], BASE))
    env.repo.add(appointment(env.doctor, env.patients[1], BASE + timedelta(hours=2)))
    env.session.commit()

    window = env.repo.spans_between(
        env.doctor.id, BASE + timedelta(minutes=10), BASE + timedelta(hours=1)
    )
    upcoming = env.repo.upcoming_spans(env.doctor.id, BASE + timedelta(minutes=30))

    assert [s.start_time for s in window] == [BASE]  # touches, not merely adjacent
    assert [s.start_time for s in upcoming] == [BASE + timedelta(hours=2)]
    assert (
        env.repo.spans_between(
            env.doctor.id, BASE + timedelta(minutes=20), BASE + timedelta(hours=1)
        )
        == []
    )
    assert env.repo.spans_between(uuid.uuid4(), BASE, BASE + timedelta(days=1)) == []


def test_list_filters_orders_and_paginates(env: Env) -> None:
    first = appointment(env.doctor, env.patients[0], BASE)
    second = appointment(env.doctor, env.patients[1], BASE + timedelta(hours=1))
    third = appointment(env.doctor, env.patients[0], BASE + timedelta(days=1))
    third.status = AppointmentStatus.COMPLETED
    for a in (third, second, first):
        env.repo.add(a)
    env.session.commit()

    everything = env.repo.list(None, None, None, None, None, 1, 10)
    assert [a.id for a in everything.items] == [first.id, second.id, third.id]
    assert everything.total == 3
    by_patient = env.repo.list(None, env.patients[0].id, None, None, None, 1, 10)
    assert [a.id for a in by_patient.items] == [first.id, third.id]
    day = env.repo.list(
        env.doctor.id, None, BASE - timedelta(hours=1), BASE + timedelta(hours=5), None, 1, 10
    )
    assert [a.id for a in day.items] == [first.id, second.id]
    done = env.repo.list(None, None, None, None, AppointmentStatus.COMPLETED, 1, 10)
    assert [a.id for a in done.items] == [third.id]
    paged = env.repo.list(None, None, None, None, None, 2, 2)
    assert (paged.total, [a.id for a in paged.items]) == (3, [third.id])


def test_concurrent_overlapping_bookings_for_one_doctor_yield_exactly_one_success(
    env: Env,
) -> None:
    outcomes = _race(
        env,
        lambda i: (env.doctor, env.patients[i], BASE + timedelta(minutes=5 * i)),
    )

    assert sorted(outcomes) == ["SlotAlreadyBooked", "ok"]
    assert env.repo.list(None, None, None, None, None, 1, 10).total == 1


def test_concurrent_bookings_for_one_patient_with_two_doctors_yield_exactly_one_success(
    env: Env,
) -> None:
    second_doctor = make_doctor(env.session, "racer@x.test")[2]
    env.session.commit()
    doctors = [env.doctor, second_doctor]

    outcomes = _race(env, lambda i: (doctors[i], env.patients[0], BASE))

    assert sorted(outcomes) == ["PatientAlreadyBooked", "ok"]
    assert env.repo.list(None, None, None, None, None, 1, 10).total == 1


def test_many_concurrent_bookings_of_one_slot_never_create_a_double_booking(env: Env) -> None:
    extra = []
    patients = PostgresPatientRepository(env.session)
    for n in range(6):
        p = make_patient(f"Racer {n}", f"+9199{n}")
        patients.add(p)
        extra.append(p)
    env.session.commit()

    outcomes = _race(env, lambda i: (env.doctor, extra[i], BASE), threads=6)

    assert outcomes.count("ok") == 1, outcomes
    assert outcomes.count("SlotAlreadyBooked") == 5, outcomes


def _race(env: Env, plan, threads: int = 2) -> list[str]:  # type: ignore[no-untyped-def]
    """Run `threads` bookings at the same instant, each in its own session and transaction."""
    barrier = threading.Barrier(threads)
    outcomes: list[str] = [""] * threads

    def worker(index: int) -> None:
        doctor, patient, start = plan(index)
        with get_session_factory()() as session:
            repo = PostgresAppointmentRepository(session)
            barrier.wait()
            try:
                repo.add(appointment(doctor, patient, start))
                session.commit()
                outcomes[index] = "ok"
            except (SlotAlreadyBooked, PatientAlreadyBooked) as error:
                session.rollback()
                outcomes[index] = type(error).__name__
            except Exception as error:  # noqa: BLE001 - record whatever happened
                session.rollback()
                outcomes[index] = (
                    type(error).__name__
                    + ":"
                    + str(getattr(getattr(error, "orig", None), "sqlstate", ""))
                )

    workers = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=30)
    return outcomes
