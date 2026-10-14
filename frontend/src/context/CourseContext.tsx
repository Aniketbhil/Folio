import React, { useCallback, useEffect, useState } from 'react'
import {
  createCourse,
  deleteCourse,
  getCourseDetail,
  listCourses,
} from '../api/courses'
import { formatApiError } from '../api/errors'
import { CourseContext } from './courseContextDef'
import type {
  CourseCreate,
  CourseDetailRead,
  CourseRead,
} from '../types/course'

const STORAGE_KEY = 'folio_active_course_id'

export const CourseProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [courses, setCourses] = useState<CourseRead[]>([])
  const [activeCourseId, setActiveCourseIdState] = useState<number | null>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = parseInt(stored, 10)
        return isNaN(parsed) ? null : parsed
      }
    }
    return null
  })
  const [activeCourseDetail, setActiveCourseDetail] =
    useState<CourseDetailRead | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Validation helper
  const syncActiveCourseWithList = useCallback((data: CourseRead[]) => {
    setActiveCourseIdState((currentId) => {
      if (currentId === null) {
        if (data.length === 1) {
          try {
            localStorage.setItem(STORAGE_KEY, String(data[0].id))
          } catch {
            // ignore
          }
          return data[0].id
        }
        return null
      }

      const exists = data.some((c) => c.id === currentId)
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

  // Explicit setter for active course
  const setActiveCourseId = useCallback((id: number | null) => {
    setActiveCourseIdState(id)
    try {
      if (id === null) {
        localStorage.removeItem(STORAGE_KEY)
      } else {
        localStorage.setItem(STORAGE_KEY, String(id))
      }
    } catch {
      // ignore
    }
  }, [])

  // Manual refresh for course details
  const refreshActiveCourseDetail = useCallback(
    async (targetId?: number | null): Promise<void> => {
      const idToFetch = targetId !== undefined ? targetId : activeCourseId
      if (idToFetch === null) {
        setActiveCourseDetail(null)
        return
      }

      setIsLoadingDetail(true)
      try {
        const detail = await getCourseDetail(idToFetch)
        // Guard against race conditions: only update activeCourseDetail if still the active course
        setActiveCourseIdState((currentId) => {
          if (currentId === idToFetch) {
            setActiveCourseDetail(detail)
          }
          return currentId
        })
        // Synchronize the course's kb_status and metadata in the courses list
        setCourses((prev) =>
          prev.map((c) =>
            c.id === idToFetch
              ? {
                  ...c,
                  kb_status: detail.kb_status,
                  kb_error: detail.kb_error,
                  kb_built_at: detail.kb_built_at,
                }
              : c
          )
        )
      } catch (err) {
        // Do not silently overwrite valid metrics with zero/null if network request fails
        console.error('Failed to refresh course detail', err)
      } finally {
        setIsLoadingDetail(false)
      }
    },
    [activeCourseId]
  )

  // Manual refresh callable by UI (refreshes course list AND active course detail)
  const refreshCourses = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await listCourses()
      setCourses(data)
      syncActiveCourseWithList(data)

      // Also refresh active course detail if a course is active
      if (activeCourseId !== null) {
        await refreshActiveCourseDetail(activeCourseId)
      }
    } catch (err) {
      setError(formatApiError(err, 'Failed to load courses'))
    } finally {
      setIsLoading(false)
    }
  }, [activeCourseId, refreshActiveCourseDetail, syncActiveCourseWithList])

  // Mount effect: fetch courses async
  useEffect(() => {
    let isMounted = true

    listCourses()
      .then((data) => {
        if (isMounted) {
          setCourses(data)
          syncActiveCourseWithList(data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(formatApiError(err, 'Failed to load courses'))
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [syncActiveCourseWithList])

  // Fetch course detail when activeCourseId changes with race-condition guard
  useEffect(() => {
    if (activeCourseId === null) {
      const timer = window.setTimeout(() => {
        setActiveCourseDetail(null)
      }, 0)
      return () => {
        clearTimeout(timer)
      }
    }

    const currentTargetId = activeCourseId
    let isMounted = true

    getCourseDetail(currentTargetId)
      .then((detail) => {
        if (isMounted) {
          setActiveCourseIdState((currentId) => {
            if (currentId === currentTargetId) {
              setActiveCourseDetail(detail)
            }
            return currentId
          })
        }
      })
      .catch((err) => {
        console.error(`Failed to load initial course detail for #${currentTargetId}`, err)
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingDetail(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [activeCourseId])

  // Action: Add course
  const addCourse = useCallback(
    async (payload: CourseCreate): Promise<CourseRead> => {
      const newCourse = await createCourse(payload)
      setCourses((prev) => [...prev, newCourse])
      setActiveCourseId(newCourse.id)
      return newCourse
    },
    [setActiveCourseId]
  )

  // Action: Delete course
  const removeCourse = useCallback(
    async (id: number): Promise<void> => {
      await deleteCourse(id)
      setCourses((prev) => prev.filter((c) => c.id !== id))
      if (activeCourseId === id) {
        setActiveCourseId(null)
        setActiveCourseDetail(null)
      }
    },
    [activeCourseId, setActiveCourseId]
  )

  const activeCourse = courses.find((c) => c.id === activeCourseId) || null

  return (
    <CourseContext.Provider
      value={{
        courses,
        activeCourse,
        activeCourseDetail,
        activeCourseId,
        isLoading,
        isLoadingDetail,
        error,
        setActiveCourseId,
        refreshCourses,
        refreshActiveCourseDetail,
        addCourse,
        removeCourse,
      }}
    >
      {children}
    </CourseContext.Provider>
  )
}
