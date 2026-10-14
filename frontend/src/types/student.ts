/**
 * Student schemas matching backend/app/schemas/student.py
 */

export interface StudentCreate {
  name: string
}

export interface StudentCourseActivityOut {
  course_id: number
  course_name: string
  average_mastery: number | null
  last_active_at: string | null
}

export interface StudentRead {
  id: number
  name: string
  created_at: string
  courses_with_activity?: StudentCourseActivityOut[] | null
}

export interface StudentDeleteResponse {
  deleted: boolean
}
