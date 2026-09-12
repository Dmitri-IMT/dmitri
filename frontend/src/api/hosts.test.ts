import { beforeEach, describe, expect, it } from 'vitest'
import {
  HOST_SORT_DEFAULT_ORDER,
  listHosts,
  type HostGroup,
  type HostListParams,
} from '@/api/hosts'
import { setAccessToken } from '@/api/tokenStore'
import type { components } from '@/types/openapi'

type HostSummary = components['schemas']['HostSummary']

const listParams: HostListParams = {
  page: 1,
  per_page: 20,
  sort_by: 'last_seen_at',
  sort_order: 'desc',
  group: 'active',
}

function assertHostGroup(value: HostGroup): HostGroup {
  return value
}

describe('hosts api', () => {
  beforeEach(() => {
    setAccessToken('test-token')
  })

  it('types HostListParams with group and exports HostGroup', () => {
    expect(assertHostGroup('active')).toBe('active')
    expect(assertHostGroup('quiet')).toBe('quiet')
    expect(listParams.group).toBe('active')
  })

  it('defaults vulnerability_count sort to descending', () => {
    expect(HOST_SORT_DEFAULT_ORDER.vulnerability_count).toBe('desc')
  })

  it('lists active hosts with quiet_total from the default handler', async () => {
    const response = await listHosts(listParams)

    expect(response.quiet_total).toBeGreaterThanOrEqual(0)
    expect(response.data.every((host) => 'machine_type' in host)).toBe(true)
    expect(
      response.data.every((host) => typeof host.vulnerability_count === 'number'),
    ).toBe(true)
  })

  it('pages the quiet group separately from the active group', async () => {
    const active = await listHosts({ ...listParams, group: 'active' })
    const quiet = await listHosts({ ...listParams, group: 'quiet' })

    expect(active.total).not.toBe(quiet.total)
    expect(active.quiet_total).toBe(quiet.quiet_total)
    expect(active.quiet_total).toBe(quiet.total)

    const activeIds = new Set(active.data.map((host: HostSummary) => host.host_id))
    quiet.data.forEach((host: HostSummary) => {
      expect(activeIds.has(host.host_id)).toBe(false)
    })
  })
})
