import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { useStudent } from '../context/useStudent'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Alert } from '../components/ui/Feedback'
import { Modal } from '../components/ui/Modal'
import { changePassword as apiChangePassword } from '../api/auth'
import { formatApiError } from '../api/errors'
import { BookOpenIcon } from '../components/ui/Icons'
import {
  Calendar,
  Check,
  KeyRound,
  LogOut,
  Mail,
  Trash2,
  X,
} from 'lucide-react'

export const ProfilePage: React.FC = () => {
  const { user, logout } = useAuth()
  const { activeStudent, removeStudent } = useStudent()
  const navigate = useNavigate()

  // Change Password state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  // Logout / Delete modal state
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [isDeletingAccount, setIsDeletingAccount] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Password rules validation for new password
  const passwordRules = useMemo(() => {
    return {
      length: newPassword.length >= 8 && newPassword.length <= 128,
      uppercase: /[A-Z]/.test(newPassword),
      lowercase: /[a-z]/.test(newPassword),
      symbol: /[^a-zA-Z0-9\s]/.test(newPassword),
      matches: newPassword.length > 0 && newPassword === confirmPassword,
      different: newPassword.length > 0 && newPassword !== currentPassword,
    }
  }, [newPassword, confirmPassword, currentPassword])

  const isNewPasswordValid =
    passwordRules.length &&
    passwordRules.uppercase &&
    passwordRules.lowercase &&
    passwordRules.symbol &&
    passwordRules.different &&
    passwordRules.matches

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordSuccess(null)
    setPasswordError(null)

    if (!currentPassword) {
      setPasswordError('Current password is required.')
      return
    }

    if (!isNewPasswordValid) {
      setPasswordError('Please ensure your new password satisfies all strength rules and matches confirmation.')
      return
    }

    setIsChangingPassword(true)

    try {
      await apiChangePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setPasswordSuccess('Password successfully updated!')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      setPasswordError(formatApiError(err, 'Failed to update password.'))
    } finally {
      setIsChangingPassword(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleDeleteAccount = async () => {
    if (!user) return
    setIsDeletingAccount(true)
    setDeleteError(null)

    try {
      await removeStudent(user.id)
      navigate('/login', { replace: true })
    } catch (err: unknown) {
      setDeleteError(formatApiError(err, 'Failed to delete account.'))
      setIsDeletingAccount(false)
    }
  }

  const formattedCreatedDate = activeStudent?.created_at
    ? (() => {
        try {
          return new Date(activeStudent.created_at).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })
        } catch {
          return activeStudent.created_at
        }
      })()
    : 'Unknown'

  const courseActivities = activeStudent?.courses_with_activity || []

  return (
    <PageContainer>
      <PageHeader
        title="Student Profile"
        description="Manage your student account settings, active courses, and security credentials."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsLogoutModalOpen(true)}
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
          >
            Sign Out
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Profile overview & Course Activity (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Identity Card */}
          <Card padding="md">
            <div className="flex items-start justify-between pb-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-brand-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
                  {user?.name.charAt(0).toUpperCase() || 'S'}
                </div>
                <div>
                  <CardTitle className="text-lg">{user?.name || 'Student Profile'}</CardTitle>
                  <CardDescription className="text-xs">
                    Account ID #{user?.id}
                  </CardDescription>
                </div>
              </div>
              <Badge variant="brand" size="sm" dot>
                Active Account
              </Badge>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle text-xs">
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border-subtle dark:border-dark-border-subtle">
                <Mail className="w-4 h-4 text-surface-text-muted dark:text-dark-text-muted shrink-0" />
                <div className="truncate">
                  <div className="text-[10px] uppercase font-semibold text-surface-text-muted dark:text-dark-text-muted">
                    Email
                  </div>
                  <div className="font-medium text-surface-text dark:text-dark-text truncate">
                    {user?.email || 'No email attached'}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border-subtle dark:border-dark-border-subtle">
                <Calendar className="w-4 h-4 text-surface-text-muted dark:text-dark-text-muted shrink-0" />
                <div>
                  <div className="text-[10px] uppercase font-semibold text-surface-text-muted dark:text-dark-text-muted">
                    Member Since
                  </div>
                  <div className="font-medium text-surface-text dark:text-dark-text">
                    {formattedCreatedDate}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Active Course Activity Card */}
          <Card padding="md">
            <div className="flex items-center justify-between pb-3 border-b border-surface-border-subtle dark:border-dark-border-subtle">
              <div className="flex items-center gap-2">
                <BookOpenIcon className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                <CardTitle className="text-base">Course Progress & Activity</CardTitle>
              </div>
              <span className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                {courseActivities.length} active course(s)
              </span>
            </div>

            {courseActivities.length === 0 ? (
              <div className="py-8 text-center text-xs text-surface-text-muted dark:text-dark-text-muted space-y-1">
                <p className="font-medium">No recorded course activity yet.</p>
                <p>Start a quiz or conversation with the AI tutor to track topic mastery.</p>
              </div>
            ) : (
              <div className="divide-y divide-surface-border-subtle dark:divide-dark-border-subtle pt-2">
                {courseActivities.map((act) => (
                  <div key={act.course_id} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="font-medium text-sm text-surface-text dark:text-dark-text truncate">
                        {act.course_name}
                      </div>
                      <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                        Course ID #{act.course_id}
                        {act.last_active_at && (
                          <span> &bull; Last active {new Date(act.last_active_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      {act.average_mastery !== null ? (
                        <Badge
                          variant={act.average_mastery >= 0.7 ? 'brand' : act.average_mastery >= 0.4 ? 'neutral' : 'amber'}
                          size="sm"
                        >
                          {Math.round(act.average_mastery * 100)}% Mastery
                        </Badge>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          Unassessed
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right column: Security / Change Password & Danger Zone (1 col) */}
        <div className="space-y-6">
          {/* Change Password Card */}
          <Card padding="md">
            <div className="flex items-center gap-2 pb-3 border-b border-surface-border-subtle dark:border-dark-border-subtle">
              <KeyRound className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <CardTitle className="text-base">Change Password</CardTitle>
            </div>

            {passwordSuccess && (
              <div className="mt-3">
                <Alert variant="success" description={passwordSuccess} />
              </div>
            )}

            {passwordError && (
              <div className="mt-3">
                <Alert variant="error" description={passwordError} />
              </div>
            )}

            <form onSubmit={handlePasswordChange} className="space-y-3 pt-3">
              <Input
                label="Current Password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="current-password"
              />

              <Input
                label="New Password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="new-password"
              />

              <Input
                label="Confirm New Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                autoComplete="new-password"
              />

              {/* Requirement Checklist */}
              <div className="p-2.5 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border-subtle dark:border-dark-border-subtle text-[11px] space-y-1">
                <div className="font-semibold text-surface-text-muted dark:text-dark-text-muted uppercase tracking-wider">
                  Strength Rules
                </div>
                <div className="grid grid-cols-2 gap-1 text-surface-text-muted dark:text-dark-text-muted">
                  <div className={`flex items-center gap-1 ${passwordRules.length ? 'text-brand-600 dark:text-brand-400 font-medium' : ''}`}>
                    {passwordRules.length ? <Check className="w-3 h-3" /> : <X className="w-3 h-3 opacity-40" />}
                    <span>8+ chars</span>
                  </div>
                  <div className={`flex items-center gap-1 ${passwordRules.uppercase ? 'text-brand-600 dark:text-brand-400 font-medium' : ''}`}>
                    {passwordRules.uppercase ? <Check className="w-3 h-3" /> : <X className="w-3 h-3 opacity-40" />}
                    <span>1 uppercase</span>
                  </div>
                  <div className={`flex items-center gap-1 ${passwordRules.lowercase ? 'text-brand-600 dark:text-brand-400 font-medium' : ''}`}>
                    {passwordRules.lowercase ? <Check className="w-3 h-3" /> : <X className="w-3 h-3 opacity-40" />}
                    <span>1 lowercase</span>
                  </div>
                  <div className={`flex items-center gap-1 ${passwordRules.symbol ? 'text-brand-600 dark:text-brand-400 font-medium' : ''}`}>
                    {passwordRules.symbol ? <Check className="w-3 h-3" /> : <X className="w-3 h-3 opacity-40" />}
                    <span>1 symbol</span>
                  </div>
                </div>
              </div>

              <div className="pt-1">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  fullWidth
                  isLoading={isChangingPassword}
                  disabled={!isNewPasswordValid || !currentPassword}
                >
                  Update Password
                </Button>
              </div>
            </form>
          </Card>

          {/* Danger Zone */}
          <Card padding="md" className="border-red-200 dark:border-red-950/60 bg-red-50/20 dark:bg-red-950/10">
            <div className="flex items-center gap-2 pb-2">
              <Trash2 className="w-4 h-4 text-red-600 dark:text-red-400" />
              <CardTitle className="text-base text-red-700 dark:text-red-400">Account Actions</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Permanently delete this student account along with all study conversations, quiz attempts, and mastery history.
            </CardDescription>

            <div className="pt-4 mt-3 border-t border-red-200/60 dark:border-red-900/40 flex flex-col gap-2">
              <Button
                variant="danger"
                size="sm"
                fullWidth
                onClick={() => setIsDeleteModalOpen(true)}
              >
                Delete Account
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Logout Confirmation Modal */}
      <Modal
        isOpen={isLogoutModalOpen}
        onClose={() => setIsLogoutModalOpen(false)}
        title="Sign Out of Folio"
      >
        <div className="space-y-4">
          <p className="text-sm text-surface-text-muted dark:text-dark-text-muted">
            Are you sure you want to sign out? Your session token will be cleared from this browser.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsLogoutModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleLogout}
            >
              Sign Out
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Account Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => !isDeletingAccount && setIsDeleteModalOpen(false)}
        title="Delete Account Permanently"
      >
        <div className="space-y-4">
          <p className="text-sm text-surface-text dark:text-dark-text">
            This action <strong className="text-red-600 dark:text-red-400">cannot be undone</strong>. All your quiz attempts, grounded conversations, and mastery graph progress will be erased immediately.
          </p>

          {deleteError && (
            <Alert variant="error" description={deleteError} />
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteModalOpen(false)}
              disabled={isDeletingAccount}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              isLoading={isDeletingAccount}
              onClick={handleDeleteAccount}
            >
              Permanently Delete
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  )
}
