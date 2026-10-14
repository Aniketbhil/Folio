import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Alert } from '../components/ui/Feedback'
import { ArrowRight, Lock, Mail } from 'lucide-react'

interface LocationState {
  from?: {
    pathname: string
  }
}

export const LoginPage: React.FC = () => {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
      const state = location.state as LocationState | null
      const destination = state?.from?.pathname || '/overview'
      navigate(destination, { replace: true })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid email or password.'
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

      {/* Main Login Card */}
      <main className="w-full max-w-md mx-auto my-auto py-8">
        <Card padding="lg" className="border-surface-border dark:border-dark-border shadow-md">
          <div className="space-y-2 text-center pb-4">
            <h1 className="text-2xl font-bold font-serif text-surface-text dark:text-dark-text">
              Welcome Back
            </h1>
            <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
              Sign in to access your course materials and grounded tutor.
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4">
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
              autoFocus
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
              leftIcon={<Lock className="w-4 h-4" />}
            />

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                fullWidth
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
        </Card>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-surface-text-muted dark:text-dark-text-muted py-4">
        &copy; {new Date().getFullYear()} Folio. Source-Grounded Learning.
      </footer>
    </div>
  )
}
