import { apiRequest } from './client'
import type {
  AuthResponse,
  AuthStudent,
  ChangePasswordRequest,
  ChangePasswordResponse,
  LoginRequest,
  SignupRequest,
} from '../types/auth'

/**
 * Register a new student account.
 * Endpoint: POST /api/v1/auth/signup
 */
export async function signup(
  payload: SignupRequest,
  signal?: AbortSignal
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/auth/signup', {
    method: 'POST',
    body: payload,
    signal,
  })
}

/**
 * Authenticate student credentials and obtain an access token.
 * Endpoint: POST /api/v1/auth/login
 */
export async function login(
  payload: LoginRequest,
  signal?: AbortSignal
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>('/auth/login', {
    method: 'POST',
    body: payload,
    signal,
  })
}

/**
 * Retrieve the current authenticated student profile.
 * Endpoint: GET /api/v1/auth/me
 */
export async function getMe(signal?: AbortSignal): Promise<AuthStudent> {
  return apiRequest<AuthStudent>('/auth/me', {
    method: 'GET',
    signal,
  })
}

/**
 * Change the password for the current authenticated student.
 * Endpoint: POST /api/v1/auth/change-password
 */
export async function changePassword(
  payload: ChangePasswordRequest,
  signal?: AbortSignal
): Promise<ChangePasswordResponse> {
  return apiRequest<ChangePasswordResponse>('/auth/change-password', {
    method: 'POST',
    body: payload,
    signal,
  })
}
