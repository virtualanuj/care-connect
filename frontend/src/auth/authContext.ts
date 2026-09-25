import { createContext } from 'react'

import type { components } from '../api/schema'

export type User = components['schemas']['User']
export type Role = components['schemas']['Role']

export interface AuthState {
  user: User | null
  status: 'loading' | 'authenticated' | 'anonymous'
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)
