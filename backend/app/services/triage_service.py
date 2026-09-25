import uuid
from collections.abc import Callable

from app.domain.errors import AiServiceUnavailable, Forbidden, NotFound, ValidationFailed
from app.domain.models import (
    AuditAction,
    PatientIdentifiers,
    Role,
    TriageModelOutput,
    TriageResult,
    TriageSource,
    Urgency,
    User,
)
from app.domain.ports import (
    AppointmentRepository,
    ClinicSettingsRepository,
    Clock,
    DoctorRepository,
    LLMProvider,
    MedicalHistoryRepository,
    PatientRepository,
    SpecialtyRepository,
    TriageRepository,
)
from app.domain.red_flags import match_red_flags
from app.domain.triage import HISTORY_ENTRIES_FOR_CONTEXT, MAX_SYMPTOMS_LENGTH, TRIAGE_DISCLAIMER
from app.services.audit_service import AuditService


class TriageService:
    """AI-assisted triage with a deterministic safety net.

    Order of authority: (1) the red-flag check, which can only raise urgency and works even when
    the AI is down; (2) the model; (3) a staff override, which always wins for *effective*
    urgency while the original output is preserved for audit.
    """

    def __init__(
        self,
        patients: PatientRepository,
        history: MedicalHistoryRepository,
        specialties: SpecialtyRepository,
        triage: TriageRepository,
        appointments: AppointmentRepository,
        doctors: DoctorRepository,
        settings: ClinicSettingsRepository,
        provider: LLMProvider,
        audit: AuditService,
        clock: Clock,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._patients = patients
        self._history = history
        self._specialties = specialties
        self._triage = triage
        self._appointments = appointments
        self._doctors = doctors
        self._settings = settings
        self._provider = provider
        self._audit = audit
        self._clock = clock
        self._new_id = new_id

    # ---- running triage ---------------------------------------------------------------------

    def run(self, actor: User, patient_id: uuid.UUID, symptoms: str) -> TriageResult:
        patient = self._patients.get(patient_id)
        if patient is None:
            raise NotFound("Patient not found")
        text = symptoms.strip()
        if not text:
            raise ValidationFailed("Describe the symptoms to triage")
        if len(text) > MAX_SYMPTOMS_LENGTH:
            raise ValidationFailed(f"Symptoms must be at most {MAX_SYMPTOMS_LENGTH} characters")

        flags = match_red_flags(text)  # deterministic; runs before (and regardless of) the AI
        specialties = self._specialties.list()
        recent = sorted(
            self._history.list_for_patient(patient_id), key=lambda e: e.recorded_at, reverse=True
        )[:HISTORY_ENTRIES_FOR_CONTEXT]
        identifiers = PatientIdentifiers(patient.name, patient.phone, patient.email, patient.dob)

        model: tuple[TriageModelOutput, uuid.UUID] | None = None
        try:
            output = self._provider.classify_triage(
                text, [e.description for e in recent], [s.name for s in specialties], identifiers
            )
            matched = next(
                (
                    s
                    for s in specialties
                    if s.name.casefold() == output.suggested_specialty.casefold()
                ),
                None,
            )
            if matched is None:
                raise AiServiceUnavailable("The AI answered with an unknown specialty")
            model = (output, matched.id)
        except AiServiceUnavailable:
            if not flags:
                raise  # nothing deterministic to fall back on: report the outage honestly

        if flags:
            urgency, source = Urgency.EMERGENCY, TriageSource.RED_FLAG
        else:
            assert model is not None
            urgency, source = model[0].urgency, TriageSource.MODEL

        specialty_id = model[1] if model else self._fallback_specialty_id(specialties)
        result = TriageResult(
            id=self._new_id(),
            patient_id=patient_id,
            reported_symptoms=text,
            urgency=urgency,
            suggested_specialty_id=specialty_id,
            confidence_score=model[0].confidence if model else 1.0,
            source=source,
            disclaimer=TRIAGE_DISCLAIMER,
            created_at=self._clock.now(),
            model_version=self._provider.model_version if model else None,
            prompt_version=self._provider.prompt_version if model else None,
        )
        self._triage.add(result)
        return result

    def _fallback_specialty_id(self, specialties: list) -> uuid.UUID:  # type: ignore[type-arg]
        """Specialty for a red-flag result produced without the model."""
        configured = self._settings.get().default_triage_specialty_id
        if configured is not None and any(s.id == configured for s in specialties):
            return configured
        if not specialties:
            raise ValidationFailed("No specialties are configured")
        return specialties[0].id  # the repository lists specialties by name

    # ---- reading ----------------------------------------------------------------------------

    def for_patient(self, patient_id: uuid.UUID) -> list[TriageResult]:
        if self._patients.get(patient_id) is None:
            raise NotFound("Patient not found")
        return self._triage.list_for_patient(patient_id)

    def for_appointment(self, actor: User, appointment_id: uuid.UUID) -> TriageResult:
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFound("Appointment not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or own.id != appointment.doctor_id:
                raise Forbidden("You can only view triage for your own appointments")
        if appointment.triage_result_id is None:
            raise NotFound("This appointment has no triage result")
        result = self._triage.get(appointment.triage_result_id)
        if result is None:
            raise NotFound("Triage result not found")
        return result

    # ---- override ---------------------------------------------------------------------------

    def override(
        self,
        actor: User,
        triage_id: uuid.UUID,
        urgency: Urgency,
        reason: str,
        specialty_id: uuid.UUID | None,
    ) -> TriageResult:
        """Staff override. Wins for effective urgency; the original output is kept."""
        result = self._triage.get(triage_id)
        if result is None:
            raise NotFound("Triage result not found")
        if actor.role == Role.DOCTOR:
            own = self._doctors.get_by_user_id(actor.id)
            if own is None or not self._appointments.triage_used_by(triage_id, own.id):
                raise Forbidden("You can only override triage used by your own appointments")
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValidationFailed("A reason is required to override a triage result")
        if specialty_id is not None and self._specialties.get(specialty_id) is None:
            raise ValidationFailed("Specialty does not exist")

        previous = result.overridden_urgency
        result.overridden_urgency = urgency
        result.overridden_specialty_id = specialty_id
        result.override_reason = clean_reason
        result.overridden_by = actor.id
        result.overridden_at = self._clock.now()
        self._triage.update(result)
        self._audit.record(
            AuditAction.TRIAGE_OVERRIDE,
            actor.id,
            "triage_result",
            result.id,
            f"{result.urgency.value} -> {urgency.value}; previous override: "
            f"{previous.value if previous else 'none'}; reason: {clean_reason}",
        )
        return result
