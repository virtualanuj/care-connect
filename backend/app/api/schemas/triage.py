import uuid
from datetime import datetime

from pydantic import Field

from app.api.schemas.base import CamelModel
from app.domain.models import TriageResult, TriageSource, Urgency
from app.domain.triage import MAX_SYMPTOMS_LENGTH


class TriageRequest(CamelModel):
    reported_symptoms: str = Field(min_length=1, max_length=MAX_SYMPTOMS_LENGTH)


class OverrideRequest(CamelModel):
    overridden_urgency: Urgency
    overridden_specialty_id: uuid.UUID | None = None
    override_reason: str = Field(min_length=1)


class TriageResultOut(CamelModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    reported_symptoms: str
    urgency: Urgency
    effective_urgency: Urgency
    suggested_specialty_id: uuid.UUID
    confidence_score: float
    source: TriageSource
    model_version: str | None
    prompt_version: str | None
    disclaimer: str
    overridden_by: uuid.UUID | None
    overridden_at: datetime | None
    overridden_urgency: Urgency | None
    overridden_specialty_id: uuid.UUID | None
    override_reason: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, r: TriageResult) -> "TriageResultOut":
        return cls(
            id=r.id,
            patient_id=r.patient_id,
            reported_symptoms=r.reported_symptoms,
            urgency=r.urgency,
            effective_urgency=r.effective_urgency,
            suggested_specialty_id=r.suggested_specialty_id,
            confidence_score=r.confidence_score,
            source=r.source,
            model_version=r.model_version,
            prompt_version=r.prompt_version,
            disclaimer=r.disclaimer,
            overridden_by=r.overridden_by,
            overridden_at=r.overridden_at,
            overridden_urgency=r.overridden_urgency,
            overridden_specialty_id=r.overridden_specialty_id,
            override_reason=r.override_reason,
            created_at=r.created_at,
        )
