import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type Patient = components['schemas']['Patient']
export type PatientPageData = components['schemas']['PatientPage']
export type PatientCreate = components['schemas']['PatientCreate']
export type PatientUpdate = components['schemas']['PatientUpdate']
export type HistoryEntry = components['schemas']['MedicalHistoryEntry']
export type HistoryCreate = components['schemas']['MedicalHistoryEntryCreate']

export const PAGE_SIZE = 20

export interface PatientSearch {
  phone: string
  name: string
  page: number
}

export const usePatients = (search: PatientSearch) =>
  useQuery({
    queryKey: ['patients', search],
    queryFn: () =>
      api.request<PatientPageData>('GET', '/patients', {
        query: {
          phone: search.phone || undefined,
          name: search.name || undefined,
          page: search.page,
          pageSize: PAGE_SIZE,
        },
      }),
    placeholderData: keepPreviousData,
  })

export const usePatient = (id: string) =>
  useQuery({
    queryKey: ['patient', id],
    queryFn: () => api.request<Patient>('GET', `/patients/${id}`),
  })

export const useHistory = (id: string) =>
  useQuery({
    queryKey: ['history', id],
    queryFn: () => api.request<HistoryEntry[]>('GET', `/patients/${id}/medical-history`),
  })

export function useRegisterPatient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: PatientCreate) => api.request<Patient>('POST', '/patients', { body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  })
}

export function useUpdatePatient(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: PatientUpdate) => api.request<Patient>('PATCH', `/patients/${id}`, { body }),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['patient', id] }),
        queryClient.invalidateQueries({ queryKey: ['patients'] }),
      ]),
  })
}

export function useAddHistory(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: HistoryCreate) =>
      api.request<HistoryEntry>('POST', `/patients/${id}/medical-history`, { body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['history', id] }),
  })
}
