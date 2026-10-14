import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BookOpenIcon, MenuIcon, UserIcon } from '../ui/Icons'
import { BrandLogo } from './BrandLogo'
import { ThemeToggle } from './ThemeToggle'
import { useAuth } from '../../context/useAuth'
import { useStudent } from '../../context/useStudent'
import { useCourse } from '../../context/useCourse'
import { LogOut } from 'lucide-react'

export interface HeaderProps {
  onOpenMobileNav: () => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileNav }) => {
  const { user, logout } = useAuth()
  const { activeStudent } = useStudent()
  const { activeCourse } = useCourse()
  const location = useLocation()

  // Derive readable breadcrumb from route
  const getRouteTitle = (pathname: string): string => {
    switch (pathname) {
      case '/profile':
      case '/students':
        return 'Profile'
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
      case '/overview':
      case '/':
      default:
        return 'Overview'
    }
  }

  const currentSectionTitle = getRouteTitle(location.pathname)
  const studentName = activeStudent?.name || user?.name || 'Profile'

  return (
    <header
      className="h-14 shrink-0 bg-surface-card/95 dark:bg-dark-card/95 backdrop-blur-xs border-b border-surface-border dark:border-dark-border px-3 sm:px-5 md:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-30 transition-colors"
      role="banner"
    >
      {/* Left: Mobile Menu Trigger + Brand on Mobile; Breadcrumb on Desktop */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenMobileNav}
          className="md:hidden -ml-1 p-2 rounded-lg text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 cursor-pointer shrink-0"
          aria-label="Open mobile navigation menu"
        >
          <MenuIcon className="w-5 h-5" />
        </button>

        {/* Mobile Brand Logo */}
        <div className="md:hidden flex items-center min-w-0">
          <Link
            to="/overview"
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded flex items-center"
            aria-label="Folio Overview"
          >
            <BrandLogo showTagline={false} compactBadge={true} />
          </Link>
        </div>

        {/* Desktop Breadcrumb Section */}
        <div className="hidden md:flex items-center gap-2 text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted truncate">
          <Link
            to="/overview"
            className="font-medium hover:text-surface-text dark:hover:text-dark-text transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
          >
            Folio
          </Link>
          <span className="text-surface-border dark:text-dark-border select-none">/</span>
          <span className="font-semibold text-surface-text dark:text-dark-text truncate">
            {currentSectionTitle}
          </span>
        </div>
      </div>

      {/* Right: Active Context Controls & ThemeToggle */}
      <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
        {/* Active Course Control */}
        <Link
          to="/courses"
          className="relative inline-flex items-center gap-1.5 p-1.5 sm:px-2.5 sm:py-1 rounded-md text-xs font-medium border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 bg-surface-card dark:bg-dark-card border-surface-border dark:border-dark-border hover:bg-surface-muted dark:hover:bg-dark-muted"
          title={
            activeCourse
              ? `Active Course: ${activeCourse.name} (Click to change)`
              : 'No course selected (Click to choose a course)'
          }
          aria-label={
            activeCourse
              ? `Active Course: ${activeCourse.name}`
              : 'Select active course'
          }
        >
          <BookOpenIcon
            className={`w-3.5 h-3.5 shrink-0 ${
              activeCourse
                ? 'text-brand-600 dark:text-brand-400'
                : 'text-surface-text-muted dark:text-dark-text-muted'
            }`}
          />
          <span className="hidden sm:inline max-w-28 md:max-w-36 lg:max-w-44 truncate text-surface-text dark:text-dark-text">
            {activeCourse ? activeCourse.name : 'Select Course'}
          </span>
          <span
            className={`sm:hidden absolute -top-1 -right-1 w-2 h-2 rounded-full ring-2 ring-surface-card dark:ring-dark-card ${
              activeCourse ? 'bg-brand-500' : 'bg-amber-500'
            }`}
            aria-hidden="true"
          />
        </Link>

        {/* Authenticated Profile Control */}
        <Link
          to="/profile"
          className="relative inline-flex items-center gap-1.5 p-1.5 sm:px-2.5 sm:py-1 rounded-md text-xs font-medium border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 bg-surface-card dark:bg-dark-card border-surface-border dark:border-dark-border hover:bg-surface-muted dark:hover:bg-dark-muted"
          title={`Profile: ${studentName}`}
          aria-label={`Student Profile: ${studentName}`}
        >
          <UserIcon className="w-3.5 h-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
          <span className="hidden sm:inline max-w-24 md:max-w-32 lg:max-w-40 truncate text-surface-text dark:text-dark-text">
            {studentName}
          </span>
          <span
            className="sm:hidden absolute -top-1 -right-1 w-2 h-2 rounded-full ring-2 ring-surface-card dark:ring-dark-card bg-brand-500"
            aria-hidden="true"
          />
        </Link>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Quick Sign Out Action */}
        <button
          type="button"
          onClick={logout}
          className="p-1.5 rounded-md text-surface-text-muted hover:text-red-600 hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-red-400 dark:hover:bg-dark-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 cursor-pointer"
          title="Sign out of Folio"
          aria-label="Sign out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
