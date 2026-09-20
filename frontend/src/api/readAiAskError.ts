import type { AxiosError } from 'axios'

type ApiErrorBody = {
  error?: { code?: string; message?: string }
}

function readApiError(error: unknown): ApiErrorBody['error'] | undefined {
  const response = (error as AxiosError<ApiErrorBody>).response
  return response?.data?.error
}

/** Map contextual AI ask failures to a user-visible message. */
export function readAiAskError(error: unknown, fallback: string): string {
  const apiError = readApiError(error)
  if (
    apiError?.message &&
    ['ai_rate_limited', 'ai_context_too_large'].includes(apiError.code ?? '')
  ) {
    return apiError.message
  }
  return fallback
}
