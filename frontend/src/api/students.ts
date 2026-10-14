import { apiRequest } from './client'
import type {
  StudentCreate,
  StudentDeleteResponse,
  StudentRead,
} from '../types/student'

export async function listStudents(signal?: AbortSignal): Promise<StudentRead[]> {
  return apiRequest<StudentRead[]>('/students', {
    method: 'GET',
    signal,
  })
}

export async function createStudent(
  payload: StudentCreate,
  signal?: AbortSignal
): Promise<StudentRead> {
  return apiRequest<StudentRead>('/students', {
    method: 'POST',
    body: payload,
    signal,
  })
}

export async function getStudent(
  id: number,
  signal?: AbortSignal
): Promise<StudentRead> {
  return apiRequest<StudentRead>(`/students/${id}`, {
    method: 'GET',
    signal,
  })
}

export async function deleteStudent(
  id: number,
  signal?: AbortSignal
): Promise<StudentDeleteResponse> {
  return apiRequest<StudentDeleteResponse>(`/students/${id}`, {
    method: 'DELETE',
    signal,
  })
}
