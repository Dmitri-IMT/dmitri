import { Info } from 'lucide-react'
import TermHint from '@/components/TermHint'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

export default function RiskBreakdownHint({
  breakdown,
}: {
  breakdown?: components['schemas']['RiskBreakdown'] | null
}) {
  const { t } = useI18n()
  const rows = [
    ['severity', 45],
    ['likelihood', 35],
    ['confidence', 15],
    ['reachable', 5],
  ] as const
  return (
    <TermHint
      term="risk"
      label={<Info aria-hidden="true" className="size-4" />}
      wide
      ariaLabel={t('risk.how')}
    >
      <div data-testid="finding-risk-breakdown" className="flex flex-col gap-4">
        <p className="text-body-md font-semibold">{t('risk.title')}</p>
        <p>{t('risk.intro')}</p>
        {breakdown ? (
          <dl className="flex flex-col gap-3">
            {rows.map(([key, max]) => (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex justify-between gap-3">
                  <dt>{t(`risk.${key}`)}</dt>
                  <dd className="font-semibold tabular-nums">
                    {breakdown[key].toFixed(1)} / {max}
                  </dd>
                </div>
                <div
                  aria-hidden="true"
                  className="h-1.5 overflow-hidden rounded-sm bg-ink-muted"
                >
                  <div
                    className="h-full bg-canvas"
                    style={{ width: `${(breakdown[key] / max) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </dl>
        ) : (
          <p>{t('risk.notCalculated')}</p>
        )}
        <p className="text-caption-md">{t('risk.footer')}</p>
      </div>
    </TermHint>
  )
}
