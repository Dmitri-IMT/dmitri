import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Collapsible } from 'radix-ui'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import ReadDetailGate from '@/components/ReadDetailGate'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { readDetailState } from '@/lib/detailState'
import { isUnfinished } from '@/lib/scanStatus'
import { SEVERITY_ORDER } from '@/lib/severity'
import FindingsTable from '@/pages/scans/FindingsTable'
import ScanAIAnalysis from '@/pages/scans/ScanAIAnalysis'
import ScanReports from '@/pages/scans/ScanReports'
import ScanDetailHeader, {
  ScanSummaryStrip,
} from '@/pages/scans/ScanDetailHeader'
import ScanFailedNotice from '@/pages/scans/ScanFailedNotice'
import ScanHostsTable from '@/pages/scans/ScanHostsTable'
import ScanIndustrialServices from '@/pages/scans/ScanIndustrialServices'
import ScanUnfinishedNotice from '@/pages/scans/ScanUnfinishedNotice'
import SeverityWord from '@/components/SeverityWord'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type Severity = components['schemas']['Severity']

const SEVERITIES = Object.keys(SEVERITY_ORDER) as Severity[]

function ScanDetail() {
  const { scanId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(() =>
    searchParams.get('finding'),
  )

  const query = useQuery({
    queryKey: queryKeys.scans.detail(scanId),
    queryFn: () => getScan(scanId),
    enabled: scanId !== '',
  })

  return (
    <ReadDetailGate
      testId="scan-detail"
      title="Scan"
      notFoundMessage="That scan doesn't exist."
      errorMessage="Couldn't load this scan."
      backTo="/scans"
      backLabel="Back to scans"
      detail={readDetailState(scanId, query)}
    >
      {(scan) => {
        const groups = SEVERITIES.map((severity) => ({
          severity,
          findings: scan.findings.filter(
            (finding: FindingRecord) => finding.severity === severity,
          ),
        })).filter((group) => group.findings.length > 0)

        return (
          <>
            <ScanDetailHeader scan={scan} />
            <ScanSummaryStrip scan={scan} />
            {scan.status === 'failed' ? (
              <ScanFailedNotice errorCode={scan.error_code} />
            ) : isUnfinished(scan.status) ? (
              <ScanUnfinishedNotice
                onCheck={() => {
                  void query.refetch()
                }}
                isChecking={query.isFetching}
              />
            ) : (
              <>
                <ScanAIAnalysis
                  scanId={scan.scan_id}
                  findings={scan.findings}
                />
                <ScanReports scanId={scan.scan_id} />
                {groups.length === 0 ? (
                  <p data-testid="scan-no-findings" className="text-body-md">
                    No vulnerabilities. Every machine in this scan came back
                    clean.
                  </p>
                ) : (
                  <div className="flex flex-col gap-8">
                    {groups.map((group) => {
                      const opensForDeepLink = group.findings.some(
                        (finding) => finding.finding_id === openFindingId,
                      )
                      return (
                        <Collapsible.Root
                          key={group.severity}
                          defaultOpen={opensForDeepLink}
                          asChild
                        >
                          <Card>
                            <CardHeader className="p-0">
                              <Collapsible.Trigger
                                className="flex w-full cursor-pointer items-center justify-between px-6 py-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                                aria-label={`Toggle ${group.severity} vulnerabilities`}
                              >
                                <h2 className="text-title-sm">
                                  <SeverityWord severity={group.severity} />
                                </h2>
                                <span
                                  aria-hidden="true"
                                  className="text-title-sm leading-none text-muted-foreground transition-transform data-[state=open]:rotate-90"
                                >
                                  ›
                                </span>
                              </Collapsible.Trigger>
                            </CardHeader>
                            <Collapsible.Content forceMount asChild>
                              <CardContent className="data-[state=closed]:hidden">
                                <FindingsTable
                                  findings={group.findings}
                                  variant="scan"
                                  testId={`findings-${group.severity}`}
                                  caption={`${group.severity} vulnerabilities in this scan`}
                                  openFindingId={openFindingId}
                                  onOpenFindingChange={setOpenFindingId}
                                />
                              </CardContent>
                            </Collapsible.Content>
                          </Card>
                        </Collapsible.Root>
                      )
                    })}
                  </div>
                )}
                {scan.hosts.some(
                  (host) => host.industrial_services.length > 0,
                ) && (
                  <Card>
                    <CardHeader>
                      <h2 className="text-title-sm">Industrial services</h2>
                    </CardHeader>
                    <CardContent>
                      <ScanIndustrialServices hosts={scan.hosts} />
                    </CardContent>
                  </Card>
                )}
                <Card>
                  <CardHeader>
                    <h2 className="text-title-sm">Machines seen</h2>
                  </CardHeader>
                  <CardContent>
                    <ScanHostsTable hosts={scan.hosts} />
                  </CardContent>
                </Card>
              </>
            )}
          </>
        )
      }}
    </ReadDetailGate>
  )
}

export default ScanDetail
