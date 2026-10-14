/**
 * Metadata schemas matching GET /api/v1/meta
 */

export interface MetaEnums {
  source_types: string[]
  source_statuses: string[]
  kb_statuses: string[]
  grounding: string[]
  assessment_kinds: string[]
  qtypes: string[]
  difficulties: string[]
  mastery_statuses: string[]
  recommendation_types: string[]
  cta_kinds: string[]
  activity_kinds: string[]
}

export interface MetaThresholds {
  mastery_weak_below: number
  mastery_strong_above: number
  review_due_below: number
  grade_correct_threshold: number
  tutor_min_score: number
}

export interface MetaLimits {
  max_upload_mb: number
  quiz_max_questions: number
  exam_max_questions: number
  diagnostic_questions: number
  message_max_chars: number
  answer_max_chars: number
}

export interface MetaFeatures {
  image_captioning: boolean
  chat_nudges: boolean
  tutor_personalization: boolean
  llm_mode: string
}

export interface MetaResponse {
  version: string
  enums: MetaEnums
  thresholds: MetaThresholds
  limits: MetaLimits
  features: MetaFeatures
}
