import { ApiClientError } from './errors'
import type { BackendErrorPayload } from '../types/api'

/**
 * Resolve the API base URL.
 * Guarantees /api/v1 is appended centrally exactly once.
 */
function resolveApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const trimmed = raw.trim().replace(/\/+$/, '')

  if (!trimmed) {
    throw new Error(
      'VITE_API_BASE_URL is not configured. Please set it in your environment or .env file.'
    )
  }

  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`
}

export const API_BASE_URL = resolveApiBaseUrl()

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  params?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
}

/**
 * Universal fetch wrapper for Folio API.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, body, headers = {}, signal, ...rest } = options

  // Normalize path
  const cleanPath = path.startsWith('/') ? path : `/${path}`

  // Build query string
  let url = `${API_BASE_URL}${cleanPath}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val))
      }
    }
    const query = searchParams.toString()
    if (query) {
      url += (url.includes('?') ? '&' : '?') + query
    }
  }

  // Configure headers and body
  const requestHeaders = new Headers(headers)
  let requestBody: BodyInit | undefined = undefined

  if (body !== undefined && body !== null) {
    if (body instanceof FormData) {
      // Browser must set boundary automatically for FormData
      requestBody = body
    } else if (typeof body === 'string') {
      requestBody = body
      if (!requestHeaders.has('Content-Type')) {
        requestHeaders.set('Content-Type', 'text/plain;charset=UTF-8')
      }
    } else {
      requestBody = JSON.stringify(body)
      if (!requestHeaders.has('Content-Type')) {
        requestHeaders.set('Content-Type', 'application/json')
      }
    }
  }

  let response: Response
  try {
    response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
      body: requestBody,
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err
    }
    throw new ApiClientError(
      0,
      'network_error',
      'Network request failed or server is unreachable',
      url
    )
  }

  // Handle errors
  if (!response.ok) {
    let errorCode = 'http_error'
    let errorMessage = `HTTP error ${response.status}: ${response.statusText}`

    try {
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const errorData = (await response.json()) as BackendErrorPayload
        if (errorData?.error) {
          errorCode = errorData.error.code || errorCode
          errorMessage = errorData.error.message || errorMessage
        }
      } else {
        const text = await response.text()
        if (text) {
          errorMessage = text
        }
      }
    } catch {
      // Fallback to HTTP status text if parsing fails
    }

    throw new ApiClientError(response.status, errorCode, errorMessage, url)
  }

  // Handle 204 No Content or empty responses
  if (response.status === 204) {
    return {} as T
  }

  const contentLength = response.headers.get('content-length')
  if (contentLength === '0') {
    return {} as T
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }

  return (await response.text()) as unknown as T
}
