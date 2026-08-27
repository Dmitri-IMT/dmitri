import { apiClient } from './client'
import type { components, operations } from '../types/openapi'

type Severity = components['schemas']['Severity']
type FindingListResponse = components['schemas']['FindingListResponse']
type ListFindingsQuery = NonNullable<
  operations['listFindings']['parameters']['query']
>

export type FindingListParams =
  | { [Key in 'scan_id' | 'severity']: ListFindingsQuery[Key] }
  | Required<Pick<ListFindingsQuery, 'host_id' | 'per_page'>>

// Order is load-bearing: the home deck shows critical findings before high ones.
export const HOME_SEVERITIES = [
  'critical',
  'high',
] as const satisfies readonly Severity[]

export const HOME_FINDINGS_PER_PAGE = 100
export const HOST_FINDINGS_PER_PAGE = 100

export async function listFindings({
  scan_id,
  severity,
}: {
  scan_id: string
  severity: Severity
}): Promise<FindingListResponse> {
  const response = await apiClient.get<FindingListResponse>('/findings', {
    params: { scan_id, severity, per_page: HOME_FINDINGS_PER_PAGE },
  })
  return response.data
}

export async function listFindingsForHost(
  hostId: string,
): Promise<FindingListResponse> {
  const response = await apiClient.get<FindingListResponse>('/findings', {
    params: { host_id: hostId, per_page: HOST_FINDINGS_PER_PAGE },
  })
  return response.data
}
