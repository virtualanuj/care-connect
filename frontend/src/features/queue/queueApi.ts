import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type DailyQueue = components['schemas']['DailyQueue']
export type QueueItem = components['schemas']['QueueItem']

/** How often the dashboard refreshes on its own (also refreshed after every action). */
export const REFRESH_MS = 15_000

export const useQueue = (date: string) =>
  useQuery({
    queryKey: ['queue', date],
    queryFn: () => api.request<DailyQueue>('GET', '/queue', { query: { date: date || undefined } }),
    refetchInterval: REFRESH_MS,
  })
