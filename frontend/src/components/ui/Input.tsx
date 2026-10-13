import React from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  helperText?: string
  error?: string
  leftIcon?: React.ReactNode
  rightSlot?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      helperText,
      error,
      leftIcon,
      rightSlot,
      id,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

    return (
      <div className="w-full space-y-1">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs sm:text-sm font-medium text-surface-text dark:text-dark-text"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="absolute left-3 flex items-center pointer-events-none text-surface-text-muted dark:text-dark-text-muted">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            className={`w-full rounded-lg text-sm bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text border ${
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
                : 'border-surface-border dark:border-dark-border focus:border-brand-500 focus:ring-brand-500/20'
            } ${leftIcon ? 'pl-9' : 'pl-3.5'} ${
              rightSlot ? 'pr-9' : 'pr-3.5'
            } py-2 min-h-10 placeholder:text-surface-text-muted/60 dark:placeholder:text-dark-text-muted/60 transition-colors focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
            {...props}
          />
          {rightSlot && (
            <div className="absolute right-3 flex items-center text-surface-text-muted dark:text-dark-text-muted">
              {rightSlot}
            </div>
          )}
        </div>
        {error ? (
          <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>
        ) : helperText ? (
          <p className="text-xs text-surface-text-muted dark:text-dark-text-muted mt-1">
            {helperText}
          </p>
        ) : null}
      </div>
    )
  }
)

Input.displayName = 'Input'
