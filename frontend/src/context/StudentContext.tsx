import React, { useCallback, useEffect, useState } from 'react'
import { createStudent, deleteStudent, listStudents } from '../api/students'
import { formatApiError } from '../api/errors'
import { StudentContext } from './studentContextDef'
import type { StudentCreate, StudentRead } from '../types/student'

const STORAGE_KEY = 'folio_active_student_id'

export const StudentProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [students, setStudents] = useState<StudentRead[]>([])
  const [activeStudentId, setActiveStudentIdState] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = parseInt(stored, 10)
        return isNaN(parsed) ? null : parsed
      }
    }
    return null
  })
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Validation helper
  const syncActiveStudentWithList = useCallback((data: StudentRead[]) => {
    setActiveStudentIdState((currentId) => {
      if (currentId === null) {
        if (data.length === 1) {
          try {
            localStorage.setItem(STORAGE_KEY, String(data[0].id))
          } catch {
            // ignore storage error
          }
          return data[0].id
        }
        return null
      }

      const exists = data.some((s) => s.id === currentId)
      if (!exists) {
        try {
          localStorage.removeItem(STORAGE_KEY)
        } catch {
          // ignore
        }
        return null
      }
      return currentId
    })
  }, [])

  // Explicit setter for active student
  const setActiveStudentId = useCallback((id: number | null) => {
    setActiveStudentIdState(id)
    try {
      if (id === null) {
        localStorage.removeItem(STORAGE_KEY)
      } else {
        localStorage.setItem(STORAGE_KEY, String(id))
      }
    } catch {
      // ignore storage error
    }
  }, [])

  // Manual refresh callable by UI
  const refreshStudents = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await listStudents()
      setStudents(data)
      syncActiveStudentWithList(data)
    } catch (err) {
      setError(formatApiError(err, 'Failed to load students'))
    } finally {
      setIsLoading(false)
    }
  }, [syncActiveStudentWithList])

  // Mount effect: fetch async without synchronous setState in effect body
  useEffect(() => {
    let isMounted = true

    listStudents()
      .then((data) => {
        if (isMounted) {
          setStudents(data)
          syncActiveStudentWithList(data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(formatApiError(err, 'Failed to load students'))
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [syncActiveStudentWithList])

  // Action: Add student
  const addStudent = useCallback(
    async (payload: StudentCreate): Promise<StudentRead> => {
      const newStudent = await createStudent(payload)
      setStudents((prev) => [...prev, newStudent])
      setActiveStudentId(newStudent.id)
      return newStudent
    },
    [setActiveStudentId]
  )

  // Action: Delete student
  const removeStudent = useCallback(
    async (id: number): Promise<void> => {
      await deleteStudent(id)
      setStudents((prev) => prev.filter((s) => s.id !== id))
      if (activeStudentId === id) {
        setActiveStudentId(null)
      }
    },
    [activeStudentId, setActiveStudentId]
  )

  const activeStudent = students.find((s) => s.id === activeStudentId) || null

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
