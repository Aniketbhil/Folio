import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { AppShell } from '../layout/AppShell'
import { BrandLogo } from '../layout/BrandLogo'

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({
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
            Authenticating session...
          </div>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <AppShell>{children}</AppShell>
}
