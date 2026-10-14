import React, { useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { CloseIcon } from '../ui/Icons'
import { BrandLogo } from './BrandLogo'
import { MAIN_NAV_ITEMS, UPCOMING_NAV_ITEMS } from './navItems'
import { useStudent } from '../../context/useStudent'
import { useCourse } from '../../context/useCourse'

export interface MobileNavProps {
  isOpen: boolean
  onClose: () => void
}

export const MobileNav: React.FC<MobileNavProps> = ({
  isOpen,
  onClose,
}) => {
  const { activeStudent } = useStudent()
  const { activeCourse } = useCourse()

  // Lock body scroll while drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Handle ESC key to dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation drawer">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer surface */}
      <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] bg-surface-card dark:bg-dark-card border-r border-surface-border dark:border-dark-border shadow-xl flex flex-col z-10">
        {/* Header with Brand and Close button */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-surface-border dark:border-dark-border">
          <NavLink to="/" onClick={onClose}>
            <BrandLogo />
          </NavLink>
          <button
            type="button"
            onClick={onClose}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 cursor-pointer"
            aria-label="Close navigation menu"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto" aria-label="Mobile application navigation">
          <div className="space-y-1">
            <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted/80 dark:text-dark-text-muted/80">
              Workspace
            </div>
            {MAIN_NAV_ITEMS.map((item) => {
              const Icon = item.icon

              return (
                <NavLink
                  key={item.id}
                  to={item.path}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `w-full min-h-11 flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                      isActive
                        ? 'bg-brand-50 text-brand-800 dark:bg-brand-950/70 dark:text-brand-200 font-semibold'
                        : 'text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div className="flex items-center gap-3">
                        <Icon
                          className={`w-4 h-4 shrink-0 ${
                            isActive
                              ? 'text-brand-600 dark:text-brand-400'
                              : 'text-surface-text-muted dark:text-dark-text-muted'
                          }`}
                        />
                        <span>{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-200">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              )
            })}
          </div>

          <div className="space-y-1 pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle">
            <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted/80 dark:text-dark-text-muted/80">
              Upcoming Modules
            </div>
            {UPCOMING_NAV_ITEMS.map((item) => {
              const Icon = item.icon

              return (
                <div
                  key={item.id}
                  className="w-full min-h-10 flex items-center justify-between px-3.5 py-2 rounded-lg text-sm text-surface-text-muted/50 dark:text-dark-text-muted/50 cursor-not-allowed select-none"
                  aria-disabled="true"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 shrink-0 text-surface-text-muted/40 dark:text-dark-text-muted/40" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-surface-muted text-surface-text-muted/70 dark:bg-dark-muted dark:text-dark-text-muted/70 border border-surface-border-subtle dark:border-dark-border-subtle">
                      {item.badge}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </nav>

        {/* Mobile footer: Real Active Context */}
        <div className="p-3 border-t border-surface-border dark:border-dark-border bg-surface-muted/30 dark:bg-dark-muted/30 space-y-1">
          <div className="text-xs truncate">
            <span className="text-surface-text-muted dark:text-dark-text-muted">Student: </span>
            <span className="font-semibold text-surface-text dark:text-dark-text">
              {activeStudent ? activeStudent.name : 'None selected'}
            </span>
          </div>
          <div className="text-xs truncate">
            <span className="text-surface-text-muted dark:text-dark-text-muted">Course: </span>
            <span className="font-semibold text-surface-text dark:text-dark-text">
              {activeCourse ? activeCourse.name : 'None selected'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
