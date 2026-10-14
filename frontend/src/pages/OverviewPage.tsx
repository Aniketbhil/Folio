import React from 'react'
import { Link } from 'react-router-dom'
import { useStudent } from '../context/useStudent'
import { useCourse } from '../context/useCourse'
import { useMeta } from '../context/useMeta'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Alert } from '../components/ui/Feedback'
import {
  ActivityIcon,
  BookOpenIcon,
  CheckCircleIcon,
  MessageSquareIcon,
  UserIcon,
} from '../components/ui/Icons'
import { ArrowRight, ShieldCheck } from 'lucide-react'

export const OverviewPage: React.FC = () => {
  const { activeStudent } = useStudent()
  const { activeCourse, activeCourseDetail, courses } = useCourse()
  const { meta, isLoading: isMetaLoading, error: metaError } = useMeta()

  const hasStudent = activeStudent !== null
  const hasCourse = activeCourse !== null
  const isReady = hasStudent && hasCourse

  return (
    <PageContainer>
      <PageHeader
        title="Learning Workspace"
        description="Source-grounded study companion with personalized tutoring, topic mastery tracking, and adaptive assessments."
        badge={
          isReady ? (
            <Badge variant="brand" size="sm" dot>
              Context Active
            </Badge>
          ) : (
            <Badge variant="amber" size="sm" dot>
              Setup Required
            </Badge>
          )
        }
      />

      {/* Backend connection / Metadata status banner */}
      {metaError ? (
        <Alert
          variant="error"
          title="Backend Connection Notice"
          description={metaError}
        />
      ) : isMetaLoading ? (
        <div className="text-xs text-surface-text-muted dark:text-dark-text-muted animate-pulse">
          Connecting to Folio backend services...
        </div>
      ) : meta ? (
        <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card shadow-xs text-xs">
          <div className="flex items-center gap-2 text-surface-text dark:text-dark-text">
            <ShieldCheck className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span className="font-medium">Backend v{meta.version} Connected</span>
            <span className="text-surface-border dark:text-dark-border">&bull;</span>
            <span className="text-surface-text-muted dark:text-dark-text-muted">
              LLM Engine: <strong className="text-surface-text dark:text-dark-text capitalize">{meta.features.llm_mode}</strong>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="neutral" size="sm">
              Max Upload: {meta.limits.max_upload_mb} MB
            </Badge>
            <Badge variant="neutral" size="sm">
              Quiz Limit: {meta.limits.quiz_max_questions} Qs
            </Badge>
          </div>
        </div>
      ) : null}

      {/* Onboarding Status Grid: Student and Course Context Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Active Student Card */}
        <Card padding="md" variant={hasStudent ? 'default' : 'muted'}>
          <div className="flex items-start justify-between pb-2">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                  hasStudent
                    ? 'bg-brand-600 text-white font-bold'
                    : 'bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted'
                }`}
              >
                <UserIcon className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                  Active Student
                </span>
                <CardTitle className="text-base">
                  {hasStudent ? activeStudent.name : 'No Student Selected'}
                </CardTitle>
              </div>
            </div>
            {hasStudent ? (
              <Badge variant="brand" size="sm" dot>
                Selected
              </Badge>
            ) : (
              <Badge variant="amber" size="sm">
                Required
              </Badge>
            )}
          </div>

          <CardDescription className="text-xs pt-1">
            {hasStudent
              ? `Profile ID #${activeStudent.id}. All quiz attempts, tutor chats, and mastery tracking are personalized to your account.`
              : 'Sign in to access your personalized tutoring and learning progress.'}
          </CardDescription>

          <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center justify-between">
            <Link to="/profile">
              <Button variant={hasStudent ? 'secondary' : 'primary'} size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                Manage Profile
              </Button>
            </Link>
            <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
              {hasStudent ? 'Active Account' : 'Sign In Required'}
            </span>
          </div>
        </Card>

        {/* Active Course Card */}
        <Card padding="md" variant={hasCourse ? 'default' : 'muted'}>
          <div className="flex items-start justify-between pb-2">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                  hasCourse
                    ? 'bg-brand-600 text-white font-bold'
                    : 'bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted'
                }`}
              >
                <BookOpenIcon className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                  Active Course
                </span>
                <CardTitle className="text-base truncate max-w-50 sm:max-w-65">
                  {hasCourse ? activeCourse.name : 'No Course Selected'}
                </CardTitle>
              </div>
            </div>
            {hasCourse ? (
              <Badge variant="brand" size="sm" dot>
                {activeCourse.kb_status === 'ready'
                  ? 'KB Ready'
                  : activeCourse.kb_status === 'building'
                  ? 'Building'
                  : 'Selected'}
              </Badge>
            ) : (
              <Badge variant="amber" size="sm">
                Required
              </Badge>
            )}
          </div>

          <CardDescription className="text-xs pt-1">
            {hasCourse
              ? activeCourseDetail
                ? `Course #${activeCourse.id}. Knowledge Base contains ${activeCourseDetail.counts.sources} sources, ${activeCourseDetail.counts.topics} topics, and ${activeCourseDetail.counts.concepts} concepts.`
                : `Course #${activeCourse.id} is active. Sources and documents will be scoped to this course.`
              : courses.length > 0
              ? `${courses.length} course(s) available. Select a syllabus to continue.`
              : 'Create a course subject to upload textbooks, lecture slides, and syllabus files.'}
          </CardDescription>

          <div className="pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center justify-between">
            <Link to="/courses">
              <Button variant={hasCourse ? 'secondary' : 'primary'} size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                {hasCourse ? 'Change Course' : 'Select or Create Course'}
              </Button>
            </Link>
            <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
              {courses.length} course(s)
            </span>
          </div>
        </Card>
      </div>

      {/* Feature Capabilities - Restrained previews for upcoming chapters */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <h2 className="text-base sm:text-lg font-semibold tracking-tight text-surface-text dark:text-dark-text">
            Folio Learning Capabilities
          </h2>
          <span className="text-xs text-surface-text-muted dark:text-dark-text-muted">
            Integrations unlocked with active student & course
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
          <Card padding="md" variant={hasCourse ? 'default' : 'muted'} className="space-y-2">
            <div className="flex items-center justify-between pb-1">
              <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/40 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <BookOpenIcon className="w-4 h-4" />
              </div>
              <Badge variant="brand" size="sm" dot>
                Ready
              </Badge>
            </div>
            <CardTitle className="text-sm">Course Sources & Ingestion</CardTitle>
            <CardDescription className="text-xs">
              Upload PDF textbooks, lecture slides, and transcripts for automated chunking and topic indexing.
            </CardDescription>
            <div className="pt-2">
              <Link to="/sources">
                <Button variant="outline" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Manage Sources
                </Button>
              </Link>
            </div>
          </Card>

          <Card padding="md" variant={isReady ? 'default' : 'muted'} className="space-y-2">
            <div className="flex items-center justify-between pb-1">
              <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/40 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <MessageSquareIcon className="w-4 h-4" />
              </div>
              <Badge variant="brand" size="sm" dot>
                Ready
              </Badge>
            </div>
            <CardTitle className="text-sm">AI Socratic Tutor</CardTitle>
            <CardDescription className="text-xs">
              Conversational assistant strictly grounded in course materials with verbatim citations and follow-up prompts.
            </CardDescription>
            <div className="pt-2">
              <Link to="/tutor">
                <Button variant="outline" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Open Tutor
                </Button>
              </Link>
            </div>
          </Card>

          <Card padding="md" variant={isReady ? 'default' : 'muted'} className="space-y-2">
            <div className="flex items-center justify-between pb-1">
              <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/40 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <CheckCircleIcon className="w-4 h-4" />
              </div>
              <Badge variant="brand" size="sm" dot>
                Ready
              </Badge>
            </div>
            <CardTitle className="text-sm">Adaptive Assessments</CardTitle>
            <CardDescription className="text-xs">
              Diagnostic tests and practice quizzes with instant Bayesian Knowledge Tracing feedback.
            </CardDescription>
            <div className="pt-2">
              <Link to="/assessments">
                <Button variant="outline" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Start Assessments
                </Button>
              </Link>
            </div>
          </Card>

          <Card padding="md" variant={isReady ? 'default' : 'muted'} className="space-y-2">
            <div className="flex items-center justify-between pb-1">
              <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/40 flex items-center justify-center text-brand-700 dark:text-brand-300">
                <ActivityIcon className="w-4 h-4" />
              </div>
              <Badge variant="brand" size="sm" dot>
                Ready
              </Badge>
            </div>
            <CardTitle className="text-sm">Topic Mastery & Graph</CardTitle>
            <CardDescription className="text-xs">
              Hierarchical prerequisite concept DAG, forgetting curves, and spaced review tracking.
            </CardDescription>
            <div className="pt-2">
              <Link to="/mastery">
                <Button variant="outline" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  View Mastery Graph
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  )
}
