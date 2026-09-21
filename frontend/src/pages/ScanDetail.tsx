import { useState } from 'react'
import { flushSync } from 'react-dom'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import PageHeader from '@/components/PageHeader'
import ReadDetailGate from '@/components/ReadDetailGate'
import { Card, CardContent } from '@/components/ui/card'
import { readDetailState } from '@/lib/detailState'
import { isUnfinished } from '@/lib/scanStatus'
import { SEVERITY_ORDER } from '@/lib/severity'
import ExposureTable from '@/pages/scans/ExposureTable'
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
import ScanDetailSection from '@/pages/scans/ScanDetailSection'
import ServiceTargetedFindings, {
  targetedFindingsTableTestId,
} from '@/pages/scans/ServiceTargetedFindings'
import SeverityWord from '@/components/SeverityWord'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type Severity = components['schemas']['Severity']

const SEVERITIES = Object.keys(SEVERITY_ORDER) as Severity[]

const TARGETED_SOURCE = 'targeted_service_assessment'

function isTargetedFinding(finding: FindingRecord): boolean {
  return finding.source === TARGETED_SOURCE
}

function ScanDetail() {
  const { t } = useI18n()
  const { scanId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const [openFindingId, setOpenFindingId] = useState<string | null>(() =>
    searchParams.get('finding'),
  )
  const [openExposureId, setOpenExposureId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: queryKeys.scans.detail(scanId),
    queryFn: () => getScan(scanId),
    enabled: scanId !== '',
    refetchInterval: (current) => {
      const status = current.state.data?.status
      return status != null && isUnfinished(status) ? 2000 : false
    },
    refetchIntervalInBackground: true,
  })

  if (query.isPending) {
    return (
      <div data-testid="scan-detail" className="flex flex-col gap-12">
        <PageHeader title="Scan" />
        <div className="flex flex-col gap-8" aria-label="Loading scan">
          <table
            className="w-full table-fixed"
            aria-label="Loading scan summary"
          >
            <LoadingSkeleton rows={1} columns={6} />
          </table>
          <Card>
            <CardContent>
              <table
                className="w-full table-fixed"
                aria-label="Loading scan data"
              >
                <LoadingSkeleton rows={3} columns={5} />
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

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
        const severityFindings = scan.findings.filter(
          (finding) => !isTargetedFinding(finding),
        )
        const groups = SEVERITIES.map((severity) => ({
          severity,
          findings: severityFindings.filter(
            (finding: FindingRecord) => finding.severity === severity,
          ),
        })).filter((group) => group.findings.length > 0)
        const metadata = scan.metadata ?? {}
        const hasTargetedSection =
          metadata.targeted_units_planned != null ||
          scan.findings.some(isTargetedFinding)
        const opensTargetedDeepLink =
          openFindingId != null &&
          scan.findings.some(
            (finding) =>
              isTargetedFinding(finding) &&
              finding.finding_id === openFindingId,
          )
        const partial = metadata.partial_result === true
        const completedPartial =
          partial && metadata.terminated_by === 'completed'
        const interruptedStage =
          typeof metadata.interrupted_stage === 'string'
            ? metadata.interrupted_stage
            : ''
        const stageLabels: Record<string, string> = {
          discovery: 'Host discovery',
          ports: 'Port scanning',
          deep_inspection: 'Deep inspection',
          ot_inspection: 'Industrial inspection',
          targeted_assessment: 'Targeted service assessment',
          normalize: 'Results generation',
        }

        return (
          <>
            <ScanDetailHeader scan={scan} />
            <ScanSummaryStrip scan={scan} />
            {scan.status === 'failed' ? (
              <ScanFailedNotice errorCode={scan.error_code} />
            ) : isUnfinished(scan.status) ? (
              <ScanUnfinishedNotice
                scan={scan}
                onCheck={() => {
                  void query.refetch()
                }}
                isChecking={query.isFetching}
              />
            ) : (
              <>
                {partial && (
                  <div
                    data-testid="scan-partial-notice"
                    role="status"
                    className="flex flex-col gap-2 border border-edge p-6"
                  >
                    <p className="text-title-xs">
                      {completedPartial
                        ? 'INCOMPLETE EVIDENCE'
                        : 'STOPPED SCAN'}
                    </p>
                    <p className="max-w-prose text-body-md text-muted-foreground">
                      {completedPartial
                        ? 'The scan finished, but some checks did not complete. Counts below use accepted evidence only; missing coverage is not a clean result.'
                        : stageLabels[interruptedStage]
                          ? `${stageLabels[interruptedStage]} did not finish. Counts below use accepted evidence only.`
                          : 'The scan did not finish. Counts below use accepted evidence only.'}
                    </p>
                  </div>
                )}
                <ScanAIAnalysis
                  scanId={scan.scan_id}
                  findings={scan.findings}
                />
                <ScanReports scanId={scan.scan_id} />
                {groups.length === 0 ? (
                  <p data-testid="scan-no-findings" className="text-body-md">
                    {partial
                      ? 'No confirmed vulnerabilities in accepted evidence.'
                      : 'No confirmed vulnerabilities were found in this scan.'}
                  </p>
                ) : (
                  <div className="flex flex-col gap-8">
                    {groups.map((group) => {
                      const opensForDeepLink = group.findings.some(
                        (finding) => finding.finding_id === openFindingId,
                      )
                      return (
                        <ScanDetailSection
                          key={group.severity}
                          title={<SeverityWord severity={group.severity} />}
                          defaultOpen={opensForDeepLink}
                          openWhen={opensForDeepLink}
                          triggerAriaLabel={`Toggle ${group.severity} vulnerabilities`}
                        >
                          <FindingsTable
                            findings={group.findings}
                            variant="scan"
                            testId={`findings-${group.severity}`}
                            caption={`${group.severity} vulnerabilities in this scan`}
                            openFindingId={openFindingId}
                            onOpenFindingChange={setOpenFindingId}
                          />
                        </ScanDetailSection>
                      )
                    })}
                  </div>
                )}
                <ScanDetailSection title="Attack surface">
                  {scan.assessment_status === 'unavailable' ? (
                    <div
                      data-testid="scan-assessment-unavailable"
                      className="flex flex-col gap-2 text-body-md"
                    >
                      <p>
                        Unavailable — this scan predates attack-surface
                        analysis.
                      </p>
                      <p className="text-muted-foreground">
                        Re-run the scan to produce this data.
                      </p>
                    </div>
                  ) : scan.exposures.length === 0 ? (
                    <p data-testid="scan-no-exposures" className="text-body-md">
                      No reachable services were found in this scan.
                    </p>
                  ) : (
                    <ExposureTable
                      exposures={scan.exposures}
                      findings={scan.findings}
                      testId="scan-exposures-table"
                      openExposureId={openExposureId}
                      onOpenExposureChange={setOpenExposureId}
                      onOpenFinding={(id) => {
                        const finding = scan.findings.find(
                          (item) => item.finding_id === id,
                        )
                        flushSync(() => setOpenFindingId(id))
                        if (finding == null) {
                          return
                        }
                        const table = isTargetedFinding(finding)
                          ? targetedFindingsTableTestId(finding)
                          : `findings-${finding.severity}`
                        document
                          .querySelector<HTMLButtonElement>(
                            `[data-testid="${table}-caret-${id}"]`,
                          )
                          ?.focus()
                      }}
                    />
                  )}
                </ScanDetailSection>
                {hasTargetedSection && (
                  <ScanDetailSection
                    title="Service Targeted Tools"
                    openWhen={opensTargetedDeepLink}
                  >
                    <ServiceTargetedFindings
                      findings={scan.findings}
                      openFindingId={openFindingId}
                      onOpenFindingChange={setOpenFindingId}
                    />
                  </ScanDetailSection>
                )}
                {scan.hosts.some(
                  (host) => host.industrial_services.length > 0,
                ) && (
                  <ScanDetailSection title={t('common.industrialServices')}>
                    <ScanIndustrialServices hosts={scan.hosts} />
                  </ScanDetailSection>
                )}
                <ScanDetailSection title={t('common.machinesSeen')}>
                  {scan.hosts.length === 0 ? (
                    <p className="text-body-md">No machines were discovered.</p>
                  ) : (
                    <ScanHostsTable hosts={scan.hosts} />
                  )}
                </ScanDetailSection>
              </>
            )}
          </>
        )
      }}
    </ReadDetailGate>
  )
}

export default ScanDetail
