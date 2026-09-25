import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../api/api'
import type { components } from '../../api/schema'

export type UserItem = components['schemas']['User']
export type UserPageData = components['schemas']['UserPage']
export type UserCreate = components['schemas']['UserCreate']
export type UserUpdate = components['schemas']['UserUpdate']

export const PAGE_SIZE = 10

export function useUsers(page: number) {
  return useQuery({
    queryKey: ['users', page],
    queryFn: () =>
      api.request<UserPageData>('GET', '/users', { query: { page, pageSize: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  })
}

function useUsersMutation<TVariables>(fn: (variables: TVariables) => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export const useCreateUser = () =>
  useUsersMutation((body: UserCreate) => api.request('POST', '/users', { body }))

export const useUpdateUser = () =>
  useUsersMutation(({ id, body }: { id: string; body: UserUpdate }) =>
    api.request('PATCH', `/users/${id}`, { body }),
  )

export const useResetPassword = () =>
  useUsersMutation(({ id, newPassword }: { id: string; newPassword: string }) =>
    api.request('POST', `/users/${id}/reset-password`, { body: { newPassword } }),
  )
