import React from 'react'
import { MenuIcon, UserIcon } from '../ui/Icons'
import { BrandLogo } from './BrandLogo'
import { ThemeToggle } from './ThemeToggle'

export interface HeaderProps {
  onOpenMobileNav: () => void
  currentSectionTitle?: string
}

export const Header: React.FC<HeaderProps> = ({
  onOpenMobileNav,
  currentSectionTitle = 'Overview',
}) => {
  return (
    <header
      className="h-14 shrink-0 bg-surface-card/95 dark:bg-dark-card/95 backdrop-blur-xs border-b border-surface-border dark:border-dark-border px-4 sm:px-5 md:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-30 transition-colors"
      role="banner"
    >
      {/* Left: Mobile Menu Trigger + Brand on Mobile; Breadcrumb on Desktop */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenMobileNav}
          className="md:hidden -ml-1.5 p-2 rounded-lg text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 cursor-pointer"
          aria-label="Open mobile navigation menu"
        >
          <MenuIcon className="w-5 h-5" />
        </button>

        {/* Mobile Brand Logo */}
        <div className="md:hidden">
          <BrandLogo showTagline={false} />
        </div>

        {/* Desktop Breadcrumb Section */}
        <div className="hidden md:flex items-center gap-2 text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
          <span className="font-medium text-surface-text-muted dark:text-dark-text-muted">
            Folio
          </span>
          <span className="text-surface-border dark:text-dark-border select-none">/</span>
          <span className="font-semibold text-surface-text dark:text-dark-text">
            {currentSectionTitle}
          </span>
        </div>
      </div>

      {/* Right: Actions, Course/Student Context, ThemeToggle */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Workspace context badge */}
        <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border text-surface-text-muted dark:text-dark-text-muted">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500" aria-hidden="true" />
          <span>Active Course</span>
        </div>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Student Avatar / Profile Pill */}
        <div
          className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-lg border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card hover:bg-surface-muted dark:hover:bg-dark-muted transition-colors cursor-pointer select-none text-xs font-medium"
          title="Student Profile"
          role="button"
          tabIndex={0}
          aria-label="Student account"
        >
          <div className="w-6 h-6 rounded-full bg-brand-100 dark:bg-brand-950 flex items-center justify-center text-brand-700 dark:text-brand-300">
            <UserIcon className="w-3.5 h-3.5" />
          </div>
          <span className="hidden sm:inline text-surface-text dark:text-dark-text">
            Student
          </span>
        </div>
      </div>
    </header>
  )
}
