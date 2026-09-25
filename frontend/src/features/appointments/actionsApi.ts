import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { Appointment } from './appointmentsApi'

export type Action =
  | 'check-in'
  | 'start-consultation'
  | 'complete'
  | 'no-show'
  | 'cancel'
  | 'force-cancel'
  | 'reschedule'
  | 'follow-up'

/** POST /appointments/{id}/{action}; refreshes the appointment, lists and slot searches. */
export function useAppointmentAction(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ action, body }: { action: Action; body?: unknown }) =>
      api.request<Appointment>('POST', `/appointments/${id}/${action}`, { body }),
    onSuccess: () =>
      Promise.all(
        ['appointment', 'appointments', 'slots', 'queue'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      ),
  })
}
