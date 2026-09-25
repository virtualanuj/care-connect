import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.errors import AiServiceUnavailable, Forbidden, NotFound
from app.domain.models import (
    Appointment,
    HistoryKind,
    MedicalHistoryEntry,
    PatientIdentifiers,
    PreVisitSummary,
    Role,
    TriageResult,
    User,
)
from app.domain.ports import (
    AppointmentRepository,
    Clock,
    DoctorRepository,
    LLMProvider,
    MedicalHistoryRepository,
    PatientRepository,
    SummaryRepository,
    TriageRepository,
)
from app.domain.triage import (
    AI_TEXT_DISCLAIMER,
    MAX_PREVISIT_SUMMARY_CHARS,
    PREVISIT_HISTORY_ENTRIES,
)

MAX_DRAFT_CHARS = 4000


@dataclass(frozen=True)
class SummaryView:
    """A stored pre-visit summary plus whether its inputs have changed since."""

    appointment_id: uuid.UUID
    summary: str
    disclaimer: str
    generated_at: datetime
    stale: bool


class SummaryService:
    """AI text for doctors: the pre-visit summary and (via VisitNoteService) note drafts."""

    def __init__(
        self,
        appointments: AppointmentRepository,
        patients: PatientRepository,
        history: MedicalHistoryRepository,
        triage: TriageRepository,
        summaries: SummaryRepository,
        doctors: DoctorRepository,
        provider: LLMProvider,
        clock: Clock,
    ) -> None:
        self._appointments = appointments
        self._patients = patients
        self._history = history
        self._triage = triage
        self._summaries = summaries
        self._doctors = doctors
        self._provider = provider
        self._clock = clock

    # ---- pre-visit summary ------------------------------------------------------------------

    def generate(self, actor: User, appointment_id: uuid.UUID) -> PreVisitSummary:
        """(Re)generate the summary. A provider failure leaves any previous summary untouched."""
        appointment = self._load(actor, appointment_id)
        text, inputs_hash = self._inputs(appointment)
        answer = self._provider.generate_text("previsit", text, self._identifiers(appointment))
        clean = answer.strip()
        if not clean or len(clean) > MAX_PREVISIT_SUMMARY_CHARS:
            raise AiServiceUnavailable("The AI service returned an invalid answer")
        summary = PreVisitSummary(
            appointment_id=appointment.id,
            summary=clean,
            disclaimer=AI_TEXT_DISCLAIMER,
            inputs_hash=inputs_hash,
            generated_at=self._clock.now(),
        )
        self._summaries.save(summary)
        return summary

    def get(self, actor: User, appointment_id: uuid.UUID) -> SummaryView:
        """The stored summary, flagged stale if history, symptoms or triage changed since."""
        appointment = self._load(actor, appointment_id)
        stored = self._summaries.get(appointment.id)
        if stored is None:
            raise NotFound("No pre-visit summary has been generated for this appointment")
        _, current_hash = self._inputs(appointment)
        return SummaryView(
            appointment_id=stored.appointment_id,
            summary=stored.summary,
            disclaimer=stored.disclaimer,
            generated_at=stored.generated_at,
            stale=stored.inputs_hash != current_hash,
        )

    # ---- note drafting (called by VisitNoteService) -----------------------------------------

    def draft_from_notes(self, appointment: Appointment, notes: str) -> str:
        answer = self._provider.generate_text("draft", notes, self._identifiers(appointment))
        clean = answer.strip()
        if not clean or len(clean) > MAX_DRAFT_CHARS:
            raise AiServiceUnavailable("The AI service returned an invalid answer")
        return clean

    # ---- helpers ----------------------------------------------------------------------------

    def _load(self, actor: User, appointment_id: uuid.UUID) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or own.id != appointment.doctor_id:
                raise Forbidden("You can only access your own appointments")
        return appointment

    def _identifiers(self, appointment: Appointment) -> PatientIdentifiers:
        patient = self._patients.get(appointment.patient_id)
        if patient is None:
            raise NotFound("Patient not found")
        return PatientIdentifiers(patient.name, patient.phone, patient.email, patient.dob)

    def _history_lines(self, patient_id: uuid.UUID) -> list[str]:
        """The most recent entries, each with its latest amendment merged in."""
        everything = sorted(self._history.list_for_patient(patient_id), key=lambda e: e.recorded_at)
        latest_amendment: dict[uuid.UUID, MedicalHistoryEntry] = {}
        for entry in everything:
            if entry.kind == HistoryKind.AMENDMENT and entry.amends_entry_id is not None:
                latest_amendment[entry.amends_entry_id] = entry
        entries = [e for e in everything if e.kind == HistoryKind.ENTRY][-PREVISIT_HISTORY_ENTRIES:]
        lines = []
        for entry in entries:
            line = f"- {entry.description}"
            if entry.id in latest_amendment:
                line += f" [amended: {latest_amendment[entry.id].description}]"
            lines.append(line)
        return lines

    def _triage_line(self, appointment: Appointment) -> tuple[str, dict[str, str] | None]:
        result: TriageResult | None = (
            self._triage.get(appointment.triage_result_id) if appointment.triage_result_id else None
        )
        if result is None:
            return "Triage: none", None
        line = f"Triage: {result.effective_urgency.value}"
        if result.overridden_urgency is not None:
            line += f" (staff override of AI suggestion {result.urgency.value})"
        return line, {
            "id": str(result.id),
            "urgency": result.effective_urgency.value,
            "override": result.overridden_urgency.value if result.overridden_urgency else "",
        }

    def _inputs(self, appointment: Appointment) -> tuple[str, str]:
        """The prompt text and a hash of exactly the inputs it is built from."""
        history = self._history_lines(appointment.patient_id)
        triage_line, triage_key = self._triage_line(appointment)
        symptoms = appointment.reported_symptoms or "none reported"
        text = "\n".join(
            [
                f"Reported symptoms: {symptoms}",
                triage_line,
                "Patient history (oldest first):",
                *(history or ["- none recorded"]),
            ]
        )
        canonical = json.dumps(
            {"symptoms": symptoms, "triage": triage_key, "history": history},
            sort_keys=True,
            separators=(",", ":"),
        )
        return text, hashlib.sha256(canonical.encode()).hexdigest()
