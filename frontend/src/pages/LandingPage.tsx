import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { BrandLogo } from '../components/layout/BrandLogo'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { BookOpenIcon } from '../components/ui/Icons'
import {
  ArrowRight,
  BookMarked,
  Check,
  CheckCircle2,
  GraduationCap,
  Layers,
  Network,
  Sparkles,
  TrendingUp,
} from 'lucide-react'

type PreviewTab = 'tutor' | 'graph' | 'quiz'

export const LandingPage: React.FC = () => {
  const { isAuthenticated, user } = useAuth()
  const [activeTab, setActiveTab] = useState<PreviewTab>('tutor')
  const [selectedQuizOption, setSelectedQuizOption] = useState<number | null>(1)

  return (
    <div className="min-h-screen bg-surface-canvas dark:bg-dark-canvas text-surface-text dark:text-dark-text flex flex-col selection:bg-brand-500/20">
      {/* Public Navigation Bar - Unified gutters */}
      <header className="h-16 shrink-0 border-b border-surface-border dark:border-dark-border bg-surface-card/90 dark:bg-dark-card/90 backdrop-blur-md sticky top-0 z-40 transition-colors">
        <div className="max-w-8xl mx-auto h-full px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <Link
            to="/"
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg flex items-center"
            aria-label="Folio Home"
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
                  <span className="hidden sm:inline">Workspace ({user?.name.split(' ')[0]})</span>
                  <span className="sm:hidden">Workspace</span>
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
      <section className="relative overflow-hidden pt-12 pb-14 md:pt-20 md:pb-20 border-b border-surface-border-subtle dark:border-dark-border-subtle">
        {/* Subtle Warm Forest-Green Glow */}
        <div
          className="absolute -top-32 left-1/2 -translate-x-1/2 w-160 h-96 bg-brand-500/10 dark:bg-brand-500/5 blur-3xl pointer-events-none rounded-full"
          aria-hidden="true"
        />

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center animate-fade-in">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-brand-200 dark:border-brand-900/60 bg-brand-50/80 dark:bg-brand-950/40 text-brand-800 dark:text-brand-300 text-xs font-semibold mb-6">
            <Sparkles className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
            <span>Source-Grounded Study Platform</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight font-serif text-balance max-w-4xl mx-auto leading-[1.14]">
            Master your courses with AI that{' '}
            <span className="text-brand-700 dark:text-brand-400 underline decoration-brand-400/50 decoration-wavy decoration-2">
              cites your actual sources
            </span>
            .
          </h1>

          <p className="mt-6 text-base sm:text-lg md:text-xl text-surface-text-muted dark:text-dark-text-muted max-w-2xl mx-auto leading-relaxed text-balance">
            Folio transforms dense lecture slides, textbooks, and course syllabi into an interactive
            knowledge engine. Experience hallucination-free Socratic tutoring, adaptive multi-format
            quizzes, and Bayesian mastery tracking.
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
                  Enter Your Learning Workspace
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
              <span>Verifiable Textbook & Slide Citations</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>Strict Account & Student Isolation</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Check className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span>No Fabricated Formulas or Answers</span>
            </div>
          </div>
        </div>

        {/* Interactive Living Product Showcase Preview */}
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mt-12 sm:mt-16">
          <div className="rounded-2xl border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card shadow-lg overflow-hidden transition-all">
            {/* Window Top Bar with Course Status and Tab Controls */}
            <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border bg-surface-muted/50 dark:bg-dark-muted/40 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-400/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-brand-500/80" />
                </div>
                <span className="text-xs font-semibold text-surface-text dark:text-dark-text ml-1 flex items-center gap-1.5">
                  <BookOpenIcon className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                  Machine Learning Foundations
                </span>
                <Badge variant="brand" size="sm" dot>
                  KB Ready &bull; 14 Sources
                </Badge>
              </div>

              {/* Tab Selector */}
              <div className="flex items-center rounded-lg bg-surface-canvas dark:bg-dark-canvas border border-surface-border-subtle dark:border-dark-border-subtle p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setActiveTab('tutor')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                    activeTab === 'tutor'
                      ? 'bg-brand-600 text-white shadow-xs'
                      : 'text-surface-text-muted hover:text-surface-text dark:text-dark-text-muted dark:hover:text-dark-text'
                  }`}
                >
                  Grounded Tutor
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('graph')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                    activeTab === 'graph'
                      ? 'bg-brand-600 text-white shadow-xs'
                      : 'text-surface-text-muted hover:text-surface-text dark:text-dark-text-muted dark:hover:text-dark-text'
                  }`}
                >
                  Concept Graph
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('quiz')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                    activeTab === 'quiz'
                      ? 'bg-brand-600 text-white shadow-xs'
                      : 'text-surface-text-muted hover:text-surface-text dark:text-dark-text-muted dark:hover:text-dark-text'
                  }`}
                >
                  Adaptive Quiz
                </button>
              </div>
            </div>

            {/* Tab 1: Grounded Socratic Tutor Demo */}
            {activeTab === 'tutor' && (
              <div className="p-4 sm:p-6 lg:p-8 space-y-4 animate-fade-in">
                {/* Student Query Bubble */}
                <div className="flex justify-end">
                  <div className="max-w-lg rounded-2xl rounded-tr-xs bg-brand-600 text-white p-3.5 text-xs sm:text-sm shadow-xs">
                    <p className="font-medium">
                      How does L2 weight decay regularize neural networks during gradient descent?
                    </p>
                  </div>
                </div>

                {/* AI Tutor Grounded Response Bubble */}
                <div className="flex justify-start">
                  <div className="max-w-2xl rounded-2xl rounded-tl-xs bg-surface-muted/60 dark:bg-dark-muted/50 border border-surface-border-subtle dark:border-dark-border-subtle p-4 text-xs sm:text-sm space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-brand-700 dark:text-brand-300">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Folio Tutor &bull; Grounded in Course Textbook</span>
                    </div>

                    <p className="text-surface-text dark:text-dark-text leading-relaxed">
                      Weight decay introduces an L2 penalty term <span className="font-mono bg-surface-card dark:bg-dark-card px-1 py-0.5 rounded border border-surface-border-subtle dark:border-dark-border-subtle text-xs">½ &lambda; ||w||²</span> to the objective. At each gradient descent iteration, the parameters are scaled by <span className="font-mono bg-surface-card dark:bg-dark-card px-1 py-0.5 rounded border border-surface-border-subtle dark:border-dark-border-subtle text-xs">(1 &minus; &epsilon;&lambda;)</span> before the standard loss gradient is subtracted:
                    </p>

                    <div className="p-2.5 rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border-subtle dark:border-dark-border-subtle font-mono text-xs text-brand-800 dark:text-brand-200">
                      w &larr; (1 &minus; &epsilon;&lambda;)w &minus; &epsilon; &nabla;L(w)
                    </div>

                    {/* Verifiable Citation Card */}
                    <div className="p-3 rounded-lg border border-brand-200 dark:border-brand-900/60 bg-brand-50/60 dark:bg-brand-950/40 space-y-1.5 text-xs">
                      <div className="flex items-center justify-between font-semibold text-brand-800 dark:text-brand-300">
                        <span className="flex items-center gap-1.5">
                          <BookMarked className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                          Deep Learning Book &bull; Section 7.1.1 (p. 227)
                        </span>
                        <span className="text-[10px] uppercase font-mono tracking-wider bg-brand-100 dark:bg-brand-900/80 px-1.5 py-0.5 rounded text-brand-700 dark:text-brand-200">
                          Chunk #142 &bull; 94% Match
                        </span>
                      </div>
                      <p className="text-[11px] text-surface-text-muted dark:text-dark-text-muted italic">
                        &ldquo;We can see that L2 regularization causes the learning algorithm to &lsquo;perceive&rsquo; the input as having higher variance, which shrinks the weights on features whose covariance with the output is small relative to this added variance.&rdquo;
                      </p>
                    </div>

                    <div className="pt-1 flex items-center gap-2 text-xs text-surface-text-muted dark:text-dark-text-muted">
                      <span className="font-medium text-surface-text dark:text-dark-text">Suggested Next Step:</span>
                      <span>Compare L1 vs L2 regularization sparsity effects</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Concept Graph Preview */}
            {activeTab === 'graph' && (
              <div className="p-4 sm:p-6 lg:p-8 space-y-6 animate-fade-in">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-surface-border-subtle dark:border-dark-border-subtle">
                  <div>
                    <h3 className="font-semibold text-sm">Course Prerequisite Taxonomy &amp; Mastery Map</h3>
                    <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                      Extracted automatically from your course syllabus. Node colors reflect Bayesian Knowledge Tracing.
                    </p>
                  </div>
                  <Badge variant="brand" size="sm">
                    Course Mastery: 72%
                  </Badge>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-xl border border-brand-300 dark:border-brand-800 bg-brand-50/50 dark:bg-brand-950/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wider font-semibold text-brand-700 dark:text-brand-300">
                        Foundation
                      </span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                    </div>
                    <div className="font-semibold text-xs sm:text-sm">Cost Functions &amp; Loss</div>
                    <div className="text-xs text-brand-800 dark:text-brand-300 font-mono">95% Mastery &bull; Strong</div>
                  </div>

                  <div className="p-3.5 rounded-xl border border-brand-300 dark:border-brand-800 bg-brand-50/50 dark:bg-brand-950/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wider font-semibold text-brand-700 dark:text-brand-300">
                        Prerequisite
                      </span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
                    </div>
                    <div className="font-semibold text-xs sm:text-sm">Gradient Descent</div>
                    <div className="text-xs text-brand-800 dark:text-brand-300 font-mono">88% Mastery &bull; Mastered</div>
                  </div>

                  <div className="p-3.5 rounded-xl border border-amber-300 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wider font-semibold text-amber-700 dark:text-amber-300">
                        In Progress
                      </span>
                      <TrendingUp className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <div className="font-semibold text-xs sm:text-sm">L2 Weight Decay</div>
                    <div className="text-xs text-amber-800 dark:text-amber-300 font-mono">65% Mastery &bull; 1 Review Due</div>
                  </div>

                  <div className="p-3.5 rounded-xl border border-surface-border dark:border-dark-border bg-surface-muted/30 dark:bg-dark-muted/20 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                        Target Concept
                      </span>
                      <Layers className="w-3.5 h-3.5 text-surface-text-muted dark:text-dark-text-muted" />
                    </div>
                    <div className="font-semibold text-xs sm:text-sm">Dropout Ensembling</div>
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted font-mono">Unassessed &bull; Prereqs Met</div>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-surface-muted/30 dark:bg-dark-muted/30 border border-surface-border-subtle dark:border-dark-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2 text-surface-text dark:text-dark-text">
                    <Network className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                    <span>Prerequisite chain: <strong>Cost Functions</strong> &rarr; <strong>Gradient Descent</strong> &rarr; <strong>Weight Decay</strong></span>
                  </div>
                  <span className="text-surface-text-muted dark:text-dark-text-muted text-[11px]">
                    Updated via BKT algorithm on every quiz answer
                  </span>
                </div>
              </div>
            )}

            {/* Tab 3: Adaptive Quiz Demo */}
            {activeTab === 'quiz' && (
              <div className="p-4 sm:p-6 lg:p-8 space-y-4 animate-fade-in">
                <div className="flex items-center justify-between pb-2 border-b border-surface-border-subtle dark:border-dark-border-subtle text-xs">
                  <div className="flex items-center gap-2">
                    <Badge variant="brand" size="sm">
                      Question 3 of 8
                    </Badge>
                    <span className="text-surface-text-muted dark:text-dark-text-muted">
                      Topic: <strong>Weight Decay &amp; Regularization</strong>
                    </span>
                  </div>
                  <span className="font-mono text-brand-700 dark:text-brand-300 font-semibold">
                    Target Difficulty: Medium
                  </span>
                </div>

                <div className="space-y-3">
                  <p className="font-medium text-sm sm:text-base">
                    In gradient descent with learning rate &epsilon; and weight decay coefficient &lambda;, what is the effective factor by which the weight vector w is rescaled at each parameter update?
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                    {[
                      { id: 0, text: '(1 + \u03B5\u03BB)', correct: false },
                      { id: 1, text: '(1 \u2212 \u03B5\u03BB)', correct: true },
                      { id: 2, text: '(1 \u2212 \u03BB / \u03B5)', correct: false },
                      { id: 3, text: '(1 \u2212 \u03B5 / \u03BB)', correct: false },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setSelectedQuizOption(opt.id)}
                        className={`p-3 rounded-lg border text-left text-xs sm:text-sm font-medium transition-all cursor-pointer flex items-center justify-between ${
                          selectedQuizOption === opt.id
                            ? opt.correct
                              ? 'border-brand-500 bg-brand-50/80 text-brand-900 dark:bg-brand-950/60 dark:text-brand-200 ring-2 ring-brand-500/30'
                              : 'border-red-500 bg-red-50 text-red-900 dark:bg-red-950/60 dark:text-red-200 ring-2 ring-red-500/30'
                            : 'border-surface-border hover:border-surface-text-muted dark:border-dark-border bg-surface-card dark:bg-dark-card'
                        }`}
                      >
                        <span className="font-mono">{opt.text}</span>
                        {selectedQuizOption === opt.id && opt.correct && (
                          <Check className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>

                  {selectedQuizOption === 1 && (
                    <div className="p-3 rounded-lg bg-brand-50/70 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-900/60 text-xs text-brand-900 dark:text-brand-200 space-y-1 animate-fade-in">
                      <div className="font-semibold flex items-center gap-1.5 text-brand-700 dark:text-brand-300">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Correct! Bayesian Mastery increased: 51% &rarr; 65% (+14%)</span>
                      </div>
                      <p className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                        Memory stability calculated at 4.5 days. Next spaced review scheduled for Monday.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Editorial Section: Why Verifiable Grounding Matters (Open Layout) */}
      <section className="py-16 md:py-24 border-b border-surface-border-subtle dark:border-dark-border-subtle">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mb-12">
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-400">
              The Architecture Difference
            </span>
            <h2 className="text-2xl sm:text-4xl font-bold font-serif tracking-tight mt-1.5">
              Why generic chat tools fail students — and how Folio fixes it.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12">
            {/* The Problem Column */}
            <div className="space-y-4 p-6 sm:p-8 rounded-2xl bg-surface-muted/30 dark:bg-dark-muted/20 border border-surface-border-subtle dark:border-dark-border-subtle">
              <div className="text-xs uppercase font-semibold tracking-wider text-red-600 dark:text-red-400">
                The Generic LLM Dilemma
              </div>
              <h3 className="text-lg sm:text-xl font-semibold font-serif text-surface-text dark:text-dark-text">
                Plausible answers without proof
              </h3>
              <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Standard conversational models generate answers from internet training data. They cannot verify whether a formula matches your professor&rsquo;s notation, hallucinate citations that do not exist, and cannot tell what you are about to forget.
              </p>
              <ul className="space-y-2.5 pt-2 text-xs text-surface-text-muted dark:text-dark-text-muted">
                <li className="flex items-start gap-2">
                  <span className="text-red-500 font-bold">&times;</span>
                  <span>Invented equations and untraceable references</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 font-bold">&times;</span>
                  <span>No awareness of syllabus prerequisite progression</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 font-bold">&times;</span>
                  <span>Zero tracking of retention, decay, or study intervals</span>
                </li>
              </ul>
            </div>

            {/* The Folio Solution Column */}
            <div className="space-y-4 p-6 sm:p-8 rounded-2xl bg-brand-50/40 dark:bg-brand-950/20 border border-brand-200/60 dark:border-brand-900/40">
              <div className="text-xs uppercase font-semibold tracking-wider text-brand-700 dark:text-brand-400">
                The Folio Grounded Pipeline
              </div>
              <h3 className="text-lg sm:text-xl font-semibold font-serif text-surface-text dark:text-dark-text">
                Verifiable chunks &amp; mathematical mastery
              </h3>
              <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Folio parses your actual textbooks, slides, and syllabus files into semantic chunks. Answers are strictly bounded to that evidence, and every practice question adjusts your mastery curve via Bayesian Knowledge Tracing.
              </p>
              <ul className="space-y-2.5 pt-2 text-xs text-surface-text dark:text-dark-text">
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <span>Exact chunk and page citations for every factual claim</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <span>Hierarchical taxonomy tree generated from course syllabus</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                  <span>BKT tracking with memory stability and spaced review cues</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Editorial Section: Four Methodological Pillars (Open Grid) */}
      <section className="py-16 md:py-24 border-b border-surface-border-subtle dark:border-dark-border-subtle">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl mb-12">
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-400">
              Methodology
            </span>
            <h2 className="text-2xl sm:text-4xl font-bold font-serif tracking-tight mt-1.5">
              Four Pillars of Knowledge Acquisition
            </h2>
            <p className="mt-3 text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
              Designed from pedagogical principles of cognitive load theory, active recall, and spaced retrieval.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="space-y-3 pt-4 border-t-2 border-brand-500/40">
              <span className="text-xs font-mono font-bold text-brand-700 dark:text-brand-400">01</span>
              <h3 className="font-semibold text-base font-serif">Curriculum Ingestion</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Upload PDFs, notes, slides, and transcripts. Overlapping semantic windows prevent split equations or lost context between slides.
              </p>
            </div>

            <div className="space-y-3 pt-4 border-t-2 border-brand-500/40">
              <span className="text-xs font-mono font-bold text-brand-700 dark:text-brand-400">02</span>
              <h3 className="font-semibold text-base font-serif">Knowledge Taxonomy</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Automatic generation of hierarchical topic trees and concept dependency graphs to visualize prerequisite pathways before exam day.
              </p>
            </div>

            <div className="space-y-3 pt-4 border-t-2 border-brand-500/40">
              <span className="text-xs font-mono font-bold text-brand-700 dark:text-brand-400">03</span>
              <h3 className="font-semibold text-base font-serif">Socratic Tutoring</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                The tutor uses guided questioning to help you derive solutions independently, strictly bounded by source material citations.
              </p>
            </div>

            <div className="space-y-3 pt-4 border-t-2 border-brand-500/40">
              <span className="text-xs font-mono font-bold text-brand-700 dark:text-brand-400">04</span>
              <h3 className="font-semibold text-base font-serif">Bayesian Mastery (BKT)</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                Adaptive multi-format assessments continuously update your latent mastery probability and predict memory stability decay.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section - Connected Flow */}
      <section className="py-16 md:py-20 border-b border-surface-border-subtle dark:border-dark-border-subtle bg-surface-muted/20 dark:bg-dark-muted/10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-xl mx-auto mb-12">
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-400">
              Simple Workflow
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold font-serif mt-1">
              From Raw Material to Topic Mastery
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-base flex items-center justify-center shadow-xs">
                1
              </div>
              <h3 className="font-semibold text-base">Upload Course Documents</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed max-w-xs">
                Add PDF textbooks, lecture slides, notes, or video transcripts to your course library.
              </p>
            </div>

            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-base flex items-center justify-center shadow-xs">
                2
              </div>
              <h3 className="font-semibold text-base">Automatic Knowledge Base Build</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed max-w-xs">
                Folio chunks, embeds, and structures your documents into a prerequisite topic graph.
              </p>
            </div>

            <div className="flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-base flex items-center justify-center shadow-xs">
                3
              </div>
              <h3 className="font-semibold text-base">Learn, Practice &amp; Retain</h3>
              <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed max-w-xs">
                Chat with the grounded tutor, take adaptive quizzes, and maintain retention before exams.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Closing Call to Action Banner */}
      <section className="py-16 md:py-24">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="p-8 sm:p-12 lg:p-16 rounded-3xl bg-linear-to-b from-brand-50/80 to-surface-card dark:from-brand-950/40 dark:to-dark-card border border-brand-200 dark:border-brand-900/60 shadow-xs text-center space-y-5">
            <GraduationCap className="w-12 h-12 text-brand-700 dark:text-brand-300 mx-auto" />
            <h2 className="text-2xl sm:text-4xl font-bold font-serif text-balance max-w-2xl mx-auto">
              Ready to experience study AI built on verifiable truth?
            </h2>
            <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted max-w-md mx-auto leading-relaxed">
              Join Folio today and turn course materials into lasting personal mastery.
            </p>
            <div className="pt-3">
              <Link to={isAuthenticated ? '/overview' : '/register'}>
                <Button size="lg" variant="primary" rightIcon={<ArrowRight className="w-4 h-4" />}>
                  {isAuthenticated ? 'Open Learning Workspace' : 'Create Free Student Account'}
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Unified Footer */}
      <footer className="mt-auto border-t border-surface-border dark:border-dark-border py-8 text-xs text-surface-text-muted dark:text-dark-text-muted transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <BrandLogo showTagline={false} compactBadge={true} />
            <span className="text-surface-border dark:text-dark-border">&bull;</span>
            <span>Source-Grounded Knowledge Engine</span>
          </div>
          <div className="flex items-center gap-5">
            <Link to="/" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
              Home
            </Link>
            <Link to="/login" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
              Sign In
            </Link>
            <Link to="/register" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
              Register
            </Link>
            {isAuthenticated && (
              <Link to="/overview" className="hover:text-surface-text dark:hover:text-dark-text transition-colors">
                Workspace
              </Link>
            )}
          </div>
        </div>
      </footer>
    </div>
  )
}
