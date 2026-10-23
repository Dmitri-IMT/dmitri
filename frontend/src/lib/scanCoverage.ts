import type { components } from '@/types/openapi'

export function coverageCounts(
  scan: components['schemas']['ScanDetailResponse'],
) {
  const units = scan.coverage ?? []
  return {
    done: units.filter((unit) => unit.outcome === 'completed').length,
    total: units.length,
    incomplete: units.filter((unit) => unit.outcome !== 'completed').length,
    machines: new Set(
      units
        .filter((unit) => unit.outcome !== 'completed')
        .map((unit) => unit.ip),
    ).size,
  }
}
