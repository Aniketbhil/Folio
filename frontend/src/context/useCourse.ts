import { useContext } from 'react'
import { CourseContext, type CourseContextValue } from './courseContextDef'

export function useCourse(): CourseContextValue {
  const context = useContext(CourseContext)
  if (!context) {
    throw new Error('useCourse must be used within a CourseProvider')
  }
  return context
}
