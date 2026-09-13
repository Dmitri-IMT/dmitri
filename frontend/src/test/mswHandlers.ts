import { http, HttpResponse } from 'msw'
import type { components } from '@/types/openapi'

type UserProfileResponse = components['schemas']['UserProfileResponse']
type ScanSummary = components['schemas']['ScanSummary']
type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type ScanListResponse = components['schemas']['ScanListResponse']
type ScanMode = components['schemas']['ScanMode']
type ScanStatus = components['schemas']['ScanStatus']
type HostSummary = components['schemas']['HostSummary']
type MachineType = components['schemas']['MachineType']
type HostDetailResponse = components['schemas']['HostDetailResponse']
type HostListResponse = components['schemas']['HostListResponse']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']
type InviteLookupResponse = components['schemas']['InviteLookupResponse']
type OrgMember = components['schemas']['OrgMember']
type PendingInvite = components['schemas']['PendingInvite']
type UpdateUserRoleRequest = components['schemas']['UpdateUserRoleRequest']
type InviteCreatedResponse = components['schemas']['InviteCreatedResponse']
type AgentDetail = components['schemas']['AgentDetail']
type AgentSummary = components['schemas']['AgentSummary']
type CommandDetail = components['schemas']['CommandDetail']
type HomeSnapshot = components['schemas']['HomeSnapshot']

const baseURL = 'http://localhost:8000/api/v1'

const NOW_MS = Date.now()
function minutesAgo(minutes: number): string {
  return new Date(NOW_MS - minutes * 60 * 1000).toISOString()
}
function weeksAgo(weeks: number): string {
  return new Date(NOW_MS - weeks * 7 * 24 * 60 * 60 * 1000).toISOString()
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

export const defaultAgent: AgentDetail = {
  agent_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  display_name: 'DMITRI-NSPI-01',
  online: true,
  last_seen_at: minutesAgo(1),
  available_subnets: [
    { interface: 'eth0', cidr: '192.168.0.0/24', is_default_route: false },
    { interface: 'wlan0', cidr: '10.12.0.0/16', is_default_route: true },
  ],
  target_subnet: '192.168.0.0/24',
  active_command_id: null,
}
export const agentFixture = defaultAgent

const secondAgentDetail: AgentDetail = {
  agent_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  display_name: 'Reception spare',
  online: true,
  last_seen_at: minutesAgo(10),
  available_subnets: [
    { interface: 'eth0', cidr: '192.168.0.0/24', is_default_route: true },
  ],
  target_subnet: null,
  active_command_id: null,
}

const thirdAgentDetail: AgentDetail = {
  agent_id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  display_name: 'Old office',
  online: false,
  last_seen_at: weeksAgo(4),
  available_subnets: [
    { interface: 'eth0', cidr: '172.16.0.0/24', is_default_route: true },
  ],
  target_subnet: '172.16.0.0/24',
  active_command_id: null,
}

export const agentSummaries: AgentSummary[] = [
  {
    agent_id: defaultAgent.agent_id,
    display_name: defaultAgent.display_name,
    online: defaultAgent.online,
    last_seen_at: defaultAgent.last_seen_at,
    target_subnet: defaultAgent.target_subnet,
    active_command_id: defaultAgent.active_command_id,
  },
  {
    agent_id: secondAgentDetail.agent_id,
    display_name: secondAgentDetail.display_name,
    online: secondAgentDetail.online,
    last_seen_at: secondAgentDetail.last_seen_at,
    target_subnet: secondAgentDetail.target_subnet,
    active_command_id: secondAgentDetail.active_command_id,
  },
  {
    agent_id: thirdAgentDetail.agent_id,
    display_name: thirdAgentDetail.display_name,
    online: thirdAgentDetail.online,
    last_seen_at: thirdAgentDetail.last_seen_at,
    target_subnet: thirdAgentDetail.target_subnet,
    active_command_id: thirdAgentDetail.active_command_id,
  },
]

export const agentDetails: Record<string, AgentDetail> = {
  [defaultAgent.agent_id]: defaultAgent,
  [secondAgentDetail.agent_id]: secondAgentDetail,
  [thirdAgentDetail.agent_id]: thirdAgentDetail,
}

function agentById(agentId: string): AgentDetail | undefined {
  return agentDetails[agentId]
}

export const defaultCommand: CommandDetail = {
  command_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  scan_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  agent_id: defaultAgent.agent_id,
  scan_mode: 'quick',
  subnet: '192.168.0.0/24',
  status: 'queued',
  error_code: null,
  created_at: minutesAgo(1),
  delivered_at: null,
  started_at: null,
  completed_at: null,
}
export const commandFixture = defaultCommand

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
  agent_id: defaultAgent.agent_id,
  box_name: defaultAgent.display_name,
  duration: null,
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
  agent_id: defaultAgent.agent_id,
  box_name: defaultAgent.display_name,
  duration: 500,
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
  host_hostname: 'host-01',
  first_seen_at: weeksAgo(3),
  last_seen_at: minutesAgo(60),
  fixed_at: null,
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
  host_hostname: 'host-01',
  first_seen_at: weeksAgo(2),
  last_seen_at: minutesAgo(59),
  fixed_at: null,
}

const scanModes = [
  'quick',
  'standard',
  'extensive',
  'nspi',
  'max',
] as const satisfies readonly ScanMode[]

const scanStatuses = [
  'completed',
  'failed',
  'completed',
  'accepted',
  'completed',
] as const satisfies readonly ScanStatus[]

function fixtureId(index: number): string {
  return `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`
}

export const scanFixtures: ScanSummary[] = [
  latestScan,
  latestSuccessfulScan,
  ...Array.from({ length: 23 }, (_, index): ScanSummary => {
    const status = scanStatuses[index % scanStatuses.length]
    const finished = status === 'completed'
    return {
      scan_id: fixtureId(100 + index),
      timestamp: minutesAgo(120 + index * 30),
      subnet: `10.${index}.0.0/24`,
      scan_mode: scanModes[index % scanModes.length],
      status,
      host_count: finished ? 5 + index : 0,
      finding_count: finished ? index % 4 : 0,
      highest_severity:
        finished && index % 4 > 0 ? (index % 2 === 0 ? 'high' : 'low') : null,
      agent_id: defaultAgent.agent_id,
      box_name: defaultAgent.display_name,
      duration: finished ? 45 : null,
    }
  }),
]

const machineTypes = [
  'computer',
  'router',
  'camera',
  'printer',
  'unknown',
] as const satisfies readonly MachineType[]

export const hostFixtures: HostSummary[] = Array.from(
  { length: 25 },
  (_, index): HostSummary => ({
    host_id:
      index === 0
        ? '55555555-5555-4555-8555-555555555555'
        : fixtureId(200 + index),
    ip: `192.168.1.${10 + index}`,
    mac:
      index === 24 ? null : `02:00:00:00:${String(index).padStart(2, '0')}:01`,
    hostname: index === 24 ? '' : `host-${String(index + 1).padStart(2, '0')}`,
    vendor: `Vendor ${String.fromCharCode(65 + index)}`,
    first_seen_at: minutesAgo(10_000 + index * 60),
    last_seen_at: minutesAgo(10 + index * 10),
    open_ports_count: index % 5,
    machine_type: machineTypes[index % machineTypes.length],
    vulnerability_count: index % 4 === 3 ? 0 : (index % 7) + 1,
    unreadable_fields: [],
    highest_severity:
      index % 4 === 0
        ? 'critical'
        : index % 4 === 1
          ? 'high'
          : index % 4 === 2
            ? 'medium'
            : null,
  }),
)

const otherHostFinding: FindingRecord = {
  ...highFinding,
  finding_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  host_id: hostFixtures[1].host_id,
  host_ip: hostFixtures[1].ip,
  host_hostname: null,
  first_seen_at: weeksAgo(1),
  last_seen_at: minutesAgo(59),
  fixed_at: null,
  severity: 'medium',
  title: 'TLS certificate expired',
  cve_id: null,
  cvss_score: 5.3,
}

export const findingFixtures: FindingRecord[] = [
  criticalFinding,
  highFinding,
  otherHostFinding,
]

export const hostDetailFixtures: HostDetailResponse[] = hostFixtures.map(
  (host, index) => ({
    ...host,
    ports:
      index % 5 === 0
        ? []
        : [
            {
              port: index % 2 === 0 ? 443 : 22,
              protocol: 'tcp',
              service: index % 2 === 0 ? 'https' : 'ssh',
              version: index % 2 === 0 ? 'nginx 1.24' : 'OpenSSH 9.6',
              first_seen_at: minutesAgo(10_000 + index * 60),
              last_seen_at: minutesAgo(10 + index * 10),
            },
          ],
    scan_history: [
      {
        scan_id: latestSuccessfulScan.scan_id,
        timestamp: latestSuccessfulScan.timestamp,
        scan_mode: latestSuccessfulScan.scan_mode,
        open_ports_count: host.open_ports_count,
        highest_severity: host.highest_severity,
      },
    ],
    industrial_services: [],
  }),
)

export const scanDetailFixtures: ScanDetailResponse[] = scanFixtures.map(
  (scan) => ({
    ...scan,
    hosts: hostDetailFixtures.slice(0, 2).map((host) => ({
      host_id: host.host_id,
      ip: host.ip,
      mac: host.mac,
      hostname: host.hostname,
      vendor: host.vendor,
      ports: host.ports.map((port) => ({
        port: port.port,
        protocol: port.protocol,
        state: 'open' as const,
        service: port.service,
        version: port.version,
      })),
      industrial_services: host.industrial_services,
      unreadable_fields: host.unreadable_fields,
    })),
    findings: findingFixtures.filter(
      (finding) => finding.scan_id === scan.scan_id,
    ),
    error_code: scan.status === 'failed' ? 'device_offline' : null,
  }),
)

export function homeSnapshot(
  overrides: Partial<HomeSnapshot> = {},
  attentionPage = 1,
): HomeSnapshot {
  return {
    review_state: 'pending',
    review_count: 2,
    latest_successful_scan: latestSuccessfulScan,
    notices: [],
    attention: {
      data: [criticalFinding, highFinding],
      total: 2,
      page: attentionPage,
    },
    events: { data: [], total: 0, page: 1 },
    activity: { data: [], total: 0, page: 1 },
    ...overrides,
  }
}

export function paginate<T>(rows: T[], url: string) {
  const params = new URL(url).searchParams
  const page = Number(params.get('page') ?? 1)
  const perPage = Number(params.get('per_page') ?? 20)
  const start = (page - 1) * perPage
  return { data: rows.slice(start, start + perPage), total: rows.length, page }
}

const hostSortKeys = [
  'last_seen_at',
  'hostname',
  'vendor',
  'ip',
  'vulnerability_count',
] as const satisfies readonly components['parameters']['HostSortBy'][]

const QUIET_AFTER_MS = 7 * 24 * 60 * 60 * 1000

function isQuietFixture(host: HostSummary): boolean {
  return NOW_MS - new Date(host.last_seen_at).getTime() > QUIET_AFTER_MS
}

function compareHosts(
  left: HostSummary,
  right: HostSummary,
  sortBy: components['parameters']['HostSortBy'],
): number {
  return String(left[sortBy]).localeCompare(String(right[sortBy]), undefined, {
    numeric: true,
  })
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
  http.get(`${baseURL}/hosts`, ({ request }) => {
    const params = new URL(request.url).searchParams
    const requestedSort = params.get('sort_by')
    const sortBy = hostSortKeys.find((key) => key === requestedSort)
    if (requestedSort !== null && sortBy === undefined) {
      return new HttpResponse(null, { status: 422 })
    }
    const sortOrder = params.get('sort_order') === 'asc' ? 'asc' : 'desc'
    const quiet = params.get('group') === 'quiet'
    const grouped = hostFixtures.filter(
      (host) => isQuietFixture(host) === quiet,
    )
    const sorted = grouped.sort((left, right) => {
      const comparison = compareHosts(left, right, sortBy ?? 'last_seen_at')
      return sortOrder === 'asc' ? comparison : -comparison
    })
    return HttpResponse.json({
      ...paginate(sorted, request.url),
      quiet_total: hostFixtures.filter(isQuietFixture).length,
    } satisfies HostListResponse)
  }),
  http.get(`${baseURL}/users/me`, () => HttpResponse.json(adminProfile)),
  http.get(`${baseURL}/agents`, () =>
    HttpResponse.json({ data: agentSummaries }),
  ),
  http.get(`${baseURL}/agents/:agentId`, ({ params }) => {
    const agent = agentById(params.agentId as string)
    if (!agent) return new HttpResponse(null, { status: 404 })
    return HttpResponse.json(agent)
  }),
  http.patch(`${baseURL}/agents/:agentId`, async ({ request, params }) => {
    const agent = agentById(params.agentId as string)
    if (!agent) return new HttpResponse(null, { status: 404 })
    const body =
      (await request.json()) as components['schemas']['UpdateAgentTargetSubnetRequest']
    return HttpResponse.json({
      ...agent,
      target_subnet: body.target_subnet,
    })
  }),
  http.post(`${baseURL}/agents/:agentId/commands`, () =>
    HttpResponse.json(
      {
        command_id: defaultCommand.command_id,
        scan_id: defaultCommand.scan_id,
        agent_id: defaultAgent.agent_id,
        status: 'queued' as const,
      },
      { status: 202 },
    ),
  ),
  http.get(`${baseURL}/commands/:commandId`, () =>
    HttpResponse.json(defaultCommand),
  ),
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
    const params = new URL(request.url).searchParams
    const status = params.get('status')
    const agentId = params.get('agent_id')
    const rows = scanFixtures.filter((scan) => {
      if (status && scan.status !== status) return false
      if (agentId && scan.agent_id !== agentId) return false
      return true
    })
    return HttpResponse.json(
      paginate(rows, request.url) satisfies ScanListResponse,
    )
  }),
  http.get(`${baseURL}/scans/:scanId`, ({ params }) => {
    const scan = scanDetailFixtures.find(
      (fixture) => fixture.scan_id === params.scanId,
    )
    return scan
      ? HttpResponse.json(scan)
      : new HttpResponse(null, { status: 404 })
  }),
  http.get(`${baseURL}/scans/:scanId/analysis`, ({ params }) =>
    HttpResponse.json({
      scan_id: params.scanId as string,
      analysis_id: null,
      status: 'unavailable',
      analysis: null,
      provider: null,
      model: null,
      context_version: null,
      prompt_version: null,
      created_at: null,
      updated_at: null,
      completed_at: null,
    } satisfies components['schemas']['ScanAIAnalysisResponse']),
  ),
  http.post(`${baseURL}/scans/:scanId/analysis`, ({ params }) =>
    HttpResponse.json(
      {
        scan_id: params.scanId as string,
        analysis_id: null,
        status: 'pending',
        analysis: null,
        provider: null,
        model: null,
        context_version: null,
        prompt_version: null,
        created_at: null,
        updated_at: null,
        completed_at: null,
      } satisfies components['schemas']['ScanAIAnalysisResponse'],
      { status: 202 },
    ),
  ),
  http.get(`${baseURL}/hosts/:hostId`, ({ params }) => {
    const host = hostDetailFixtures.find(
      (fixture) => fixture.host_id === params.hostId,
    )
    return host
      ? HttpResponse.json(host)
      : new HttpResponse(null, { status: 404 })
  }),
  http.get(`${baseURL}/findings`, ({ request }) => {
    const params = new URL(request.url).searchParams
    const severity = params.get('severity')
    const hostId = params.get('host_id')
    const scanId = params.get('scan_id')
    const rows = findingFixtures.filter(
      (finding) =>
        (severity === null || finding.severity === severity) &&
        (hostId === null || finding.host_id === hostId) &&
        (scanId === null || finding.scan_id === scanId),
    )
    return HttpResponse.json(
      paginate(rows, request.url) satisfies FindingListResponse,
    )
  }),
  http.get(`${baseURL}/home`, ({ request }) => {
    const url = new URL(request.url)
    const attentionPage = Number(url.searchParams.get('attention_page') ?? '1')
    const eventsPage = Number(url.searchParams.get('events_page') ?? '1')
    const activityPage = Number(url.searchParams.get('activity_page') ?? '1')
    const snapshot = homeSnapshot({}, attentionPage)
    return HttpResponse.json({
      ...snapshot,
      events: { ...snapshot.events, page: eventsPage },
      activity: { ...snapshot.activity, page: activityPage },
    })
  }),
]
