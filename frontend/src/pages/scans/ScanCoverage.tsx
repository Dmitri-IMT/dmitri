import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'
import type { MessageKey } from '@/i18n/messages'

type CoverageUnit = NonNullable<
  components['schemas']['ScanDetailResponse']['coverage']
>[number]

const stageKeys: Record<CoverageUnit['stage'], MessageKey> = {
  ports: 'scans.coveragePorts',
  deep_inspection: 'scans.coverageDeepInspection',
  targeted_assessment: 'scans.coverageTargetedAssessment',
}

const outcomeKeys: Record<CoverageUnit['outcome'], MessageKey> = {
  completed: 'scans.coverageOutcomeCompleted',
  partial: 'scans.coverageOutcomePartial',
  failed: 'scans.coverageOutcomeFailed',
  timed_out: 'scans.coverageOutcomeTimedOut',
  skipped: 'scans.coverageOutcomeSkipped',
}

function endpoint(unit: CoverageUnit): string {
  return unit.port == null
    ? unit.ip
    : `${unit.ip}:${unit.port}/${unit.protocol ?? 'tcp'}`
}

function ScanCoverage({ coverage }: { coverage: CoverageUnit[] }) {
  const { t } = useI18n()
  if (coverage.length === 0) {
    return (
      <p data-testid="scan-coverage-unavailable" className="text-body-md">
        {t('scans.coverageUnavailable')}
      </p>
    )
  }

  const endpoints = new Map<string, CoverageUnit[]>()
  for (const unit of coverage) {
    const address = endpoint(unit)
    endpoints.set(address, [...(endpoints.get(address) ?? []), unit])
  }

  return (
    <div data-testid="scan-coverage" className="flex flex-col gap-6">
      {[...endpoints].map(([address, units]) => {
        const completed = units.filter(
          (unit) => unit.outcome === 'completed',
        ).length
        return (
          <section key={address} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-baseline gap-2">
              <h3 className="font-mono text-title-xs">{address}</h3>
              <p className="text-body-sm text-muted-foreground">
                {t('scans.coverageCompleted', {
                  completed,
                  total: units.length,
                })}
              </p>
            </div>
            <ul className="flex flex-col gap-2">
              {units.map((unit, index) => (
                <li
                  key={`${unit.stage}-${unit.tool ?? ''}-${index}`}
                  className="rounded-md border border-border p-3 text-body-sm"
                >
                  <span className="font-medium">
                    {unit.tool ?? t(stageKeys[unit.stage])}:{' '}
                    {t(outcomeKeys[unit.outcome])}
                  </span>
                  {unit.reason_code && (
                    <span className="text-muted-foreground">
                      {' '}
                      (<code>{unit.reason_code}</code>)
                    </span>
                  )}
                  {(unit.observations?.length ?? 0) > 0 && (
                    <ul className="list-disc pl-6">
                      {unit.observations?.map((observation) => (
                        <li key={observation.observation_key}>
                          {observation.summary}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

export default ScanCoverage
