/**
 * Authentication and authorization schemas matching backend/app/schemas/auth.py
 */

export interface SignupRequest {
  name: string
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface AuthStudent {
  id: number
  name: string
  email?: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  student: AuthStudent
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ChangePasswordResponse {
  changed: boolean
}

export interface AuthState {
  user: AuthStudent | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}
