import { TriangleAlert } from 'lucide-react'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function ScanPartialWarning({ scan }: { scan: ScanDetailResponse }) {
  const { t } = useI18n()
  if (scan.metadata?.partial_result !== true) return null

  return (
    <p
      data-testid="scan-partial-warning"
      className="flex shrink-0 items-center gap-2"
    >
      <TriangleAlert aria-hidden="true" className="size-4 text-amber-600" />
      {t('scans.partialWarningTitle')}
    </p>
  )
}

export default ScanPartialWarning
