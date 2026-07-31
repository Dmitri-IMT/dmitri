import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import { STALE_COVERAGE_DAYS, deriveReview } from './review'

type ScanSummary = components['schemas']['ScanSummary']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']

const NOW = new Date('2026-07-29T12:00:00Z')

function makeScan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    scan_id: '9c858c1c-1f7e-4c4e-9b1f-3a6f5b6f9a11',
    timestamp: '2026-07-29T09:00:00Z',
    subnet: '10.0.4.0/24',
    scan_mode: 'standard',
    status: 'completed',
    host_count: 12,
    finding_count: 0,
    highest_severity: null,
    ...overrides,
  }
}

function makeFinding(overrides: Partial<FindingRecord> = {}): FindingRecord {
  return {
    finding_id: '3f6a9e10-9b2b-4b3a-9a3f-1c2d3e4f5a6b',
    scan_id: '9c858c1c-1f7e-4c4e-9b1f-3a6f5b6f9a11',
    host_id: null,
    host_ip: '10.0.4.22',
    port: 443,
    protocol: 'tcp',
    service: 'https',
    source: 'nmap',
    source_script: 'vuln',
    cve_id: 'CVE-2024-3400',
    cvss_score: 9.8,
    severity: 'critical',
    title: 'PAN-OS command injection',
    description: 'Unauthenticated command injection in GlobalProtect gateway.',
    recommendation: 'Apply the vendor patch and rotate device certificates.',
    evidence: 'Vulnerable build string 11.1.2-h3 observed in banner.',
    references: [],
    detected_at: '2026-07-29T08:00:00Z',
    ...overrides,
  }
}

function makeEnvelope(
  data: FindingRecord[],
  overrides: Partial<FindingListResponse> = {},
): FindingListResponse {
  return { data, total: data.length, page: 1, ...overrides }
}

describe('deriveReview', () => {
  it('reports reviewCount from total, not from the number of rows returned (AC 17)', () => {
    const rows = Array.from({ length: 20 }, (_, i) =>
      makeFinding({
        finding_id: `3f6a9e10-9b2b-4b3a-9a3f-1c2d3e4f5a${i.toString(16).padStart(2, '0')}`,
        detected_at: '2026-07-29T08:00:00Z',
      }),
    )
    const result = deriveReview({
      latestScan: makeScan(),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope(rows, { total: 37 }),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.reviewCount).toBe(37)
  })

  it('is all-clear when there are no findings, no failed scan and coverage is fresh (AC 9)', () => {
    const result = deriveReview({
      latestScan: makeScan(),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.reviewCount).toBe(0)
    expect(result.deckFindings).toEqual([])
    expect(result.scanItem).toBeNull()
    expect(result.coverageItem).toBeNull()
  })

  it('is items-pending when critical and high findings exist (AC 10)', () => {
    const critical = makeFinding({ severity: 'critical' })
    const high = makeFinding({
      finding_id: '5a6b9e10-9b2b-4b3a-9a3f-1c2d3e4f5a6c',
      severity: 'high',
      cve_id: 'CVE-2023-44487',
    })
    const result = deriveReview({
      latestScan: makeScan(),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([critical]),
      highFindings: makeEnvelope([high]),
      now: NOW,
    })

    expect(result.reviewCount).toBe(2)
    expect(result.deckFindings).toEqual([critical, high])
  })

  it('treats medium/low-only findings as all-clear with no deck item (AC 11)', () => {
    const result = deriveReview({
      latestScan: makeScan(),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([], { total: 0 }),
      highFindings: makeEnvelope([], { total: 0 }),
      now: NOW,
    })

    expect(result.reviewCount).toBe(0)
    expect(result.deckFindings).toEqual([])
  })

  it('produces a scanItem when the latest scan failed (AC 12)', () => {
    const failedScan = makeScan({ status: 'failed' })
    const result = deriveReview({
      latestScan: failedScan,
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.scanItem).toEqual({ scan: failedScan })
    expect(result.reviewCount).toBe(1)
  })

  it('does not produce a scanItem when the latest scan completed', () => {
    const result = deriveReview({
      latestScan: makeScan({ status: 'completed' }),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.scanItem).toBeNull()
  })

  it('does not flag coverage as stale exactly at the boundary of STALE_COVERAGE_DAYS (AC 13)', () => {
    const boundaryScan = makeScan({
      timestamp: new Date(
        NOW.getTime() - STALE_COVERAGE_DAYS * 24 * 60 * 60 * 1000 + 1000,
      ).toISOString(),
    })
    const result = deriveReview({
      latestScan: boundaryScan,
      latestSuccessfulScan: boundaryScan,
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.coverageItem).toBeNull()
    expect(result.reviewCount).toBe(0)
  })

  it('flags coverage as stale once STALE_COVERAGE_DAYS have elapsed (AC 13)', () => {
    const staleScan = makeScan({
      timestamp: new Date(
        NOW.getTime() - STALE_COVERAGE_DAYS * 24 * 60 * 60 * 1000,
      ).toISOString(),
    })
    const result = deriveReview({
      latestScan: staleScan,
      latestSuccessfulScan: staleScan,
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.coverageItem).toEqual({
      latestSuccessfulScan: staleScan,
      daysSinceLastSuccess: STALE_COVERAGE_DAYS,
    })
    expect(result.reviewCount).toBe(1)
  })

  it('reports stale coverage even when the latest scan itself failed recently (AC 13)', () => {
    const staleSuccessfulScan = makeScan({
      scan_id: '1a2b3c4d-5e6f-4a1b-8c9d-0e1f2a3b4c5d',
      timestamp: new Date(
        NOW.getTime() - (STALE_COVERAGE_DAYS + 5) * 24 * 60 * 60 * 1000,
      ).toISOString(),
    })
    const recentFailedScan = makeScan({
      scan_id: '6f5e4d3c-2b1a-4f6e-9d8c-7b6a5f4e3d2c',
      timestamp: '2026-07-29T11:00:00Z',
      status: 'failed',
    })
    const result = deriveReview({
      latestScan: recentFailedScan,
      latestSuccessfulScan: staleSuccessfulScan,
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.scanItem).toEqual({ scan: recentFailedScan })
    expect(result.coverageItem).not.toBeNull()
    expect(result.coverageItem?.latestSuccessfulScan).toEqual(
      staleSuccessfulScan,
    )
    expect(result.reviewCount).toBe(2)
  })

  it('omits coverageItem rather than computing "stale since never" when there is no successful scan', () => {
    const result = deriveReview({
      latestScan: makeScan({ status: 'failed' }),
      latestSuccessfulScan: null,
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.coverageItem).toBeNull()
    expect(result.reviewCount).toBe(1)
  })

  it('does not double-count when the same completed scan is both the latest and the latest successful scan', () => {
    const sharedScan = makeScan({ status: 'completed' })
    const result = deriveReview({
      latestScan: sharedScan,
      latestSuccessfulScan: sharedScan,
      criticalFindings: makeEnvelope([]),
      highFindings: makeEnvelope([]),
      now: NOW,
    })

    expect(result.scanItem).toBeNull()
    expect(result.coverageItem).toBeNull()
    expect(result.reviewCount).toBe(0)
  })

  it('orders deckFindings critical before high, newest first within each severity, from a shuffled input', () => {
    const criticalOld = makeFinding({
      finding_id: '11111111-1111-4111-8111-111111111111',
      cve_id: 'CVE-2021-44228',
      detected_at: '2026-07-20T08:00:00Z',
    })
    const criticalNew = makeFinding({
      finding_id: '22222222-2222-4222-8222-222222222222',
      cve_id: 'CVE-2024-3400',
      detected_at: '2026-07-28T08:00:00Z',
    })
    const highOld = makeFinding({
      finding_id: '33333333-3333-4333-8333-333333333333',
      severity: 'high',
      cve_id: 'CVE-2023-44487',
      detected_at: '2026-07-18T08:00:00Z',
    })
    const highNew = makeFinding({
      finding_id: '44444444-4444-4444-8444-444444444444',
      severity: 'high',
      cve_id: 'CVE-2022-40684',
      detected_at: '2026-07-27T08:00:00Z',
    })

    const result = deriveReview({
      latestScan: makeScan(),
      latestSuccessfulScan: makeScan(),
      criticalFindings: makeEnvelope([criticalOld, criticalNew]),
      highFindings: makeEnvelope([highNew, highOld]),
      now: NOW,
    })

    expect(result.deckFindings).toEqual([
      criticalNew,
      criticalOld,
      highNew,
      highOld,
    ])
  })
})
