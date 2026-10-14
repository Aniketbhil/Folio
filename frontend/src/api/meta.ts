import { apiRequest } from './client'
import type { MetaResponse } from '../types/meta'
import type { HealthResponse } from '../types/api'

export async function getMeta(signal?: AbortSignal): Promise<MetaResponse> {
  return apiRequest<MetaResponse>('/meta', {
    method: 'GET',
    signal,
  })
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', {
    method: 'GET',
    signal,
  })
}
