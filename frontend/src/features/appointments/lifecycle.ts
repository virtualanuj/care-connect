import type { Action } from './actionsApi'
import type { Appointment } from './appointmentsApi'

/** The forward-moving lifecycle actions and the statuses they apply to (docs/spec.md §3). */
export const LIFECYCLE: { action: Action; label: string; from: Appointment['status'][] }[] = [
  { action: 'check-in', label: 'Check in', from: ['booked'] },
  { action: 'start-consultation', label: 'Start consultation', from: ['checked_in'] },
  { action: 'complete', label: 'Complete', from: ['in_consultation'] },
  { action: 'no-show', label: 'No-show', from: ['booked', 'checked_in'] },
]
