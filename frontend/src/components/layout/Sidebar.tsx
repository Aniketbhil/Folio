import { BrandLogo } from './BrandLogo'
import { NAV_ITEMS } from './navItems'

export interface SidebarProps {
  activeId: string
  onSelect: (id: string) => void
  className?: string
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeId,
  onSelect,
  className = '',
}) => {
  return (
    <aside
      className={`w-60 lg:w-64 shrink-0 bg-surface-card dark:bg-dark-card border-r border-surface-border dark:border-dark-border flex flex-col h-screen sticky top-0 select-none ${className}`}
      aria-label="Main sidebar navigation"
    >
      {/* Brand Header */}
      <div className="h-14 px-5 flex items-center border-b border-surface-border dark:border-dark-border">
        <BrandLogo />
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Application sections">
        <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted/80 dark:text-dark-text-muted/80">
          Navigation
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = activeId === item.id
          const Icon = item.icon

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                isActive
                  ? 'bg-brand-50 text-brand-800 dark:bg-brand-950/70 dark:text-brand-200 font-semibold'
                  : 'text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
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
            </button>
          )
        })}
      </nav>

      {/* Workspace Context Footer */}
      <div className="p-3 border-t border-surface-border dark:border-dark-border bg-surface-muted/30 dark:bg-dark-muted/30">
        <div className="p-2.5 rounded-lg border border-surface-border-subtle dark:border-dark-border-subtle bg-surface-card dark:bg-dark-card space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
              Active Session
            </span>
            <span className="inline-block w-2 h-2 rounded-full bg-brand-500" title="System Ready" />
          </div>
          <div className="text-xs font-semibold text-surface-text dark:text-dark-text truncate">
            Folio Learning Workspace
          </div>
          <div className="text-[11px] text-surface-text-muted dark:text-dark-text-muted truncate">
            Grounded AI Companion
          </div>
        </div>
      </div>
    </aside>
  )
}
