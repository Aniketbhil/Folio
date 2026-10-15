import React, { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Alert } from '../components/ui/Feedback'
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  User,
  X,
} from 'lucide-react'

export const RegisterPage: React.FC = () => {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Password rule checks matching backend validate_password
  const passwordRules = useMemo(() => {
    return {
      length: password.length >= 8 && password.length <= 128,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      symbol: /[^a-zA-Z0-9\s]/.test(password),
      matches: password.length > 0 && password === confirmPassword,
    }
  }, [password, confirmPassword])

  const isPasswordValid =
    passwordRules.length &&
    passwordRules.uppercase &&
    passwordRules.lowercase &&
    passwordRules.symbol

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedName = name.trim()
    const trimmedEmail = email.trim()

    if (!trimmedName) {
      setErrorMessage('Full name is required (1 to 80 characters).')
      return
    }

    if (trimmedName.length > 80) {
      setErrorMessage('Full name must be at most 80 characters.')
      return
    }

    if (!trimmedEmail) {
      setErrorMessage('A valid email address is required.')
      return
    }

    if (!isPasswordValid) {
      setErrorMessage('Please ensure your password meets all strength requirements.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.')
      return
    }

    setIsLoading(true)
    setErrorMessage(null)

    try {
      await register({
        name: trimmedName,
        email: trimmedEmail,
        password,
      })
      // Successful registration: redirect user to /login with helpful success notification
      navigate('/login', {
        replace: true,
        state: {
          registered: true,
          email: trimmedEmail,
          message: 'Account created successfully! Please sign in with your email and password.',
        },
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed. Please check your details.'
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
            <Link to="/login" className="hidden sm:inline-flex">
              <Button variant="ghost" size="sm">
                Sign In
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
                  Start your journey toward true subject mastery.
                </h2>
                <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                  Join Folio to turn lecture materials, course syllabi, and textbooks into verifiable AI tutoring and adaptive assessments.
                </p>
              </div>

              {/* Feature Highlights */}
              <div className="space-y-3 pt-2">
                <div className="flex items-start gap-2.5 text-xs">
                  <div className="w-5 h-5 rounded-md bg-brand-100 dark:bg-brand-900/50 flex items-center justify-center shrink-0 mt-0.5 text-brand-700 dark:text-brand-300">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="font-semibold text-surface-text dark:text-dark-text">Zero Hallucinations</span>
                    <p className="text-surface-text-muted dark:text-dark-text-muted text-[11px]">
                      Answers cite exact chunks and page numbers from uploaded documents.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5 text-xs">
                  <div className="w-5 h-5 rounded-md bg-brand-100 dark:bg-brand-900/50 flex items-center justify-center shrink-0 mt-0.5 text-brand-700 dark:text-brand-300">
                    <BookOpen className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="font-semibold text-surface-text dark:text-dark-text">Automated Taxonomy</span>
                    <p className="text-surface-text-muted dark:text-dark-text-muted text-[11px]">
                      Extracts hierarchical concept trees and prerequisite dependency graphs.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2.5 text-xs">
                  <div className="w-5 h-5 rounded-md bg-brand-100 dark:bg-brand-900/50 flex items-center justify-center shrink-0 mt-0.5 text-brand-700 dark:text-brand-300">
                    <ShieldCheck className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="font-semibold text-surface-text dark:text-dark-text">Account Isolation</span>
                    <p className="text-surface-text-muted dark:text-dark-text-muted text-[11px]">
                      Your conversations, attempts, and mastery progress remain strictly private.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Quote */}
            <div className="pt-6 border-t border-surface-border-subtle dark:border-dark-border-subtle text-[11px] text-surface-text-muted dark:text-dark-text-muted italic">
              "Folio guarantees verifiable evidence for every answer and recommendation."
            </div>
          </div>

          {/* Right Form Column */}
          <div className="lg:col-span-7 p-6 sm:p-8 lg:p-10 flex flex-col justify-center">
            <div className="space-y-1.5 pb-6">
              <h1 className="text-2xl font-bold font-serif text-surface-text dark:text-dark-text">
                Create Your Account
              </h1>
              <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
                Enter your details to register as a student on Folio.
              </p>
            </div>

            {errorMessage && (
              <div className="mb-5 animate-fade-in">
                <Alert variant="error" description={errorMessage} />
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Full Name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ada Lovelace"
                required
                maxLength={80}
                autoComplete="name"
                autoFocus
                leftIcon={<User className="w-4 h-4" />}
              />

              <Input
                label="Email Address"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@example.edu"
                required
                autoComplete="email"
                leftIcon={<Mail className="w-4 h-4" />}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <Input
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  autoComplete="new-password"
                  leftIcon={<Lock className="w-4 h-4" />}
                />

                <Input
                  label="Confirm Password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  autoComplete="new-password"
                  leftIcon={<Lock className="w-4 h-4" />}
                />
              </div>

              {/* Password Strength Checklist */}
              <div className="p-3 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border-subtle dark:border-dark-border-subtle space-y-1.5 text-xs transition-colors">
                <div className="font-semibold text-surface-text-muted dark:text-dark-text-muted text-[11px] uppercase tracking-wider">
                  Password Requirements
                </div>
                <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                  <div
                    className={`flex items-center gap-1.5 transition-colors ${
                      passwordRules.length
                        ? 'text-brand-700 dark:text-brand-400 font-medium'
                        : 'text-surface-text-muted dark:text-dark-text-muted'
                    }`}
                  >
                    {passwordRules.length ? (
                      <Check className="w-3.5 h-3.5 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 shrink-0 opacity-40" />
                    )}
                    <span>8+ characters</span>
                  </div>

                  <div
                    className={`flex items-center gap-1.5 transition-colors ${
                      passwordRules.uppercase
                        ? 'text-brand-700 dark:text-brand-400 font-medium'
                        : 'text-surface-text-muted dark:text-dark-text-muted'
                    }`}
                  >
                    {passwordRules.uppercase ? (
                      <Check className="w-3.5 h-3.5 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 shrink-0 opacity-40" />
                    )}
                    <span>1 uppercase</span>
                  </div>

                  <div
                    className={`flex items-center gap-1.5 transition-colors ${
                      passwordRules.lowercase
                        ? 'text-brand-700 dark:text-brand-400 font-medium'
                        : 'text-surface-text-muted dark:text-dark-text-muted'
                    }`}
                  >
                    {passwordRules.lowercase ? (
                      <Check className="w-3.5 h-3.5 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 shrink-0 opacity-40" />
                    )}
                    <span>1 lowercase</span>
                  </div>

                  <div
                    className={`flex items-center gap-1.5 transition-colors ${
                      passwordRules.symbol
                        ? 'text-brand-700 dark:text-brand-400 font-medium'
                        : 'text-surface-text-muted dark:text-dark-text-muted'
                    }`}
                  >
                    {passwordRules.symbol ? (
                      <Check className="w-3.5 h-3.5 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 shrink-0 opacity-40" />
                    )}
                    <span>1 symbol (@#$...)</span>
                  </div>
                </div>

                {confirmPassword.length > 0 && (
                  <div
                    className={`pt-1.5 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center gap-1.5 transition-colors ${
                      passwordRules.matches
                        ? 'text-brand-700 dark:text-brand-400 font-medium'
                        : 'text-red-600 dark:text-red-400'
                    }`}
                  >
                    {passwordRules.matches ? (
                      <Check className="w-3.5 h-3.5 shrink-0" />
                    ) : (
                      <X className="w-3.5 h-3.5 shrink-0" />
                    )}
                    <span>{passwordRules.matches ? 'Passwords match' : 'Passwords do not match'}</span>
                  </div>
                )}
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  fullWidth
                  size="md"
                  isLoading={isLoading}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Create Account
                </Button>
              </div>
            </form>

            <div className="mt-6 pt-5 border-t border-surface-border-subtle dark:border-dark-border-subtle text-center text-xs text-surface-text-muted dark:text-dark-text-muted">
              Already have an account?{' '}
              <Link
                to="/login"
                className="font-semibold text-brand-700 dark:text-brand-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
              >
                Sign In
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
