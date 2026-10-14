/**
 * Course schemas matching backend/app/schemas/course.py
 */

export interface CourseCreate {
  name: string
  description?: string | null
}

export interface CourseCounts {
  sources: number
  chunks: number
  embedded_chunks: number
  topics: number
  concepts: number
}

export type CourseKbStatus = 'empty' | 'building' | 'ready' | 'failed'

export interface CourseRead {
  id: number
  name: string
  description?: string | null
  kb_status: CourseKbStatus | string
  kb_error?: string | null
  kb_built_at?: string | null
  created_at: string
}

export interface CourseDetailRead extends CourseRead {
  counts: CourseCounts
}

export interface CourseDeleteResponse {
  deleted: boolean
}
