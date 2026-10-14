import React, { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Alert } from '../components/ui/Feedback'
import { ArrowRight, Check, Lock, Mail, User, X } from 'lucide-react'

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
      navigate('/overview', { replace: true })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed. Please check your details.'
      setErrorMessage(msg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-bg dark:bg-dark-bg flex flex-col justify-between p-4 sm:p-6 lg:p-8">
      {/* Top Header bar with Logo and ThemeToggle */}
      <header className="flex items-center justify-between max-w-5xl mx-auto w-full">
        <Link
          to="/"
          className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg"
          aria-label="Folio Home"
        >
          <BrandLogo />
        </Link>
        <ThemeToggle />
      </header>

      {/* Main Registration Card */}
      <main className="w-full max-w-md mx-auto my-auto py-8">
        <Card padding="lg" className="border-surface-border dark:border-dark-border shadow-md">
          <div className="space-y-2 text-center pb-4">
            <h1 className="text-2xl font-bold font-serif text-surface-text dark:text-dark-text">
              Create Your Account
            </h1>
            <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
              Get started with personalized, source-grounded learning.
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4">
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

            {/* Password Strength Checklist */}
            <div className="p-3 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border-subtle dark:border-dark-border-subtle space-y-1.5 text-xs">
              <div className="font-semibold text-surface-text-muted dark:text-dark-text-muted text-[11px] uppercase tracking-wider mb-1">
                Password Requirements
              </div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                <div
                  className={`flex items-center gap-1.5 ${
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
                  className={`flex items-center gap-1.5 ${
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
                  className={`flex items-center gap-1.5 ${
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
                  className={`flex items-center gap-1.5 ${
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
                  className={`pt-1 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center gap-1.5 ${
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
                isLoading={isLoading}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Register & Start Learning
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
        </Card>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-surface-text-muted dark:text-dark-text-muted py-4">
        &copy; {new Date().getFullYear()} Folio. Source-Grounded Learning.
      </footer>
    </div>
  )
}
