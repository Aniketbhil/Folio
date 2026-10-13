import React, { useEffect } from 'react'
import { CloseIcon } from '../ui/Icons'
import { BrandLogo } from './BrandLogo'
import { NAV_ITEMS, type NavItem } from './navItems'

export interface MobileNavProps {
  isOpen: boolean
  onClose: () => void
  activeId: string
  onSelect: (id: string) => void
}

export const MobileNav: React.FC<MobileNavProps> = ({
  isOpen,
  onClose,
  activeId,
  onSelect,
}) => {
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
      <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] bg-surface-card dark:bg-dark-card border-r border-surface-border dark:border-dark-border shadow-xl flex flex-col z-10 animate-in slide-in-from-left duration-200">
        {/* Header with Brand and Close button */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-surface-border dark:border-dark-border">
          <BrandLogo />
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
        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto" aria-label="Mobile application navigation">
          <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted/80 dark:text-dark-text-muted/80">
            Navigation
          </div>
          {NAV_ITEMS.map((item: NavItem) => {
            const isActive = activeId === item.id
            const Icon = item.icon

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onSelect(item.id)
                  onClose()
                }}
                className={`w-full min-h-11 flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                  isActive
                    ? 'bg-brand-50 text-brand-800 dark:bg-brand-950/70 dark:text-brand-200 font-semibold'
                    : 'text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
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
              </button>
            )
          })}
        </nav>

        {/* Mobile footer */}
        <div className="p-4 border-t border-surface-border dark:border-dark-border bg-surface-muted/30 dark:bg-dark-muted/30">
          <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
            Folio Adaptive Learning System
          </p>
        </div>
      </div>
    </div>
  )
}
