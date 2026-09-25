import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { DoctorItem } from '../../api/referenceHooks'
import type { components } from '../../api/schema'

export type Rule = components['schemas']['Availability']
export type RuleCreate = components['schemas']['AvailabilityCreate']
export type RuleUpdate = components['schemas']['AvailabilityUpdate']
export type ExceptionItem = components['schemas']['AvailabilityException']
export type ExceptionCreate = components['schemas']['AvailabilityExceptionCreate']
export type DayOfWeek = components['schemas']['DayOfWeek']

export const DAYS: { value: DayOfWeek; label: string }[] = [
  { value: 'monday', label: 'Monday' },
  { value: 'tuesday', label: 'Tuesday' },
  { value: 'wednesday', label: 'Wednesday' },
  { value: 'thursday', label: 'Thursday' },
  { value: 'friday', label: 'Friday' },
  { value: 'saturday', label: 'Saturday' },
  { value: 'sunday', label: 'Sunday' },
]

export const useDoctor = (id: string) =>
  useQuery({
    queryKey: ['doctor', id],
    queryFn: () => api.request<DoctorItem>('GET', `/doctors/${id}`),
  })

export const useRules = (id: string) =>
  useQuery({
    queryKey: ['rules', id],
    queryFn: () => api.request<Rule[]>('GET', `/doctors/${id}/availability`),
  })

export const useExceptions = (id: string) =>
  useQuery({
    queryKey: ['exceptions', id],
    queryFn: () => api.request<ExceptionItem[]>('GET', `/doctors/${id}/availability-exceptions`),
  })

function useInvalidating<TVariables>(
  doctorId: string,
  key: 'rules' | 'exceptions',
  fn: (variables: TVariables) => Promise<unknown>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [key, doctorId] }),
  })
}

export const useAddRule = (doctorId: string) =>
  useInvalidating(doctorId, 'rules', (body: RuleCreate) =>
    api.request('POST', `/doctors/${doctorId}/availability`, { body }),
  )

export const useUpdateRule = (doctorId: string) =>
  useInvalidating(doctorId, 'rules', ({ id, body }: { id: string; body: RuleUpdate }) =>
    api.request('PATCH', `/doctors/${doctorId}/availability/${id}`, { body }),
  )

export const useDeleteRule = (doctorId: string) =>
  useInvalidating(doctorId, 'rules', (id: string) =>
    api.request('DELETE', `/doctors/${doctorId}/availability/${id}`),
  )

export const useAddException = (doctorId: string) =>
  useInvalidating(doctorId, 'exceptions', (body: ExceptionCreate) =>
    api.request('POST', `/doctors/${doctorId}/availability-exceptions`, { body }),
  )

export const useDeleteException = (doctorId: string) =>
  useInvalidating(doctorId, 'exceptions', (id: string) =>
    api.request('DELETE', `/doctors/${doctorId}/availability-exceptions/${id}`),
  )
