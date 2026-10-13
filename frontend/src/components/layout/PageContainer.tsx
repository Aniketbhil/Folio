import React from 'react'

export interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  maxWidth?: 'standard' | 'wide' | 'narrow' | 'full'
}

export const PageContainer: React.FC<PageContainerProps> = ({
  children,
  maxWidth = 'standard',
  className = '',
  ...props
}) => {
  const maxWidthStyles = {
    narrow: 'max-w-4xl',
    standard: 'max-w-7xl',
    wide: 'max-w-[1600px]',
    full: 'max-w-full',
  }[maxWidth]

  return (
    <div
      className={`w-full mx-auto px-4 sm:px-5 md:px-6 lg:px-8 py-4 sm:py-6 space-y-5 sm:space-y-6 ${maxWidthStyles} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export interface PageHeaderProps {
  title: string
  description?: string
  badge?: React.ReactNode
  actions?: React.ReactNode
  className?: string
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  badge,
  actions,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-1 border-b border-surface-border-subtle dark:border-dark-border-subtle ${className}`}
    >
      <div className="space-y-1 min-w-0">
        <div className="flex items-center gap-2.5 flex-wrap">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-surface-text dark:text-dark-text truncate">
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted max-w-3xl leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 sm:self-center shrink-0 flex-wrap">
          {actions}
        </div>
      )}
    </div>
  )
}
