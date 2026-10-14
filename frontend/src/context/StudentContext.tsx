import React, { useCallback, useEffect, useState } from 'react'
import { deleteStudent, getStudent } from '../api/students'
import { formatApiError } from '../api/errors'
import { StudentContext } from './studentContextDef'
import { useAuth } from './useAuth'
import type { StudentRead } from '../types/student'

export const StudentProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { user, isAuthenticated, logout } = useAuth()
  const [studentDetail, setStudentDetail] = useState<StudentRead | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch full student record asynchronously when user is authenticated
  useEffect(() => {
    if (!user || !isAuthenticated) {
      return
    }

    let isMounted = true
    getStudent(user.id)
      .then((data) => {
        if (isMounted) {
          setStudentDetail(data)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(formatApiError(err, 'Failed to fetch student details'))
        }
      })

    return () => {
      isMounted = false
    }
  }, [user, isAuthenticated])

  // Derive active student profile strictly tied to authenticated user (Account Isolation)
  const activeStudent: StudentRead | null = user
    ? studentDetail && studentDetail.id === user.id
      ? studentDetail
      : {
          id: user.id,
          name: user.name,
          created_at: new Date().toISOString(),
          courses_with_activity: null,
        }
    : null

  const students: StudentRead[] = activeStudent ? [activeStudent] : []
  const activeStudentId: number | null = activeStudent ? activeStudent.id : null

  const setActiveStudentId = useCallback(() => {
    // Account isolation: student ID is strictly bound to the authenticated account
  }, [])

  const refreshStudents = useCallback(async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await getStudent(user.id)
      setStudentDetail(data)
    } catch (err) {
      setError(formatApiError(err, 'Failed to fetch student details'))
    } finally {
      setIsLoading(false)
    }
  }, [user])

  const addStudent = useCallback(async (): Promise<StudentRead> => {
    throw new Error('Please register a new account to create a student profile.')
  }, [])

  const removeStudent = useCallback(
    async (id: number): Promise<void> => {
      await deleteStudent(id)
      logout()
    },
    [logout]
  )

  return (
    <StudentContext.Provider
      value={{
        students,
        activeStudent,
        activeStudentId,
        isLoading,
        error,
        setActiveStudentId,
        refreshStudents,
        addStudent,
        removeStudent,
      }}
    >
      {children}
    </StudentContext.Provider>
  )
}
