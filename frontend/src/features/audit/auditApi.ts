import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type AuditAction = components['schemas']['AuditAction']
export type AuditEntry = components['schemas']['AuditLogEntry']
type AuditPage = components['schemas']['AuditLogPage']
type UserPage = components['schemas']['UserPage']

export const AUDIT_PAGE_SIZE = 20

export const ACTION_LABELS: Record<AuditAction, string> = {
  force_cancel: 'Force cancel',
  triage_override: 'Triage override',
  emergency_authorization: 'Emergency authorization',
  user_created: 'User created',
  user_updated: 'User updated',
  password_reset: 'Password reset',
  clinic_settings_changed: 'Clinic settings changed',
}

export const useAuditLog = (action: AuditAction | '', page: number) =>
  useQuery({
    queryKey: ['audit', action, page],
    queryFn: () =>
      api.request<AuditPage>('GET', '/audit-log', {
        query: { action: action || undefined, page, pageSize: AUDIT_PAGE_SIZE },
      }),
    placeholderData: keepPreviousData,
  })

/** Staff id → name, so the log shows who acted rather than a UUID. */
export const useStaffNames = () =>
  useQuery({
    queryKey: ['staff-names'],
    queryFn: async () => {
      const page = await api.request<UserPage>('GET', '/users', {
        query: { page: 1, pageSize: 100 },
      })
      return new Map(page.items.map((u) => [u.id, u.name]))
    },
  })
