import React from 'react'

export type BadgeVariant =
  | 'neutral'
  | 'brand'
  | 'amber'
  | 'terracotta'
  | 'success'
  | 'warning'
  | 'error'

export type BadgeSize = 'sm' | 'md'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className = '',
  ...props
}) => {
  const baseStyles = 'inline-flex items-center font-medium rounded-full select-none'

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 gap-1 leading-tight',
    md: 'text-xs px-2.5 py-0.5 gap-1.5 leading-normal',
  }[size]

  const variantStyles = {
    neutral:
      'bg-surface-muted text-surface-text-muted border border-surface-border dark:bg-dark-muted dark:text-dark-text-muted dark:border-dark-border',
    brand:
      'bg-brand-50 text-brand-800 border border-brand-200 dark:bg-brand-950 dark:text-brand-200 dark:border-brand-800',
    amber:
      'bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800/80',
    terracotta:
      'bg-terracotta-50 text-terracotta-800 border border-terracotta-200 dark:bg-terracotta-950/60 dark:text-terracotta-200 dark:border-terracotta-800/80',
    success:
      'bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-800',
    warning:
      'bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800',
    error:
      'bg-red-50 text-red-800 border border-red-200 dark:bg-red-950/60 dark:text-red-200 dark:border-red-800',
  }[variant]

  const dotColors = {
    neutral: 'bg-surface-text-muted dark:bg-dark-text-muted',
    brand: 'bg-brand-600 dark:bg-brand-400',
    amber: 'bg-amber-600 dark:bg-amber-400',
    terracotta: 'bg-terracotta-600 dark:bg-terracotta-400',
    success: 'bg-emerald-600 dark:bg-emerald-400',
    warning: 'bg-amber-600 dark:bg-amber-400',
    error: 'bg-red-600 dark:bg-red-400',
  }[variant]

  return (
    <span className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`} {...props}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColors}`} aria-hidden="true" />}
      <span>{children}</span>
    </span>
  )
}
