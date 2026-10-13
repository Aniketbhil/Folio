import React, { useState } from 'react'
import { Header } from './Header'
import { MobileNav } from './MobileNav'
import { Sidebar } from './Sidebar'
import { NAV_ITEMS } from './navItems'

export interface AppShellProps {
  children?: React.ReactNode
  activeSection: string
  onSectionChange: (sectionId: string) => void
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  activeSection,
  onSectionChange,
}) => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const currentItem = NAV_ITEMS.find((item) => item.id === activeSection)
  const currentTitle = currentItem ? currentItem.label : 'Overview'

  return (
    <div className="min-h-screen flex bg-surface-canvas text-surface-text dark:bg-dark-canvas dark:text-dark-text transition-colors duration-150">
      {/* Desktop Persistent Sidebar (Restrained width, hidden on mobile) */}
      <Sidebar
        activeId={activeSection}
        onSelect={onSectionChange}
        className="hidden md:flex"
      />

      {/* Mobile Slide-Over Drawer */}
      <MobileNav
        isOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        activeId={activeSection}
        onSelect={onSectionChange}
      />

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenMobileNav={() => setMobileNavOpen(true)}
          currentSectionTitle={currentTitle}
        />

        <main className="flex-1 overflow-x-hidden" id="main-content">
          {children}
        </main>

        <footer className="py-3 px-4 sm:px-6 md:px-8 border-t border-surface-border dark:border-dark-border text-xs text-surface-text-muted dark:text-dark-text-muted flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Folio &bull; Personalized Tutoring & Adaptive Learning</span>
          <span>Source-Grounded AI Study Companion</span>
        </footer>
      </div>
    </div>
  )
}
