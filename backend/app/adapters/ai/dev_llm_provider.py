"""Deterministic stand-ins for the AI provider, for local development and end-to-end tests.

Selected with LLM_PROVIDER=fake or fake-down, and only allowed when ENV=dev (see config.py).
They never make a network call.
"""

from collections.abc import Sequence

from app.domain.errors import AiServiceUnavailable
from app.domain.models import PatientIdentifiers, TriageModelOutput, Urgency

_URGENT_WORDS = ("fever", "vomiting", "infection", "severe")


class DevLLMProvider:
    model_version = "dev-fake"
    prompt_version = "dev-fake"

    def __init__(self, down: bool = False) -> None:
        self._down = down

    def classify_triage(
        self,
        symptoms: str,
        history: Sequence[str],
        specialties: Sequence[str],
        identifiers: PatientIdentifiers,
    ) -> TriageModelOutput:
        if self._down:
            raise AiServiceUnavailable("The AI service is unavailable")
        urgent = any(word in symptoms.lower() for word in _URGENT_WORDS)
        return TriageModelOutput(Urgency.URGENT if urgent else Urgency.ROUTINE, specialties[0], 0.6)

    def generate_text(self, task: str, text: str, identifiers: PatientIdentifiers) -> str:
        if self._down:
            raise AiServiceUnavailable("The AI service is unavailable")
        return f"[dev {task}] " + text[:200]
