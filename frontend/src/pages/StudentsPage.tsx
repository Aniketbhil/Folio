import React, { useState } from 'react'
import { useStudent } from '../context/useStudent'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Alert, EmptyState, LoadingState } from '../components/ui/Feedback'
import { SearchIcon, UserIcon } from '../components/ui/Icons'
import { Check, Plus, RefreshCw, Trash2, UserCheck } from 'lucide-react'

export const StudentsPage: React.FC = () => {
  const {
    students,
    activeStudentId,
    isLoading,
    error,
    setActiveStudentId,
    refreshStudents,
    addStudent,
    removeStudent,
  } = useStudent()

  // Local state
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingStudentId, setDeletingStudentId] = useState<number | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Handle student creation
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = nameInput.trim()
    if (!trimmed) {
      setFormError('Student name is required.')
      return
    }

    setIsSubmitting(true)
    setFormError(null)
    try {
      await addStudent({ name: trimmed })
      setNameInput('')
      setIsCreateOpen(false)
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to create student.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle student deletion
  const handleDelete = async () => {
    if (deletingStudentId === null) return
    setIsDeleting(true)
    try {
      await removeStudent(deletingStudentId)
      setDeletingStudentId(null)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete student.')
    } finally {
      setIsDeleting(false)
    }
  }

  // Filter students by search
  const filteredStudents = students.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <PageContainer>
      <PageHeader
        title="Student Profiles"
        description="Select an active student profile to personalize tutoring, practice quizzes, and mastery tracking."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refreshStudents()}
              disabled={isLoading}
              title="Refresh students from server"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setFormError(null)
                setNameInput('')
                setIsCreateOpen(true)
              }}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Add Student
            </Button>
          </div>
        }
      />

      {/* Global Server Error */}
      {error && (
        <Alert
          variant="error"
          title="Could not load students"
          description={error}
          action={
            <Button size="sm" variant="outline" onClick={() => void refreshStudents()}>
              Retry
            </Button>
          }
        />
      )}

      {/* Filter and stats row */}
      {students.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="max-w-xs w-full">
            <Input
              placeholder="Search students by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<SearchIcon className="w-4 h-4" />}
            />
          </div>
          <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">
            Showing <span className="font-semibold">{filteredStudents.length}</span> of{' '}
            <span className="font-semibold">{students.length}</span> registered students
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && students.length === 0 ? (
        <LoadingState message="Loading student profiles from backend..." />
      ) : students.length === 0 ? (
        <EmptyState
          icon={<UserIcon className="w-6 h-6" />}
          title="No Students Registered Yet"
          description="Create your first learner profile to begin personalized tutoring and adaptive learning."
          action={
            <Button
              variant="primary"
              size="md"
              onClick={() => {
                setFormError(null)
                setNameInput('')
                setIsCreateOpen(true)
              }}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              Register First Student
            </Button>
          }
        />
      ) : filteredStudents.length === 0 ? (
        <EmptyState
          title="No Matching Students"
          description={`No students match the search query "${searchQuery}".`}
          action={
            <Button variant="outline" size="sm" onClick={() => setSearchQuery('')}>
              Clear Search
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-4">
          {filteredStudents.map((student) => {
            const isActive = student.id === activeStudentId
            const formattedDate = new Date(student.created_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            })

            return (
              <Card
                key={student.id}
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
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                          isActive
                            ? 'bg-brand-600 text-white font-bold'
                            : 'bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted border border-surface-border dark:border-dark-border'
                        }`}
                      >
                        {student.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <CardTitle className="text-base truncate">{student.name}</CardTitle>
                        <CardDescription className="text-xs">
                          Student ID: #{student.id} &bull; Joined {formattedDate}
                        </CardDescription>
                      </div>
                    </div>

                    {isActive && (
                      <Badge variant="brand" size="sm" dot>
                        Active
                      </Badge>
                    )}
                  </div>

                  {/* Course Activity Summary */}
                  {student.courses_with_activity && student.courses_with_activity.length > 0 ? (
                    <div className="mt-3 pt-3 border-t border-surface-border-subtle dark:border-dark-border-subtle space-y-1.5">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                        Active Courses ({student.courses_with_activity.length})
                      </span>
                      <div className="space-y-1">
                        {student.courses_with_activity.map((act) => (
                          <div
                            key={act.course_id}
                            className="flex items-center justify-between text-xs py-0.5"
                          >
                            <span className="truncate max-w-40 text-surface-text dark:text-dark-text">
                              {act.course_name}
                            </span>
                            <span className="text-surface-text-muted dark:text-dark-text-muted font-mono">
                              {act.average_mastery !== null
                                ? `${Math.round(act.average_mastery * 100)}% mastery`
                                : 'Started'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                {/* Actions row */}
                <div className="flex items-center justify-between pt-4 mt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle gap-2">
                  {isActive ? (
                    <div className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 dark:text-brand-300">
                      <UserCheck className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                      <span>Current Profile</span>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setActiveStudentId(student.id)}
                      leftIcon={<Check className="w-3.5 h-3.5" />}
                    >
                      Select
                    </Button>
                  )}

                  <button
                    type="button"
                    onClick={() => setDeletingStudentId(student.id)}
                    className="p-1.5 text-surface-text-muted/60 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded transition-colors cursor-pointer"
                    title={`Delete ${student.name}`}
                    aria-label={`Delete student ${student.name}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Modal: Create Student */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => !isSubmitting && setIsCreateOpen(false)}
        title="Add New Student"
        description="Enter the display name for the student. Profile progress and tutoring history will be linked to this account."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Student Display Name *"
            placeholder="e.g. Maya Chen, Alex Rivera"
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
              Create Student
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Delete Confirmation */}
      <Modal
        isOpen={deletingStudentId !== null}
        onClose={() => !isDeleting && setDeletingStudentId(null)}
        title="Delete Student Profile"
        description="Are you sure you want to delete this student? All associated assessment history and chat sessions will be permanently removed."
        maxWidth="sm"
      >
        <div className="space-y-4">
          <Alert
            variant="warning"
            description="This action cannot be undone. Cascade deletion removes all student mastery events."
          />

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setDeletingStudentId(null)}
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
