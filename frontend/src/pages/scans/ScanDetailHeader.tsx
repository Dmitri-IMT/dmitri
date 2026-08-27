import PageHeader from '@/components/PageHeader'
import Timestamp from '@/components/Timestamp'
import { hidesCounts } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function ScanDetailHeader({ scan }: { scan: ScanDetailResponse }) {
  const meta = hidesCounts(scan.status)
    ? `${scan.scan_mode} mode · ${scan.subnet}`
    : `${scan.scan_mode} mode · ${scan.subnet} · ${scan.host_count} hosts · ${scan.finding_count} findings`

  return (
    <PageHeader
      testId="scan-detail-header"
      title={
        <>
          Scan — <Timestamp value={scan.timestamp} />
        </>
      }
      subtitle={meta}
    />
  )
}

export default ScanDetailHeader
