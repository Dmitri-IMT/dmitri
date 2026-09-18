import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { HOST_FINDINGS_PER_PAGE, listFindings } from '@/api/findings'
import { queryKeys } from '@/api/queryKeys'
import ErrorRetry from '@/components/ErrorRetry'
import FindingsTable from '@/pages/scans/FindingsTable'

// The vulnerabilities of a machine are a second request, so this section owns
// its three states. A failed or pending read never takes down the identity,
// services and history that already answer "what does this thing expose".
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
        message="Couldn't load this machine's vulnerabilities."
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }

  if (!query.isPending && query.data.data.length === 0) {
    return (
      <p data-testid="host-no-findings" className="text-body-md">
        No confirmed vulnerabilities were found on this machine.
      </p>
    )
  }

  return (
    <FindingsTable
      findings={query.data?.data ?? []}
      variant="host"
      isPending={query.isPending}
      testId="host-findings-table"
      caption="Vulnerabilities on this machine"
      openFindingId={openFindingId}
      onOpenFindingChange={setOpenFindingId}
    />
  )
}

export default HostFindings
