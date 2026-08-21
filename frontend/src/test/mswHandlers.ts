import { http, HttpResponse } from 'msw'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type ScanSummary = components['schemas']['ScanSummary']
type ScanListResponse = components['schemas']['ScanListResponse']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']
type InviteLookupResponse = components['schemas']['InviteLookupResponse']
type OrgMember = components['schemas']['OrgMember']
type PendingInvite = components['schemas']['PendingInvite']
type UpdateUserRoleRequest = components['schemas']['UpdateUserRoleRequest']
type InviteCreatedResponse = components['schemas']['InviteCreatedResponse']

const baseURL = 'http://localhost:8000/api/v1'

const NOW_MS = Date.now()
function minutesAgo(minutes: number): string {
  return new Date(NOW_MS - minutes * 60 * 1000).toISOString()
}

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

export const liveInvite: InviteLookupResponse = {
  email: 'ana@northwind.example',
  role: 'viewer',
  org_name: 'Northwind Security',
}

export const selfMember: OrgMember = {
  user_id: adminProfile.user_id,
  email: adminProfile.email,
  role: 'admin',
  last_seen_at: minutesAgo(3),
}

export const otherMember: OrgMember = {
  user_id: viewerProfile.user_id,
  email: viewerProfile.email,
  role: 'viewer',
  last_seen_at: null,
}

export const recentMember: OrgMember = {
  user_id: '99999999-9999-4999-8999-999999999999',
  email: 'sam@northwind.example',
  role: 'viewer',
  last_seen_at: minutesAgo(12),
}

export const pendingInvite: PendingInvite = {
  invite_id: '77777777-7777-4777-8777-777777777777',
  email: 'ana@northwind.example',
  role: 'viewer',
  expires_at: new Date(NOW_MS + 3 * 24 * 60 * 60 * 1000).toISOString(),
}

export const createdInvite: InviteCreatedResponse = {
  invite_token: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6', // pragma: allowlist secret
  expires_at: new Date(NOW_MS + 48 * 60 * 60 * 1000).toISOString(),
}

export const latestScan: ScanSummary = {
  scan_id: '33333333-3333-4333-8333-333333333333',
  timestamp: minutesAgo(5),
  subnet: '192.168.1.0/24',
  scan_mode: 'standard',
  status: 'processing',
  host_count: 12,
  finding_count: 2,
  highest_severity: 'critical',
}

export const latestSuccessfulScan: ScanSummary = {
  scan_id: '88888888-8888-4888-8888-888888888888',
  timestamp: minutesAgo(65),
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
  detected_at: minutesAgo(60),
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
  detected_at: minutesAgo(59),
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
  http.post(
    `${baseURL}/auth/forgot-password`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.post(
    `${baseURL}/auth/reset-password`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.post(
    `${baseURL}/auth/change-password`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.post(`${baseURL}/invites/lookup`, () => HttpResponse.json(liveInvite)),
  http.post(`${baseURL}/invites/accept`, () =>
    HttpResponse.json(validLoginResponse, { status: 201 }),
  ),
  http.get(`${baseURL}/users`, () =>
    HttpResponse.json({ data: [selfMember, otherMember] }),
  ),
  http.post(`${baseURL}/invites`, () =>
    HttpResponse.json(createdInvite, { status: 201 }),
  ),
  http.get(`${baseURL}/invites`, () =>
    HttpResponse.json({ data: [pendingInvite] }),
  ),
  http.delete(
    `${baseURL}/invites/:inviteId`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.get(`${baseURL}/hosts`, () => HttpResponse.json([])),
  http.get(`${baseURL}/users/me`, () => HttpResponse.json(adminProfile)),
  http.patch(`${baseURL}/users/:userId`, async ({ params, request }) => {
    const body = (await request.json()) as UpdateUserRoleRequest
    return HttpResponse.json({
      ...recentMember,
      user_id: String(params.userId),
      role: body.role,
    })
  }),
  // MSW resolves the first matching handler, and `:userId` also matches "me", so the
  // literal `/users/me` route has to stay above it or account deletion silently
  // resolves against the remove-a-member handler instead.
  http.delete(
    `${baseURL}/users/me`,
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.delete(
    `${baseURL}/users/:userId`,
    () => new HttpResponse(null, { status: 204 }),
  ),
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
