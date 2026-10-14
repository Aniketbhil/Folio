import type { TutorCitation } from './tutor'

export type QuestionType = 'mcq' | 'short_answer' | 'numerical'
export type AssessmentKind = 'quiz' | 'mock_exam' | 'diagnostic'
export type AssessmentStatus = 'in_progress' | 'submitted' | 'completed'
export type AssessmentDifficulty = 'auto' | 'easy' | 'medium' | 'hard'

export interface QuestionOption {
  key: string
  text: string
}

export interface AttemptOut {
  id?: number
  answer: string
  is_correct: boolean
  score: number
  feedback?: string | null
  time_taken_sec?: number | null
  created_at?: string
}

export interface QuestionTopicOut {
  id: number
  name: string
  parent_id?: number | null
  parent_name?: string | null
}

export interface QuestionConceptOut {
  id: number
  name: string
}

export interface QuestionSourceOut {
  chunk_id: number
  source_id: number
  source_title: string
  source_type: string
  location: Record<string, unknown>
}

export interface QuestionAttemptOut {
  id?: number
  answer: string
  is_correct: boolean
  score: number
  feedback?: string
}

export interface QuestionOut {
  id: number
  position?: number
  assessment_id?: number
  topic_id?: number
  topic: QuestionTopicOut | string
  concept_id?: number | null
  concept?: QuestionConceptOut | string | null
  qtype: QuestionType | string
  question_type?: QuestionType | string
  prompt: string
  options?: QuestionOption[] | null
  difficulty: string
  unit?: string | null
  sources: (TutorCitation | QuestionSourceOut)[]
  answered: boolean
  attempt?: AttemptOut | QuestionAttemptOut | null
  correct_answer?: string | null
  explanation?: string | null
}

export interface AssessmentListItem {
  id: number
  kind: AssessmentKind | string
  title?: string | null
  status: AssessmentStatus | string
  difficulty?: string | number
  score?: number | null
  num_questions: number
  question_count?: number
  answered_count: number
  created_at: string
  submitted_at?: string | null
}

export interface AssessmentOut {
  id: number
  course_id: number
  student_id: number
  kind: AssessmentKind | string
  status: AssessmentStatus | string
  difficulty?: string | number
  score?: number | null
  title?: string | null
  created_at: string
  submitted_at?: string | null
  num_questions: number
  answered_count?: number
  config?: Record<string, unknown>
  warnings?: string[]
  generation_report?: Record<string, unknown>
  questions: QuestionOut[]
}

export interface AssessmentCreate {
  student_id?: number
  kind?: AssessmentKind
  topic_ids?: number[] | null
  num_questions?: number
  difficulty?: AssessmentDifficulty | string
  question_types?: QuestionType[] | null
  title?: string | null
}

export interface AnswerSubmitRequest {
  answer: string
  time_taken_sec?: number | null
  student_id?: number | null
}

export interface MasteryUpdate {
  topic_id?: number
  topic?: Record<string, unknown>
  p_mastery_before?: number
  p_mastery_after?: number
  before?: number
  after?: number
  status_before?: string
  status_after?: string
}

export interface AnswerSubmitResponse {
  attempt_id: number
  question_id?: number
  is_correct: boolean
  score: number
  correct_answer: unknown
  explanation: string
  feedback: string
  citations: (TutorCitation | QuestionSourceOut)[]
  mastery_update?: MasteryUpdate | null
  misconception?: string | null
  key_points_hit?: string[] | null
  key_points_missing?: string[] | null
  progress: {
    answered: number
    total: number
  }
}

export interface TopicScoreSummary {
  topic_id?: number
  topic_name?: string
  topic?: { id: number; name: string }
  total: number
  correct: number
  accuracy: number
}

export interface AssessmentSummary {
  score: number
  score_pct: number
  total_questions: number
  answered: number
  correct: number
  skipped?: number
  avg_time_sec?: number | null
  total_time_sec?: number | null
}

export interface AssessmentQuestionReview {
  question_id: number
  position?: number
  prompt: string
  qtype?: string
  question_type?: string
  topic: QuestionTopicOut | string
  concept?: QuestionConceptOut | string | null
  options?: QuestionOption[] | null
  correct_answer: unknown
  explanation: string
  your_answer?: string | null
  student_answer?: string | null
  is_correct?: boolean | null
  score?: number | null
  feedback?: string | null
  misconception?: string | null
  citations?: TutorCitation[]
}

export interface AssessmentReportResponse {
  assessment?: {
    id: number
    kind: string
    title?: string | null
    status: string
    submitted_at?: string | null
  }
  assessment_id?: number
  title?: string | null
  kind?: string
  status?: string
  submitted_at?: string
  summary: AssessmentSummary
  by_topic: TopicScoreSummary[]
  weak_topics: unknown[]
  strong_topics: unknown[]
  by_difficulty?: unknown[]
  by_type?: unknown[]
  misconceptions: unknown[]
  review: AssessmentQuestionReview[]
  recommended_next_steps: unknown[]
  diagnostic_note?: string | null
}

