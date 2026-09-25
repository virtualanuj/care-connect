"""Domain errors. One class per ErrorCode in docs/openapi.yaml (the source of truth)."""

from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    SLOT_ALREADY_BOOKED = "SLOT_ALREADY_BOOKED"
    PATIENT_ALREADY_BOOKED = "PATIENT_ALREADY_BOOKED"
    INVALID_SLOT = "INVALID_SLOT"
    EMERGENCY_JUSTIFICATION_REQUIRED = "EMERGENCY_JUSTIFICATION_REQUIRED"
    EMERGENCY_NOT_AUTHORIZED = "EMERGENCY_NOT_AUTHORIZED"
    CANCELLATION_WINDOW_CLOSED = "CANCELLATION_WINDOW_CLOSED"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    FOLLOW_UP_WINDOW_EXCEEDED = "FOLLOW_UP_WINDOW_EXCEEDED"
    APPOINTMENT_NOT_COMPLETED = "APPOINTMENT_NOT_COMPLETED"
    PATIENT_ALREADY_EXISTS = "PATIENT_ALREADY_EXISTS"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    DOCTOR_ALREADY_EXISTS = "DOCTOR_ALREADY_EXISTS"
    SPECIALTY_ALREADY_EXISTS = "SPECIALTY_ALREADY_EXISTS"
    AVAILABILITY_OVERLAP = "AVAILABILITY_OVERLAP"
    AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS = "AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS"
    VISIT_NOTE_NOT_WRITABLE = "VISIT_NOTE_NOT_WRITABLE"
    VISIT_NOTE_LOCKED = "VISIT_NOTE_LOCKED"
    NO_NOTES_TO_DRAFT = "NO_NOTES_TO_DRAFT"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """Base class: carries the API error code, HTTP status, and a safe message.

    Messages must never contain patient names, phone numbers, symptoms, or notes.
    """

    code: ClassVar[ErrorCode]
    status_code: ClassVar[int]

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailed(DomainError):
    code, status_code = ErrorCode.VALIDATION_ERROR, 400


class Unauthenticated(DomainError):
    code, status_code = ErrorCode.UNAUTHENTICATED, 401


class InvalidCredentials(DomainError):
    code, status_code = ErrorCode.INVALID_CREDENTIALS, 401


class Forbidden(DomainError):
    code, status_code = ErrorCode.FORBIDDEN, 403


class NotFound(DomainError):
    code, status_code = ErrorCode.NOT_FOUND, 404


class RateLimited(DomainError):
    code, status_code = ErrorCode.RATE_LIMITED, 429


class SlotAlreadyBooked(DomainError):
    code, status_code = ErrorCode.SLOT_ALREADY_BOOKED, 409


class PatientAlreadyBooked(DomainError):
    code, status_code = ErrorCode.PATIENT_ALREADY_BOOKED, 409


class InvalidSlot(DomainError):
    code, status_code = ErrorCode.INVALID_SLOT, 422


class EmergencyJustificationRequired(DomainError):
    code, status_code = ErrorCode.EMERGENCY_JUSTIFICATION_REQUIRED, 422


class EmergencyNotAuthorized(DomainError):
    code, status_code = ErrorCode.EMERGENCY_NOT_AUTHORIZED, 422


class CancellationWindowClosed(DomainError):
    code, status_code = ErrorCode.CANCELLATION_WINDOW_CLOSED, 422


class InvalidTransition(DomainError):
    code, status_code = ErrorCode.INVALID_TRANSITION, 409


class FollowUpWindowExceeded(DomainError):
    code, status_code = ErrorCode.FOLLOW_UP_WINDOW_EXCEEDED, 422


class AppointmentNotCompleted(DomainError):
    code, status_code = ErrorCode.APPOINTMENT_NOT_COMPLETED, 409


class PatientAlreadyExists(DomainError):
    code, status_code = ErrorCode.PATIENT_ALREADY_EXISTS, 409


class UserAlreadyExists(DomainError):
    code, status_code = ErrorCode.USER_ALREADY_EXISTS, 409


class DoctorAlreadyExists(DomainError):
    code, status_code = ErrorCode.DOCTOR_ALREADY_EXISTS, 409


class SpecialtyAlreadyExists(DomainError):
    code, status_code = ErrorCode.SPECIALTY_ALREADY_EXISTS, 409


class AvailabilityOverlap(DomainError):
    code, status_code = ErrorCode.AVAILABILITY_OVERLAP, 409


class AvailabilityConflictsWithAppointments(DomainError):
    code, status_code = ErrorCode.AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS, 409


class VisitNoteNotWritable(DomainError):
    code, status_code = ErrorCode.VISIT_NOTE_NOT_WRITABLE, 409


class VisitNoteLocked(DomainError):
    code, status_code = ErrorCode.VISIT_NOTE_LOCKED, 409


class NoNotesToDraft(DomainError):
    code, status_code = ErrorCode.NO_NOTES_TO_DRAFT, 422


class AiServiceUnavailable(DomainError):
    code, status_code = ErrorCode.AI_SERVICE_UNAVAILABLE, 503


class InternalError(DomainError):
    code, status_code = ErrorCode.INTERNAL_ERROR, 500


ERROR_CLASSES: dict[ErrorCode, type[DomainError]] = {
    cls.code: cls for cls in DomainError.__subclasses__()
}
