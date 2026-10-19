import { apiClient } from './client'
import type { components, operations } from '../types/openapi'

type HostListResponse = components['schemas']['HostListResponse']
type HostDetailResponse = components['schemas']['HostDetailResponse']
type HostDeletionResponse = components['schemas']['HostDeletionResponse']
type ListHostsQuery = NonNullable<
  operations['listHosts']['parameters']['query']
>

export type HostSortBy = components['parameters']['HostSortBy']
export type HostListParams = Required<
  Pick<ListHostsQuery, 'page' | 'per_page' | 'sort_by' | 'sort_order' | 'group'>
>
export type HostGroup = NonNullable<ListHostsQuery['group']>

export const HOSTS_PER_PAGE = 20

export const HOST_LIST_DEFAULT_SORT_BY = 'last_seen_at'

/** The order a column starts in the first time it becomes the sort column. */
export const HOST_SORT_DEFAULT_ORDER: Record<
  HostSortBy,
  HostListParams['sort_order']
> = {
  last_seen_at: 'desc',
  hostname: 'asc',
  vendor: 'asc',
  ip: 'asc',
  vulnerability_count: 'desc',
}

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

export async function deleteHost(hostId: string): Promise<void> {
  await apiClient.delete(`/hosts/${hostId}`)
}

export async function deleteAllHosts(): Promise<HostDeletionResponse> {
  const response = await apiClient.delete<HostDeletionResponse>('/hosts')
  return response.data
}
