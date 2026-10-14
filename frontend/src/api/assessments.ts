import { apiRequest } from './client'
import type {
  AssessmentCreate,
  AssessmentListItem,
  AssessmentOut,
  AssessmentReportResponse,
  AnswerSubmitRequest,
  AnswerSubmitResponse,
} from '../types/assessment'

/**
 * List assessments for a course, optionally filtered by student_id
 */
export async function listCourseAssessments(
  courseId: number,
  studentId?: number,
  signal?: AbortSignal
): Promise<AssessmentListItem[]> {
  return apiRequest<AssessmentListItem[]>(`/courses/${courseId}/assessments`, {
    method: 'GET',
    params: studentId !== undefined ? { student_id: studentId } : undefined,
    signal,
  })
}

/**
 * Create a new assessment (quiz, mock exam, or diagnostic)
 */
export async function createAssessment(
  courseId: number,
  payload: AssessmentCreate,
  signal?: AbortSignal
): Promise<AssessmentOut> {
  return apiRequest<AssessmentOut>(`/courses/${courseId}/assessments`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

/**
 * Create or resume an in-progress diagnostic assessment for a student
 */
export async function createOrResumeDiagnostic(
  courseId: number,
  studentId: number,
  signal?: AbortSignal
): Promise<AssessmentOut> {
  return apiRequest<AssessmentOut>(`/courses/${courseId}/diagnostic`, {
    method: 'POST',
    params: { student_id: studentId },
    signal,
  })
}

/**
 * Get assessment details including question prompts and choices
 */
export async function getAssessment(
  assessmentId: number,
  signal?: AbortSignal
): Promise<AssessmentOut> {
  return apiRequest<AssessmentOut>(`/assessments/${assessmentId}`, {
    method: 'GET',
    signal,
  })
}

/**
 * Submit an answer to a single question with immediate grading and mastery updates
 */
export async function submitQuestionAnswer(
  assessmentId: number,
  questionId: number,
  payload: AnswerSubmitRequest,
  signal?: AbortSignal
): Promise<AnswerSubmitResponse> {
  return apiRequest<AnswerSubmitResponse>(
    `/assessments/${assessmentId}/questions/${questionId}/answer`,
    {
      method: 'POST',
      body: payload,
      signal,
    }
  )
}

/**
 * Finalize/submit the full assessment and obtain the final report
 */
export async function submitAssessment(
  assessmentId: number,
  signal?: AbortSignal
): Promise<AssessmentReportResponse> {
  return apiRequest<AssessmentReportResponse>(`/assessments/${assessmentId}/submit`, {
    method: 'POST',
    signal,
  })
}

/**
 * Retrieve the comprehensive assessment report
 */
export async function getAssessmentReport(
  assessmentId: number,
  signal?: AbortSignal
): Promise<AssessmentReportResponse> {
  return apiRequest<AssessmentReportResponse>(`/assessments/${assessmentId}/report`, {
    method: 'GET',
    signal,
  })
}

/**
 * Delete an assessment
 */
export async function deleteAssessment(
  assessmentId: number,
  signal?: AbortSignal
): Promise<{ deleted: boolean; assessment_id: number }> {
  return apiRequest<{ deleted: boolean; assessment_id: number }>(
    `/assessments/${assessmentId}`,
    {
      method: 'DELETE',
      signal,
    }
  )
}
