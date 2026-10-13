import React from 'react'
import { ChevronDownIcon } from './Icons'

export interface SelectOption {
  value: string | number
  label: string
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  helperText?: string
  error?: string
  options?: SelectOption[]
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      helperText,
      error,
      options,
      children,
      id,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

    return (
      <div className="w-full space-y-1">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-xs sm:text-sm font-medium text-surface-text dark:text-dark-text"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={`w-full appearance-none rounded-lg text-sm bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text border ${
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
                : 'border-surface-border dark:border-dark-border focus:border-brand-500 focus:ring-brand-500/20'
            } pl-3.5 pr-10 py-2 min-h-10 transition-colors focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
            {...props}
          >
            {options
              ? options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))
              : children}
          </select>
          <div className="absolute right-3 pointer-events-none flex items-center text-surface-text-muted dark:text-dark-text-muted">
            <ChevronDownIcon className="w-4 h-4" />
          </div>
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

Select.displayName = 'Select'
