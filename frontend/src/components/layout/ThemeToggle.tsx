import React from 'react'
import { useTheme } from '../../context/useTheme'
import { MoonIcon, SunIcon } from '../ui/Icons'

export const ThemeToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { isDark, toggleTheme } = useTheme()

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`relative inline-flex items-center justify-center w-9 h-9 rounded-lg border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text hover:bg-surface-muted dark:hover:bg-dark-muted transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-dark-card ${className}`}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {isDark ? (
        <SunIcon className="w-4 h-4 text-amber-500 transition-transform duration-200" />
      ) : (
        <MoonIcon className="w-4 h-4 text-surface-text-muted hover:text-surface-text transition-transform duration-200" />
      )}
    </button>
  )
}
