import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'
import type { Patient } from '../patients/patientsApi'

export type Appointment = components['schemas']['Appointment']
export type AppointmentPageData = components['schemas']['AppointmentPage']
export type AppointmentStatus = components['schemas']['AppointmentStatus']

export const PAGE_SIZE = 20

export interface AppointmentFilters {
  date: string
  doctorId: string
  status: string
  page: number
}

export const STATUS_LABELS: Record<AppointmentStatus, string> = {
  booked: 'Booked',
  checked_in: 'Checked in',
  in_consultation: 'In consultation',
  completed: 'Completed',
  no_show: 'No-show',
  cancelled: 'Cancelled',
}

export const useAppointments = (filters: AppointmentFilters) =>
  useQuery({
    queryKey: ['appointments', filters],
    queryFn: () =>
      api.request<AppointmentPageData>('GET', '/appointments', {
        query: {
          date: filters.date || undefined,
          doctorId: filters.doctorId || undefined,
          status: filters.status || undefined,
          page: filters.page,
          pageSize: PAGE_SIZE,
        },
      }),
    placeholderData: keepPreviousData,
  })

export const useAppointment = (id: string) =>
  useQuery({
    queryKey: ['appointment', id],
    queryFn: () => api.request<Appointment>('GET', `/appointments/${id}`),
  })

export const usePatientNames = (ids: string[]) => {
  const unique = [...new Set(ids)]
  const results = useQueries({
    queries: unique.map((id) => ({
      queryKey: ['patient', id],
      queryFn: () => api.request<Patient>('GET', `/patients/${id}`),
      staleTime: 60_000,
    })),
  })
  return new Map(unique.map((id, i) => [id, results[i].data?.name] as const))
}
