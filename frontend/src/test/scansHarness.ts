import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type ExposureRead = components['schemas']['ExposureRead']

export const baseURL = 'http://localhost:8000/api/v1'

export const relatedExposure: ExposureRead = {
  exposure_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  scan_id: '88888888-8888-4888-8888-888888888888',
  host_id: '55555555-5555-4555-8555-555555555555',
  ip: '192.168.0.42',
  port: 443,
  protocol: 'tcp',
  observed_service: 'https',
  observed_version: 'nginx 1.24',
  role: 'administration',
  attention: 'review',
  confidence: 'high',
  reason: 'An administrative service is reachable.',
  evidence: [
    { kind: 'service', source: 'Nmap service', value: 'https' },
    { kind: 'version', source: 'Nmap version', value: 'nginx 1.24' },
  ],
  related_finding_ids: ['bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'],
  detected_at: '2026-09-15T10:21:00Z',
}

export const awarenessExposure: ExposureRead = {
  ...relatedExposure,
  exposure_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  port: 5353,
  observed_service: 'mdns',
  observed_version: null,
  role: 'discovery',
  attention: 'informational',
  confidence: 'medium',
  reason: 'A discovery service is reachable.',
  evidence: [{ kind: 'port', source: 'Nmap port', value: '5353/udp' }],
  related_finding_ids: [],
}

export function withAssessment(
  scan: ScanDetailResponse,
  exposures: ExposureRead[] = [],
): ScanDetailResponse {
  return {
    ...scan,
    assessment_status: 'available',
    assessment_policy_version: '2026-09-15.1',
    exposures,
  }
}

export function withoutAssessment(
  scan: ScanDetailResponse,
): ScanDetailResponse {
  return {
    ...scan,
    assessment_status: 'unavailable',
    assessment_policy_version: null,
    exposures: [],
  }
}

export function withPartialResult(
  scan: ScanDetailResponse,
  terminatedBy: components['schemas']['TerminatedBy'],
  interruptedStage?: string,
): ScanDetailResponse {
  return {
    ...scan,
    terminated_by: terminatedBy,
    evidence_completeness: 'partial',
    metadata: {
      ...(scan.metadata ?? {}),
      partial_result: true,
      terminated_by: terminatedBy,
      ...(interruptedStage ? { interrupted_stage: interruptedStage } : {}),
    },
  }
}

export function scansFail() {
  server.use(
    http.get(`${baseURL}/scans`, () => new HttpResponse(null, { status: 500 })),
  )
}

export function scanDetail(scan: ScanDetailResponse) {
  server.use(
    http.get(`${baseURL}/scans/:scanId`, () => HttpResponse.json(scan)),
  )
}

export function scanNotFound() {
  server.use(
    http.get(
      `${baseURL}/scans/:scanId`,
      () => new HttpResponse(null, { status: 404 }),
    ),
  )
}

export function scanDetailFails() {
  server.use(
    http.get(
      `${baseURL}/scans/:scanId`,
      () => new HttpResponse(null, { status: 500 }),
    ),
  )
}
