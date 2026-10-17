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
    finding_observations: [],
    finding_observations_truncated: false,
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

  it('treats standalone observations and truncation as failed-scan evidence', () => {
    const standalone = scanDetailView(
      scan({
        status: 'failed',
        finding_observations: [
          {
            condition_key: 'modbus:device-identification',
            method: 'specific_check',
            result: 'inconclusive',
            source: 'modbus-discover',
            source_script: null,
            rule_id: 'DEVICE_IDENTIFICATION',
            rule_version: '1',
            evidence: 'No response before disconnect',
          },
        ],
      }),
    )
    expect(standalone.body).toBe('evidence')
    expect(standalone.sections.coverage).toBe(true)

    const truncated = scanDetailView(
      scan({
        status: 'failed',
        finding_observations: [],
        finding_observations_truncated: true,
      }),
    )
    expect(truncated.body).toBe('evidence')
    expect(truncated.sections.coverage).toBe(true)
  })

  it('reads evidence completeness and an operator stop', () => {
    const view = scanDetailView(
      scan({ terminated_by: 'user_cancel', evidence_completeness: 'partial' }),
    )
    expect(view.completeness).toBe('partial')
    expect(view.stoppedEarly).toBe(true)
  })

  it('opens the targeted section when targeted units were planned', () => {
    expect(
      scanDetailView(scan({ metadata: { targeted_units_planned: 0 } })).sections
        .targeted,
    ).toBe(true)
  })
})
