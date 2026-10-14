import React, { useState } from 'react'
import { useCourse } from '../context/useCourse'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Alert, EmptyState, LoadingState } from '../components/ui/Feedback'
import { BookOpenIcon, SearchIcon } from '../components/ui/Icons'
import { BookCheck, Check, Plus, RefreshCw, Trash2 } from 'lucide-react'

export const CoursesPage: React.FC = () => {
  const {
    courses,
    activeCourseId,
    activeCourseDetail,
    isLoading,
    isLoadingDetail,
    error,
    setActiveCourseId,
    refreshCourses,
    refreshActiveCourseDetail,
    addCourse,
    removeCourse,
  } = useCourse()

  // Local state
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [descInput, setDescInput] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingCourseId, setDeletingCourseId] = useState<number | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Handle course creation
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedName = nameInput.trim()
    if (!trimmedName) {
      setFormError('Course name is required.')
      return
    }

    setIsSubmitting(true)
    setFormError(null)
    try {
      await addCourse({
        name: trimmedName,
        description: descInput.trim() || undefined,
      })
      setNameInput('')
      setDescInput('')
      setIsCreateOpen(false)
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to create course.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle course deletion
  const handleDelete = async () => {
    if (deletingCourseId === null) return
    setIsDeleting(true)
    try {
      await removeCourse(deletingCourseId)
      setDeletingCourseId(null)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete course.')
    } finally {
      setIsDeleting(false)
    }
  }

  // Filter courses by search
  const filteredCourses = courses.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  // Status badge helper
  const renderKbBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return (
          <Badge variant="brand" size="sm" dot>
            KB Ready
          </Badge>
        )
      case 'building':
        return (
          <Badge variant="amber" size="sm" dot>
            KB Building
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="error" size="sm" dot>
            KB Failed
          </Badge>
        )
      case 'empty':
      default:
        return (
          <Badge variant="neutral" size="sm">
            KB Empty
          </Badge>
        )
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Course Subjects"
        description="Select an active course syllabus to scope AI tutoring, source documents, and assessment generation."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                await refreshCourses()
                await refreshActiveCourseDetail()
              }}
              disabled={isLoading || isLoadingDetail}
              title="Refresh courses and knowledge base metrics from server"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading || isLoadingDetail ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setFormError(null)
                setNameInput('')
                setDescInput('')
                setIsCreateOpen(true)
              }}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              New Course
            </Button>
          </div>
        }
      />

      {/* Global Server Error */}
      {error && (
        <Alert
          variant="error"
          title="Could not load courses"
          description={error}
          action={
            <Button size="sm" variant="outline" onClick={() => void refreshCourses()}>
              Retry
            </Button>
          }
        />
      )}

      {/* Search and Counts Header */}
      {courses.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="max-w-xs w-full">
            <Input
              placeholder="Search courses or topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<SearchIcon className="w-4 h-4" />}
            />
          </div>
          <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">
            Showing <span className="font-semibold">{filteredCourses.length}</span> of{' '}
            <span className="font-semibold">{courses.length}</span> available courses
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && courses.length === 0 ? (
        <LoadingState message="Loading courses from backend..." />
      ) : courses.length === 0 ? (
        <EmptyState
          icon={<BookOpenIcon className="w-6 h-6" />}
          title="No Courses Available"
          description="Create your first course subject to begin ingesting textbooks, slides, and syllabus documents."
          action={
            <Button
              variant="primary"
              size="md"
              onClick={() => {
                setFormError(null)
                setNameInput('')
                setDescInput('')
                setIsCreateOpen(true)
              }}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Create First Course
            </Button>
          }
        />
      ) : filteredCourses.length === 0 ? (
        <EmptyState
          title="No Matching Courses"
          description={`No courses found matching "${searchQuery}".`}
          action={
            <Button variant="outline" size="sm" onClick={() => setSearchQuery('')}>
              Clear Search
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-4">
          {filteredCourses.map((course) => {
            const isActive = course.id === activeCourseId
            const formattedDate = new Date(course.created_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })

            return (
              <Card
                key={course.id}
                variant={isActive ? 'default' : 'muted'}
                padding="md"
                className={`relative flex flex-col justify-between transition-all ${
                  isActive
                    ? 'border-brand-500/80 ring-1 ring-brand-500/30 bg-surface-card dark:bg-dark-card'
                    : 'hover:border-surface-border'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 pb-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-base truncate">{course.name}</CardTitle>
                      </div>
                      <CardDescription className="text-xs mt-0.5">
                        Course #{course.id} &bull; Created {formattedDate}
                      </CardDescription>
                    </div>
                    {renderKbBadge(course.kb_status)}
                  </div>

                  {course.description && (
                    <p className="text-xs text-surface-text-muted dark:text-dark-text-muted mt-2 line-clamp-2 leading-relaxed">
                      {course.description}
                    </p>
                  )}

                  {/* Active Course Metrics inspection */}
                  {isActive && activeCourseDetail && (
                    <div className="mt-3.5 pt-3 border-t border-surface-border-subtle dark:border-dark-border-subtle">
                      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted pb-1.5">
                        <span>Knowledge Base Metrics</span>
                        {isLoadingDetail && <span className="lowercase font-normal">updating...</span>}
                      </div>

                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="p-2 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border-subtle dark:border-dark-border-subtle">
                          <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                            {activeCourseDetail.counts.sources}
                          </div>
                          <div className="text-[10px] text-surface-text-muted dark:text-dark-text-muted">
                            Sources
                          </div>
                        </div>

                        <div className="p-2 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border-subtle dark:border-dark-border-subtle">
                          <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                            {activeCourseDetail.counts.topics}
                          </div>
                          <div className="text-[10px] text-surface-text-muted dark:text-dark-text-muted">
                            Topics
                          </div>
                        </div>

                        <div className="p-2 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border-subtle dark:border-dark-border-subtle">
                          <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                            {activeCourseDetail.counts.concepts}
                          </div>
                          <div className="text-[10px] text-surface-text-muted dark:text-dark-text-muted">
                            Concepts
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions row */}
                <div className="flex items-center justify-between pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle gap-2">
                  {isActive ? (
                    <div className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 dark:text-brand-300">
                      <BookCheck className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                      <span>Current Course</span>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setActiveCourseId(course.id)}
                      leftIcon={<Check className="w-3.5 h-3.5" />}
                    >
                      Select
                    </Button>
                  )}

                  <button
                    type="button"
                    onClick={() => setDeletingCourseId(course.id)}
                    className="p-1.5 text-surface-text-muted/60 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded transition-colors cursor-pointer"
                    title={`Delete ${course.name}`}
                    aria-label={`Delete course ${course.name}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Modal: Create Course */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => !isSubmitting && setIsCreateOpen(false)}
        title="Create New Course"
        description="Provide a title and optional syllabus description for the course."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Course Name *"
            placeholder="e.g. Cognitive Psychology, Linear Algebra"
            value={nameInput}
            onChange={(e) => {
              setNameInput(e.target.value)
              if (formError) setFormError(null)
            }}
            error={formError || undefined}
            autoFocus
            disabled={isSubmitting}
            required
          />

          <div className="space-y-1">
            <label
              htmlFor="course-desc"
              className="block text-xs sm:text-sm font-medium text-surface-text dark:text-dark-text"
            >
              Description / Syllabus Overview (Optional)
            </label>
            <textarea
              id="course-desc"
              rows={3}
              placeholder="e.g. Fundamental topics, key textbook chapters, or focus areas..."
              value={descInput}
              onChange={(e) => setDescInput(e.target.value)}
              disabled={isSubmitting}
              className="w-full rounded-lg text-sm bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text border border-surface-border dark:border-dark-border focus:border-brand-500 focus:ring-brand-500/20 p-3 placeholder:text-surface-text-muted/60 dark:placeholder:text-dark-text-muted/60 transition-colors focus:outline-none focus:ring-2 disabled:opacity-50"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsCreateOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
              disabled={!nameInput.trim()}
            >
              Create Course
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Delete Confirmation */}
      <Modal
        isOpen={deletingCourseId !== null}
        onClose={() => !isDeleting && setDeletingCourseId(null)}
        title="Delete Course Subject"
        description="Are you sure you want to delete this course? All associated uploaded files, extracted knowledge base vectors, and assessment records will be permanently deleted."
        maxWidth="sm"
      >
        <div className="space-y-4">
          <Alert
            variant="warning"
            description="This action cannot be undone. All extracted chunks, topics, and question vector embeddings will be cascade deleted."
          />

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setDeletingCourseId(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() => void handleDelete()}
              isLoading={isDeleting}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  )
}
