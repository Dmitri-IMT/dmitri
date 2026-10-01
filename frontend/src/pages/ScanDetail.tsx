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
import ScanCoverage from '@/pages/scans/ScanCoverage'
import ScanDetailHeader, {
  ScanSummaryStrip,
} from '@/pages/scans/ScanDetailHeader'
import ScanFailedNotice from '@/pages/scans/ScanFailedNotice'
import ScanHostsTable from '@/pages/scans/ScanHostsTable'
import ScanIndustrialServices from '@/pages/scans/ScanIndustrialServices'
import ScanStoppedNotice from '@/pages/scans/ScanStoppedNotice'
import ScanUnfinishedNotice from '@/pages/scans/ScanUnfinishedNotice'
import ScanDetailSection from '@/pages/scans/ScanDetailSection'
import ServiceTargetedFindings, {
  targetedFindingsTableTestId,
} from '@/pages/scans/ServiceTargetedFindings'
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
        const opensTargetedDeepLink = scan.findings.some(
          (finding) =>
            isTargetedFinding(finding) && finding.finding_id === openFindingId,
        )
        const partial = metadata.partial_result === true
        const coverage = scan.coverage ?? []
        const omittedUnlisted =
          typeof metadata.targeted_units_omitted_unlisted === 'number'
            ? metadata.targeted_units_omitted_unlisted
            : 0
        const hasRecordedEvidence =
          scan.findings.length > 0 ||
          scan.exposures.length > 0 ||
          scan.hosts.length > 0 ||
          coverage.length > 0
        const stoppedEarly = scan.terminated_by === 'user_cancel'

        return (
          <>
            <ScanDetailHeader scan={scan} />
            <ScanSummaryStrip scan={scan} />
            {partial && (
              <div
                data-testid="scan-partial-notice"
                className="rounded-md border border-border bg-muted p-4 text-body-md"
              >
                {t('scans.partialEvidence')}
              </div>
            )}
            {scan.status === 'failed' && (
              <ScanFailedNotice errorCode={scan.error_code} />
            )}
            {scan.status === 'cancelled' ? (
              <ScanStoppedNotice variant="empty" />
            ) : isUnfinished(scan.status) ? (
              <ScanUnfinishedNotice
                scan={scan}
                onCheck={() => {
                  void query.refetch()
                }}
                isChecking={query.isFetching}
              />
            ) : scan.status !== 'failed' || hasRecordedEvidence ? (
              <div
                data-testid={
                  scan.status === 'failed' ? 'scan-failed-evidence' : undefined
                }
                className="flex flex-col gap-8"
              >
                {stoppedEarly && <ScanStoppedNotice variant="partial" />}
                {scan.status === 'failed' && (
                  <p className="text-body-md text-muted-foreground">
                    {t('scans.failedEvidence')}
                  </p>
                )}
                {scan.status !== 'failed' && (
                  <ScanAIAnalysis
                    scanId={scan.scan_id}
                    findings={scan.findings}
                    partial={partial}
                  />
                )}
                {groups.length === 0 && scan.status !== 'failed' ? (
                  <p data-testid="scan-no-findings" className="text-body-md">
                    {partial
                      ? t('common.noVulnerabilitiesAcceptedEvidence')
                      : t('common.noVulnerabilitiesInScan')}
                  </p>
                ) : groups.length > 0 ? (
                  <div className="flex flex-col gap-8">
                    {groups.map((group) => {
                      const opensForDeepLink = group.findings.some(
                        (finding) => finding.finding_id === openFindingId,
                      )
                      return (
                        <ScanDetailSection
                          key={group.severity}
                          title={t('common.severityGroupTitle', {
                            severity: group.severity,
                            count: group.findings.length,
                          })}
                          openToken={
                            opensForDeepLink
                              ? (openFindingId ?? undefined)
                              : undefined
                          }
                          triggerAriaLabel={t('common.severityGroupToggle', {
                            severity: group.severity,
                          })}
                        >
                          <FindingsTable
                            findings={group.findings}
                            variant="scan"
                            testId={`findings-${group.severity}`}
                            caption={t('common.severityGroupCaption', {
                              severity: group.severity,
                            })}
                            openFindingId={openFindingId}
                            onOpenFindingChange={setOpenFindingId}
                          />
                        </ScanDetailSection>
                      )
                    })}
                  </div>
                ) : null}
                {(scan.status !== 'failed' || scan.exposures.length > 0) && (
                  <ScanDetailSection title={t('common.attackSurface')}>
                    {scan.assessment_status === 'unavailable' ? (
                      <div
                        data-testid="scan-assessment-unavailable"
                        className="flex flex-col gap-2 text-body-md"
                      >
                        <p>{t('common.attackSurfaceUnavailable')}</p>
                        <p className="text-muted-foreground">
                          {t('common.rerunForData')}
                        </p>
                      </div>
                    ) : scan.exposures.length === 0 ? (
                      <p
                        data-testid="scan-no-exposures"
                        className="text-body-md"
                      >
                        {t('common.noReachableServices')}
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
                )}
                {hasTargetedSection && (
                  <ScanDetailSection
                    key="targeted"
                    title="Service Targeted Tools"
                    openToken={
                      opensTargetedDeepLink
                        ? (openFindingId ?? undefined)
                        : undefined
                    }
                    triggerAriaLabel="Toggle service-targeted findings"
                  >
                    <ServiceTargetedFindings
                      findings={scan.findings}
                      openFindingId={openFindingId}
                      onOpenFindingChange={setOpenFindingId}
                    />
                  </ScanDetailSection>
                )}
                {(scan.status !== 'failed' || coverage.length > 0) && (
                  <ScanDetailSection title={t('scans.checkCoverage')}>
                    <ScanCoverage
                      coverage={coverage}
                      omittedUnlisted={omittedUnlisted}
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
                {(scan.status !== 'failed' || scan.hosts.length > 0) && (
                  <ScanDetailSection title={t('common.machinesSeen')}>
                    {scan.hosts.length === 0 ? (
                      <p className="text-body-md">
                        No machines were discovered.
                      </p>
                    ) : (
                      <ScanHostsTable hosts={scan.hosts} />
                    )}
                  </ScanDetailSection>
                )}
              </div>
            ) : null}
          </>
        )
      }}
    </ReadDetailGate>
  )
}

export default ScanDetail
