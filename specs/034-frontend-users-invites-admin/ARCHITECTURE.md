# ARCHITECTURE — Users and invites admin surface

Frontend-only. React 19 + TypeScript + Vite 8 + Tailwind v4 + TanStack Query v5 + React Router v7,
all under `frontend/`.

**No backend, contract, or `hardware-agent/` change.** The API shipped complete in spec 030
(DMI-76) and spec 029 (DMI-102); `contracts/openapi/openapi.yaml` and
`frontend/src/types/openapi.d.ts` already carry every schema this screen needs. If an implementer
finds themselves editing either, they have gone off-spec.

No `INTEGRATION.md`: nothing here crosses a layer boundary.

Behaviour is fixed by [`TRUTH.md`](TRUTH.md); copy and layout by
[`DESIGN.md`](DESIGN.md) and `docs/ui/SCREENS.md` § USERS & INVITES.

## System context

The app shell is `App.tsx` → `RequireSession` → `AppShell` → a page. This feature adds the
product's **first role-gated route** and its **first role-gated affordance**, so it introduces two
guards rather than one:

```
App.tsx
└── RequireSession            (exists — redirects anonymous → /login)
    └── AppShell              (exists — TopBar + Outlet)
        ├── /            Home
        ├── /settings    Settings
        ├── RequireAdmin                    ← NEW outlet guard
        │   └── /users   Users              ← NEW page
        └── *            NotFound

TopBar
└── AdminOnly                               ← NEW wrapper
    └── NavLink /users  data-testid="nav-users"
```

`AdminOnly` and `RequireAdmin` are separate because hiding a link and refusing a URL are different
jobs, and TRUTH rule 1 requires **both**. Neither takes a `fallback` or a `disabled` prop, so no
call site can produce a greyed-out role-gated control (TRUTH rule 2).

## Data model / contracts

### The four calls

| Purpose | Method + path | Request type | Response type |
|---|---|---|---|
| List members | `GET /users` | — | `OrgMemberListResponse` |
| List pending invites | `GET /invites` | — | `PendingInviteListResponse` |
| Change a role | `PATCH /users/{user_id}` | `UpdateUserRoleRequest` | `OrgMember` |
| Remove a member | `DELETE /users/{user_id}` | — | `204` |
| Revoke an invite | `DELETE /invites/{invite_id}` | — | `204` |
| Create an invite | `POST /invites` | `CreateInviteRequest` | `InviteCreatedResponse` |

All six go over `apiClient`, and it is **imported from `frontend/src/api/client.ts`** — not from
`instances.ts`. This distinction is load-bearing, not stylistic:

- `instances.ts` creates the bare axios instances. `apiClient` there carries **no `withCredentials`**
  — the business client never sends the refresh cookie, and that policy is asserted by
  `api/client.test.ts`. Do not widen it.
- `client.ts` imports that same instance, attaches the **`Authorization: Bearer` request
  interceptor** and the 401-refresh-and-retry response interceptor, and re-exports it.

An implementer who imports `apiClient` from `instances.ts` gets an instance with no `Authorization`
header, and all six admin calls answer `401`. Every business module in the codebase already imports
from `./client` (`findings.ts`, `passwords.ts`, `scans.ts`, `users.ts`); only `auth.ts` reaches into
`instances.ts`, and only for `authClient`.

### Types — all generated, none hand-written

Every request and response type is read from `frontend/src/types/openapi.d.ts` via
`components['schemas'][…]`, exactly as `src/api/users.ts` and `src/hooks/useHomeReview.ts` already
do. The names:

```ts
type OrgMember            = components['schemas']['OrgMember']
type PendingInvite        = components['schemas']['PendingInvite']
type UpdateUserRoleRequest = components['schemas']['UpdateUserRoleRequest']
type CreateInviteRequest  = components['schemas']['CreateInviteRequest']
type InviteCreatedResponse = components['schemas']['InviteCreatedResponse']
```

Their actual shapes, which drive the display model below:

```ts
OrgMember      { user_id: string; email: string; role: 'admin' | 'viewer'; last_seen_at: string | null }
PendingInvite  { invite_id: string; email: string; role: 'admin' | 'viewer'; expires_at: string }
```

### The invite link is built client-side

`InviteCreatedResponse` carries `{ invite_token, expires_at }` — **there is no URL on the wire.**
The dialog's copyable link (DESIGN §2.7) is assembled in the frontend:

```ts
const inviteLink = `${window.location.origin}/invite?token=${response.invite_token}`
```

`/invite?token=` is not a new shape: `src/pages/AcceptInvite.tsx` already reads that exact query
parameter, and `/invite` is already a route in `App.tsx`. Only the host was open, and it is taken
from the browser rather than from configuration.

**Why `window.location.origin` and not a new env var.** The backend writes its emailed link from
`settings.app_base_url` (`backend/src/api/services/mailer.py:45`). Mirroring that into a
`VITE_APP_URL` would add a second setting whose only job is to repeat the address the browser is
already on, and a second way for the two to drift. The product is served at one address
(`nspi.up.railway.app`) with no second address planned. Decided by the operator 2026-08-20.

If the app ever gains a second public address, this is the line to revisit — the copied link would
then follow the admin's host while the emailed link follows the server's.

**Expiry copy comes from `expires_at`, not from a constant.** The invite TTL is configurable
(`INVITE_TTL_HOURS`, default 48 — `backend/src/api/core/config.py:64`). SCREENS.md fixes the
sentence "It works once, and expires in 48 hours."; render the duration from the returned
`expires_at` so the sentence stays true if the setting changes.

### The display model — `DirectoryRow`

**There is no `status` field on the wire.** `OrgMember` carries four fields and none of them is a
status; `PendingInvite` carries no `last_seen_at`. Status is *derived from which list a row came
from*, and the two shapes are merged into one discriminated union for rendering:

```ts
export type DirectoryRow =
  | { kind: 'member'; id: string; email: string; role: Role
      lastSeenAt: string | null; isSelf: boolean }
  | { kind: 'invite'; id: string; email: string; role: Role
      expiresAt: string }
```

`kind` decides everything the table branches on: which Status text renders, whether Last seen shows
a time / "Not recorded yet" / `—`, whether Role is a dropdown or plain text, and whether the row
action is Remove or Revoke. `isSelf` is `member.user_id === session.user.user_id`, and it is the
**only** thing that suppresses the role control and the Remove action on a member row (TRUTH
rule 11).

Ordering (TRUTH rule 4): **both lists arrive already sorted, and neither is re-sorted client-side.**
`GET /users` sorts `last_seen_at DESC NULLS LAST` (`backend/src/api/services/users.py`) and
`GET /invites` sorts `expires_at ASC` (`backend/src/api/services/invites.py`, `list_pending_invites`).
The merge is a concatenation — members, then invites — and nothing more. A pending invite has no
`last_seen_at`, so a single sort across both would order half the rows on a field they lack.

**Expired invites never arrive.** `list_pending_invites` filters `expires_at > utc_now()`, so the
table has no expired-invite row kind and needs no copy for one. An invite that lapses simply stops
appearing on the next refetch.

### The two guards, precisely

`useSession()` returns `status: 'booting' | 'authenticated' | 'anonymous'` and
`user: UserProfileResponse | null`. **`user` is nullable, so neither guard may read `user.role`
without a null check**, and neither may treat "no user yet" as "not an admin" — that would flash
the not-found page during boot.

`RequireAdmin` renders inside `RequireSession`, so by the time it runs the status is already
`authenticated`. It still mirrors `RequireSession.tsx`'s shape rather than assuming that:

```tsx
export function RequireAdmin() {
  const { status, user } = useSession()
  if (status === 'booting') return null      // same as RequireSession — render nothing, not a redirect
  if (user?.role !== 'admin') return <NotFound />
  return <Outlet />
}
```

Three things an implementer gets wrong here:

- **`<NotFound />` is rendered, not navigated to.** A `<Navigate to="/404">` would rewrite the
  address bar and tell the viewer their URL was rejected. TRUTH rule 1 requires the viewer to learn
  nothing.
- **`user?.role !== 'admin'`, not `user?.role === 'viewer'`.** A null user must fail closed.
- **`return null` while booting**, exactly as `RequireSession.tsx:8` does. Returning `<NotFound />`
  during boot flashes it for every admin on every reload.

`AdminOnly` follows the same null rule: `user?.role === 'admin' ? children : null`.

### Query keys and invalidation

```
['org', 'members']   → GET /users
['org', 'invites']   → GET /invites
```

Every mutation invalidates **both** keys on success. Role change strictly only needs `members`, but
invalidating one key per mutation is a rule an implementer has to remember per call site, and the
lists are small. No optimistic updates and no `setQueryData` patching (TRUTH out-of-scope): all
three writes are admin actions on a membership table, where a wrong guess briefly displays a false
fact about who can reach the org's data.

### The role Select is controlled by server state, never by local state

DESIGN §2.9: "Cancelling returns the dropdown to its previous value." That behaviour is **free if
and only if** the Select's `value` is the row's role from the query and nothing writes it locally:

```tsx
<Select.Root
  value={row.role}                       // server state, never a useState
  onValueChange={(next) => openRoleDialog(row, next as Role)}
>
```

`onValueChange` opens the dialog and stores the *pending* choice on the dialog, not on the row.
Cancelling closes the dialog and the Select re-renders from `row.role`, which never changed.
Confirming invalidates `['org', 'members']`, the row refetches, and the new value arrives from the
server.

An implementer who mirrors the role into `useState` gets a dropdown that keeps the cancelled value
— a control showing "Admin" for a person who is still a viewer, which is the single most misleading
thing this screen could display.

### One error state from two queries

TRUTH rule 7: **either** list failing puts the whole table into its error state with no rows. The
existing precedent for this is `useHomeReview` (`src/hooks/useHomeReview.ts`), which folds several
queries into one discriminated union, and `useOrgDirectory` follows it exactly:

```ts
export type OrgDirectory =
  | { state: 'loading' }
  | { state: 'error';  retry: () => void }
  | { state: 'blank';  rows: DirectoryRow[] }   // only the caller's own row
  | { state: 'ready';  rows: DirectoryRow[] }
```

Resolution order inside the hook, and it matters:

1. `membersQuery.isError || invitesQuery.isError` → `error`. **Checked before loading**, so a
   fast failure does not sit behind a slow success.
2. `membersQuery.isPending || invitesQuery.isPending` → `loading`.
3. Otherwise merge; `blank` when the merged list is just the caller's own row and there are no
   invites, `ready` otherwise.

`retry` refetches both. The page renders the state, never the raw queries — components must not
reach into `isPending`/`isError` themselves, or the "no partial table" rule leaks.

### Errors on write

`readApiError(err)` (`src/api/apiError.ts`) returns `{ status, code }`; branch on both, exactly as
`Settings.tsx` does.

| Action | Case | Copy source |
|---|---|---|
| Invite | `400 email_already_member` | its own message |
| Invite | `409 invite_already_pending` | its own, **distinct** message |
| Invite | anything else | generic invite failure |
| Role change | any failure | one generic line + retry |
| Remove | any failure | one generic line + retry |
| Revoke | any failure | one generic line + retry |

Two notes an implementer will otherwise get wrong:

- **The pending case is `409`, not `400`.** Code that switches on status alone will miss it.
- **`self_target` and `last_admin` on `PATCH /users/{user_id}` get no copy at all.** They are
  unreachable from this screen: `self_target` needs the admin to target their own row, which draws
  no role control, and `last_admin` needs the target to be the org's only admin while not being the
  caller — impossible, since the caller is an admin in that org, and
  `backend/src/api/routers/users.py` checks self-targeting first. They remain backend guards
  against direct API calls. Writing UI branches for them is error handling for an impossible
  scenario (`.claude/CLAUDE.md` §2).

## New files and naming (mandatory)

| Layer | Path | Notes |
|---|---|---|
| Role gate (render) | `frontend/src/components/AdminOnly.tsx` | **new.** `{ children }` → children for admins, `null` otherwise. Reads `useSession()`. **No `fallback` prop, no `disabled` prop.** |
| Role gate (route) | `frontend/src/auth/RequireAdmin.tsx` | **new.** Outlet guard mirroring `RequireSession.tsx`. Viewer → renders `NotFound`, not a redirect, not an access-denied page. |
| Select primitive | `frontend/src/components/ui/select.tsx` | **new.** Radix `Select` wrapped in the shadcn shape the three existing `ui/` primitives use (`style: radix-nova`, `components.json`). First select in the product. Needs jsdom stubs — see Testing expectations. |
| Toast | `frontend/src/components/Toast.tsx` | **new.** Provider + viewport over Radix `Toast`. First call site in the product. 5s duration, closable, and **one at a time — `show()` replaces the visible toast, it does not queue or stack** (DESIGN §2.12). That keeps `data-testid="toast"` unique. |
| Toast hook | `frontend/src/hooks/useToast.ts` | **new.** `useToast().show(message)`. Context split from the component file for Fast Refresh, same reason as `SessionContext.ts`. |
| Page header | `frontend/src/components/PageHeader.tsx` | **new.** `{ title }` → the title and the rule beneath it. `SCREENS.md:244` declares it a foundation for Scans, Hosts, Agents and Users; Users is the **first** of the four to be built, so this file does not exist yet. Nothing else — no subtitle prop, no actions slot, until a screen needs one. |
| Page | `frontend/src/pages/Users.tsx` | **new.** Owns page header, the invite button, dialog open/close state, and toast calls. |
| Table | `frontend/src/pages/users/DirectoryTable.tsx` | **new.** Renders the four states' bodies and the four row kinds. |
| Invite dialog | `frontend/src/pages/users/InviteDialog.tsx` | **new.** Form state + created state with the copyable link. |
| Role dialog | `frontend/src/pages/users/RoleChangeDialog.tsx` | **new.** Single-click confirm, both directions. |
| Revoke dialog | `frontend/src/pages/users/RevokeDialog.tsx` | **new.** Single-click confirm for a pending invite (DESIGN §2.11, testids `revoke-dialog` / `revoke-confirm` / `revoke-error`). Same shape as `RoleChangeDialog`, not a `ConfirmByTyping` — nothing is deleted but an unused token. |
| Remove dialog | `frontend/src/pages/users/RemoveMemberDialog.tsx` | **new.** Thin wrapper over the existing `ConfirmByTyping`. |
| Directory hook | `frontend/src/hooks/useOrgDirectory.ts` | **new.** The two queries → one `OrgDirectory` union. |
| Merge helpers | `frontend/src/lib/directory.ts` | **new.** Pure: merge, order, derive status, format Last seen. Unit-tested without React. |
| Invites API | `frontend/src/api/invites.ts` | **new.** `listPendingInvites`, `createInvite`, `revokeInvite`. |
| Users API | `frontend/src/api/users.ts` | **extend.** Add `listOrgMembers`, `updateUserRole`, `deleteUser`. Keep the two existing functions untouched. |
| Routes | `frontend/src/App.tsx` | **extend.** Nest `/users` under `RequireAdmin`, inside the existing `AppShell` route. |
| Nav | `frontend/src/components/TopBar.tsx` | **extend.** Add the `Users` `NavLink` (`data-testid="nav-users"`) wrapped in `AdminOnly`. |
| Toast mount | `frontend/src/main.tsx` **or** `frontend/src/components/AppShell.tsx` | **extend.** Mount the toast provider/viewport once. Prefer `AppShell` — toasts are an inside-shell concern and the public auth screens raise none. |

The `src/pages/users/` subfolder mirrors the existing `src/pages/home/` precedent; do not invent a
different layout.

### Files deliberately **not** touched

| Path | Why |
|---|---|
| `frontend/src/components/ConfirmByTyping.tsx` | Reused **as-is**. Its props already cover this call site, and its disabled-until-match behaviour arrives free (ADR-017 §5 as amended 2026-08-17). Adding a prop for this screen would be a visible change to a shared component. |
| `frontend/src/api/instances.ts` | The business client's credential policy is asserted by `api/client.test.ts`. |
| `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts` | Contract is complete and generated. |
| `backend/**` | No backend work in this issue. |
| `frontend/src/auth/RequireSession.tsx` | `RequireAdmin` is a sibling, not an edit. Role and session are separate questions and composing two guards keeps each one testable alone. |

### `ConfirmByTyping` — the props this screen passes

Fixed by the shipped component; do not deviate:

```ts
<ConfirmByTyping
  open={…} onOpenChange={…}
  heading={`Remove ${row.email}?`}
  body="They lose access immediately and their account is deleted. This can't be undone. You can invite them again later."
  expectedValue={row.email}          // THEIR address, not the admin's
  confirmLabel="Remove"
  confirmPendingLabel="Removing…"
  onConfirm={…}                      // must return a Promise
  error={removeError}
/>
```

`expectedValue` being the **target's** address is the one thing that differs from Settings, where it
is the caller's own. Matching is trimmed and case-insensitive inside the component.

## Constraints

- **Load the `frontend-conventions` skill before writing any file under `frontend/src/`.** It is
  binding and carries the API-type rule, the spacing scale, and the React 19 / Tailwind v4 traps.
- No new dependency. Radix (`radix-ui`) is already installed and supplies both `Toast` and `Select`; TanStack Query
  supplies the cache. If an implementer reaches for a toast library, that is scope creep.
- Copy is **taken verbatim** from `docs/ui/SCREENS.md` § USERS & INVITES. Do not paraphrase.
- Copy shared with other screens goes through `src/lib/copy.ts`; copy unique to this screen lives
  in the component. Note the existing comment in that file: **tests assert literal strings and must
  not import the constants.**
- No `ruff`/backend gates apply. The gate is `npm run lint`, `npm run typecheck`, `npm test`,
  `npm run build`.
- `AdminOnly` and `RequireAdmin` must never gain a `fallback` or `disabled` prop. That absence is
  the enforcement mechanism for TRUTH rule 2, not a stylistic preference.

## Testing expectations

Vitest + Testing Library + MSW, mirroring the existing suites. MSW handlers for the four new
endpoints go in `frontend/src/test/mswHandlers.ts`.

**Radix `Select` needs jsdom stubs before any test can open it.** It calls pointer-capture and
scroll APIs that jsdom does not implement, so opening the role dropdown throws without these.
Add them once to `frontend/src/test/setup.ts` — not per test file:

```ts
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})
```

This is the accepted cost of the operator's 2026-08-20 choice of Radix `Select` over a native
`<select>`, taken for a dropdown that matches the rest of the product's chrome. Driving it in a
test is a click on the trigger then a click on the option — **not** `userEvent.selectOptions`,
which only works on a native element.

### `frontend/src/lib/directory.test.ts` (new)

Pure, no React. Members before invites; member order preserved from input; invites sorted by
`expires_at` ascending; `isSelf` set on exactly the matching `user_id`; a `null` `last_seen_at`
yields the "not recorded" case and **not** the invite's `—` case.

### `frontend/src/components/AdminOnly.test.tsx` (new)

Renders children for an admin session; renders nothing for a viewer. One assertion that matters
more than it looks: **the viewer render produces no element at all**, not a hidden or disabled one.

### `frontend/src/auth/RequireAdmin.test.tsx` (new)

Admin reaches the child route; viewer gets the not-found copy and none of the Users surface.

### `frontend/src/components/TopBar.test.tsx` (extend)

`nav-users` **absent from the DOM** for a viewer; present and pointing at `/users` for an admin.
This is the test DMI-90 cares most about.

### `frontend/src/pages/Users.test.tsx` (new)

The bulk of the suite:

- All four row kinds render correctly — own row (no Remove, no dropdown, role as text), another
  member (dropdown + Remove), a member with `last_seen_at: null` ("Not recorded yet"), a pending
  invite (`—`, plain-text role, Revoke only).
- **Either query failing renders the error state and zero rows** — assert once with `GET /users`
  failing and once with `GET /invites` failing.
- Role change: dialog asks for one click and contains **no text input**; success raises the toast
  and refetches.
- Remove: confirm stays inert on a mistyped address and **no request fires**; the exact address
  enables it; success raises the toast and drops the row.
- Revoke: success raises the toast and drops the row.
- Invite: success shows the copyable link and the once-only nudge, and raises **no** toast;
  dismissing refetches; `400 email_already_member` and `409 invite_already_pending` render two
  **different** messages.

Assert on user-visible text and `data-testid`, never on query internals.

### Not tested here

- The disabled-until-match mechanics of `ConfirmByTyping` — already covered by
  `ConfirmByTyping.test.tsx` from spec 033. Test this screen's *use* of it, not the component again.
- `self_target` / `last_admin` role-change responses. Unreachable from this UI; a test would have
  to fake a state the product cannot enter.
