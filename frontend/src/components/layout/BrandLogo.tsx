import React from 'react'

interface BrandLogoProps {
  showTagline?: boolean
  className?: string
}

export const BrandLogo: React.FC<BrandLogoProps> = ({ showTagline = true, className = '' }) => {
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Brand Icon Mark: Monogram on deep forest emerald */}
      <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-base shadow-xs shrink-0 tracking-tight">
        <span>F</span>
      </div>
      <div className="flex flex-col">
        <div className="flex items-center gap-1.5 leading-none">
          <span className="font-bold text-base tracking-tight text-surface-text dark:text-dark-text">
            Folio
          </span>
          <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-sm bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300 border border-brand-200/80 dark:border-brand-800/80">
            Learn
          </span>
        </div>
        {showTagline && (
          <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted font-normal tracking-normal mt-0.5">
            Adaptive AI Study Companion
          </span>
        )}
      </div>
    </div>
  )
}
