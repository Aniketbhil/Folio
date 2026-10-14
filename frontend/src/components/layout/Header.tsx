import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BookOpenIcon, MenuIcon, UserIcon } from '../ui/Icons'
import { BrandLogo } from './BrandLogo'
import { ThemeToggle } from './ThemeToggle'
import { useStudent } from '../../context/useStudent'
import { useCourse } from '../../context/useCourse'

export interface HeaderProps {
  onOpenMobileNav: () => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileNav }) => {
  const { activeStudent } = useStudent()
  const { activeCourse } = useCourse()
  const location = useLocation()

  // Derive readable breadcrumb from route
  const getRouteTitle = (pathname: string): string => {
    switch (pathname) {
      case '/students':
        return 'Students'
      case '/courses':
        return 'Courses'
      case '/sources':
        return 'Sources & Library'
      case '/tutor':
        return 'AI Tutor'
      case '/assessments':
        return 'Assessments'
      case '/mastery':
        return 'Mastery & Knowledge'
      case '/':
      default:
        return 'Overview'
    }
  }

  const currentSectionTitle = getRouteTitle(location.pathname)

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
          <Link to="/" className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
            <BrandLogo showTagline={false} />
          </Link>
        </div>

        {/* Desktop Breadcrumb Section */}
        <div className="hidden md:flex items-center gap-2 text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
          <Link
            to="/"
            className="font-medium hover:text-surface-text dark:hover:text-dark-text transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
          >
            Folio
          </Link>
          <span className="text-surface-border dark:text-dark-border select-none">/</span>
          <span className="font-semibold text-surface-text dark:text-dark-text">
            {currentSectionTitle}
          </span>
        </div>
      </div>

      {/* Right: Active Context Pills & ThemeToggle */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Active Course Pill */}
        <Link
          to="/courses"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 bg-surface-card dark:bg-dark-card border-surface-border dark:border-dark-border hover:bg-surface-muted dark:hover:bg-dark-muted"
          title={activeCourse ? `Active Course: ${activeCourse.name}` : 'Click to select an active course'}
        >
          <BookOpenIcon
            className={`w-3.5 h-3.5 ${
              activeCourse ? 'text-brand-600 dark:text-brand-400' : 'text-surface-text-muted dark:text-dark-text-muted'
            }`}
          />
          <span className="max-w-25 sm:max-w-35 truncate text-surface-text dark:text-dark-text">
            {activeCourse ? activeCourse.name : 'Select Course'}
          </span>
        </Link>

        {/* Active Student Pill */}
        <Link
          to="/students"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 bg-surface-card dark:bg-dark-card border-surface-border dark:border-dark-border hover:bg-surface-muted dark:hover:bg-dark-muted"
          title={activeStudent ? `Active Student: ${activeStudent.name}` : 'Click to select an active student'}
        >
          <UserIcon
            className={`w-3.5 h-3.5 ${
              activeStudent ? 'text-brand-600 dark:text-brand-400' : 'text-surface-text-muted dark:text-dark-text-muted'
            }`}
          />
          <span className="max-w-20 sm:max-w-30 truncate text-surface-text dark:text-dark-text">
            {activeStudent ? activeStudent.name : 'Select Student'}
          </span>
        </Link>

        {/* Theme Toggle */}
        <ThemeToggle />
      </div>
    </header>
  )
}
