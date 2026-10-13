import { useState } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import { AppShell } from './components/layout/AppShell'
import { PageContainer, PageHeader } from './components/layout/PageContainer'
import { Button } from './components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/Card'
import { Badge } from './components/ui/Badge'
import { Input } from './components/ui/Input'
import { Select } from './components/ui/Select'
import { Alert, EmptyState } from './components/ui/Feedback'
import {
  ActivityIcon,
  BookOpenIcon,
  CheckCircleIcon,
  MessageSquareIcon,
  SearchIcon,
} from './components/ui/Icons'

function AppContent() {
  const [activeSection, setActiveSection] = useState<string>('overview')
  const [dismissedAlert, setDismissedAlert] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDifficulty, setSelectedDifficulty] = useState('auto')

  return (
    <AppShell activeSection={activeSection} onSectionChange={setActiveSection}>
      <PageContainer>
        {activeSection === 'overview' && (
          <div className="space-y-6">
            <PageHeader
              title="Learning Workspace"
              description="Source-grounded study companion with personalized tutoring, topic mastery tracking, and adaptive assessments."
              badge={
                <Badge variant="brand" size="sm" dot>
                  Workspace Ready
                </Badge>
              }
              actions={
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setActiveSection('sources')}
                  >
                    View Sources
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setActiveSection('tutor')}
                  >
                    Open Tutor
                  </Button>
                </div>
              }
            />

            {!dismissedAlert && (
              <Alert
                variant="info"
                title="Adaptive Learning Environment"
                description="Folio analyzes course documents to generate structured concept hierarchies, evidence-backed tutoring answers, and spaced review practice."
                onDismiss={() => setDismissedAlert(true)}
              />
            )}

            {/* Core Capability Cards Grid - Compact and responsive */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
              <Card
                variant="interactive"
                padding="md"
                onClick={() => setActiveSection('sources')}
              >
                <div className="flex items-center justify-between pb-2">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/80 flex items-center justify-center text-brand-700 dark:text-brand-300">
                    <BookOpenIcon className="w-4 h-4" />
                  </div>
                  <Badge variant="brand" size="sm">
                    Sources
                  </Badge>
                </div>
                <CardTitle className="text-sm sm:text-base">Course Library</CardTitle>
                <CardDescription className="text-xs">
                  Upload PDFs, presentations, and transcripts for automated knowledge extraction.
                </CardDescription>
              </Card>

              <Card
                variant="interactive"
                padding="md"
                onClick={() => setActiveSection('tutor')}
              >
                <div className="flex items-center justify-between pb-2">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/80 flex items-center justify-center text-brand-700 dark:text-brand-300">
                    <MessageSquareIcon className="w-4 h-4" />
                  </div>
                  <Badge variant="amber" size="sm">
                    Interactive
                  </Badge>
                </div>
                <CardTitle className="text-sm sm:text-base">Socratic Tutor</CardTitle>
                <CardDescription className="text-xs">
                  Source-grounded conversational assistant with citations and follow-up guidance.
                </CardDescription>
              </Card>

              <Card
                variant="interactive"
                padding="md"
                onClick={() => setActiveSection('assessments')}
              >
                <div className="flex items-center justify-between pb-2">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/80 flex items-center justify-center text-brand-700 dark:text-brand-300">
                    <CheckCircleIcon className="w-4 h-4" />
                  </div>
                  <Badge variant="terracotta" size="sm">
                    Practice
                  </Badge>
                </div>
                <CardTitle className="text-sm sm:text-base">Assessments</CardTitle>
                <CardDescription className="text-xs">
                  Diagnostics, targeted quizzes, and mock exams with immediate concept feedback.
                </CardDescription>
              </Card>

              <Card
                variant="interactive"
                padding="md"
                onClick={() => setActiveSection('mastery')}
              >
                <div className="flex items-center justify-between pb-2">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/80 flex items-center justify-center text-brand-700 dark:text-brand-300">
                    <ActivityIcon className="w-4 h-4" />
                  </div>
                  <Badge variant="neutral" size="sm">
                    Tracking
                  </Badge>
                </div>
                <CardTitle className="text-sm sm:text-base">Mastery Model</CardTitle>
                <CardDescription className="text-xs">
                  Bayesian Knowledge Tracing and forgetting curves for scheduled topic retention.
                </CardDescription>
              </Card>
            </div>

            {/* Design System Foundations Section */}
            <div className="space-y-4 pt-2">
              <h2 className="text-base sm:text-lg font-semibold tracking-tight text-surface-text dark:text-dark-text">
                Design System & Interface Primitives
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Component Gallery: Buttons & Badges */}
                <Card padding="md" className="space-y-4">
                  <CardHeader>
                    <CardTitle className="text-sm sm:text-base">Button & Status Tokens</CardTitle>
                    <CardDescription>
                      Tested contrast and interaction states in both light and dark modes.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2 items-center">
                      <Button variant="primary" size="sm">
                        Primary
                      </Button>
                      <Button variant="secondary" size="sm">
                        Secondary
                      </Button>
                      <Button variant="outline" size="sm">
                        Outline
                      </Button>
                      <Button variant="ghost" size="sm">
                        Ghost
                      </Button>
                      <Button variant="danger" size="sm">
                        Destructive
                      </Button>
                    </div>

                    <div className="pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle flex flex-wrap gap-2 items-center">
                      <Badge variant="brand" size="sm" dot>
                        Forest Green
                      </Badge>
                      <Badge variant="amber" size="sm" dot>
                        Amber Progress
                      </Badge>
                      <Badge variant="terracotta" size="sm" dot>
                        Terracotta Highlight
                      </Badge>
                      <Badge variant="success" size="sm">
                        Ready
                      </Badge>
                      <Badge variant="warning" size="sm">
                        Review Due
                      </Badge>
                      <Badge variant="neutral" size="sm">
                        Neutral
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                {/* Component Gallery: Form Controls */}
                <Card padding="md" className="space-y-4">
                  <CardHeader>
                    <CardTitle className="text-sm sm:text-base">Inputs & Controls</CardTitle>
                    <CardDescription>
                      Touch-friendly controls with accessible labels and states.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Input
                      label="Search Library"
                      placeholder="Filter concepts or topics..."
                      leftIcon={<SearchIcon className="w-4 h-4" />}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    <Select
                      label="Practice Difficulty"
                      value={selectedDifficulty}
                      onChange={(e) => setSelectedDifficulty(e.target.value)}
                      options={[
                        { value: 'auto', label: 'Adaptive (Recommended)' },
                        { value: 'easy', label: 'Foundational (Easy)' },
                        { value: 'medium', label: 'Core (Medium)' },
                        { value: 'hard', label: 'Advanced (Hard)' },
                      ]}
                    />
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        )}

        {activeSection === 'sources' && (
          <div className="space-y-6">
            <PageHeader
              title="Course Sources & Library"
              description="Manage uploaded textbook PDFs, slide decks, and lecture transcripts."
              actions={
                <Button variant="primary" size="sm">
                  Upload Material
                </Button>
              }
            />
            <EmptyState
              icon={<BookOpenIcon className="w-5 h-5" />}
              title="No Course Materials Added"
              description="Upload course documents (PDF, PPTX, or transcripts) to automatically build the knowledge base."
              action={
                <Button variant="secondary" size="sm">
                  Select Files to Ingest
                </Button>
              }
            />
          </div>
        )}

        {activeSection === 'tutor' && (
          <div className="space-y-6">
            <PageHeader
              title="AI Study Tutor"
              description="Ask questions about course concepts. Answers are strictly grounded in course materials."
              actions={
                <Button variant="outline" size="sm">
                  New Conversation
                </Button>
              }
            />
            <EmptyState
              icon={<MessageSquareIcon className="w-5 h-5" />}
              title="Start a Tutoring Conversation"
              description="Select a topic or type a question to begin a source-grounded study session."
              action={
                <Button variant="primary" size="sm">
                  Ask a Question
                </Button>
              }
            />
          </div>
        )}

        {activeSection === 'assessments' && (
          <div className="space-y-6">
            <PageHeader
              title="Assessments & Practice"
              description="Targeted quizzes, diagnostic assessments, and full mock exams."
              actions={
                <Button variant="primary" size="sm">
                  Create Quiz
                </Button>
              }
            />
            <EmptyState
              icon={<CheckCircleIcon className="w-5 h-5" />}
              title="No Active Assessments"
              description="Generate a practice quiz or diagnostic exam to evaluate your concept mastery."
              action={
                <Button variant="primary" size="sm">
                  Start Diagnostic
                </Button>
              }
            />
          </div>
        )}

        {activeSection === 'mastery' && (
          <div className="space-y-6">
            <PageHeader
              title="Knowledge Graph & Topic Mastery"
              description="Inspect topic hierarchies, prerequisite relationships, and memory retention."
            />
            <EmptyState
              icon={<ActivityIcon className="w-5 h-5" />}
              title="Knowledge Graph"
              description="The concept graph visualizes topic prerequisites and your retention curve based on Bayesian Knowledge Tracing."
              action={
                <Button variant="secondary" size="sm">
                  View Syllabus Topics
                </Button>
              }
            />
          </div>
        )}
      </PageContainer>
    </AppShell>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  )
}
