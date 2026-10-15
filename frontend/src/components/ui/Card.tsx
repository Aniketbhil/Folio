import React from 'react'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'muted' | 'interactive'
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    {
      children,
      variant = 'default',
      padding = 'md',
      className = '',
      ...props
    },
    ref
  ) => {
    const baseStyles = 'rounded-xl border transition-colors overflow-hidden'

    const variantStyles = {
      default:
        'bg-surface-card border-surface-border shadow-xs dark:bg-dark-card dark:border-dark-border',
      muted:
        'bg-surface-muted border-surface-border-subtle dark:bg-dark-muted dark:border-dark-border-subtle',
      interactive:
        'bg-surface-card border-surface-border shadow-xs hover:border-brand-500/50 hover:shadow-sm active:scale-[0.99] cursor-pointer dark:bg-dark-card dark:border-dark-border dark:hover:border-brand-500/50 transition-all duration-150',
    }[variant]

    // Spacing scale: compact on mobile (14-16px), comfortable on desktop (16-20px)
    const paddingStyles = {
      none: '',
      sm: 'p-3 sm:p-3.5',
      md: 'p-3.5 sm:p-4 md:p-5',
      lg: 'p-4 sm:p-5 md:p-6',
    }[padding]

    return (
      <div
        ref={ref}
        className={`${baseStyles} ${variantStyles} ${paddingStyles} ${className}`}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <div className={`flex flex-col space-y-1 mb-3 sm:mb-4 ${className}`} {...props}>
    {children}
  </div>
)

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <h3
    className={`text-base sm:text-lg font-semibold tracking-tight text-surface-text dark:text-dark-text ${className}`}
    {...props}
  >
    {children}
  </h3>
)

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <p
    className={`text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed ${className}`}
    {...props}
  >
    {children}
  </p>
)

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => <div className={`space-y-3 ${className}`} {...props}>{children}</div>

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  children,
  ...props
}) => (
  <div
    className={`flex items-center justify-between pt-3 sm:pt-4 mt-3 sm:mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle ${className}`}
    {...props}
  >
    {children}
  </div>
)
