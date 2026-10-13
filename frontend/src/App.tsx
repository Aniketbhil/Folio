import { useEffect, useState } from "react";

export default function App() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("folio-theme");
      if (stored) return stored === "dark";
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    return false;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
      localStorage.setItem("folio-theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("folio-theme", "light");
    }
  }, [isDark]);

  const toggleTheme = () => setIsDark((prev) => !prev);

  return (
    <div className="min-h-screen bg-surface-canvas text-surface-text dark:bg-dark-canvas dark:text-dark-text transition-colors duration-200">
      <header className="border-b border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm shadow-xs">
              F
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-surface-text dark:text-dark-text">
                Folio
              </h1>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                Personalized Tutoring & Adaptive Learning
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md border border-surface-border dark:border-dark-border bg-surface-muted dark:bg-dark-muted hover:bg-surface-border/50 dark:hover:bg-dark-border/50 transition-colors cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-brand-500"
            aria-label="Toggle light and dark theme"
          >
            <span>{isDark ? "🌙 Dark" : "☀️ Light"}</span>
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        <div className="rounded-xl border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card p-6 shadow-xs space-y-4">
          <h2 className="text-2xl font-bold tracking-tight text-surface-text dark:text-dark-text">
            Folio Design System & Frontend Foundation
          </h2>
          <p className="text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed max-w-2xl">
            Cleanly initialized with React 19, TypeScript 6, Vite 8, and
            Tailwind CSS v4.3 CSS-first design tokens. Configured with warm
            ivory/charcoal surfaces and emerald accents, avoiding generic
            template styles.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
            <div className="p-4 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border">
              <span className="text-xs font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                Brand Accent
              </span>
              <div className="mt-2 flex items-center gap-2">
                <div className="w-4 h-4 rounded-sm bg-brand-600"></div>
                <span className="text-sm font-medium">
                  Forest Green / Emerald
                </span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border">
              <span className="text-xs font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                Surfaces
              </span>
              <div className="mt-2 flex items-center gap-2">
                <div className="w-4 h-4 rounded-sm bg-surface-canvas border border-surface-border"></div>
                <span className="text-sm font-medium">
                  Warm Ivory & Deep Charcoal
                </span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border">
              <span className="text-xs font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                API Base
              </span>
              <div className="mt-2 flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-brand-500"></div>
                <span className="text-sm font-mono">
                  /api/v1 (FastAPI)
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
