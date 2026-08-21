import type { components } from '@/types/openapi'

type OrgMember = components['schemas']['OrgMember']
type PendingInvite = components['schemas']['PendingInvite']
export type Role = components['schemas']['OrgMember']['role']

export const NOT_RECORDED = 'Not recorded yet'
export const NO_LAST_SEEN = '—'

// Shared by the toast copy on the Users page and the heading of the confirm dialog, so
// the two always name the same role the same way.
export const ROLE_NOUN = { admin: 'an admin', viewer: 'a viewer' } as const

export type DirectoryRow =
  | {
      kind: 'member'
      id: string
      email: string
      role: Role
      lastSeenAt: string | null
      isSelf: boolean
    }
  | { kind: 'invite'; id: string; email: string; role: Role; expiresAt: string }

export type LastSeenCell =
  { kind: 'time'; value: string } | { kind: 'text'; value: string }

// Admins are pinned above viewers whatever the server sent, then each group runs
// most-recently-seen first with never-signed-in last. Email breaks ties so the order is
// total: two members with the same role and the same last-seen must not swap between
// renders. Sorts a copy — the caller's array is the query cache's own data.
const ROLE_RANK = { admin: 0, viewer: 1 } as const

function lastSeenMs(member: OrgMember): number {
  return member.last_seen_at === null
    ? Number.NEGATIVE_INFINITY
    : new Date(member.last_seen_at).getTime()
}

function byRoleThenLastSeen(a: OrgMember, b: OrgMember): number {
  const rank = ROLE_RANK[a.role] - ROLE_RANK[b.role]
  if (rank !== 0) {
    return rank
  }
  const seen = lastSeenMs(b) - lastSeenMs(a)
  if (seen !== 0 && !Number.isNaN(seen)) {
    return seen
  }
  return a.email.localeCompare(b.email)
}

export function mergeDirectory(
  members: OrgMember[],
  invites: PendingInvite[],
  selfUserId: string,
): DirectoryRow[] {
  return [
    ...[...members].sort(byRoleThenLastSeen).map((member): DirectoryRow => ({
      kind: 'member',
      id: member.user_id,
      email: member.email,
      role: member.role,
      lastSeenAt: member.last_seen_at,
      isSelf: member.user_id === selfUserId,
    })),
    ...invites.map((invite): DirectoryRow => ({
      kind: 'invite',
      id: invite.invite_id,
      email: invite.email,
      role: invite.role,
      expiresAt: invite.expires_at,
    })),
  ]
}

export function statusLabel(row: DirectoryRow, now: Date = new Date()): string {
  if (row.kind === 'member') return 'Active'
  const days = Math.max(
    1,
    Math.ceil(
      (new Date(row.expiresAt).getTime() - now.getTime()) /
        (1000 * 60 * 60 * 24),
    ),
  )
  return `Invited — expires in ${days} ${days === 1 ? 'day' : 'days'}`
}

export function lastSeenCell(row: DirectoryRow): LastSeenCell {
  if (row.kind === 'invite') return { kind: 'text', value: NO_LAST_SEEN }
  if (row.lastSeenAt === null) return { kind: 'text', value: NOT_RECORDED }
  return { kind: 'time', value: row.lastSeenAt }
}
