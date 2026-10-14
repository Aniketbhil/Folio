import { apiRequest } from './client'
import type {
  ConversationCreate,
  ConversationDeleteResponse,
  ConversationListItem,
  ConversationRead,
  MessageCreate,
  MessageRead,
  TutorResponse,
} from '../types/tutor'

/**
 * Create a new conversation session for a course and student.
 */
export async function createConversation(
  courseId: number,
  payload: ConversationCreate,
  signal?: AbortSignal
): Promise<ConversationRead> {
  return apiRequest<ConversationRead>(`/courses/${courseId}/conversations`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

/**
 * List conversations for a course and student, newest first.
 */
export async function listCourseConversations(
  courseId: number,
  studentId: number,
  limit = 50,
  offset = 0,
  signal?: AbortSignal
): Promise<ConversationListItem[]> {
  return apiRequest<ConversationListItem[]>(`/courses/${courseId}/conversations`, {
    method: 'GET',
    params: {
      student_id: studentId,
      limit,
      offset,
    },
    signal,
  })
}

/**
 * Retrieve conversation details and message count.
 */
export async function getConversation(
  conversationId: number,
  signal?: AbortSignal
): Promise<ConversationRead> {
  return apiRequest<ConversationRead>(`/conversations/${conversationId}`, {
    method: 'GET',
    signal,
  })
}

/**
 * Retrieve message history for a conversation, ordered oldest first.
 */
export async function getConversationMessages(
  conversationId: number,
  limit = 100,
  offset = 0,
  signal?: AbortSignal
): Promise<MessageRead[]> {
  return apiRequest<MessageRead[]>(`/conversations/${conversationId}/messages`, {
    method: 'GET',
    params: {
      limit,
      offset,
    },
    signal,
  })
}

/**
 * Send a student question to the AI tutor and receive a source-grounded response.
 */
export async function sendConversationMessage(
  conversationId: number,
  payload: MessageCreate,
  signal?: AbortSignal
): Promise<TutorResponse> {
  return apiRequest<TutorResponse>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: payload,
    signal,
  })
}

/**
 * Delete a conversation and all its messages.
 */
export async function deleteConversation(
  conversationId: number,
  signal?: AbortSignal
): Promise<ConversationDeleteResponse> {
  return apiRequest<ConversationDeleteResponse>(`/conversations/${conversationId}`, {
    method: 'DELETE',
    signal,
  })
}
