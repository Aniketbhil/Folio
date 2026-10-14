import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { BrandLogo } from '../layout/BrandLogo'

interface LocationState {
  from?: {
    pathname: string
  }
}

export const PublicRoute: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-bg dark:bg-dark-bg flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center gap-4 animate-pulse">
          <BrandLogo />
          <div className="flex items-center gap-2 text-xs text-surface-text-muted dark:text-dark-text-muted font-mono">
            <span className="inline-block w-2 h-2 rounded-full bg-brand-500 animate-ping" />
            Loading Folio...
          </div>
        </div>
      </div>
    )
  }

  if (isAuthenticated) {
    const state = location.state as LocationState | null
    const origin = state?.from?.pathname || '/overview'
    return <Navigate to={origin} replace />
  }

  return <>{children}</>
}
