import React from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  ActivityIcon,
  CheckCircleIcon,
  MessageSquareIcon,
} from '../components/ui/Icons'
import {
  ArrowRight,
  Brain,
  Check,
  GraduationCap,
  Sparkles,
} from 'lucide-react'

export const LandingPage: React.FC = () => {
  const { isAuthenticated, user } = useAuth()

  return (
    <div className="min-h-screen bg-surface-bg dark:bg-dark-bg text-surface-text dark:text-dark-text flex flex-col selection:bg-brand-500/20">
      {/* Public Navigation Bar */}
      <header className="h-16 shrink-0 border-b border-surface-border dark:border-dark-border bg-surface-card/90 dark:bg-dark-card/90 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto h-full flex items-center justify-between">
          <Link
            to="/"
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg"
          >
            <BrandLogo />
          </Link>

          <div className="flex items-center gap-3">
            <ThemeToggle />

            {isAuthenticated ? (
              <Link to="/overview">
                <Button
                  variant="primary"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  <span className="hidden sm:inline">Welcome back, {user?.name.split(' ')[0]}</span>
                  <span className="sm:hidden">Dashboard</span>
                </Button>
              </Link>
            ) : (
              <div className="flex items-center gap-2">
                <Link to="/login">
                  <Button variant="ghost" size="sm">
                    Sign In
                  </Button>
                </Link>
                <Link to="/register">
                  <Button
                    variant="primary"
                    size="sm"
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  >
                    Get Started
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-16 md:pt-20 md:pb-24 border-b border-surface-border/60 dark:border-dark-border/60">
        {/* Subtle background glow effect */}
        <div
          className="absolute -top-40 left-1/2 -translate-x-1/2 w-150 h-87.5 bg-brand-500/10 dark:bg-brand-500/5 blur-3xl pointer-events-none rounded-full"
          aria-hidden="true"
        />

        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-brand-200 dark:border-brand-900/60 bg-brand-50/80 dark:bg-brand-950/40 text-brand-800 dark:text-brand-300 text-xs font-semibold mb-6">
            <Sparkles className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
            <span>Source-Grounded AI Study Companion</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight font-serif text-balance max-w-4xl mx-auto leading-[1.15]">
            Master your courses with AI that{' '}
            <span className="text-brand-700 dark:text-brand-400 underline decoration-brand-400/50 decoration-wavy decoration-2">
              cites your actual sources
            </span>
            .
          </h1>

          <p className="mt-6 text-base sm:text-lg md:text-xl text-surface-text-muted dark:text-dark-text-muted max-w-2xl mx-auto leading-relaxed">
            Folio turns your lecture notes, textbooks, and syllabus into an interactive knowledge
            graph with hallucination-free tutoring, adaptive assessments, and Bayesian mastery tracking.
          </p>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5">
            {isAuthenticated ? (
              <Link to="/overview" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  variant="primary"
                  fullWidth
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Enter Your Workspace
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/register" className="w-full sm:w-auto">
                  <Button
                    size="lg"
                    variant="primary"
                    fullWidth
                    rightIcon={<ArrowRight className="w-4 h-4" />}
                  >
                    Start Learning Free
                  </Button>
                </Link>
                <Link to="/login" className="w-full sm:w-auto">
                  <Button size="lg" variant="secondary" fullWidth>
                    Sign In to Account
                  </Button>
                </Link>
              </>
            )}
          </div>

          {/* Social Proof / Security Badges */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-6 text-xs text-surface-text-muted dark:text-dark-text-muted font-medium">
            <div className="flex items-center gap-1.5">
              <Check className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>Verifiable Chunks & Citations</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>Strict Account Isolation</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>No Fabricated Answers</span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights Grid */}
      <section className="py-16 md:py-24 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold font-serif">
            A Complete Learning Engine Built for Depth
          </h2>
          <p className="mt-3 text-sm sm:text-base text-surface-text-muted dark:text-dark-text-muted">
            Designed for serious learners who need verifiable correctness, structured taxonomies, and measurable skill progression.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1 */}
          <Card padding="md" className="flex flex-col justify-between hover:border-brand-500/40 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-950/60 border border-brand-200 dark:border-brand-900 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <MessageSquareIcon className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-base">Grounded AI Tutor</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Tutor answers are strictly bounded by your ingested course material. Every response includes direct verifiable citations and snippets.
              </p>
            </div>
            <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle">
              <Badge variant="brand" size="sm">Zero Hallucinations</Badge>
            </div>
          </Card>

          {/* Card 2 */}
          <Card padding="md" className="flex flex-col justify-between hover:border-brand-500/40 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-950/60 border border-brand-200 dark:border-brand-900 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <Brain className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-base">Knowledge Base Graph</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Hierarchical taxonomy trees and concept dependency graphs are automatically extracted from your syllabus and uploaded sources.
              </p>
            </div>
            <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle">
              <Badge variant="neutral" size="sm">Structured Graphs</Badge>
            </div>
          </Card>

          {/* Card 3 */}
          <Card padding="md" className="flex flex-col justify-between hover:border-brand-500/40 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-950/60 border border-brand-200 dark:border-brand-900 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <CheckCircleIcon className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-base">Adaptive Assessments</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Generate dynamic multi-format quizzes (MCQ, short answer, numerical) generated specifically for topics where your mastery is weak.
              </p>
            </div>
            <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle">
              <Badge variant="brand" size="sm">Multi-Format Quizzes</Badge>
            </div>
          </Card>

          {/* Card 4 */}
          <Card padding="md" className="flex flex-col justify-between hover:border-brand-500/40 transition-colors">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-950/60 border border-brand-200 dark:border-brand-900 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <ActivityIcon className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-base">Bayesian Mastery Tracking</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Track probabilistic knowledge acquisition (BKT) with memory stability and forgetting curves that highlight due reviews.
              </p>
            </div>
            <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle">
              <Badge variant="amber" size="sm">BKT + Forgetting</Badge>
            </div>
          </Card>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-16 bg-surface-muted/30 dark:bg-dark-muted/20 border-y border-surface-border dark:border-dark-border">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-xl mx-auto mb-12">
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-400">
              Workflow
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold font-serif mt-1">
              How Folio Powers Your Learning
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-lg flex items-center justify-center shadow-md">
                1
              </div>
              <h3 className="font-semibold text-base">Upload Your Sources</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Add PDFs, text documents, lecture notes, or transcripts to your course library.
              </p>
            </div>

            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-lg flex items-center justify-center shadow-md">
                2
              </div>
              <h3 className="font-semibold text-base">Build Knowledge Graph</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Folio automatically chunks, embeds, and structures your documents into topic taxonomies.
              </p>
            </div>

            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-lg flex items-center justify-center shadow-md">
                3
              </div>
              <h3 className="font-semibold text-base">Ask, Practice & Retain</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Chat with the grounded tutor, take adaptive quizzes, and watch your mastery grow over time.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Call to Action Banner */}
      <section className="py-16 md:py-20 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div className="p-8 sm:p-12 rounded-2xl bg-linear-to-b from-brand-50 to-surface-card dark:from-brand-950/40 dark:to-dark-card border border-brand-200 dark:border-brand-900/60 shadow-xs space-y-5">
          <GraduationCap className="w-10 h-10 text-brand-700 dark:text-brand-300 mx-auto" />
          <h2 className="text-2xl sm:text-3xl font-bold font-serif text-balance">
            Ready to experience hallucination-free study companion AI?
          </h2>
          <p className="text-sm text-surface-text-muted dark:text-dark-text-muted max-w-lg mx-auto">
            Join Folio today and transform course materials into personal mastery.
          </p>
          <div className="pt-2">
            <Link to={isAuthenticated ? '/overview' : '/register'}>
              <Button size="lg" variant="primary" rightIcon={<ArrowRight className="w-4 h-4" />}>
                {isAuthenticated ? 'Open Overview' : 'Create Free Account'}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-surface-border dark:border-dark-border py-8 px-4 sm:px-6 lg:px-8 text-center text-xs text-surface-text-muted dark:text-dark-text-muted">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <BrandLogo showTagline={false} compactBadge={true} />
            <span>— Source-Grounded Knowledge Engine</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
              Sign In
            </Link>
            <Link to="/register" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
              Register
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
