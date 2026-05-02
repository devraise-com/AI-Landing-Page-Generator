interface ApiErrorBody {
  error?: string
  code?: string
  request_id?: string
}

export class ApiError extends Error {
  status: number
  code: string | undefined
  requestId: string | undefined

  constructor(status: number, body: ApiErrorBody) {
    super(body.error ?? `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.requestId = body.request_id
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}
