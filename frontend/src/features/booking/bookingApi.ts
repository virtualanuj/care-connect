import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type Slot = components['schemas']['Slot']
export type Appointment = components['schemas']['Appointment']
export type AppointmentCreate = components['schemas']['AppointmentCreate']

export interface SlotQuery {
  mode: 'doctor' | 'specialty'
  doctorId: string
  specialtyId: string
  date: string
}

export const useSlots = (query: SlotQuery | null) =>
  useQuery({
    queryKey: ['slots', query],
    enabled: query !== null,
    queryFn: () =>
      api.request<Slot[]>('GET', '/slots', {
        query: {
          date: query!.date,
          doctorId: query!.mode === 'doctor' ? query!.doctorId : undefined,
          specialtyId: query!.mode === 'specialty' ? query!.specialtyId : undefined,
        },
      }),
  })

export const useBook = () =>
  useMutation({
    mutationFn: (body: AppointmentCreate) =>
      api.request<Appointment>('POST', '/appointments', { body }),
  })
