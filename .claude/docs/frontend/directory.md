---
type: Module
title: frontend org directory model
description: DirectoryRow — the merged member/invite display union — and useOrgDirectory(), which folds two list reads into one state union where error outranks loading.
resource: frontend/src/lib/directory.ts
tags: [frontend, users, invites, directory, tanstack-query]
timestamp: 2026-08-21T00:00:00Z
---

# frontend org directory model

## Purpose

`src/lib/directory.ts` and `src/hooks/useOrgDirectory.ts` are the layer between the two org list
endpoints and the Users table. The lib half is pure: it merges `OrgMember[]` and `PendingInvite[]`
into one discriminated union the table can render row-by-row without re-asking which kind it holds.
The hook half runs the two reads and collapses them into a **single** four-way state, so the screen
never renders half a table or a spinner over a known failure.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `DirectoryRow` | The display union, discriminated on `kind`. A `member` row carries `lastSeenAt` and `isSelf`; an `invite` row carries `expiresAt` and neither. The two never share a field they cannot both answer. | `frontend/src/lib/directory.ts:14` |
| `mergeDirectory(members, invites, selfUserId)` | **Members then invites**, always. Members are re-sorted by `byRoleThenLastSeen`; invites keep server order. `isSelf` is `member.user_id === selfUserId`. Sorts a **copy** — the array it receives is the query cache's own data. | `frontend/src/lib/directory.ts:52` |
| `byRoleThenLastSeen` / `ROLE_RANK` | Admins above viewers whatever the server sent, then most-recently-seen first inside each group, never-signed-in (`last_seen_at: null`) last, email breaking a full tie. The tiebreak makes the order **total**: without it two members matching on role and last-seen could swap between renders. `null` maps to `-Infinity`, so the null-vs-null subtraction is `NaN` and falls through to the email compare. | `frontend/src/lib/directory.ts:40` |
| `statusLabel(row, now?)` | `'Active'` for a member; `Invited — expires in N days` for an invite. `now` is a plain parameter, not an injected clock, and the day count is clamped at 1. | `frontend/src/lib/directory.ts:76` |
| `lastSeenCell(row)` | Three distinct cases: `{kind:'time'}` carrying the raw ISO value, `{kind:'text', value: NOT_RECORDED}`, `{kind:'text', value: NO_LAST_SEEN}`. | `frontend/src/lib/directory.ts:88` |
| `NOT_RECORDED` / `NO_LAST_SEEN` | `'Not recorded yet'` (a member who has never signed in) and `'—'` (an invite, which cannot have a last-seen). Deliberately different strings — the table must not blur the two. | `frontend/src/lib/directory.ts:7` |
| `Role` / `ROLE_NOUN` | `Role` is the `'admin' \| 'viewer'` union read off `OrgMember`, exported so the page and the dialogs share one name for it — `OrgMember`, `UpdateUserRoleRequest`, `PendingInvite` and `CreateInviteRequest` all declare the same two values. `ROLE_NOUN` is the `{ admin: 'an admin', viewer: 'a viewer' }` phrasing used by both the role-change heading and its success toast, so the two cannot drift apart. | `frontend/src/lib/directory.ts:5` |
| `OrgDirectory` | The hook's return union: `loading` \| `error` \| `blank` \| `ready`. `isPending`/`isError` never escape. | `frontend/src/hooks/useOrgDirectory.ts:7` |
| `useOrgDirectory()` | Two queries keyed `['org','members']` and `['org','invites']`, merged through `mergeDirectory` with the self id from `useSession()`. `retry` refetches both. The shared `['org']` prefix is load-bearing: every mutation on the Users page refreshes both lists with a single `invalidateQueries({ queryKey: ['org'] })`, so a new key under `['org']` is picked up automatically and no call site has to list the keys. | `frontend/src/hooks/useOrgDirectory.ts:13` |

## How it connects

- Consumes [api](./api.md)'s `listOrgMembers()` and `listPendingInvites()`, and [auth](./auth.md)'s
  `useSession()` for the caller's `user_id`.
- Consumed by [screens](./screens.md)'s `Users` page, which switches over the union exactly as
  `Home` switches over [review](./review.md)'s `useHome()`.
- Row rendering (Status text, Last seen cell) is done by `DirectoryTable` calling `statusLabel` and
  `lastSeenCell`; the `time` case is handed to the shared `Timestamp` component.

## Notes / gotchas

- **Row order is the client's decision, not the server's.** The list endpoints return their own
  order and the table overrides it: admins are pinned to the top so the people who can change the
  organisation are always the first ones read, and everyone else sorts by recency of use. Members
  and invites never interleave — an invite is not a person yet, and mixing the two would put a row
  with no last-seen in the middle of a column sorted by it.
- **Error is resolved before loading.** A fast failure on one list must not sit behind a slow
  success on the other, so the hook checks `isError` first. Reversing the two checks is a real
  behaviour change, not a style preference.
- **`lastSeenCell` returns the raw ISO string, not a formatted date.** `Timestamp` already owns
  relative-vs-absolute formatting; formatting here would be a second, drifting implementation.
- **`blank` means the caller is alone** — no other member and no pending invite. It is not the same
  as an empty list, because the caller is always in their own member list.
- **A null session user passes `''` as the self id**, so no row is `isSelf` while the session is
  still booting. No extra state for a case the route guard already prevents.
- The merge preserves input order exactly. The server owns sort order; re-sorting here would make
  the screen disagree with any future paging.

# Citations

[1] [specs/034-frontend-users-invites-admin/ARCHITECTURE.md](../../../specs/034-frontend-users-invites-admin/ARCHITECTURE.md)
[2] [specs/034-frontend-users-invites-admin/TRUTH.md](../../../specs/034-frontend-users-invites-admin/TRUTH.md)
