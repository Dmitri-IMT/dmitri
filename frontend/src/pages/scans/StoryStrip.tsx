import { Card, CardContent, CardHeader } from '@/components/ui/card'
import useI18n from '@/i18n/useI18n'
import { SCAN_MODE_LABEL } from '@/lib/scanModes'
import { formatScanDuration } from '@/lib/scanDuration'
import { coverageCounts } from '@/lib/scanCoverage'
import type { components } from '@/types/openapi'

export default function StoryStrip({
  scan,
}: {
  scan: components['schemas']['ScanDetailResponse']
}) {
  const { t } = useI18n()
  const counts = coverageCounts(scan)
  const types = new Map<components['schemas']['MachineType'], number>()
  scan.hosts.forEach((host) => {
    const kind = host.machine_type ?? 'unknown'
    types.set(kind, (types.get(kind) ?? 0) + 1)
  })
  const hasKnownType = [...types.keys()].some((type) => type !== 'unknown')
  const known = scan.evidence_completeness !== 'unknown' && counts.total > 0
  const stopped =
    scan.terminated_by != null && scan.terminated_by !== 'completed'
  const finished = stopped
    ? t('scans.stoppedEarly')
    : known
      ? t('story.checks', counts)
      : t('story.notReported')
  return (
    <Card data-testid="scan-story">
      <CardHeader>
        <h2 className="text-title-xs">{t('story.title')}</h2>
      </CardHeader>
      <CardContent>
        <ol className="grid grid-cols-4 gap-6">
          <li data-testid="scan-story-looked" className="flex flex-col gap-2">
            <p className="text-caption-md text-ink-muted">
              {t('story.looked')}
            </p>
            <p className="text-title-sm">{t('story.network')}</p>
            <p className="font-mono text-body-sm">{scan.subnet}</p>
            <p className="text-body-sm text-ink-muted">
              {t('story.networkHelp')}
            </p>
          </li>
          <li data-testid="scan-story-found" className="flex flex-col gap-2">
            <p className="text-caption-md text-ink-muted">{t('story.found')}</p>
            <p className="text-title-sm">
              {scan.host_count
                ? t('story.machines', { n: scan.host_count })
                : t('story.none')}
            </p>
            <p className="text-body-sm text-ink-muted">
              {scan.host_count
                ? hasKnownType
                  ? [...types]
                      .map(([type, n]) => t(`machine.count.${type}`, { n }))
                      .join(' · ')
                  : ''
                : t('story.noneHelp')}
            </p>
          </li>
          <li data-testid="scan-story-checked" className="flex flex-col gap-2">
            <p className="text-caption-md text-ink-muted">
              {t('story.checked')}
            </p>
            <p className="text-title-sm">{SCAN_MODE_LABEL[scan.scan_mode]}</p>
            {scan.duration != null && (
              <p className="text-body-sm">
                {t('story.took', {
                  duration: formatScanDuration(scan.duration) ?? '—',
                })}
              </p>
            )}
            <p className="text-body-sm text-ink-muted">
              {t(`story.mode.${scan.scan_mode}`)}
            </p>
          </li>
          <li data-testid="scan-story-finished" className="flex flex-col gap-2">
            <p className="text-caption-md text-ink-muted">
              {t('story.finished')}
            </p>
            <p className="text-title-sm">{finished}</p>
            {known && !stopped && (
              <div
                role="img"
                aria-label={finished}
                className="h-2 overflow-hidden rounded-sm bg-rule"
              >
                <div
                  className="h-full bg-ink"
                  style={{ width: `${(counts.done / counts.total) * 100}%` }}
                />
              </div>
            )}
            {!known ? (
              <p className="text-body-sm text-ink-muted">
                {t('story.unknown')}
              </p>
            ) : (
              counts.incomplete > 0 && (
                <p className="text-body-sm text-ink-muted">
                  {t('story.missing', { n: counts.incomplete })}
                </p>
              )
            )}
          </li>
        </ol>
      </CardContent>
    </Card>
  )
}
