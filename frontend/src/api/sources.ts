import { API_BASE_URL, apiRequest } from './client'
import type {
  ChunkRead,
  KBRebuildResponse,
  KBStatusResponse,
  SourceDeleteResponse,
  SourceRead,
  SourceUploadPayload,
} from '../types/source'

export async function listCourseSources(
  courseId: number,
  signal?: AbortSignal
): Promise<SourceRead[]> {
  return apiRequest<SourceRead[]>(`/courses/${courseId}/sources`, {
    method: 'GET',
    signal,
  })
}

export async function uploadCourseSource(
  courseId: number,
  payload: SourceUploadPayload,
  signal?: AbortSignal
): Promise<SourceRead> {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.title && payload.title.trim()) {
    formData.append('title', payload.title.trim())
  }
  if (payload.media_url && payload.media_url.trim()) {
    formData.append('media_url', payload.media_url.trim())
  }

  return apiRequest<SourceRead>(`/courses/${courseId}/sources`, {
    method: 'POST',
    body: formData,
    signal,
  })
}

export async function getSource(
  sourceId: number,
  signal?: AbortSignal
): Promise<SourceRead> {
  return apiRequest<SourceRead>(`/sources/${sourceId}`, {
    method: 'GET',
    signal,
  })
}

export async function deleteSource(
  sourceId: number,
  signal?: AbortSignal
): Promise<SourceDeleteResponse> {
  return apiRequest<SourceDeleteResponse>(`/sources/${sourceId}`, {
    method: 'DELETE',
    signal,
  })
}

export async function retrySource(
  sourceId: number,
  signal?: AbortSignal
): Promise<SourceRead> {
  return apiRequest<SourceRead>(`/sources/${sourceId}/retry`, {
    method: 'POST',
    signal,
  })
}

export function getSourceFileUrl(sourceId: number): string {
  return `${API_BASE_URL}/sources/${sourceId}/file`
}

export async function listSourceChunks(
  sourceId: number,
  limit = 50,
  offset = 0,
  signal?: AbortSignal
): Promise<ChunkRead[]> {
  return apiRequest<ChunkRead[]>(`/sources/${sourceId}/chunks`, {
    method: 'GET',
    params: { limit, offset },
    signal,
  })
}

export async function getCourseKbStatus(
  courseId: number,
  signal?: AbortSignal
): Promise<KBStatusResponse> {
  return apiRequest<KBStatusResponse>(`/courses/${courseId}/kb/status`, {
    method: 'GET',
    signal,
  })
}

export async function rebuildCourseKb(
  courseId: number,
  signal?: AbortSignal
): Promise<KBRebuildResponse> {
  return apiRequest<KBRebuildResponse>(`/courses/${courseId}/kb/rebuild`, {
    method: 'POST',
    signal,
  })
}
