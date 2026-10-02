import { describe, expect, it } from 'vitest'
import { criticalFinding, latestSuccessfulScan } from '@/test/mswHandlers'
import { relatedExposure } from '@/test/scansHarness'
import type { components } from '@/types/openapi'
import { scanDetailView } from './scanDetailView'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function scan(overrides: Partial<ScanDetailResponse> = {}): ScanDetailResponse {
  return {
    ...latestSuccessfulScan,
    hosts: [],
    findings: [],
    exposures: [],
    coverage: [],
    assessment_status: 'available',
    assessment_policy_version: '2026-09-15.1',
    error_code: null,
    ...overrides,
  }
}

const coverageUnit: components['schemas']['CoverageUnitPayload'] = {
  ip: '192.168.1.42',
  stage: 'ports',
  port: null,
  outcome: 'timed_out',
  evidence_source: 'nmap_ports',
}

describe('scanDetailView', () => {
  it('picks one body per status', () => {
    expect(scanDetailView(scan({ status: 'cancelled' })).body).toBe('stopped')
    expect(scanDetailView(scan({ status: 'processing' })).body).toBe('progress')
    expect(scanDetailView(scan()).body).toBe('evidence')
    expect(scanDetailView(scan({ status: 'failed' })).body).toBe('none')
    expect(
      scanDetailView(scan({ status: 'failed', exposures: [relatedExposure] }))
        .body,
    ).toBe('evidence')
  })

  it('shows empty states on a completed scan', () => {
    expect(scanDetailView(scan()).sections).toEqual({
      aiAnalysis: true,
      noFindings: true,
      attackSurface: true,
      targeted: false,
      coverage: true,
      industrial: false,
      machines: true,
    })
  })

  it('shows only sections with data on a failed scan', () => {
    const view = scanDetailView(
      scan({
        status: 'failed',
        findings: [criticalFinding],
        coverage: [coverageUnit],
      }),
    )
    expect(view.failed).toBe(true)
    expect(view.sections).toEqual({
      aiAnalysis: false,
      noFindings: false,
      attackSurface: false,
      targeted: false,
      coverage: true,
      industrial: false,
      machines: false,
    })
  })

  it('reads partial evidence and an operator stop', () => {
    const view = scanDetailView(
      scan({
        terminated_by: 'user_cancel',
        metadata: { partial_result: true },
      }),
    )
    expect(view.partial).toBe(true)
    expect(view.stoppedEarly).toBe(true)
  })

  it('opens the targeted section when targeted units were planned', () => {
    expect(
      scanDetailView(scan({ metadata: { targeted_units_planned: 0 } })).sections
        .targeted,
    ).toBe(true)
  })
})
