import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type DoctorCreate = components['schemas']['DoctorCreate']
export type DoctorUpdate = components['schemas']['DoctorUpdate']
export type SpecialtyCreate = components['schemas']['SpecialtyCreate']
export type SpecialtyUpdate = components['schemas']['SpecialtyUpdate']
type UserPage = components['schemas']['UserPage']

/** User accounts (front-desk only) used to pick who a new doctor profile belongs to. */
export const useAccounts = (enabled: boolean) =>
  useQuery({
    queryKey: ['accounts'],
    queryFn: () => api.request<UserPage>('GET', '/users', { query: { page: 1, pageSize: 100 } }),
    enabled,
  })

function useInvalidating<TVariables>(
  fn: (variables: TVariables) => Promise<unknown>,
  keys: string[],
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () =>
      Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key] }))),
  })
}

export const useCreateDoctor = () =>
  useInvalidating((body: DoctorCreate) => api.request('POST', '/doctors', { body }), ['doctors'])

export const useUpdateDoctor = () =>
  useInvalidating(
    ({ id, body }: { id: string; body: DoctorUpdate }) =>
      api.request('PATCH', `/doctors/${id}`, { body }),
    ['doctors'],
  )

export const useCreateSpecialty = () =>
  useInvalidating(
    (body: SpecialtyCreate) => api.request('POST', '/specialties', { body }),
    ['specialties'],
  )

export const useUpdateSpecialty = () =>
  useInvalidating(
    ({ id, body }: { id: string; body: SpecialtyUpdate }) =>
      api.request('PATCH', `/specialties/${id}`, { body }),
    ['specialties'],
  )
