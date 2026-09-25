import { ApiError } from './client'
import type { ErrorCode } from './types'

/**
 * User-facing text for every API error code. Typed as an exhaustive Record so that adding a code
 * to docs/openapi.yaml (and regenerating src/api/schema.d.ts) fails typechecking until it is
 * handled here.
 */
export const ERROR_MESSAGES: Record<ErrorCode, string> = {
  VALIDATION_ERROR: 'Some of the information entered is invalid. Please check and try again.',
  UNAUTHENTICATED: 'Your session has expired. Please sign in again.',
  INVALID_CREDENTIALS: 'Incorrect email or password.',
  FORBIDDEN: 'You do not have permission to do that.',
  NOT_FOUND: 'That record could not be found.',
  RATE_LIMITED: 'Too many attempts. Please wait a few minutes and try again.',
  SLOT_ALREADY_BOOKED:
    'That time is no longer available for this doctor. Please pick another slot.',
  PATIENT_ALREADY_BOOKED: 'This patient already has an appointment that overlaps this time.',
  INVALID_SLOT: 'That is not a valid bookable slot. Please search for slots again.',
  EMERGENCY_JUSTIFICATION_REQUIRED:
    'An emergency slot needs a justification (triage or front-desk reason).',
  EMERGENCY_NOT_AUTHORIZED: 'The triage result does not authorize an emergency slot.',
  CANCELLATION_WINDOW_CLOSED:
    'This appointment is too close to its start time to change. Front-desk can force-cancel it.',
  INVALID_TRANSITION: 'That action is not allowed for the appointment in its current state.',
  FOLLOW_UP_WINDOW_EXCEEDED: 'The follow-up is too far after the original visit.',
  APPOINTMENT_NOT_COMPLETED: 'A follow-up can only be booked from a completed visit.',
  PATIENT_ALREADY_EXISTS: 'A patient with this name and phone number is already registered.',
  USER_ALREADY_EXISTS: 'A user with this email already exists.',
  AVAILABILITY_OVERLAP: 'That availability overlaps another rule for the same day.',
  AVAILABILITY_CONFLICTS_WITH_APPOINTMENTS:
    'That change would affect existing appointments. Cancel or reschedule them first.',
  VISIT_NOTE_NOT_WRITABLE: 'Notes can only be written once the consultation has started.',
  VISIT_NOTE_LOCKED: 'This visit summary has been finalized and can no longer be changed.',
  NO_NOTES_TO_DRAFT: 'Write some visit notes before requesting an AI draft.',
  AI_SERVICE_UNAVAILABLE: 'The AI assistant is unavailable right now. You can continue without it.',
  INTERNAL_ERROR: 'Something went wrong on our side. Please try again.',
}

export function messageForError(error: unknown): string {
  if (error instanceof ApiError) return ERROR_MESSAGES[error.code]
  return ERROR_MESSAGES.INTERNAL_ERROR
}
