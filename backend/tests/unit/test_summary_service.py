import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.errors import AiServiceUnavailable, Forbidden, NotFound
from app.domain.models import (
    Appointment,
    AppointmentSource,
    AppointmentStatus,
    Doctor,
    HistoryKind,
    MedicalHistoryEntry,
    Patient,
    Role,
    Specialty,
    TriageResult,
    TriageSource,
    Urgency,
    User,
)
from app.domain.triage import AI_TEXT_DISCLAIMER
from app.services.summary_service import SummaryService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.repositories import (
    InMemoryAppointmentRepository,
    InMemoryDoctorRepository,
    InMemoryMedicalHistoryRepository,
    InMemoryPatientRepository,
    InMemorySpecialtyRepository,
    InMemorySummaryRepository,
    InMemoryTriageRepository,
)

NOW = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


class Setup:
    def __init__(self) -> None:
        self.provider = FakeLLMProvider()
        self.clock = FixedClock(NOW)
        self.appointments = InMemoryAppointmentRepository()
        self.patients = InMemoryPatientRepository()
        self.history = InMemoryMedicalHistoryRepository()
        self.triage = InMemoryTriageRepository()
        self.summaries = InMemorySummaryRepository()
        self.doctors = InMemoryDoctorRepository()
        self.specialties = InMemorySpecialtyRepository()
        self.service = SummaryService(
            self.appointments,
            self.patients,
            self.history,
            self.triage,
            self.summaries,
            self.doctors,
            self.provider,
            self.clock,
        )
        self.specialty = Specialty(uuid.uuid4(), "General", 20)
        self.admin = User(uuid.uuid4(), "fd@x.test", "FD", Role.FRONT_DESK_ADMIN, "h")
        self.doc_user = User(uuid.uuid4(), "d@x.test", "D", Role.DOCTOR, "h")
        self.other_user = User(uuid.uuid4(), "o@x.test", "O", Role.DOCTOR, "h")
        self.doctor = Doctor(uuid.uuid4(), self.doc_user.id, "Dr One", self.specialty.id, 20)
        self.other = Doctor(uuid.uuid4(), self.other_user.id, "Dr Two", self.specialty.id, 20)
        self.doctors.add(self.doctor)
        self.doctors.add(self.other)
        self.asha = Patient(
            uuid.uuid4(), "Asha Rao", "+919876543210", NOW, date(1990, 5, 1), "asha@example.com"
        )
        self.patients.add(self.asha)
        self.appointment = Appointment(
            id=uuid.uuid4(),
            doctor_id=self.doctor.id,
            patient_id=self.asha.id,
            start_time=NOW,
            end_time=NOW + timedelta(minutes=20),
            status=AppointmentStatus.BOOKED,
            source=AppointmentSource.SCHEDULED,
            is_emergency_slot=False,
            created_at=NOW,
            reported_symptoms="cough for a week",
        )
        self.appointments.items[self.appointment.id] = self.appointment

    def add_history(self, text: str, minutes: int = 0, **kwargs) -> MedicalHistoryEntry:  # type: ignore[no-untyped-def]
        entry = MedicalHistoryEntry(
            id=uuid.uuid4(),
            patient_id=self.asha.id,
            kind=kwargs.pop("kind", HistoryKind.ENTRY),
            description=text,
            recorded_at=NOW - timedelta(days=1) + timedelta(minutes=minutes),
            recorded_by=self.admin.id,
            **kwargs,
        )
        self.history.add(entry)
        return entry

    def add_triage(self, urgency: Urgency = Urgency.URGENT) -> TriageResult:
        result = TriageResult(
            id=uuid.uuid4(),
            patient_id=self.asha.id,
            reported_symptoms="cough",
            urgency=urgency,
            suggested_specialty_id=self.specialty.id,
            confidence_score=0.7,
            source=TriageSource.MODEL,
            disclaimer="d",
            created_at=NOW,
        )
        self.triage.add(result)
        self.appointment.triage_result_id = result.id
        return result


@pytest.fixture
def s() -> Setup:
    return Setup()


def test_generate_stores_the_summary_with_disclaimer_hash_and_time(s: Setup) -> None:
    s.provider.text_output = "Patient has a week-long cough."

    summary = s.service.generate(s.admin, s.appointment.id)

    assert summary.summary == "Patient has a week-long cough."
    assert summary.disclaimer == AI_TEXT_DISCLAIMER
    assert summary.generated_at == NOW
    assert len(summary.inputs_hash) == 64  # sha256 hex
    assert s.summaries.get(s.appointment.id) == summary


def test_the_provider_is_asked_with_symptoms_triage_history_and_the_patients_identifiers(
    s: Setup,
) -> None:
    s.add_history("Allergic to penicillin")
    s.add_triage(Urgency.URGENT)

    s.service.generate(s.admin, s.appointment.id)

    (task, text, identifiers) = s.provider.text_calls[0]
    assert task == "previsit"
    assert "cough for a week" in text
    assert "urgent" in text.lower()
    assert "Allergic to penicillin" in text
    assert identifiers.name == "Asha Rao"


def test_an_amendment_is_shown_with_the_entry_it_corrects_not_as_a_separate_fact(s: Setup) -> None:
    original = s.add_history("Allergic to penicillin", minutes=0)
    s.add_history(
        "Actually amoxicillin", minutes=5, kind=HistoryKind.AMENDMENT, amends_entry_id=original.id
    )

    s.service.generate(s.admin, s.appointment.id)

    text = s.provider.text_calls[0][1]
    assert "Allergic to penicillin" in text and "Actually amoxicillin" in text
    assert text.count("Actually amoxicillin") == 1
    assert "corrected" in text.lower() or "amended" in text.lower()


def test_only_the_twenty_most_recent_history_entries_are_used(s: Setup) -> None:
    for i in range(25):
        s.add_history(f"entry-{i:02d}", minutes=i)

    s.service.generate(s.admin, s.appointment.id)

    text = s.provider.text_calls[0][1]
    assert "entry-24" in text and "entry-05" in text
    assert "entry-04" not in text


def test_the_summary_is_not_stale_until_an_input_changes(s: Setup) -> None:
    s.add_history("Asthma")
    s.service.generate(s.admin, s.appointment.id)

    fresh = s.service.get(s.admin, s.appointment.id)

    assert fresh.stale is False


def test_new_history_a_new_triage_an_override_or_new_symptoms_make_it_stale_and_refresh_clears_it(
    s: Setup,
) -> None:
    s.service.generate(s.admin, s.appointment.id)
    assert s.service.get(s.admin, s.appointment.id).stale is False

    s.add_history("New allergy")
    assert s.service.get(s.admin, s.appointment.id).stale is True
    s.service.generate(s.admin, s.appointment.id)
    assert s.service.get(s.admin, s.appointment.id).stale is False

    triage = s.add_triage(Urgency.ROUTINE)
    assert s.service.get(s.admin, s.appointment.id).stale is True
    s.service.generate(s.admin, s.appointment.id)
    triage.overridden_urgency = Urgency.EMERGENCY
    assert s.service.get(s.admin, s.appointment.id).stale is True
    s.service.generate(s.admin, s.appointment.id)

    s.appointment.reported_symptoms = "cough and fever"
    assert s.service.get(s.admin, s.appointment.id).stale is True


def test_refreshing_with_unchanged_inputs_still_calls_the_provider(s: Setup) -> None:
    s.service.generate(s.admin, s.appointment.id)
    s.service.generate(s.admin, s.appointment.id)

    assert len(s.provider.text_calls) == 2


def test_get_before_any_generation_is_not_found(s: Setup) -> None:
    with pytest.raises(NotFound):
        s.service.get(s.admin, s.appointment.id)
    with pytest.raises(NotFound):
        s.service.get(s.admin, uuid.uuid4())
    with pytest.raises(NotFound):
        s.service.generate(s.admin, uuid.uuid4())


def test_a_provider_failure_keeps_the_previous_summary(s: Setup) -> None:
    s.provider.text_output = "First summary."
    first = s.service.generate(s.admin, s.appointment.id)
    s.add_history("New allergy")
    s.provider.text_output = AiServiceUnavailable("down")

    with pytest.raises(AiServiceUnavailable):
        s.service.generate(s.admin, s.appointment.id)

    kept = s.summaries.get(s.appointment.id)
    assert kept is not None and kept.summary == "First summary."
    assert kept.inputs_hash == first.inputs_hash
    assert s.service.get(s.admin, s.appointment.id).stale is True  # still flagged as out of date


@pytest.mark.parametrize("answer", ["", "   ", "x" * 2001])
def test_an_empty_or_oversized_answer_is_rejected_and_not_stored(s: Setup, answer: str) -> None:
    s.provider.text_output = answer

    with pytest.raises(AiServiceUnavailable):
        s.service.generate(s.admin, s.appointment.id)

    assert s.summaries.items == {}


def test_doctors_see_only_their_own_appointments_summaries(s: Setup) -> None:
    assert s.service.generate(s.doc_user, s.appointment.id).summary
    with pytest.raises(Forbidden):
        s.service.generate(s.other_user, s.appointment.id)
    with pytest.raises(Forbidden):
        s.service.get(s.other_user, s.appointment.id)
    assert s.service.get(s.admin, s.appointment.id).summary  # front-desk may view
