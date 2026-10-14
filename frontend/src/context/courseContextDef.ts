import { createContext } from 'react'
import type {
  CourseCreate,
  CourseDetailRead,
  CourseRead,
} from '../types/course'

export interface CourseContextValue {
  courses: CourseRead[]
  activeCourse: CourseRead | null
  activeCourseDetail: CourseDetailRead | null
  activeCourseId: number | null
  isLoading: boolean
  isLoadingDetail: boolean
  error: string | null
  setActiveCourseId: (id: number | null) => void
  refreshCourses: () => Promise<void>
  refreshActiveCourseDetail: () => Promise<void>
  addCourse: (payload: CourseCreate) => Promise<CourseRead>
  removeCourse: (id: number) => Promise<void>
}

export const CourseContext = createContext<CourseContextValue | undefined>(undefined)
