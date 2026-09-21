import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']
type DeviceProfile = components['schemas']['DeviceProfilePayload']
type ExposureRead = components['schemas']['ExposureRead']

export const baseURL = 'http://localhost:8000/api/v1'

export const confidentHostProfile: DeviceProfile = {
  manufacturer: 'Samsung',
  product_family: 'Smart TV',
  model: null,
  confidence: 'high',
  evidence: [
    { kind: 'manufacturer', source: 'Observed vendor', value: 'Samsung' },
    { kind: 'service', source: '8001/tcp', value: 'http' },
  ],
  conflicts: [],
  limitations: ['No reliable model evidence.'],
}

export function hostExposure(
  host: HostDetailResponse,
  overrides: Partial<ExposureRead> = {},
): ExposureRead {
  return {
    exposure_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    scan_id:
      host.scan_history[0]?.scan_id ?? '88888888-8888-4888-8888-888888888888',
    host_id: host.host_id,
    ip: host.ip,
    port: 8001,
    protocol: 'tcp',
    observed_service: 'http',
    observed_version: null,
    role: 'device_control',
    attention: 'review',
    confidence: 'high',
    reason: 'A device-control service is reachable.',
    evidence: [{ kind: 'service', source: '8001/tcp', value: 'http' }],
    related_finding_ids: [],
    detected_at: new Date().toISOString(),
    ...overrides,
  }
}

export function withHostAssessment(
  host: HostDetailResponse,
  overrides: Partial<HostDetailResponse> = {},
): HostDetailResponse {
  return {
    ...host,
    machine_type: 'tv',
    device_profile: confidentHostProfile,
    assessment_status: 'available',
    assessment_policy_version: '2026-09-15.1',
    exposures: [hostExposure(host)],
    ...overrides,
  }
}

export function hostsFail() {
  server.use(
    http.get(`${baseURL}/hosts`, () => new HttpResponse(null, { status: 500 })),
  )
}

export function hostDetail(
  host: HostDetailResponse,
  findings: FindingRecord[],
) {
  server.use(
    http.get(`${baseURL}/hosts/:hostId`, () => HttpResponse.json(host)),
    http.get(`${baseURL}/findings`, ({ request }) => {
      const params = new URL(request.url).searchParams
      const hostId = params.get('host_id')
      const data = findings.filter((finding) => finding.host_id === hostId)
      return HttpResponse.json({
        data,
        total: data.length,
        page: Number(params.get('page') ?? 1),
      } satisfies FindingListResponse)
    }),
  )
}

export function hostNotFound() {
  server.use(
    http.get(
      `${baseURL}/hosts/:hostId`,
      () => new HttpResponse(null, { status: 404 }),
    ),
  )
}
