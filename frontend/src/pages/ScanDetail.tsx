import { useState } from 'react'
import { flushSync } from 'react-dom'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/queryKeys'
import { getScan } from '@/api/scans'
import Disclosure from '@/components/Disclosure'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import PageHeader from '@/components/PageHeader'
import ReadDetailGate from '@/components/ReadDetailGate'
import ProblemsTable from '@/components/ProblemsTable'
import ItSections from '@/components/ItSections'
import { ObservationList } from '@/components/EvidenceDetails'
import { Card, CardContent } from '@/components/ui/card'
import { readDetailState } from '@/lib/detailState'
import { isUnfinished } from '@/lib/scanStatus'
import { coverageCounts } from '@/lib/scanCoverage'
import ExposureTable from '@/pages/scans/ExposureTable'
import TodoList from '@/pages/scans/TodoList'
import StoryStrip from '@/pages/scans/StoryStrip'
import MeaningTable from '@/pages/scans/MeaningTable'
import ScanCoverage from '@/pages/scans/ScanCoverage'
import ScanDelete from '@/pages/scans/ScanDelete'
import ScanDetailHeader from '@/pages/scans/ScanDetailHeader'
import ScanFailedNotice from '@/pages/scans/ScanFailedNotice'
import ScanHostsTable from '@/pages/scans/ScanHostsTable'
import ScanIndustrialServices from '@/pages/scans/ScanIndustrialServices'
import ScanStoppedNotice from '@/pages/scans/ScanStoppedNotice'
import ScanUnfinishedNotice from '@/pages/scans/ScanUnfinishedNotice'
import ScanDetailSection from '@/pages/scans/ScanDetailSection'
import { isTargetedFinding, scanDetailView } from '@/pages/scans/scanDetailView'
import ServiceTargetedFindings from '@/pages/scans/ServiceTargetedFindings'
import useI18n from '@/i18n/useI18n'

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
  if (query.isPending)
    return (
      <div data-testid="scan-detail" className="flex flex-col gap-8">
        <PageHeader title="Scan" />
        <Card>
          <CardContent>
            <table className="w-full" aria-label="Loading scan">
              <LoadingSkeleton rows={3} columns={5} />
            </table>
          </CardContent>
        </Card>
      </div>
    )
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
        const view = scanDetailView(scan)
        const severityFindings = scan.findings.filter(
          (finding) => !isTargetedFinding(finding),
        )
        const opensTargeted = scan.findings.some(
          (finding) =>
            isTargetedFinding(finding) && finding.finding_id === openFindingId,
        )
        const counts = coverageCounts(scan)
        const observations = scan.finding_observations ?? []
        const metadata = scan.metadata ?? {}
        const omitted =
          typeof metadata.targeted_units_omitted_unlisted === 'number'
            ? metadata.targeted_units_omitted_unlisted
            : 0
        const industrialCount = scan.hosts.reduce(
          (n, host) => n + host.industrial_services.length,
          0,
        )
        return (
          <>
            <ScanDetailHeader scan={scan} />
            {view.failed && <ScanFailedNotice errorCode={scan.error_code} />}
            {view.body === 'stopped' && <ScanStoppedNotice variant="empty" />}
            {view.body === 'progress' && (
              <ScanUnfinishedNotice
                scan={scan}
                onCheck={() => {
                  void query.refetch()
                }}
                isChecking={query.isFetching}
              />
            )}
            {view.body === 'evidence' && (
              <div
                data-testid={view.failed ? 'scan-failed-evidence' : undefined}
                className="flex flex-col gap-8"
              >
                {view.stoppedEarly && <ScanStoppedNotice variant="partial" />}
                {view.failed && (
                  <p className="text-body-md text-ink-muted">
                    {t('scans.failedEvidence')}
                  </p>
                )}
                <StoryStrip scan={scan} />
                {view.sections.aiAnalysis && (
                  <TodoList scanId={scan.scan_id} findings={scan.findings} />
                )}
                <MeaningTable scan={scan} />
                <ProblemsTable
                  findings={severityFindings}
                  openFindingId={openFindingId}
                  onOpenFindingChange={setOpenFindingId}
                />
                <ItSections>
                  {view.sections.attackSurface && (
                    <ScanDetailSection
                      testId="it-section-ports"
                      title={t('it.ports', {
                        n: scan.exposures.length,
                        m: new Set(scan.exposures.map((item) => item.host_id))
                          .size,
                      })}
                    >
                      {scan.assessment_status === 'unavailable' ? (
                        <div
                          data-testid="scan-assessment-unavailable"
                          className="flex flex-col gap-2 text-body-md"
                        >
                          <p>{t('common.attackSurfaceUnavailable')}</p>
                          <p className="text-ink-muted">
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
                            flushSync(() => setOpenFindingId(id))
                            const finding = scan.findings.find(
                              (item) => item.finding_id === id,
                            )
                            const table =
                              finding && isTargetedFinding(finding)
                                ? `targeted-${finding.severity}`
                                : 'problems-table'
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
                  {view.sections.machines && (
                    <ScanDetailSection
                      testId="it-section-machines"
                      title={t('it.machines', { n: scan.hosts.length })}
                    >
                      <ScanHostsTable hosts={scan.hosts} />
                    </ScanDetailSection>
                  )}
                  {view.sections.targeted && (
                    <ScanDetailSection
                      testId="it-section-targeted"
                      title={t('it.targeted', {
                        n: scan.findings.filter(isTargetedFinding).length,
                      })}
                      openToken={
                        opensTargeted ? (openFindingId ?? undefined) : undefined
                      }
                      triggerAriaLabel={t('scans.targetedFindingsToggle')}
                    >
                      <ServiceTargetedFindings
                        findings={scan.findings}
                        openFindingId={openFindingId}
                        onOpenFindingChange={setOpenFindingId}
                      />
                    </ScanDetailSection>
                  )}
                  {view.sections.coverage && (
                    <ScanDetailSection
                      testId="it-section-coverage"
                      title={t('it.coverage', counts)}
                    >
                      <div className="flex flex-col gap-6">
                        {(observations.length > 0 ||
                          scan.finding_observations_truncated) && (
                          <Disclosure
                            label={t('evidence.otherChecks', {
                              count: observations.length,
                            })}
                            testId="scan-other-checks"
                            caretTestId="scan-other-checks-caret"
                          >
                            <div className="w-full pt-4">
                              <ObservationList
                                observations={observations}
                                truncated={scan.finding_observations_truncated}
                                testId="scan-finding-observations"
                                title={t('evidence.observationsTitle')}
                              />
                            </div>
                          </Disclosure>
                        )}
                        <ScanCoverage
                          coverage={scan.coverage ?? []}
                          omittedUnlisted={omitted}
                        />
                      </div>
                    </ScanDetailSection>
                  )}
                  {view.sections.industrial && (
                    <ScanDetailSection
                      testId="it-section-industrial"
                      title={`${t('common.industrialServices')} · ${industrialCount}`}
                    >
                      <ScanIndustrialServices hosts={scan.hosts} />
                    </ScanDetailSection>
                  )}
                </ItSections>
              </div>
            )}
            <ScanDelete scan={scan} />
          </>
        )
      }}
    </ReadDetailGate>
  )
}
export default ScanDetail
