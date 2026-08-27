import { apiClient } from './client'
import type { components, operations } from '../types/openapi'

type HostListResponse = components['schemas']['HostListResponse']
type HostDetailResponse = components['schemas']['HostDetailResponse']
type ListHostsQuery = NonNullable<
  operations['listHosts']['parameters']['query']
>

export type HostSortBy = components['parameters']['HostSortBy']
export type HostListParams = Required<
  Pick<ListHostsQuery, 'page' | 'per_page' | 'sort_by' | 'sort_order'>
>

export const HOSTS_PER_PAGE = 20

export const HOST_LIST_DEFAULT_SORT = {
  sort_by: 'last_seen_at',
  sort_order: 'desc',
} as const

export async function listHosts(
  params: HostListParams,
): Promise<HostListResponse> {
  const response = await apiClient.get<HostListResponse>('/hosts', { params })
  return response.data
}

export async function getHost(hostId: string): Promise<HostDetailResponse> {
  const response = await apiClient.get<HostDetailResponse>(`/hosts/${hostId}`)
  return response.data
}
