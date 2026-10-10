import { Button } from '@/components/ui/button'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function ScanUnfinishedNotice({
  onCheck,
  isChecking,
  scan,
}: {
  onCheck: () => void
  isChecking: boolean
  scan: ScanDetailResponse
}) {
  const { t } = useI18n()
  const openPorts = scan.hosts.reduce(
    (total, host) =>
      total + host.ports.filter((port) => port.state === 'open').length,
    0,
  )
  const filteredPorts = scan.hosts.reduce(
    (total, host) =>
      total + host.ports.filter((port) => port.state === 'filtered').length,
    0,
  )
  const industrial = scan.hosts.reduce(
    (total, host) => total + host.industrial_services.length,
    0,
  )
  return (
    <div
      data-testid="scan-unfinished"
      className="flex flex-col items-center gap-8 py-16 text-center"
    >
      <div className="flex flex-col items-center gap-2">
        <p className="text-body-md">Running…</p>
        <p className="text-title-sm">{t('scans.running')}</p>
        <p className="max-w-prose text-body-md text-muted-foreground">
          {t('scans.liveProgress')}
        </p>
      </div>
      <div
        className="grid w-full max-w-xl grid-cols-2 gap-3 text-left sm:grid-cols-4"
        aria-live="polite"
      >
        <ProgressMetric label={t('common.machines')} value={scan.host_count} />
        <ProgressMetric label={t('scans.openPorts')} value={openPorts} />
        <ProgressMetric
          label={t('scans.filteredPorts')}
          value={filteredPorts}
        />
        <ProgressMetric
          label={t('common.industrialServices')}
          value={industrial}
        />
        <ProgressMetric
          label={t('common.vulnerabilities')}
          value={scan.finding_count}
        />
      </div>
      <Button
        type="button"
        variant="outline"
        data-testid="scan-unfinished-check"
        disabled={isChecking}
        onClick={onCheck}
      >
        {isChecking ? 'Checking…' : 'Check again'}
      </Button>
    </div>
  )
}

function ProgressMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2">
      <p className="text-caption-md uppercase text-muted-foreground">{label}</p>
      <p className="text-title-sm tabular-nums">{value}</p>
    </div>
  )
}

export default ScanUnfinishedNotice
