import { useQuery } from '@tanstack/react-query'
import { HOST_FINDINGS_PER_PAGE, listFindings } from '@/api/findings'
import { getHost } from '@/api/hosts'
import { queryKeys } from '@/api/queryKeys'
import { readDetailState, type DetailState } from '@/lib/detailState'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']
type FindingRecord = components['schemas']['FindingRecord']

export type HostDetail = {
  host: HostDetailResponse
  findings: FindingRecord[]
}

export function useHostDetail(hostId: string): DetailState<HostDetail> {
  const hostQuery = useQuery({
    queryKey: queryKeys.hosts.detail(hostId),
    queryFn: () => getHost(hostId),
    enabled: hostId !== '',
  })

  const findingsParams = {
    host_id: hostId,
    per_page: HOST_FINDINGS_PER_PAGE,
  }
  const findingsQuery = useQuery({
    queryKey: queryKeys.findings.list(findingsParams),
    queryFn: () => listFindings(findingsParams),
    enabled: hostId !== '',
  })

  const host = readDetailState(hostId, hostQuery)

  if (host.state === 'notFound') return host

  if (host.state === 'error' || findingsQuery.isError) {
    return {
      state: 'error',
      retry: () => {
        void hostQuery.refetch()
        void findingsQuery.refetch()
      },
    }
  }

  if (host.state === 'loading' || findingsQuery.isPending) {
    return { state: 'loading' }
  }

  return {
    state: 'ready',
    data: { host: host.data, findings: findingsQuery.data.data },
  }
}
