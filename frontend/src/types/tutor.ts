/**
 * Tutor and Conversation schemas matching backend/app/schemas/tutor.py
 * and backend/app/schemas/citation.py
 */

export interface TutorCitationLocation {
  page_number?: number | null
  slide_number?: number | null
  start_sec?: number | null
  end_sec?: number | null
  [key: string]: unknown
}

export interface TutorCitation {
  chunk_id: number
  source_id: number
  source_title: string
  source_type: string
  location: TutorCitationLocation
  section_title?: string | null
  snippet: string
  score?: number | null
  open_url: string
  ref: number
}

export interface RelatedTopicItem {
  id: number
  name: string
}

export interface ConversationCreate {
  student_id: number
  title?: string
}

export interface ConversationRead {
  id: number
  course_id: number
  student_id: number
  title: string
  created_at: string
  updated_at?: string | null
  message_count: number
}

export interface ConversationListItem {
  id: number
  course_id: number
  student_id: number
  title: string
  created_at: string
  updated_at?: string | null
  message_count: number
  last_message_preview?: string | null
}

export interface MessageCreate {
  content: string
  student_id: number
  topic_ids?: number[]
}

export type GroundingStatus = 'grounded' | 'partial' | 'unsupported' | null

export interface MessageRead {
  id: number
  role: 'user' | 'assistant' | string
  content: string
  grounding?: GroundingStatus
  citations: TutorCitation[]
  outside_knowledge_note?: string | null
  followups: string[]
  related_topics: RelatedTopicItem[]
  mastery_nudge?: Record<string, unknown> | null
  created_at: string
}

export interface TutorResponse {
  conversation_id: number
  user_message_id: number
  message_id: number
  assistant_message_id?: number | null
  answer: string
  grounding?: GroundingStatus
  citations: TutorCitation[]
  outside_knowledge_note?: string | null
  followups: string[]
  related_topics: RelatedTopicItem[]
  mastery_nudge?: Record<string, unknown> | null
}

export interface ConversationDeleteResponse {
  deleted: boolean
}
