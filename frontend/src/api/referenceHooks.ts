import { useQuery } from '@tanstack/react-query'

import { api } from './api'
import type { components } from './schema'

export type SpecialtyItem = components['schemas']['Specialty']
export type DoctorItem = components['schemas']['Doctor']

export const useSpecialties = () =>
  useQuery({
    queryKey: ['specialties'],
    queryFn: () => api.request<SpecialtyItem[]>('GET', '/specialties'),
  })

export const useDoctors = () =>
  useQuery({
    queryKey: ['doctors'],
    queryFn: () => api.request<DoctorItem[]>('GET', '/doctors'),
  })
