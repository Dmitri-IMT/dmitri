import type { components } from '@/types/openapi'
import type { MessageKey } from '@/i18n/messages'

type FixTask = components['schemas']['AIFixTask']
type FindingRecord = components['schemas']['FindingRecord']

export const WHO_KEY: Record<FixTask['who'], MessageKey> = {
  owner: 'todo.who.owner',
  it_person: 'todo.who.it_person',
  vendor: 'todo.who.vendor',
}

export const TIME_KEY: Record<FixTask['time'], MessageKey> = {
  '5_minutes': 'todo.time.5_minutes',
  '30_minutes': 'todo.time.30_minutes',
  '1_hour': 'todo.time.1_hour',
  half_day: 'todo.time.half_day',
  '1_day': 'todo.time.1_day',
  longer: 'todo.time.longer',
}

export function machineName(finding: FindingRecord): string | null {
  return finding.host_hostname ?? finding.host_ip ?? null
}
