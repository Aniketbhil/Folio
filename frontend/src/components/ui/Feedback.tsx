import React from 'react'
import { AlertCircleIcon, AlertTriangleIcon, CheckCircleIcon } from './Icons'

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'info' | 'success' | 'warning' | 'error'
  title?: string
  description?: string
  action?: React.ReactNode
  onDismiss?: () => void
}

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  description,
  action,
  onDismiss,
  className = '',
  children,
  ...props
}) => {
  const variantStyles = {
    info: 'bg-surface-muted text-surface-text border-surface-border dark:bg-dark-muted dark:text-dark-text dark:border-dark-border',
    success:
      'bg-emerald-50 text-emerald-950 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-800/80',
    warning:
      'bg-amber-50 text-amber-950 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-800/80',
    error:
      'bg-red-50 text-red-950 border-red-200 dark:bg-red-950/40 dark:text-red-200 dark:border-red-800/80',
  }[variant]

  const IconComponent = {
    info: AlertCircleIcon,
    success: CheckCircleIcon,
    warning: AlertTriangleIcon,
    error: AlertCircleIcon,
  }[variant]

  const iconColors = {
    info: 'text-surface-text-muted dark:text-dark-text-muted',
    success: 'text-emerald-600 dark:text-emerald-400',
    warning: 'text-amber-600 dark:text-amber-400',
    error: 'text-red-600 dark:text-red-400',
  }[variant]

  return (
    <div
      role="alert"
      className={`rounded-xl border p-3.5 sm:p-4 flex items-start gap-3 text-sm transition-colors ${variantStyles} ${className}`}
      {...props}
    >
      <div className={`shrink-0 mt-0.5 ${iconColors}`}>
        <IconComponent className="w-5 h-5" />
      </div>
      <div className="flex-1 space-y-0.5 min-w-0">
        {title && <h4 className="font-semibold text-sm leading-tight">{title}</h4>}
        {description && (
          <p className="text-xs sm:text-sm opacity-90 leading-relaxed">{description}</p>
        )}
        {children}
        {action && <div className="mt-2.5">{action}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 text-current opacity-60 hover:opacity-100 p-1 -mr-1 -mt-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          aria-label="Dismiss alert"
        >
          <span aria-hidden="true">&times;</span>
        </button>
      )}
    </div>
  )
}

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`rounded-xl border border-dashed border-surface-border dark:border-dark-border bg-surface-muted/40 dark:bg-dark-muted/40 p-6 sm:p-8 text-center flex flex-col items-center justify-center space-y-3 ${className}`}
      {...props}
    >
      {icon && (
        <div className="w-10 h-10 rounded-full bg-surface-muted dark:bg-dark-muted flex items-center justify-center text-surface-text-muted dark:text-dark-text-muted border border-surface-border dark:border-dark-border">
          {icon}
        </div>
      )}
      <div className="max-w-md space-y-1">
        <h4 className="text-base font-semibold text-surface-text dark:text-dark-text">{title}</h4>
        {description && (
          <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  )
}

export const LoadingState: React.FC<{
  message?: string
  className?: string
}> = ({ message = 'Loading...', className = '' }) => {
  return (
    <div
      className={`flex items-center justify-center gap-2.5 p-6 text-sm text-surface-text-muted dark:text-dark-text-muted ${className}`}
      role="status"
    >
      <svg
        className="animate-spin w-5 h-5 text-brand-600 dark:text-brand-400"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
      <span>{message}</span>
    </div>
  )
}
