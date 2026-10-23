import { apiClient } from './client'
import type { components } from '../types/openapi'

export type AIContextScope = 'scan' | 'host' | 'finding'
export type AILanguage = 'en' | 'pt-BR' | 'ru'
export type AIChatHistoryResponse =
  components['schemas']['AIChatHistoryResponse']
export type AIChatHistoryEntry = components['schemas']['AIChatHistoryEntry']
export type AIConversationsResponse =
  components['schemas']['AIConversationsResponse']
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
  signal?: AbortSignal,
  conversationId?: string,
): Promise<AIChatHistoryEntry> {
  const response = await apiClient.post<AIChatHistoryEntry>(
    '/ai/chat',
    {
      scope,
      context_id: contextId,
      question,
      language,
      conversation_id: conversationId,
    },
    { signal },
  )
  return response.data
}

export async function getContextAIHistory(
  scope: AIContextScope,
  contextId: string,
  conversationId?: string,
  page = 1,
): Promise<AIChatHistoryResponse> {
  const response = await apiClient.get<AIChatHistoryResponse>(
    '/ai/chat/history',
    {
      params: {
        scope,
        context_id: contextId,
        conversation_id: conversationId,
        page,
      },
    },
  )
  return response.data
}

export async function getAIConversations(
  scope: AIContextScope,
  contextId: string,
  page = 1,
): Promise<AIConversationsResponse> {
  const response = await apiClient.get<AIConversationsResponse>(
    '/ai/chat/conversations',
    {
      params: { scope, context_id: contextId, page },
    },
  )
  return response.data
}

export type AIExplanationResponse =
  | components['schemas']['ScanExplanationResponse']
  | components['schemas']['MachineExplanationResponse']
export type AIExplainRequest = components['schemas']['AIExplainRequest']

export async function explainAIContext(
  payload: AIExplainRequest,
  signal?: AbortSignal,
): Promise<AIExplanationResponse> {
  const response = await apiClient.post<AIExplanationResponse>(
    '/ai/explain',
    payload,
    { signal },
  )
  return response.data
}
