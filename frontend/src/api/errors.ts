/**
 * Typed client error handling matching FastAPI error responses:
 * { "error": { "code": "...", "message": "..." } }
 */

export class ApiClientError extends Error {
  public readonly status: number
  public readonly code: string
  public readonly url?: string

  constructor(status: number, code: string, message: string, url?: string) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.url = url
  }

  get isNetworkError(): boolean {
    return this.status === 0 || this.code === 'network_error'
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isValidationError(): boolean {
    return this.status === 422 || this.code === 'validation_error'
  }

  get isServerError(): boolean {
    return this.status >= 500
  }
}

/**
 * Format an unknown error into a clean user-facing error message.
 */
export function formatApiError(err: unknown, defaultMessage = 'An unexpected error occurred'): string {
  if (err instanceof ApiClientError) {
    if (err.isNetworkError) {
      return 'Unable to reach the Folio backend server. Please verify the backend is running.'
    }
    return err.message || defaultMessage
  }

  if (err instanceof Error) {
    if (err.name === 'AbortError') {
      return 'Request was cancelled.'
    }
    return err.message || defaultMessage
  }

  return defaultMessage
}
