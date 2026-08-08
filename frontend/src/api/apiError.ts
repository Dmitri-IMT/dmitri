import { isAxiosError } from 'axios'
import type { components } from '../types/openapi'

type ErrorResponse = components['schemas']['ErrorResponse']

interface ApiError {
  status: number | undefined
  code: string | undefined
}

// Every field is optional: a thrown value may not be an axios error at all, and an
// axios error without a response (network failure, CORS) carries neither status nor
// code. Callers branch on both, so a non-API failure falls through to their generic
// service-error message.
export function readApiError(error: unknown): ApiError {
  if (!isAxiosError<ErrorResponse>(error)) {
    return { status: undefined, code: undefined }
  }
  return {
    status: error.response?.status,
    code: error.response?.data?.error?.code,
  }
}
