import { describe, expect, it } from 'vitest'
import type { components } from '@/types/openapi'
import {
  NOT_RECORDED,
  NO_LAST_SEEN,
  lastSeenCell,
  mergeDirectory,
  statusLabel,
} from './directory'

type OrgMember = components['schemas']['OrgMember']
type PendingInvite = components['schemas']['PendingInvite']

const NOW = new Date('2026-07-29T12:00:00Z')

const SELF_ID = '2f0b9d1a-6c2e-4f7a-9c1b-3d4e5f6a7b8c'

function makeMember(overrides: Partial<OrgMember> = {}): OrgMember {
  return {
    user_id: SELF_ID,
    email: 'nadia@dmitri.io',
    role: 'admin',
    last_seen_at: '2026-07-29T08:30:00Z',
    ...overrides,
  }
}

function makeInvite(overrides: Partial<PendingInvite> = {}): PendingInvite {
  return {
    invite_id: '7a1c4b2e-88d3-4a19-bf20-11c9e0a4d5f6',
    email: 'ops@dmitri.io',
    role: 'viewer',
    expires_at: '2026-08-01T12:00:00Z',
    ...overrides,
  }
}

describe('mergeDirectory', () => {
  it('places every member before every invite and preserves invite order', () => {
    const members = [
      makeMember({ user_id: SELF_ID, email: 'nadia@dmitri.io' }),
      makeMember({
        user_id: 'b3a1f0c2-5d6e-4f80-91a2-c3d4e5f60718',
        email: 'kwame@dmitri.io',
        role: 'viewer',
      }),
    ]
    const invites = [
      makeInvite({ email: 'ops@dmitri.io' }),
      makeInvite({
        invite_id: 'd9e8c7b6-a5f4-4312-8091-2a3b4c5d6e7f',
        email: 'soc@dmitri.io',
        role: 'admin',
      }),
    ]

    const rows = mergeDirectory(members, invites, SELF_ID)

    expect(rows.map((row) => row.kind)).toEqual([
      'member',
      'member',
      'invite',
      'invite',
    ])
    expect(rows.map((row) => row.email)).toEqual([
      'nadia@dmitri.io',
      'kwame@dmitri.io',
      'ops@dmitri.io',
      'soc@dmitri.io',
    ])
  })

  it('lifts every admin above every viewer whatever order the server sent', () => {
    const rows = mergeDirectory(
      [
        makeMember({
          user_id: 'v1',
          email: 'viewer@dmitri.io',
          role: 'viewer',
        }),
        makeMember({ user_id: 'a1', email: 'admin@dmitri.io', role: 'admin' }),
      ],
      [],
      SELF_ID,
    )

    expect(rows.map((row) => row.email)).toEqual([
      'admin@dmitri.io',
      'viewer@dmitri.io',
    ])
  })

  it('orders within a role by most recently seen, never-signed-in last', () => {
    const rows = mergeDirectory(
      [
        makeMember({
          user_id: 'v1',
          email: 'stale@dmitri.io',
          role: 'viewer',
          last_seen_at: '2026-07-01T00:00:00Z',
        }),
        makeMember({
          user_id: 'v2',
          email: 'never@dmitri.io',
          role: 'viewer',
          last_seen_at: null,
        }),
        makeMember({
          user_id: 'v3',
          email: 'fresh@dmitri.io',
          role: 'viewer',
          last_seen_at: '2026-07-28T00:00:00Z',
        }),
      ],
      [],
      SELF_ID,
    )

    expect(rows.map((row) => row.email)).toEqual([
      'fresh@dmitri.io',
      'stale@dmitri.io',
      'never@dmitri.io',
    ])
  })

  it('breaks a full tie on email so the order cannot swap between renders', () => {
    const rows = mergeDirectory(
      [
        makeMember({
          user_id: 'v2',
          email: 'zoe@dmitri.io',
          role: 'viewer',
          last_seen_at: null,
        }),
        makeMember({
          user_id: 'v1',
          email: 'ana@dmitri.io',
          role: 'viewer',
          last_seen_at: null,
        }),
      ],
      [],
      SELF_ID,
    )

    expect(rows.map((row) => row.email)).toEqual([
      'ana@dmitri.io',
      'zoe@dmitri.io',
    ])
  })

  it("does not mutate the caller's array — it belongs to the query cache", () => {
    const members = [
      makeMember({ user_id: 'v1', email: 'viewer@dmitri.io', role: 'viewer' }),
      makeMember({ user_id: 'a1', email: 'admin@dmitri.io', role: 'admin' }),
    ]

    mergeDirectory(members, [], SELF_ID)

    expect(members.map((member) => member.email)).toEqual([
      'viewer@dmitri.io',
      'admin@dmitri.io',
    ])
  })

  it('marks isSelf on exactly the caller row and nowhere else', () => {
    const rows = mergeDirectory(
      [
        makeMember({
          user_id: 'b3a1f0c2-5d6e-4f80-91a2-c3d4e5f60718',
          email: 'kwame@dmitri.io',
        }),
        makeMember({ user_id: SELF_ID, email: 'nadia@dmitri.io' }),
      ],
      [makeInvite()],
      SELF_ID,
    )

    const selfRows = rows.filter((row) => row.kind === 'member' && row.isSelf)
    expect(selfRows).toHaveLength(1)
    expect(selfRows[0].email).toBe('nadia@dmitri.io')
  })

  it('discriminates on kind so invites carry no lastSeenAt and members no expiresAt', () => {
    const rows = mergeDirectory([makeMember()], [makeInvite()], SELF_ID)

    const member = rows[0]
    const invite = rows[1]
    expect(member.kind).toBe('member')
    expect(invite.kind).toBe('invite')
    expect(member).not.toHaveProperty('expiresAt')
    expect(invite).not.toHaveProperty('lastSeenAt')
    expect(invite).not.toHaveProperty('isSelf')
  })

  it('returns no rows when the organization has neither members nor invites', () => {
    expect(mergeDirectory([], [], SELF_ID)).toEqual([])
  })
})

describe('statusLabel', () => {
  it('reads Active for a member', () => {
    const [row] = mergeDirectory([makeMember()], [], SELF_ID)
    expect(statusLabel(row, NOW)).toBe('Active')
  })

  it('names the invite and its remaining days', () => {
    const [row] = mergeDirectory(
      [],
      [makeInvite({ expires_at: '2026-08-01T12:00:00Z' })],
      SELF_ID,
    )
    expect(statusLabel(row, NOW)).toBe('Invited — expires in 3 days')
  })

  it('uses the singular day and never counts below one', () => {
    const [soon] = mergeDirectory(
      [],
      [makeInvite({ expires_at: '2026-07-30T06:00:00Z' })],
      SELF_ID,
    )
    expect(statusLabel(soon, NOW)).toBe('Invited — expires in 1 day')

    const [lapsed] = mergeDirectory(
      [],
      [makeInvite({ expires_at: '2026-07-20T12:00:00Z' })],
      SELF_ID,
    )
    expect(statusLabel(lapsed, NOW)).toBe('Invited — expires in 1 day')
  })
})

describe('lastSeenCell', () => {
  it('distinguishes a member never seen from an invite that has no last seen at all', () => {
    const [member, invite] = mergeDirectory(
      [makeMember({ last_seen_at: null })],
      [makeInvite()],
      SELF_ID,
    )

    const memberCell = lastSeenCell(member)
    const inviteCell = lastSeenCell(invite)

    expect(memberCell).toEqual({ kind: 'text', value: NOT_RECORDED })
    expect(inviteCell).toEqual({ kind: 'text', value: NO_LAST_SEEN })
    expect(memberCell.value).not.toBe(inviteCell.value)
  })

  it('returns the raw timestamp for a member that has been seen', () => {
    const [member] = mergeDirectory(
      [makeMember({ last_seen_at: '2026-07-29T08:30:00Z' })],
      [],
      SELF_ID,
    )
    expect(lastSeenCell(member)).toEqual({
      kind: 'time',
      value: '2026-07-29T08:30:00Z',
    })
  })
})
