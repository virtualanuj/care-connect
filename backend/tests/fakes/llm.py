from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.errors import AiServiceUnavailable
from app.domain.models import PatientIdentifiers, TriageModelOutput, Urgency


@dataclass
class TriageCall:
    symptoms: str
    history: list[str]
    specialties: list[str]
    identifiers: PatientIdentifiers


@dataclass
class FakeLLMProvider:
    """Scripted stand-in for the AI provider: no network, records what it was asked."""

    output: TriageModelOutput | Exception = field(
        default_factory=lambda: TriageModelOutput(Urgency.ROUTINE, "General Medicine", 0.8)
    )
    text_output: str | Exception = "A generated summary."
    model_version: str = "fake-model-1"
    prompt_version: str = "fake-prompt-1"
    calls: list[TriageCall] = field(default_factory=list)
    text_calls: list[tuple[str, str, PatientIdentifiers]] = field(default_factory=list)

    def classify_triage(
        self,
        symptoms: str,
        history: Sequence[str],
        specialties: Sequence[str],
        identifiers: PatientIdentifiers,
    ) -> TriageModelOutput:
        self.calls.append(TriageCall(symptoms, list(history), list(specialties), identifiers))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_text(self, task: str, text: str, identifiers: PatientIdentifiers) -> str:
        self.text_calls.append((task, text, identifiers))
        if isinstance(self.text_output, Exception):
            raise self.text_output
        return self.text_output

    @classmethod
    def down(cls) -> "FakeLLMProvider":
        return cls(output=AiServiceUnavailable("AI is down"), text_output=AiServiceUnavailable("x"))
