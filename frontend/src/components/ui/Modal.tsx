import React, { useEffect } from 'react'
import { CloseIcon } from './Icons'

export interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  description?: string
  children: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl'
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'md',
}) => {
  // Lock body scroll while modal is open
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

  // Dismiss on ESC key
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

  const maxWidthStyles = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
  }[maxWidth]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Card */}
      <div
        className={`relative w-full ${maxWidthStyles} max-h-[90vh] flex flex-col bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-xl shadow-xl z-10 overflow-hidden transition-all animate-scale-in`}
      >
        {/* Header */}
        <div className="shrink-0 flex items-start justify-between p-4 sm:p-5 border-b border-surface-border dark:border-dark-border">
          <div className="space-y-1 pr-4">
            <h3
              id="modal-title"
              className="text-base sm:text-lg font-semibold text-surface-text dark:text-dark-text tracking-tight"
            >
              {title}
            </h3>
            {description && (
              <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:text-dark-text-muted dark:hover:text-dark-text dark:hover:bg-dark-muted p-1.5 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 cursor-pointer"
            aria-label="Close modal"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-5 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}
