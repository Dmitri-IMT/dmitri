import { apiClient } from './client'
import type { components, operations } from '../types/openapi'

type Severity = components['schemas']['Severity']
type FindingListResponse = components['schemas']['FindingListResponse']
export type AIChatResponse = components['schemas']['AIChatResponse']
export type AIChatHistoryResponse =
  components['schemas']['AIChatHistoryResponse']
type ListFindingsQuery = NonNullable<
  operations['listFindings']['parameters']['query']
>

// One filter shape per caller: the home deck reads a scan at one severity, host
// detail reads a host. `scan_id` stays optional because the home key is built
// before the scan id lands; `skipToken` there keeps the unfiltered read unsent.
export type FindingListParams =
  | { [Key in 'scan_id' | 'severity' | 'per_page']: ListFindingsQuery[Key] }
  | Required<Pick<ListFindingsQuery, 'host_id' | 'per_page'>>

// Order is load-bearing: the home deck shows critical findings before high ones.
export const HOME_SEVERITIES = [
  'critical',
  'high',
] as const satisfies readonly Severity[]

export const HOME_FINDINGS_PER_PAGE = 100
export const HOST_FINDINGS_PER_PAGE = 100

export async function listFindings(
  params: FindingListParams,
): Promise<FindingListResponse> {
  const response = await apiClient.get<FindingListResponse>('/findings', {
    params,
  })
  return response.data
}

export async function explainFinding(
  findingId: string,
  question = 'Explique esta vulnerabilidade em linguagem simples e diga o que devo fazer.',
): Promise<AIChatResponse> {
  const response = await apiClient.post<AIChatResponse>(
    `/findings/${findingId}/explain`,
    { question },
  )
  return response.data
}

export async function getFindingAIHistory(
  findingId: string,
): Promise<AIChatHistoryResponse> {
  const response = await apiClient.get<AIChatHistoryResponse>(
    `/findings/${findingId}/explain`,
  )
  return response.data
}
