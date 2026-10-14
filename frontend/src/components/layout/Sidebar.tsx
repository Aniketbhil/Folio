import React from 'react'
import { NavLink } from 'react-router-dom'
import { BrandLogo } from './BrandLogo'
import { MAIN_NAV_ITEMS, UPCOMING_NAV_ITEMS } from './navItems'
import { useStudent } from '../../context/useStudent'
import { useCourse } from '../../context/useCourse'

export interface SidebarProps {
  className?: string
  onNavigate?: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  className = '',
  onNavigate,
}) => {
  const { activeStudent } = useStudent()
  const { activeCourse } = useCourse()

  return (
    <aside
      className={`w-60 lg:w-64 shrink-0 bg-surface-card dark:bg-dark-card border-r border-surface-border dark:border-dark-border flex flex-col h-screen sticky top-0 select-none ${className}`}
      aria-label="Main sidebar navigation"
    >
      {/* Brand Header */}
      <div className="h-14 px-5 flex items-center border-b border-surface-border dark:border-dark-border">
        <NavLink to="/" onClick={onNavigate} className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg">
          <BrandLogo />
        </NavLink>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto" aria-label="Application sections">
        {/* Core Workspace Routes */}
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
                onClick={onNavigate}
                className={({ isActive }) =>
                  `w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                    isActive
                      ? 'bg-brand-50 text-brand-800 dark:bg-brand-950/70 dark:text-brand-200 font-semibold'
                      : 'text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 transition-colors ${
                          isActive
                            ? 'text-brand-600 dark:text-brand-400'
                            : 'text-surface-text-muted dark:text-dark-text-muted'
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-200">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            )
          })}
        </div>

        {/* Upcoming Features (Accessibly disabled) */}
        <div className="space-y-1 pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle">
          <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted/80 dark:text-dark-text-muted/80">
            Learning Features
          </div>
          {UPCOMING_NAV_ITEMS.map((item) => {
            const Icon = item.icon

            return (
              <div
                key={item.id}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm text-surface-text-muted/50 dark:text-dark-text-muted/50 cursor-not-allowed select-none"
                aria-disabled="true"
                title={`${item.label} will be enabled in upcoming chapters`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className="w-4 h-4 shrink-0 text-surface-text-muted/40 dark:text-dark-text-muted/40" />
                  <span className="truncate">{item.label}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-surface-muted text-surface-text-muted/70 dark:bg-dark-muted dark:text-dark-text-muted/70 border border-surface-border-subtle dark:border-dark-border-subtle">
                    {item.badge}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </nav>

      {/* Workspace Context Footer: Real Active Context */}
      <div className="p-3 border-t border-surface-border dark:border-dark-border bg-surface-muted/30 dark:bg-dark-muted/30">
        <div className="p-2.5 rounded-lg border border-surface-border-subtle dark:border-dark-border-subtle bg-surface-card dark:bg-dark-card space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
              Active Context
            </span>
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                activeStudent && activeCourse ? 'bg-brand-500' : 'bg-amber-500'
              }`}
              title={activeStudent && activeCourse ? 'Context Complete' : 'Context Incomplete'}
            />
          </div>

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
    </aside>
  )
}
