import React from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  fullWidth?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      fullWidth = false,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    // Base styles: clear typography, touch-friendly min targets, subtle transitions, accessible focus-visible
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-dark-card active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none disabled:active:scale-100'

    const sizeStyles = {
      sm: 'text-xs px-2.5 py-1.5 min-h-[34px] gap-1.5',
      md: 'text-sm px-3.5 py-2 min-h-[40px] gap-2',
      lg: 'text-base px-4.5 py-2.5 min-h-[44px] gap-2.5',
    }[size]

    const variantStyles = {
      primary:
        'bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 shadow-xs hover:shadow-sm dark:bg-brand-600 dark:hover:bg-brand-500',
      secondary:
        'bg-surface-muted text-surface-text border border-surface-border hover:bg-surface-border/60 hover:border-surface-text-muted/30 dark:bg-dark-muted dark:text-dark-text dark:border-dark-border dark:hover:bg-dark-border/80',
      outline:
        'bg-transparent text-surface-text border border-surface-border hover:bg-surface-muted hover:border-surface-text-muted/40 dark:text-dark-text dark:border-dark-border dark:hover:bg-dark-muted',
      ghost:
        'bg-transparent text-surface-text hover:bg-surface-muted dark:text-dark-text dark:hover:bg-dark-muted',
      danger:
        'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-xs dark:bg-red-600 dark:hover:bg-red-500',
    }[variant]

    const widthStyle = fullWidth ? 'w-full' : ''

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles} ${variantStyles} ${widthStyle} ${className}`}
        {...props}
      >
        {isLoading ? (
          <svg
            className="animate-spin -ml-0.5 w-4 h-4 text-current"
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
        ) : (
          leftIcon
        )}
        <span>{children}</span>
        {!isLoading && rightIcon}
      </button>
    )
  }
)

Button.displayName = 'Button'
