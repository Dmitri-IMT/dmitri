import { apiClient } from './client'
import type { components } from '../types/openapi'

export type AIContextScope = 'scan' | 'host' | 'finding'
export type AILanguage = 'en' | 'pt-BR' | 'ru'
export type AIChatResponse = components['schemas']['AIChatResponse']
export type AIChatHistoryResponse =
  components['schemas']['AIChatHistoryResponse']
export type AIUsageResponse = components['schemas']['AIUsageResponse']

export async function getAIUsage(limit = 50): Promise<AIUsageResponse> {
  const response = await apiClient.get<AIUsageResponse>('/ai/usage', {
    params: { limit },
  })
  return response.data
}

/** Shared entry point for the contextual assistant used by future global UI. */
export async function askContextAI(
  scope: AIContextScope,
  contextId: string,
  question: string,
  language: AILanguage = 'en',
): Promise<AIChatResponse> {
  const response = await apiClient.post<AIChatResponse>('/ai/chat', {
    scope,
    context_id: contextId,
    question,
    language,
  })
  return response.data
}

export async function getContextAIHistory(
  scope: AIContextScope,
  contextId: string,
): Promise<AIChatHistoryResponse> {
  const response = await apiClient.get<AIChatHistoryResponse>(
    '/ai/chat/history',
    {
      params: { scope, context_id: contextId },
    },
  )
  return response.data
}
