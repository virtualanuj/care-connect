import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type ClinicSettings = components['schemas']['ClinicSettings']
export type ClinicSettingsUpdate = components['schemas']['ClinicSettingsUpdate']
export type SpecialtyItem = components['schemas']['Specialty']

export const useClinicSettings = () =>
  useQuery({
    queryKey: ['clinic-settings'],
    queryFn: () => api.request<ClinicSettings>('GET', '/clinic-settings'),
  })

export const useSpecialties = () =>
  useQuery({
    queryKey: ['specialties'],
    queryFn: () => api.request<SpecialtyItem[]>('GET', '/specialties'),
  })

export function useUpdateClinicSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ClinicSettingsUpdate) =>
      api.request<ClinicSettings>('PATCH', '/clinic-settings', { body }),
    onSuccess: (data) => queryClient.setQueryData(['clinic-settings'], data),
  })
}
