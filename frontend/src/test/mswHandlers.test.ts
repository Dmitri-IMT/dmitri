import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken } from '@/api/tokenStore'
import { listHosts } from '@/api/hosts'
import { hostFixtures } from './mswHandlers'

const listParams = {
  page: 1,
  per_page: 20,
  sort_by: 'last_seen_at' as const,
  sort_order: 'desc' as const,
  group: 'active' as const,
}

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
