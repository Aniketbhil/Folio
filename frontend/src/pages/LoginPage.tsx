import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Alert } from '../components/ui/Feedback'
import {
  Activity,
  ArrowRight,
  Brain,
  CheckCircle2,
  Lock,
  Mail,
  MessageSquare,
  Sparkles,
} from 'lucide-react'

interface LocationState {
  from?: {
    pathname: string
  }
  registered?: boolean
  message?: string
  email?: string
}

export const LoginPage: React.FC = () => {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const locationState = location.state as LocationState | null

  const [email, setEmail] = useState(() => locationState?.email || '')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage] = useState<string | null>(
    () =>
      locationState?.message ||
      (locationState?.registered
        ? 'Account created successfully! Please sign in with your email and password.'
        : null)
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedEmail = email.trim()
    if (!trimmedEmail || !password) {
      setErrorMessage('Please enter both your email and password.')
      return
    }

    setIsLoading(true)
    setErrorMessage(null)

    try {
      await login({
        email: trimmedEmail,
        password,
      })
      const destination = locationState?.from?.pathname || '/overview'
      navigate(destination, { replace: true })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid email or password.'
      setErrorMessage(msg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-canvas dark:bg-dark-canvas text-surface-text dark:text-dark-text flex flex-col justify-between selection:bg-brand-500/20">
      {/* Top Navigation */}
      <header className="h-16 shrink-0 border-b border-surface-border dark:border-dark-border bg-surface-card/90 dark:bg-dark-card/90 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto h-full flex items-center justify-between">
          <Link
            to="/"
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg flex items-center"
            aria-label="Folio Home"
          >
            <BrandLogo />
          </Link>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link to="/register" className="hidden sm:inline-flex">
              <Button variant="ghost" size="sm">
                Create Account
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 my-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 rounded-2xl border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card shadow-sm overflow-hidden animate-fade-in">
          {/* Left Hero / Storytelling Column (Visible on lg screens) */}
          <div className="hidden lg:flex lg:col-span-5 flex-col justify-between p-8 bg-surface-muted/40 dark:bg-dark-muted/30 border-r border-surface-border-subtle dark:border-dark-border-subtle">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-brand-50 dark:bg-brand-950/60 border border-brand-200 dark:border-brand-900/60 text-[11px] font-semibold text-brand-800 dark:text-brand-300">
                <Sparkles className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                <span>Source-Grounded Study Platform</span>
              </div>

              <div className="space-y-3">
                <h2 className="text-2xl font-serif font-bold text-surface-text dark:text-dark-text leading-tight">
                  Welcome back to your personal study companion.
                </h2>
                <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                  Sign in to resume grounded tutoring sessions, review due concepts on your forgetting curve, and practice adaptive assessments.
                </p>
              </div>

              {/* Three Pill Preview */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border-subtle dark:border-dark-border-subtle text-xs">
                  <MessageSquare className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <div className="truncate">
                    <span className="font-semibold text-surface-text dark:text-dark-text">Grounded Tutor: </span>
                    <span className="text-surface-text-muted dark:text-dark-text-muted">Direct citation snippets</span>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border-subtle dark:border-dark-border-subtle text-xs">
                  <Brain className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <div className="truncate">
                    <span className="font-semibold text-surface-text dark:text-dark-text">Knowledge Graph: </span>
                    <span className="text-surface-text-muted dark:text-dark-text-muted">Prerequisite concept maps</span>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border-subtle dark:border-dark-border-subtle text-xs">
                  <Activity className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <div className="truncate">
                    <span className="font-semibold text-surface-text dark:text-dark-text">Bayesian Tracing: </span>
                    <span className="text-surface-text-muted dark:text-dark-text-muted">Real-time mastery updates</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Proof Tag */}
            <div className="pt-6 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center gap-2 text-[11px] text-surface-text-muted dark:text-dark-text-muted">
              <CheckCircle2 className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 shrink-0" />
              <span>Strict account isolation & data confidentiality</span>
            </div>
          </div>

          {/* Right Form Column */}
          <div className="lg:col-span-7 p-6 sm:p-8 lg:p-10 flex flex-col justify-center">
            <div className="space-y-1.5 pb-6">
              <h1 className="text-2xl font-bold font-serif text-surface-text dark:text-dark-text">
                Sign In to Folio
              </h1>
              <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
                Enter your credentials to access your courses and workspace.
              </p>
            </div>

            {successMessage && (
              <div className="mb-5 animate-fade-in">
                <Alert variant="success" description={successMessage} />
              </div>
            )}

            {errorMessage && (
              <div className="mb-5 animate-fade-in">
                <Alert variant="error" description={errorMessage} />
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email Address"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@example.edu"
                required
                autoComplete="email"
                autoFocus={!email}
                leftIcon={<Mail className="w-4 h-4" />}
              />

              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="current-password"
                autoFocus={!!email}
                leftIcon={<Lock className="w-4 h-4" />}
              />

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  fullWidth
                  size="md"
                  isLoading={isLoading}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Sign In
                </Button>
              </div>
            </form>

            <div className="mt-6 pt-5 border-t border-surface-border-subtle dark:border-dark-border-subtle text-center text-xs text-surface-text-muted dark:text-dark-text-muted">
              Don't have an account yet?{' '}
              <Link
                to="/register"
                className="font-semibold text-brand-700 dark:text-brand-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
              >
                Create an account
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-surface-text-muted dark:text-dark-text-muted py-6 border-t border-surface-border-subtle dark:border-dark-border-subtle">
        &copy; {new Date().getFullYear()} Folio. Source-Grounded Learning Companion.
      </footer>
    </div>
  )
}
