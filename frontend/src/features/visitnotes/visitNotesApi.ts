import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import { ApiError } from '../../api/client'
import type { components } from '../../api/schema'

export type PreVisitSummary = components['schemas']['PreVisitSummary']
export type VisitNote = components['schemas']['VisitNote']

/** A 404 means "nothing stored yet", which is a normal state for both resources. */
async function orNull<T>(request: Promise<T>): Promise<T | null> {
  try {
    return await request
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) return null
    throw caught
  }
}

export const useSummary = (appointmentId: string) =>
  useQuery({
    queryKey: ['summary', appointmentId],
    queryFn: () =>
      orNull(api.request<PreVisitSummary>('GET', `/appointments/${appointmentId}/summary`)),
  })

export function useGenerateSummary(appointmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.request<PreVisitSummary>('POST', `/appointments/${appointmentId}/summary`),
    onSuccess: (summary) => queryClient.setQueryData(['summary', appointmentId], summary),
  })
}

export const useVisitNote = (appointmentId: string, enabled: boolean) =>
  useQuery({
    queryKey: ['visit-note', appointmentId],
    enabled,
    queryFn: () =>
      orNull(api.request<VisitNote>('GET', `/appointments/${appointmentId}/visit-note`)),
  })

function useNoteMutation<V>(appointmentId: string, run: (variables: V) => Promise<VisitNote>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: (note) => queryClient.setQueryData(['visit-note', appointmentId], note),
  })
}

export const useSaveNotes = (appointmentId: string) =>
  useNoteMutation(appointmentId, (doctorNotes: string) =>
    api.request<VisitNote>('PUT', `/appointments/${appointmentId}/visit-note`, {
      body: { doctorNotes },
    }),
  )

export const useDraftNote = (appointmentId: string) =>
  useNoteMutation<void>(appointmentId, () =>
    api.request<VisitNote>('POST', `/appointments/${appointmentId}/visit-note/draft`),
  )

export const useFinalizeNote = (appointmentId: string) =>
  useNoteMutation(appointmentId, (finalSummary: string) =>
    api.request<VisitNote>('POST', `/appointments/${appointmentId}/visit-note/finalize`, {
      body: { finalSummary },
    }),
  )
