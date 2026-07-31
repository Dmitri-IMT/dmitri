import { apiClient } from './client'
import type { components } from '../types/openapi'

type Severity = components['schemas']['Severity']
type FindingListResponse = components['schemas']['FindingListResponse']

// Order is load-bearing: the home deck shows critical findings before high ones.
export const HOME_SEVERITIES = [
  'critical',
  'high',
] as const satisfies readonly Severity[]

export const HOME_FINDINGS_PER_PAGE = 100

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
