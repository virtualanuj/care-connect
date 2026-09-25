"""Live contract test against the real Gemini API.

Skipped unless GEMINI_API_KEY is set, so CI and offline runs never call the network.
Run it deliberately to check the adapter still matches the real service:

    GEMINI_API_KEY=... uv run pytest tests/contract/test_gemini_live.py
"""

import os
from datetime import date

import pytest

from app.adapters.ai.gemini_llm_provider import GeminiLLMProvider
from app.domain.models import PatientIdentifiers, Urgency

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY is not set (live test)"
)

WHO = PatientIdentifiers("Asha Rao", "+919876543210", "asha@example.com", date(1990, 5, 1))


def test_live_triage_answer_matches_the_schema() -> None:
    provider = GeminiLLMProvider(
        api_key=os.environ["GEMINI_API_KEY"],
        model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    )

    output = provider.classify_triage(
        "Asha Rao (98765 43210) has had a mild runny nose for two days",
        [],
        ["Cardiology", "General Medicine"],
        WHO,
    )

    assert output.urgency in set(Urgency)
    assert output.suggested_specialty in {"Cardiology", "General Medicine"}
    assert 0 <= output.confidence <= 1
