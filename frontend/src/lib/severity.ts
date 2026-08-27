import type { components } from '@/types/openapi'

type Severity = components['schemas']['Severity']

export const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

export function bySeverityDesc<T extends { severity: Severity }>(
  a: T,
  b: T,
): number {
  return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
}
