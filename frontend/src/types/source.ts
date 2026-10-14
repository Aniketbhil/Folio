/**
 * Source and Knowledge Base types matching backend schemas:
 * backend/app/schemas/source.py and backend/app/schemas/kb.py
 */

export type SourceType = 'pdf' | 'pptx' | 'video' | 'video_transcript'
export type SourceStatus = 'queued' | 'processing' | 'ready' | 'failed'

export interface SourceRead {
  id: number
  course_id: number
  title: string
  source_type: SourceType | string
  original_filename: string
  file_path: string
  status: SourceStatus | string
  stage?: string | null
  progress: number
  error?: string | null
  num_units: number
  meta?: Record<string, unknown>
  media_url?: string | null
  created_at: string
  chunk_count: number
}

export interface ChunkRead {
  id: number
  chunk_index: number
  source_type: string
  page_number?: number | null
  slide_number?: number | null
  start_sec?: number | null
  end_sec?: number | null
  section_title?: string | null
  token_count: number
  text: string
}

export interface SourceDeleteResponse {
  deleted: boolean
}

export interface KBStatusCounts {
  topics: number
  leaf_topics: number
  concepts: number
  total_chunks: number
  tagged_chunks: number
  untagged_chunks: number
  prerequisites: number
}

export interface KBStatusResponse {
  kb_status: 'empty' | 'building' | 'ready' | 'failed' | string
  kb_error?: string | null
  kb_built_at?: string | null
  stage: string
  progress: number
  counts: KBStatusCounts
}

export interface KBRebuildResponse {
  kb_status: string
}

export interface SourceUploadPayload {
  file: File
  title?: string
  media_url?: string
}
