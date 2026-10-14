import React, { useState } from 'react'
import { Header } from './Header'
import { MobileNav } from './MobileNav'
import { Sidebar } from './Sidebar'

export interface AppShellProps {
  children?: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-surface-canvas text-surface-text dark:bg-dark-canvas dark:text-dark-text transition-colors duration-150">
      {/* Desktop Persistent Sidebar */}
      <Sidebar className="hidden md:flex" />

      {/* Mobile Slide-Over Drawer */}
      <MobileNav
        isOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
      />

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header onOpenMobileNav={() => setMobileNavOpen(true)} />

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
