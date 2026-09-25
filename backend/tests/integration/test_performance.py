"""Query-plan and latency budget on a busy clinic: 50 doctors x 30 fully booked days.

The budget (p95 < 300 ms for /slots, /queue and /appointments) is the release-gate target from
docs/plan.md M8-B5; the numbers measured on the CI-size database are recorded in docs/runbook.md.
"""

import statistics
import time
from typing import NamedTuple

import pytest
from sqlalchemy import text

from app.db.session import get_engine
from tests.api_harness import ApiHarness
from tests.integration.test_appointments_api import API

pytestmark = pytest.mark.integration

DOCTORS = 50
DAYS = 30
SLOTS_PER_DAY = 9  # 09:00-12:00 in 20-minute slots
PATIENTS = 2000
FIRST_DAY = "2026-03-02"
BUDGET_MS = 300.0
SAMPLES = 25


class Clinic(NamedTuple):
    harness: ApiHarness
    specialty_id: str
    admin: dict[str, str]


@pytest.fixture
def busy_clinic(booking_harness: ApiHarness) -> Clinic:
    """Bulk-load through SQL: 13,500 appointments would take minutes through the API."""
    admin = booking_harness.admin_headers()
    specialty = booking_harness.client.post(
        f"{API}/specialties",
        json={"name": "General", "defaultSlotLengthMinutes": 20},
        headers=admin,
    ).json()
    with get_engine().begin() as db:
        db.execute(
            text(
                """
                INSERT INTO users (id, email, name, role, password_hash)
                SELECT gen_random_uuid(), 'perf' || n || '@clinic.test', 'Perf ' || n,
                       'doctor', 'x'
                FROM generate_series(1, :doctors) n
                """
            ),
            {"doctors": DOCTORS},
        )
        db.execute(
            text(
                """
                INSERT INTO doctors (id, user_id, name, specialty_id, slot_length_minutes)
                SELECT gen_random_uuid(), u.id, u.name, :sid, 20
                FROM users u WHERE u.email LIKE 'perf%'
                """
            ),
            {"sid": specialty["id"]},
        )
        db.execute(
            text(
                """
                INSERT INTO availability (id, doctor_id, day_of_week, start_time, end_time)
                SELECT gen_random_uuid(), d.id, dow.name::day_of_week, '09:00', '12:00'
                FROM doctors d,
                     unnest(ARRAY['monday','tuesday','wednesday','thursday','friday',
                                  'saturday','sunday']) AS dow(name)
                """
            )
        )
        db.execute(
            text(
                """
                INSERT INTO patients (id, name, name_normalized, phone)
                SELECT gen_random_uuid(), 'Patient ' || n, 'patient ' || n, '+9190000' || lpad(n::text, 5, '0')
                FROM generate_series(1, :patients) n
                """
            ),
            {"patients": PATIENTS},
        )
        db.execute(
            text(
                """
                WITH d AS (SELECT id, row_number() OVER (ORDER BY id) - 1 AS di FROM doctors),
                     p AS (SELECT id, row_number() OVER (ORDER BY id) - 1 AS pi FROM patients)
                INSERT INTO appointments (id, doctor_id, patient_id, start_time, end_time)
                SELECT gen_random_uuid(), d.id, p.id,
                       (CAST(:first AS date) + day * interval '1 day' + interval '9 hours'
                        + slot * interval '20 minutes') AT TIME ZONE 'UTC',
                       (CAST(:first AS date) + day * interval '1 day' + interval '9 hours'
                        + (slot + 1) * interval '20 minutes') AT TIME ZONE 'UTC'
                FROM d
                CROSS JOIN generate_series(0, :days - 1) day
                CROSS JOIN generate_series(0, :slots - 1) slot
                JOIN p ON p.pi = (d.di + slot * 7 + day * 11) % :patients
                """
            ),
            {"first": FIRST_DAY, "days": DAYS, "slots": SLOTS_PER_DAY, "patients": PATIENTS},
        )
        db.execute(text("ANALYZE"))
    return Clinic(booking_harness, specialty["id"], admin)


def p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=20)[-1]


def timed(harness: ApiHarness, url: str, params: dict[str, str], headers: dict[str, str]) -> float:
    started = time.perf_counter()
    response = harness.client.get(url, params=params, headers=headers)
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    return elapsed


def test_the_busy_clinic_was_loaded_as_intended(busy_clinic: Clinic) -> None:
    with get_engine().connect() as db:
        total = db.execute(text("SELECT count(*) FROM appointments")).scalar_one()
    assert total == DOCTORS * DAYS * SLOTS_PER_DAY


@pytest.mark.parametrize(
    "label",
    ["slots-by-specialty", "queue", "appointments-by-day", "appointments-by-doctor"],
)
def test_p95_latency_stays_under_the_budget(busy_clinic: Clinic, label: str) -> None:
    harness, specialty_id, headers = busy_clinic
    with get_engine().connect() as db:
        doctor_id = str(db.execute(text("SELECT id FROM doctors LIMIT 1")).scalar_one())
    requests = {
        "slots-by-specialty": (f"{API}/slots", {"date": "2026-03-10", "specialtyId": specialty_id}),
        "queue": (f"{API}/queue", {"date": "2026-03-10"}),
        "appointments-by-day": (f"{API}/appointments", {"date": "2026-03-10", "pageSize": "50"}),
        "appointments-by-doctor": (f"{API}/appointments", {"doctorId": doctor_id}),
    }
    url, params = requests[label]
    timed(harness, url, params, headers)  # warm-up

    samples = [timed(harness, url, params, headers) for _ in range(SAMPLES)]

    print(f"{label}: p50={statistics.median(samples):.0f} ms p95={p95(samples):.0f} ms")
    assert p95(samples) < BUDGET_MS


@pytest.mark.parametrize(
    ("label", "sql", "index"),
    [
        (
            "queue / list by day",
            "SELECT * FROM appointments WHERE start_time >= '2026-03-10' "
            "AND start_time < '2026-03-11'",
            "appointments_start_idx",
        ),
        (
            "doctor's day and conflicts",
            "SELECT start_time, end_time FROM appointments WHERE doctor_id = "
            "(SELECT id FROM doctors LIMIT 1) AND start_time >= '2026-03-10' "
            "AND start_time < '2026-03-11'",
            "appointments_doctor_start_idx",
        ),
        (
            "patient's appointments",
            "SELECT * FROM appointments WHERE patient_id = "
            "(SELECT id FROM patients LIMIT 1) ORDER BY start_time",
            "appointments_patient_start_idx",
        ),
    ],
)
def test_hot_queries_use_their_indexes(
    busy_clinic: Clinic, label: str, sql: str, index: str
) -> None:
    with get_engine().connect() as db:
        plan = "\n".join(row[0] for row in db.execute(text(f"EXPLAIN {sql}")))

    assert index in plan or "appointments_no_" in plan, f"{label} did not use an index:\n{plan}"
    assert "Seq Scan on appointments" not in plan, f"{label} scans the whole table:\n{plan}"
