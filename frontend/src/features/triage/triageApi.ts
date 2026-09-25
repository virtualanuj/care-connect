import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type TriageResult = components['schemas']['AITriageResult']
export type Urgency = components['schemas']['Urgency']

export const useTriageHistory = (patientId: string) =>
  useQuery({
    queryKey: ['triage', patientId],
    queryFn: () => api.request<TriageResult[]>('GET', `/patients/${patientId}/triage`),
  })

export function useRunTriage(patientId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reportedSymptoms: string) =>
      api.request<TriageResult>('POST', `/patients/${patientId}/triage`, {
        body: { reportedSymptoms },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triage', patientId] }),
  })
}

export function useOverrideTriage(triageId: string, patientId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      overriddenUrgency: Urgency
      overrideReason: string
      overriddenSpecialtyId?: string
    }) => api.request<TriageResult>('PATCH', `/triage-results/${triageId}/override`, { body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triage', patientId] }),
  })
}
