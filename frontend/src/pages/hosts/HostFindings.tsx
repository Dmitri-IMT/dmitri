import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { HOST_FINDINGS_PER_PAGE, listFindings } from '@/api/findings'
import { queryKeys } from '@/api/queryKeys'
import ErrorRetry from '@/components/ErrorRetry'
import FindingsTable from '@/pages/scans/FindingsTable'

// The findings of a host are a second request, so this section owns its three
// states. A failed or pending findings read never takes down the identity,
// ports and history that already answer "what does this thing expose".
function HostFindings({ hostId }: { hostId: string }) {
  const [openFindingId, setOpenFindingId] = useState<string | null>(null)
  const params = { host_id: hostId, per_page: HOST_FINDINGS_PER_PAGE }
  const query = useQuery({
    queryKey: queryKeys.findings.list(params),
    queryFn: () => listFindings(params),
  })

  if (query.isError) {
    return (
      <ErrorRetry
        testId="host-findings-error"
        message="Couldn't load this host's findings."
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }

  return (
    <FindingsTable
      findings={query.data?.data ?? []}
      isPending={query.isPending}
      testId="host-findings-table"
      caption="Findings on this host"
      emptyTestId="host-no-findings"
      emptyCopy="No findings on this host."
      openFindingId={openFindingId}
      onOpenFindingChange={setOpenFindingId}
    />
  )
}

export default HostFindings
