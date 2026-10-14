import { apiRequest } from './client'
import type {
  ConceptItem,
  CourseMasteryResponse,
  GraphResponse,
  TopicDetailResponse,
} from '../types/mastery'

/**
 * Get the knowledge graph with topics (nodes) and prerequisite edges
 */
export async function getCourseKnowledgeGraph(
  courseId: number,
  signal?: AbortSignal
): Promise<GraphResponse> {
  return apiRequest<GraphResponse>(`/courses/${courseId}/graph`, {
    method: 'GET',
    signal,
  })
}

/**
 * Get learner mastery states for all leaf topics in a course
 */
export async function getStudentCourseMastery(
  studentId: number,
  courseId: number,
  tzOffsetMin = 0,
  signal?: AbortSignal
): Promise<CourseMasteryResponse> {
  return apiRequest<CourseMasteryResponse>(
    `/students/${studentId}/courses/${courseId}/mastery`,
    {
      method: 'GET',
      params: { tz_offset_min: tzOffsetMin },
      signal,
    }
  )
}

/**
 * Get detailed topic information including parent, children, concepts, prerequisites, and source citations
 */
export async function getTopicDetail(
  topicId: number,
  signal?: AbortSignal
): Promise<TopicDetailResponse> {
  return apiRequest<TopicDetailResponse>(`/topics/${topicId}`, {
    method: 'GET',
    signal,
  })
}

/**
 * Get course concepts, optionally filtered by topic
 */
export async function getCourseConcepts(
  courseId: number,
  topicId?: number,
  signal?: AbortSignal
): Promise<ConceptItem[]> {
  return apiRequest<ConceptItem[]>(`/courses/${courseId}/concepts`, {
    method: 'GET',
    params: topicId !== undefined ? { topic_id: topicId } : undefined,
    signal,
  })
}
