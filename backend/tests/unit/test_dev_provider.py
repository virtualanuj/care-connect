import pytest

from app.adapters.ai.dev_llm_provider import OUTAGE_MARKER, DevLLMProvider
from app.domain.errors import AiServiceUnavailable
from app.domain.models import PatientIdentifiers, Urgency

WHO = PatientIdentifiers("Asha Rao")
SPECIALTIES = ["Cardiology", "General Medicine"]


def test_the_dev_provider_is_deterministic_and_uses_the_first_listed_specialty() -> None:
    routine = DevLLMProvider().classify_triage("mild headache", [], SPECIALTIES, WHO)
    urgent = DevLLMProvider().classify_triage("high fever", [], SPECIALTIES, WHO)

    assert (routine.urgency, routine.suggested_specialty) == (Urgency.ROUTINE, "Cardiology")
    assert urgent.urgency == Urgency.URGENT


def test_the_outage_marker_simulates_an_ai_outage_in_a_running_server() -> None:
    with pytest.raises(AiServiceUnavailable):
        DevLLMProvider().classify_triage(f"chest pain {OUTAGE_MARKER}", [], SPECIALTIES, WHO)


def test_down_mode_always_fails() -> None:
    with pytest.raises(AiServiceUnavailable):
        DevLLMProvider(down=True).classify_triage("cough", [], SPECIALTIES, WHO)
    with pytest.raises(AiServiceUnavailable):
        DevLLMProvider(down=True).generate_text("draft", "notes", WHO)


def test_generated_text_is_a_short_deterministic_echo() -> None:
    assert DevLLMProvider().generate_text("draft", "notes", WHO) == "[dev draft] notes"
