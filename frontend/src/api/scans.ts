import { apiClient } from './client'
import type { components, operations } from '../types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']
type ScanDetailResponse = components['schemas']['ScanDetailResponse']
export type ScanAIAnalysisResponse =
  components['schemas']['ScanAIAnalysisResponse']
type ListScansQuery = NonNullable<
  operations['listScans']['parameters']['query']
>

export type ScanListParams = Required<
  Pick<ListScansQuery, 'page' | 'per_page' | 'sort_by' | 'sort_order'>
> &
  Pick<ListScansQuery, 'agent_id'>

export const SCANS_PER_PAGE = 20

export const SCAN_LIST_SORT = {
  sort_by: 'timestamp',
  sort_order: 'desc',
} as const

export const LATEST_SCAN_QUERY = {
  per_page: 1,
  sort_by: 'timestamp',
  sort_order: 'desc',
} as const

export const LATEST_SUCCESSFUL_SCAN_QUERY = {
  ...LATEST_SCAN_QUERY,
  status: 'completed',
} as const

async function getLatestScanByQuery(
  params: Partial<ListScansQuery>,
): Promise<ScanSummary | null> {
  const response = await apiClient.get<ScanListResponse>('/scans', { params })
  return response.data.data[0] ?? null
}

export function getLatestScan(): Promise<ScanSummary | null> {
  return getLatestScanByQuery(LATEST_SCAN_QUERY)
}

export function getLatestSuccessfulScan(): Promise<ScanSummary | null> {
  return getLatestScanByQuery(LATEST_SUCCESSFUL_SCAN_QUERY)
}

export async function listScans(
  params: ScanListParams,
): Promise<ScanListResponse> {
  const response = await apiClient.get<ScanListResponse>('/scans', { params })
  return response.data
}

export async function getScan(scanId: string): Promise<ScanDetailResponse> {
  const response = await apiClient.get<ScanDetailResponse>(`/scans/${scanId}`)
  return response.data
}

export async function getScanAnalysis(
  scanId: string,
): Promise<ScanAIAnalysisResponse> {
  const response = await apiClient.get<ScanAIAnalysisResponse>(
    `/scans/${scanId}/analysis`,
  )
  return response.data
}

export async function requestScanAnalysis(
  scanId: string,
): Promise<ScanAIAnalysisResponse> {
  const response = await apiClient.post<ScanAIAnalysisResponse>(
    `/scans/${scanId}/analysis`,
  )
  return response.data
}
