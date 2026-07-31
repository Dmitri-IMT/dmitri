import { apiClient } from './client'
import type { components } from '../types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']

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
  params: Record<string, string | number>,
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
