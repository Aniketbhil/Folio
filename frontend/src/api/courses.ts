import { apiRequest } from './client'
import type {
  CourseCreate,
  CourseDeleteResponse,
  CourseDetailRead,
  CourseRead,
} from '../types/course'

export async function listCourses(signal?: AbortSignal): Promise<CourseRead[]> {
  return apiRequest<CourseRead[]>('/courses', {
    method: 'GET',
    signal,
  })
}

export async function createCourse(
  payload: CourseCreate,
  signal?: AbortSignal
): Promise<CourseRead> {
  return apiRequest<CourseRead>('/courses', {
    method: 'POST',
    body: payload,
    signal,
  })
}

export async function getCourseDetail(
  id: number,
  signal?: AbortSignal
): Promise<CourseDetailRead> {
  return apiRequest<CourseDetailRead>(`/courses/${id}`, {
    method: 'GET',
    signal,
  })
}

export async function deleteCourse(
  id: number,
  signal?: AbortSignal
): Promise<CourseDeleteResponse> {
  return apiRequest<CourseDeleteResponse>(`/courses/${id}`, {
    method: 'DELETE',
    signal,
  })
}
