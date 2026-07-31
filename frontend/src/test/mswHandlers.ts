import { http, HttpResponse } from 'msw'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']

const baseURL = 'http://localhost:8000/api/v1'

export const validLoginResponse = {
  access_token: 'test-access-token',
  token_type: 'bearer',
  expires_in: 3600,
}

export const adminProfile: UserProfileResponse = {
  user_id: '11111111-1111-4111-8111-111111111111',
  email: 'admin@dmitri.dev',
  role: 'admin',
}

export const viewerProfile: UserProfileResponse = {
  user_id: '22222222-2222-4222-8222-222222222222',
  email: 'viewer@dmitri.dev',
  role: 'viewer',
}

export const latestScan: ScanSummary = {
  scan_id: '33333333-3333-4333-8333-333333333333',
  timestamp: '2026-07-28T10:00:00Z',
  subnet: '192.168.1.0/24',
  scan_mode: 'standard',
  status: 'processing',
  host_count: 12,
  finding_count: 2,
  highest_severity: 'critical',
}

export const latestSuccessfulScan: ScanSummary = {
  scan_id: '88888888-8888-4888-8888-888888888888',
  timestamp: '2026-07-28T09:00:00Z',
  subnet: '192.168.1.0/24',
  scan_mode: 'standard',
  status: 'completed',
  host_count: 12,
  finding_count: 2,
  highest_severity: 'critical',
}

export const criticalFinding: FindingRecord = {
  finding_id: '44444444-4444-4444-8444-444444444444',
  scan_id: latestScan.scan_id,
  host_id: '55555555-5555-4555-8555-555555555555',
  host_ip: '192.168.1.42',
  port: 22,
  protocol: 'tcp',
  service: 'ssh',
  source: 'nmap',
  source_script: 'ssh2-enum-algos',
  cve_id: 'CVE-2023-38408',
  cvss_score: 9.8,
  severity: 'critical',
  title: 'OpenSSH remote code execution',
  description: 'Vulnerable OpenSSH version allows remote code execution.',
  recommendation: 'Upgrade OpenSSH to the latest patched release.',
  evidence: 'SSH-2.0-OpenSSH_8.2',
  references: ['https://nvd.nist.gov/vuln/detail/CVE-2023-38408'],
  detected_at: '2026-07-28T09:05:00Z',
}

export const highFinding: FindingRecord = {
  finding_id: '66666666-6666-4666-8666-666666666666',
  scan_id: latestScan.scan_id,
  host_id: '55555555-5555-4555-8555-555555555555',
  host_ip: '192.168.1.42',
  port: 80,
  protocol: 'tcp',
  service: 'http',
  source: 'nmap',
  source_script: 'http-vuln-cve2017-5638',
  cve_id: 'CVE-2017-5638',
  cvss_score: 8.1,
  severity: 'high',
  title: 'Apache Struts remote code execution',
  description: 'Vulnerable Struts version allows remote code execution.',
  recommendation: 'Upgrade Apache Struts to the latest patched release.',
  evidence: 'Server: Apache-Coyote/1.1',
  references: ['https://nvd.nist.gov/vuln/detail/CVE-2017-5638'],
  detected_at: '2026-07-28T09:06:00Z',
}

function scanListResponse(data: ScanSummary[]): ScanListResponse {
  return { data, total: data.length, page: 1 }
}

function findingListResponse(data: FindingRecord[]): FindingListResponse {
  return { data, total: data.length, page: 1 }
}

export const handlers = [
  http.post(`${baseURL}/auth/login`, () =>
    HttpResponse.json(validLoginResponse),
  ),
  http.post(`${baseURL}/auth/refresh`, () =>
    HttpResponse.json(validLoginResponse),
  ),
  http.post(
    `${baseURL}/auth/logout`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.get(`${baseURL}/hosts`, () => HttpResponse.json([])),
  http.get(`${baseURL}/users/me`, () => HttpResponse.json(adminProfile)),
  http.get(`${baseURL}/scans`, ({ request }) => {
    const status = new URL(request.url).searchParams.get('status')
    if (status === 'completed') {
      return HttpResponse.json(scanListResponse([latestSuccessfulScan]))
    }
    return HttpResponse.json(scanListResponse([latestScan]))
  }),
  http.get(`${baseURL}/findings`, ({ request }) => {
    const severity = new URL(request.url).searchParams.get('severity')
    if (severity === 'critical') {
      return HttpResponse.json(findingListResponse([criticalFinding]))
    }
    if (severity === 'high') {
      return HttpResponse.json(findingListResponse([highFinding]))
    }
    return HttpResponse.json(findingListResponse([]))
  }),
]
