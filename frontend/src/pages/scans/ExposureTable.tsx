import { Button } from '@/components/ui/button'
import { Link } from 'react-router'
import DataTable from '@/components/DataTable'
import useI18n from '@/i18n/useI18n'
import type { MessageKey } from '@/i18n/messages'
import {
  exposureColumns,
  exposureEndpoint,
} from '@/pages/scans/exposureColumns'
import type { components } from '@/types/openapi'

type ExposureRead = components['schemas']['ExposureRead']
type FindingRecord = components['schemas']['FindingRecord']

type ExposureTableProps = {
  exposures: ExposureRead[]
  findings: FindingRecord[]
  testId: string
  openExposureId: string | null
  onOpenExposureChange: (id: string | null) => void
  onOpenFinding?: (id: string) => void
  relatedFindingHref?: (exposure: ExposureRead, findingId: string) => string
  caption?: MessageKey
  showSummary?: boolean
}

function ExposurePanel({
  exposure,
  findings,
  onOpenFinding,
  relatedFindingHref,
}: {
  exposure: ExposureRead
  findings: FindingRecord[]
  onOpenFinding?: (id: string) => void
  relatedFindingHref?: (exposure: ExposureRead, findingId: string) => string
}) {
  const { t } = useI18n()
  const relatedFindings = exposure.related_finding_ids
    .map((id) => findings.find((finding) => finding.finding_id === id))
    .filter((finding): finding is FindingRecord => finding !== undefined)

  return (
    <div className="flex flex-col gap-6 p-4">
      <div className="flex gap-4">
        <p className="w-1/4 shrink-0 text-caption-md uppercase tracking-widest text-muted-foreground">
          {t('scans.exposureWhyItMatters')}
        </p>
        <p className="min-w-0 max-w-prose text-body-md">{exposure.reason}</p>
      </div>
      <div className="flex gap-4">
        <p className="w-1/4 shrink-0 text-caption-md uppercase tracking-widest text-muted-foreground">
          {t('common.evidence')}
        </p>
        <ul className="flex min-w-0 flex-1 flex-col gap-2 text-body-md">
          {exposure.evidence.map((item, index) => (
            <li key={`${item.kind}-${item.source}-${index}`}>
              {item.source}: {item.value}
            </li>
          ))}
        </ul>
      </div>
      {exposure.related_finding_ids.length > 0 && (
        <div className="flex gap-4">
          <p className="w-1/4 shrink-0 text-caption-md uppercase tracking-widest text-muted-foreground">
            {t('scans.exposureRelatedVulnerabilities')}
          </p>
          <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
            {exposure.related_finding_ids.map((findingId) => {
              const finding = relatedFindings.find(
                (candidate) => candidate.finding_id === findingId,
              )
              if (!finding && !relatedFindingHref) return null
              return (
                <div key={findingId} className="flex items-center gap-4">
                  {finding && (
                    <span className="text-body-md">{finding.title}</span>
                  )}
                  {relatedFindingHref ? (
                    <Button
                      asChild
                      variant="link"
                      className="h-auto p-0 text-body-md"
                    >
                      <Link
                        to={relatedFindingHref(exposure, findingId)}
                        data-testid={`exposure-related-finding-${findingId}`}
                      >
                        {t('scans.exposureOpenVulnerability')}
                      </Link>
                    </Button>
                  ) : onOpenFinding ? (
                    <Button
                      type="button"
                      variant="link"
                      data-testid={`exposure-related-finding-${findingId}`}
                      className="h-auto p-0 text-body-md"
                      onClick={() => onOpenFinding(findingId)}
                    >
                      {t('scans.exposureOpenVulnerability')}
                    </Button>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function ExposureTable({
  exposures,
  findings,
  testId,
  openExposureId,
  onOpenExposureChange,
  onOpenFinding,
  relatedFindingHref,
  caption = 'scans.exposureTableCaption',
  showSummary = true,
}: ExposureTableProps) {
  const { t } = useI18n()
  const needsReview = exposures.filter(
    (exposure) => exposure.attention !== 'informational',
  ).length

  return (
    <div className="flex flex-col gap-4">
      {showSummary && (
        <p className="text-body-sm font-medium">
          {t('common.reachableServices', { count: exposures.length })} ·{' '}
          {t('common.needsReview', { count: needsReview })}
        </p>
      )}
      <p className="text-body-sm text-muted-foreground">
        {t('scans.exposureTableGuidance')}
      </p>
      <DataTable
        columns={exposureColumns(t)}
        rows={exposures}
        rowId={(exposure) => exposure.exposure_id}
        testId={testId}
        caption={t(caption)}
        rowAction={{
          kind: 'expand',
          panel: (exposure) => (
            <ExposurePanel
              exposure={exposure}
              findings={findings}
              onOpenFinding={onOpenFinding}
              relatedFindingHref={relatedFindingHref}
            />
          ),
          label: (exposure) =>
            t('scans.exposureRowDetails', {
              service: exposure.observed_service,
              endpoint: exposureEndpoint(exposure),
            }),
          openRowId: openExposureId,
          onOpenRowChange: onOpenExposureChange,
        }}
      />
    </div>
  )
}

export default ExposureTable
