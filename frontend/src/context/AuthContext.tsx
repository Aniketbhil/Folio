import React, { useCallback, useEffect, useState } from 'react'
import {
  clearAuthToken,
  getAuthToken,
  setAuthToken,
  setUnauthorizedHandler,
} from '../api/client'
import { getMe, login as apiLogin, signup as apiSignup } from '../api/auth'
import { formatApiError } from '../api/errors'
import { AuthContext } from './authContextDef'
import type { AuthStudent, LoginRequest, SignupRequest } from '../types/auth'

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [token, setTokenState] = useState<string | null>(() => getAuthToken())
  const [user, setUser] = useState<AuthStudent | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(() => !!getAuthToken())
  const [error, setError] = useState<string | null>(null)

  // Handle centralized 401s from client.ts
  const handleUnauthorized = useCallback(() => {
    setUser(null)
    setTokenState(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(handleUnauthorized)
    return () => {
      setUnauthorizedHandler(null)
    }
  }, [handleUnauthorized])

  // Bootstrap user profile on startup if token is present
  useEffect(() => {
    let isMounted = true
    const storedToken = getAuthToken()

    if (!storedToken) {
      return
    }

    getMe()
      .then((student) => {
        if (isMounted) {
          setUser(student)
          setTokenState(storedToken)
          setIsLoading(false)
        }
      })
      .catch(() => {
        if (isMounted) {
          clearAuthToken()
          setTokenState(null)
          setUser(null)
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [])

  const login = useCallback(async (payload: LoginRequest) => {
    setError(null)
    try {
      const response = await apiLogin(payload)
      setAuthToken(response.access_token)
      setTokenState(response.access_token)
      setUser(response.student)
    } catch (err) {
      const msg = formatApiError(err, 'Failed to sign in. Please verify your credentials.')
      setError(msg)
      throw err
    }
  }, [])

  const register = useCallback(async (payload: SignupRequest) => {
    setError(null)
    try {
      await apiSignup(payload)
      // Account created successfully on backend. User is redirected to login to authenticate.
    } catch (err) {
      const msg = formatApiError(err, 'Failed to create account. Please check your details.')
      setError(msg)
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    clearAuthToken()
    setTokenState(null)
    setUser(null)
    setError(null)
  }, [])

  const refreshUser = useCallback(async () => {
    if (!getAuthToken()) return
    try {
      const student = await getMe()
      setUser(student)
    } catch (err) {
      console.warn('Failed to refresh user profile:', err)
    }
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const isAuthenticated = !!token && !!user

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        isLoading,
        error,
        login,
        register,
        logout,
        refreshUser,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
