/**
 * Base API response and error structures matching FastAPI backend contract.
 */

export interface BackendErrorPayload {
  error: {
    code: string
    message: string
  }
}

export interface ApiSuccessResponse<T> {
  data: T
  status: number
}

export interface HealthResponse {
  status: string
  db: string
  vector_store: string
  llm_mode: string
  version: string
  uptime_sec: number
  counts: {
    students: number
    courses: number
    sources: number
    chunks: number
  }
  kb_building_courses: number
  ingestion_active: number
}
