import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken } from '@/api/tokenStore'
import { listHosts } from '@/api/hosts'
import type { components } from '@/types/openapi'
import {
  criticalFinding,
  findingFixtures,
  hostFixtures,
  highFinding,
} from './mswHandlers'

type FindingRecord = components['schemas']['FindingRecord']

const listParams = {
  page: 1,
  per_page: 20,
  sort_by: 'last_seen_at' as const,
  sort_order: 'desc' as const,
  group: 'active' as const,
}

describe('mswHandlers host fixtures', () => {
  it('carries machine_type and vulnerability_count on every host', () => {
    expect(hostFixtures.length).toBeGreaterThan(0)
    hostFixtures.forEach((host) => {
      expect(host.machine_type).toBeTruthy()
      expect(typeof host.vulnerability_count).toBe('number')
    })
  })
})

describe('mswHandlers finding fixtures', () => {
  it('carries hostname and life fields on every finding', () => {
    const requiredKeys: (keyof FindingRecord)[] = [
      'host_hostname',
      'first_seen_at',
      'last_seen_at',
      'fixed_at',
    ]

    findingFixtures.forEach((finding) => {
      requiredKeys.forEach((key) => {
        expect(key in finding).toBe(true)
      })
    })
    expect(criticalFinding.host_hostname).toBe('host-01')
    expect(highFinding.fixed_at).toBeNull()
  })
})

describe('mswHandlers /hosts group split', () => {
  beforeEach(() => {
    setAccessToken('test-token')
  })

  it('returns quiet_total on the active response and honors group=quiet', async () => {
    const active = await listHosts(listParams)
    const quiet = await listHosts({ ...listParams, group: 'quiet' })

    expect(active.quiet_total).toBe(quiet.total)
    expect(active.data.length + quiet.data.length).toBeLessThanOrEqual(
      hostFixtures.length,
    )
  })
})
