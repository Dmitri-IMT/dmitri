import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

export type EvidenceFilter = 'all' | 'confirmed' | 'unverified'

const FILTERS = ['all', 'confirmed', 'unverified'] as const

function isEvidenceFilter(value: string): value is EvidenceFilter {
  return (FILTERS as readonly string[]).includes(value)
}

function FindingEvidenceFilter({
  findings,
  value,
  onChange,
}: {
  findings: FindingRecord[]
  value: EvidenceFilter
  onChange: (filter: EvidenceFilter) => void
}) {
  const { t } = useI18n()
  const confirmed = findings.filter((finding) => finding.demonstrated).length
  const counts: Record<EvidenceFilter, number> = {
    all: findings.length,
    confirmed,
    unverified: findings.length - confirmed,
  }

  return (
    <Tabs
      value={value}
      onValueChange={(next) => {
        if (isEvidenceFilter(next)) onChange(next)
      }}
    >
      <TabsList
        variant="line"
        aria-label={t('evidence.filter.label')}
        className="h-auto gap-12 p-0"
      >
        {FILTERS.map((filter) => (
          <TabsTrigger
            key={filter}
            value={filter}
            data-testid={`evidence-filter-${filter}`}
            className="flex-none flex-col items-start gap-1 px-0 py-2 text-muted-foreground after:hidden data-active:text-foreground"
          >
            <span className="text-title-lg tabular-nums">{counts[filter]}</span>
            <span className="text-caption-md">
              {t(`evidence.filter.${filter}`)}
            </span>
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}

export default FindingEvidenceFilter
