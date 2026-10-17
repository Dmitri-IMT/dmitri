import { useState } from 'react'
import ExposureTable from '@/pages/scans/ExposureTable'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function HostExposures({ host }: { host: HostDetailResponse }) {
  const [openExposureId, setOpenExposureId] = useState<string | null>(null)

  if (host.assessment_status === 'unavailable') {
    return (
      <p data-testid="host-exposures-unavailable" className="text-body-md">
        Unavailable — this scan predates attack-surface analysis.
      </p>
    )
  }

  if (host.exposures.length === 0) {
    return (
      <p data-testid="host-no-exposures" className="text-body-md">
        No reachable services were found on this machine.
      </p>
    )
  }

  const reviewCount = host.exposures.filter(
    (exposure) => exposure.attention !== 'informational',
  ).length

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body-md text-muted-foreground">
        {host.exposures.length}{' '}
        {host.exposures.length === 1
          ? 'reachable service'
          : 'reachable services'}{' '}
        · {reviewCount} {reviewCount === 1 ? 'needs' : 'need'} review
      </p>
      <ExposureTable
        exposures={host.exposures}
        findings={[]}
        testId="host-exposures-table"
        openExposureId={openExposureId}
        onOpenExposureChange={setOpenExposureId}
        caption="scans.exposureTableHostCaption"
        showSummary={false}
        relatedFindingHref={(exposure, findingId) =>
          `/scans/${exposure.scan_id}?finding=${findingId}`
        }
      />
    </div>
  )
}

export default HostExposures
