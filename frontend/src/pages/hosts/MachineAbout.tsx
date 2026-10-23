import { Card, CardContent, CardHeader } from '@/components/ui/card'
import Timestamp from '@/components/Timestamp'
import TermHint from '@/components/TermHint'
import useI18n from '@/i18n/useI18n'
import { bySeverityDesc } from '@/lib/severity'
import type { components } from '@/types/openapi'

export default function MachineAbout({
  host,
  findings,
}: {
  host: components['schemas']['HostDetailResponse']
  findings: components['schemas']['FindingRecord'][]
}) {
  const { t } = useI18n()
  const highest = [...findings].sort(bySeverityDesc)[0]?.severity
  const risk = findings.reduce<number | null>(
    (max, finding) =>
      finding.risk_score == null ? max : Math.max(max ?? 0, finding.risk_score),
    null,
  )
  const previous = host.scan_history[1]
  const newCount = previous
    ? findings.filter(
        (finding) =>
          Date.parse(finding.first_seen_at ?? finding.detected_at) >
          Date.parse(previous.timestamp),
      ).length
    : null
  return (
    <Card data-testid="machine-about">
      <CardHeader>
        <h2 className="text-title-xs">{t('machine.about')}</h2>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-4 gap-6">
          <div className="flex flex-col gap-2">
            <dt className="text-caption-md text-ink-muted">
              {t('machine.what')}
            </dt>
            <dd className="text-body-md">
              {t(`machine.type.${host.machine_type}`)}
              {host.vendor && ` · ${host.vendor}`}
              {host.device_profile && (
                <p className="text-body-sm text-ink-muted">
                  {t('machine.guess')}
                </p>
              )}
            </dd>
          </div>
          <div className="flex flex-col gap-2">
            <dt className="text-caption-md text-ink-muted">
              <TermHint term="ports" label={t('machine.doors')}>
                <p>{t('hint.ports')}</p>
              </TermHint>
            </dt>
            <dd className="flex flex-col gap-2">
              <strong className="text-title-sm">{host.open_ports_count}</strong>
              <span className="text-body-sm text-ink-muted">
                {[
                  ...new Set(
                    host.ports.map((port) => port.service).filter(Boolean),
                  ),
                ].join(', ')}
              </span>
            </dd>
          </div>
          <div className="flex flex-col gap-2">
            <dt className="text-caption-md text-ink-muted">
              {t('machine.problems')}
            </dt>
            <dd className="flex flex-col gap-2">
              <strong className="text-title-sm">{findings.length}</strong>
              {highest && (
                <span className="text-body-sm text-ink-muted">
                  {t('machine.highest', {
                    level: t('common.severity', { severity: highest }),
                    risk: risk == null ? '—' : Math.round(risk),
                  })}
                </span>
              )}
            </dd>
          </div>
          <div className="flex flex-col gap-2">
            <dt className="text-caption-md text-ink-muted">
              {t('machine.history')}
            </dt>
            <dd className="flex flex-col gap-2">
              <strong className="text-body-md">
                {t('machine.scans', { n: host.scan_history.length })}
              </strong>
              <p className="text-body-sm text-ink-muted">
                {t('machine.first')} <Timestamp value={host.first_seen_at} />.
              </p>
              {newCount !== null && (
                <p className="text-body-sm text-ink-muted">
                  {newCount
                    ? t('machine.new', { n: newCount })
                    : t('machine.same')}
                </p>
              )}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
