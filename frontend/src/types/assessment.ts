import type { TutorCitation } from './tutor'

export type QuestionType = 'mcq' | 'short_answer' | 'numerical'
export type AssessmentKind = 'quiz' | 'mock_exam' | 'diagnostic'
export type AssessmentStatus = 'in_progress' | 'submitted' | 'completed'

export interface QuestionOption {
  key: string
  text: string
}

export interface AttemptOut {
  id: number
  answer: string
  is_correct: boolean
  score: number
  feedback?: string | null
  time_taken_sec?: number | null
  created_at: string
}

export interface QuestionOut {
  id: number
  assessment_id: number
  topic_id: number
  topic: string
  concept_id?: number | null
  concept?: string | null
  question_type: QuestionType
  prompt: string
  options?: QuestionOption[] | null
  difficulty: number
  unit?: string | null
  sources: TutorCitation[]
  answered: boolean
  attempt?: AttemptOut | null
}

export interface AssessmentListItem {
  id: number
  kind: AssessmentKind
  title?: string | null
  status: AssessmentStatus
  difficulty: number
  score?: number | null
  question_count: number
  answered_count: number
  created_at: string
  submitted_at?: string | null
}

export interface AssessmentOut {
  id: number
  course_id: number
  student_id: number
  kind: AssessmentKind
  status: AssessmentStatus
  difficulty: number
  score?: number | null
  title?: string | null
  created_at: string
  submitted_at?: string | null
  questions: QuestionOut[]
}

export interface AssessmentCreate {
  student_id: number
  kind?: AssessmentKind
  topic_ids?: number[] | null
  num_questions?: number
  difficulty?: number
  question_types?: QuestionType[] | null
  title?: string | null
}

export interface AnswerSubmitRequest {
  answer: string
  time_taken_sec?: number | null
  student_id?: number | null
}

export interface MasteryUpdate {
  topic_id: number
  p_mastery_before: number
  p_mastery_after: number
}

export interface AnswerSubmitResponse {
  attempt_id: number
  is_correct: boolean
  score: number
  correct_answer: string
  explanation: string
  feedback: string
  citations: TutorCitation[]
  mastery_update?: MasteryUpdate | null
  progress: {
    answered: number
    total: number
  }
}

export interface TopicScoreSummary {
  topic_id: number
  topic_name: string
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
  avg_time_sec?: number | null
}

export interface AssessmentQuestionReview {
  question_id: number
  prompt: string
  question_type: string
  topic: string
  concept?: string | null
  options?: QuestionOption[] | null
  correct_answer: string
  explanation: string
  student_answer?: string | null
  is_correct: boolean
  feedback?: string | null
  citations: TutorCitation[]
}

export interface AssessmentReportResponse {
  assessment_id: number
  title?: string | null
  kind: string
  status: string
  submitted_at: string
  summary: AssessmentSummary
  by_topic: TopicScoreSummary[]
  weak_topics: string[]
  strong_topics: string[]
  misconceptions: string[]
  review: AssessmentQuestionReview[]
  recommended_next_steps: string[]
}
