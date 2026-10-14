import { createContext } from 'react'
import type { AuthStudent, LoginRequest, SignupRequest } from '../types/auth'

export interface AuthContextValue {
  user: AuthStudent | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (payload: LoginRequest) => Promise<void>
  register: (payload: SignupRequest) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  clearError: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
