import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, useSyncExternalStore, type ReactNode } from 'react'

import { api } from '../api/api'
import type { paths } from '../api/schema'
import { AuthContext, type AuthState, type User } from './authContext'
import { tokenStore } from './tokenStore'

type TokenResponse = paths['/auth/login']['post']['responses']['200']['content']['application/json']

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const token = useSyncExternalStore(tokenStore.subscribe, tokenStore.get)

  const me = useQuery({
    queryKey: ['me', token],
    queryFn: () => api.request<User>('GET', '/auth/me'),
    enabled: token !== null,
    staleTime: Infinity,
  })

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.request<TokenResponse>('POST', '/auth/login', {
      body: { email, password },
    })
    tokenStore.set(result.accessToken)
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    queryClient.clear()
  }, [queryClient])

  const value = useMemo<AuthState>(() => {
    const status =
      token === null
        ? 'anonymous'
        : me.isSuccess
          ? 'authenticated'
          : me.isError
            ? 'anonymous'
            : 'loading'
    return { user: me.data ?? null, status, login, logout }
  }, [token, me.isSuccess, me.isError, me.data, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
