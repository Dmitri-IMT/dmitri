import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { HOST_FINDINGS_PER_PAGE, listFindings } from '@/api/findings'
import { queryKeys } from '@/api/queryKeys'
import ErrorRetry from '@/components/ErrorRetry'
import FindingsTable from '@/pages/scans/FindingsTable'
import { EvidenceSummary } from '@/pages/scans/FindingPanel'
import useI18n from '@/i18n/useI18n'

// The vulnerabilities of a machine are a second request, so this section owns
// its three states. A failed or pending read never takes down the identity,
// services and history that already answer "what does this thing expose".
function HostFindings({ hostId }: { hostId: string }) {
  const { t } = useI18n()
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
        message={t('common.findingsLoadError')}
        onRetry={() => {
          void query.refetch()
        }}
      />
    )
  }

  if (!query.isPending && query.data.data.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <EvidenceSummary
          summary={query.data.evidence_summary}
          scope="filtered_findings"
        />
        <p data-testid="host-no-findings" className="text-body-md">
          {t('common.noVulnerabilities')}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <EvidenceSummary
        summary={query.data?.evidence_summary}
        scope="filtered_findings"
      />
      <FindingsTable
        findings={query.data?.data ?? []}
        variant="host"
        isPending={query.isPending}
        testId="host-findings-table"
        caption={t('common.vulnerabilitiesOnMachine')}
        openFindingId={openFindingId}
        onOpenFindingChange={setOpenFindingId}
      />
    </div>
  )
}

export default HostFindings
