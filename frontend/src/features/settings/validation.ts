import type { ClinicSettings } from './settingsApi'

export interface FormState {
  cutoff: string
  emergency: string
  followUp: string
  timezone: string
  triageSpecialty: string
}

export function toForm(settings: ClinicSettings): FormState {
  return {
    cutoff: String(settings.cancellationCutoffHours),
    emergency: String(settings.emergencySlotsPerDoctorPerDay),
    followUp: String(settings.followUpMaxDays),
    timezone: settings.clinicTimezone,
    triageSpecialty: settings.defaultTriageSpecialtyId ?? '',
  }
}

export function validate(form: FormState): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {}
  const cutoff = Number(form.cutoff)
  if (form.cutoff.trim() === '' || Number.isNaN(cutoff) || cutoff < 0) {
    errors.cutoff = 'Cancellation cutoff must be 0 or more hours.'
  }
  const emergency = Number(form.emergency)
  if (form.emergency.trim() === '' || !Number.isInteger(emergency) || emergency < 0) {
    errors.emergency = 'Emergency slots must be a whole number, 0 or more.'
  }
  const followUp = Number(form.followUp)
  if (form.followUp.trim() === '' || !Number.isInteger(followUp) || followUp < 1) {
    errors.followUp = 'Follow-up window must be at least 1 day.'
  }
  if (!form.timezone) errors.timezone = 'Choose a time zone.'
  return errors
}
