# Tasks — Users and invites admin surface (`034-frontend-users-invites-admin`)

9 tasks. **Unblocked now: #1, #2, #3**

## Agents and gate — this feature is `frontend/`, not Python

Every task's blast radius is `frontend/`. `test-engineer` and `code-reviewer` write pytest and gate
on `uv run pytest` / `uv run ruff check`, neither of which exists here. The orchestrator must spawn:

| Role | Agent |
|---|---|
| Coder | `agent-developer` (unchanged) |
| Tests | **`frontend-test-engineer`** |
| Review | **`frontend-code-reviewer`** |

Gate for every task:

```
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
```

No backend, contract, or `hardware-agent/` file is touched by any task. An implementer editing
`contracts/openapi/openapi.yaml` or `frontend/src/types/openapi.d.ts` has gone off-spec
(ARCHITECTURE.md §head).

**Load the `frontend-conventions` skill before writing any file under `frontend/src/`** — binding
per ARCHITECTURE.md §Constraints.

---

## Task 1: Directory merge helpers
- **Description**: Build the pure display-model layer per ARCHITECTURE.md §"The display model —
  `DirectoryRow`". Define the `DirectoryRow` discriminated union, merge `OrgMember[]` +
  `PendingInvite[]` into it, derive Status, and format the Last seen cell's three cases. Both input
  lists arrive already sorted by the server — **the merge is a concatenation, members then invites,
  and re-sorts nothing**. Types come from `components['schemas'][…]`, never hand-written.
- **Dependencies**: —
- **Target Files**: [`frontend/src/lib/directory.ts`, `frontend/src/lib/directory.test.ts`]
- **Tests**: `directory.test.ts` — pure, no React, mirroring `src/lib/review.test.ts`.
- **Success Criteria**:
  - Members precede invites; member input order is preserved exactly; invite input order is
    preserved exactly (TRUTH rule 4).
  - `isSelf` is `true` on exactly the row whose `user_id` matches the caller, and nowhere else.
  - A member with `last_seen_at: null` yields the **"Not recorded yet"** case and **not** the
    invite's `—` case — the two are asserted as distinct values (TRUTH rule 5).
  - A member's Status reads "Active"; an invite's Status names that it is invited and when it
    expires (TRUTH §Definitions).
  - No invite row exposes a `lastSeenAt`, and no member row exposes an `expiresAt` — the union
    discriminates on `kind`.
  - Gate passes.

## Task 2: Role gates — `AdminOnly`, `RequireAdmin`, and the nav item
- **Description**: Build the product's first role-gated affordance and first role-gated route per
  ARCHITECTURE.md §"The two guards, precisely". `AdminOnly` renders children for admins and `null`
  otherwise. `RequireAdmin` is an outlet guard mirroring `RequireSession.tsx`: `null` while
  booting, `<NotFound />` **rendered** (never navigated to) for a non-admin, `<Outlet />` for an
  admin. Add the `Users` `NavLink` to `TopBar`, wrapped in `AdminOnly`. This task does **not** wire
  `App.tsx` — Task 5 owns that, once there is a page to route to; `RequireAdmin.test.tsx` uses its
  own `MemoryRouter` with a stub child route.
- **Dependencies**: —
- **Target Files**: [`frontend/src/components/AdminOnly.tsx`,
  `frontend/src/components/AdminOnly.test.tsx`, `frontend/src/auth/RequireAdmin.tsx`,
  `frontend/src/auth/RequireAdmin.test.tsx`, `frontend/src/components/TopBar.tsx`,
  `frontend/src/components/TopBar.test.tsx`]
- **Tests**: `AdminOnly.test.tsx`, `RequireAdmin.test.tsx` (new); `TopBar.test.tsx` (extend).
  These are the tests DMI-90 cares most about.
- **Success Criteria**:
  - `nav-users` is **absent from the DOM** for a viewer — asserted with `queryByTestId(…)` being
    `null`, not with a disabled or hidden check (TRUTH acceptance "Viewer: no nav item").
  - `nav-users` is present for an admin and points at `/users`.
  - A viewer at the guarded route gets the `NotFound` copy and **no part of the Users surface**;
    the URL is unchanged, proving a render rather than a redirect (TRUTH rule 1).
  - `RequireAdmin` returns `null` while `status === 'booting'` — a test proves `NotFound` does not
    flash for an admin mid-boot.
  - Both guards fail closed on a `null` `user`: `user?.role !== 'admin'`, never
    `user?.role === 'viewer'`.
  - Neither `AdminOnly` nor `RequireAdmin` accepts a `fallback` or `disabled` prop — this absence
    is the enforcement mechanism for TRUTH rule 2, not a style choice.
  - Gate passes.

## Task 3: `Toast` and `useToast`
- **Description**: Build the shared toast per ARCHITECTURE.md naming table and DESIGN.md §2.12.
  Provider + viewport over Radix `Toast`, with the context split into `useToast.ts` for Fast
  Refresh (same reason as `SessionContext.ts`). Mount it once in `AppShell`, not `main.tsx` —
  toasts are an inside-shell concern and the public auth screens raise none. This is a shared
  foundation Agents will later reuse (`SCREENS.md:251`), so its behaviour is fixed here.
- **Dependencies**: —
- **Target Files**: [`frontend/src/components/Toast.tsx`, `frontend/src/components/Toast.test.tsx`,
  `frontend/src/hooks/useToast.ts`, `frontend/src/components/AppShell.tsx`]
- **Tests**: `Toast.test.tsx` — the dismissal contract, driven through a test component that calls
  `useToast().show(…)`.
- **Success Criteria**:
  - `show(message)` renders one element at `data-testid="toast"` carrying that message.
  - **A second `show()` replaces the first** — after two calls, `getByTestId('toast')` resolves
    (the testid stays unique) and displays only the second message. It does not queue or stack.
  - Auto-dismisses after 5s, asserted with fake timers.
  - A close affordance labelled "Dismiss" removes it before the timer.
  - `useToast` is importable without pulling a component into the same module — no
    `react-refresh/only-export-components` lint error.
  - Mounted once in `AppShell`; the auth screens (`Login`, `AcceptInvite`) still render without a
    provider in scope, and their existing suites still pass.
  - Gate passes.

## Task 4: API functions and `useOrgDirectory`
- **Description**: Wire the six calls and fold the two lists into one state union per
  ARCHITECTURE.md §"The four calls", §"Query keys and invalidation" and §"One error state from two
  queries". `apiClient` is imported from **`src/api/client.ts`, never `instances.ts`** — the
  `Authorization` interceptor lives in `client.ts`, and importing the bare instance makes all six
  calls answer `401` (ARCHITECTURE.md §"The four calls"). Query keys are `['org','members']` and
  `['org','invites']`. Resolution order inside the hook is load-bearing: **error is checked before
  loading**, so a fast failure does not sit behind a slow success.
- **Absorbed**: `frontend/src/api/invites.ts` and the `frontend/src/api/users.ts` extension —
  thin typed wrappers over `apiClient` with no logic beyond the URL and the type, so neither can
  carry a failing test of its own; both are exercised end-to-end through this hook's MSW-backed
  suite. Also the MSW handlers in `frontend/src/test/mswHandlers.ts`, which are test fixtures and
  belong with their first consumer.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/src/api/invites.ts`, `frontend/src/api/users.ts`,
  `frontend/src/hooks/useOrgDirectory.ts`, `frontend/src/hooks/useOrgDirectory.test.ts`,
  `frontend/src/test/mswHandlers.ts`]
- **Tests**: `useOrgDirectory.test.ts`, mirroring `useHomeReview.test.ts`.
- **Success Criteria**:
  - The hook returns the `OrgDirectory` union — `loading` | `error` | `blank` | `ready` — and never
    exposes `isPending`/`isError` to callers.
  - **`GET /users` failing** yields `state: 'error'` with **zero rows**; **`GET /invites` failing**
    yields the same. Both asserted separately (TRUTH rule 7).
  - Error wins over loading: with one query still pending and the other already failed, the state is
    `error`, not `loading`.
  - `blank` when the caller is the only person — no other member and no pending invite (TRUTH
    rule 6); `ready` otherwise.
  - `retry` refetches **both** queries.
  - The two existing exports in `api/users.ts` (`getCurrentUser`, `deleteCurrentUser`) are
    untouched, and `Settings.test.tsx` still passes.
  - Every request and response type is read from `components['schemas'][…]`; no hand-written
    interface for a wire shape.
  - Gate passes.

## Task 5: The Users page, the table, and the route
- **Description**: Build the read-only screen per DESIGN.md §2.2–2.5, §3 and §4 — page header,
  the four table states, and the four row kinds. Wire `/users` into `App.tsx` nested under
  `RequireAdmin` inside the existing `AppShell` route. The table is the product's first: **five
  columns, four headings**, actions in a fifth cell whose header carries screen-reader text only,
  one `<tr>` per person (DESIGN.md §2.2). No row navigates anywhere — the `SCREENS.md` rule-4
  carve-out in DESIGN.md §3 explains why. Copy is taken **verbatim** from `docs/ui/SCREENS.md`
  § USERS & INVITES. Row actions open nothing yet; Tasks 6–9 attach the dialogs.
- **Absorbed**: `frontend/src/components/ui/select.tsx` — a shadcn-shaped wrapper over Radix
  `Select` whose only behaviour is what the role cell exercises, so it is tested where it first
  renders. `frontend/src/components/PageHeader.tsx` — a title and a rule, presentational only,
  asserted through this page's output. `frontend/src/test/setup.ts` — the jsdom pointer-capture and
  `scrollIntoView` stubs Radix `Select` needs, which are setup, not a testable unit.
  `frontend/src/App.tsx` — a three-line route nesting, gated here by the route tests rather than by
  a grep.
- **Dependencies**: Task 2, Task 4
- **Target Files**: [`frontend/src/pages/Users.tsx`, `frontend/src/pages/Users.test.tsx`,
  `frontend/src/pages/users/DirectoryTable.tsx`, `frontend/src/components/PageHeader.tsx`,
  `frontend/src/components/ui/select.tsx`, `frontend/src/App.tsx`,
  `frontend/src/test/setup.ts`]
- **Tests**: `Users.test.tsx` — the states and the row kinds. Tasks 6–9 extend this same file.
- **Success Criteria**:
  - All four row kinds render correctly in one table: **own row** (`user-row-self`, role as plain
    text at `row-role-text-{id}`, no `row-role-{id}`, no `row-remove-{id}`); **another member**
    (role dropdown + Remove); **a member with `last_seen_at: null`** (Last seen reads "Not recorded
    yet"); **a pending invite** (Last seen reads `—`, role is plain text, only `row-revoke-{id}`).
  - Members render before invites, never interleaved (TRUTH rule 4).
  - Loading renders `users-loading` with real column headings over skeleton cells, and
    `invite-open` is **absent**.
  - Blank renders `users-blank` with "You're the only person here.", table chrome absent, and
    `invite-open` **present** (TRUTH rule 6).
  - Error renders `users-error` + `users-error-retry`, **zero rows**, and `invite-open` absent;
    clicking retry refetches (TRUTH rule 7).
  - The role dropdown is **controlled by `row.role`** and never mirrored into `useState`
    (ARCHITECTURE.md §"The role Select is controlled by server state").
  - `data-testid="row-role-{id}"` sits on the Radix `Select.Trigger`; the test opens it by clicking
    the trigger then the option — **not** `userEvent.selectOptions` (DESIGN.md §6).
  - Four column headings exactly — Person · Role · Status · Last seen — with the fifth header cell
    carrying screen-reader text only.
  - An admin at `/users` reaches the screen; a viewer at `/users` gets the not-found page and no
    part of the Users surface (TRUTH acceptance "Viewer: no route").
  - `ConfirmByTyping.tsx` and `api/instances.ts` are **not modified**.
  - Gate passes.

## Task 6: Role change
- **Description**: Attach `RoleChangeDialog` to the role dropdown per DESIGN.md §2.9 and TRUTH
  rule 8. Picking a value opens a dialog naming the person and the new role, confirmed by a
  **single click** — no text input. On success, raise the toast and invalidate **both** query keys.
  Cancelling returns the dropdown to its previous value, which is free because the Select is
  controlled by server state. No copy for `self_target` or `last_admin`: both are unreachable from
  this screen and remain backend guards (ARCHITECTURE.md §"Errors on write").
- **Dependencies**: Task 3, Task 5
- **Target Files**: [`frontend/src/pages/users/RoleChangeDialog.tsx`,
  `frontend/src/pages/Users.tsx`, `frontend/src/pages/Users.test.tsx`]
- **Tests**: `Users.test.tsx` (extend).
- **Success Criteria**:
  - The dialog names the person and the new role, and **contains no text input** — asserted
    directly (TRUTH acceptance "Role change asks once").
  - Both directions render their own body copy: promoting "They'll be able to run scans and invite
    people."; demoting "They'll only be able to see scans, hosts and findings."
  - Success raises a toast reading "**sam@acme.com** is now an admin." (demotion: "…is now a
    viewer.") and the table refetches **without a full page reload**.
  - Cancelling closes the dialog, fires **no request**, and leaves the dropdown showing the
    original role.
  - Failure renders exactly one message, "Couldn't change that role.", plus a retry — and no
    message mentioning a refusal this screen cannot provoke (TRUTH rule 14).
  - In flight the confirm button reads "Changing…", Cancel is unmounted, and Escape is ignored
    (DESIGN.md §5).
  - Both `['org','members']` and `['org','invites']` are invalidated on success.
  - Gate passes.

## Task 7: Remove a member
- **Description**: Attach `RemoveMemberDialog` — a thin wrapper over the **existing, unmodified**
  `ConfirmByTyping` — per DESIGN.md §2.10 and ARCHITECTURE.md §"`ConfirmByTyping` — the props this
  screen passes". `expectedValue` is the **target's** email, not the caller's; that is the one
  difference from the Settings call site. Own rows have no Remove action at all (TRUTH rule 11).
- **Dependencies**: Task 3, Task 5
- **Target Files**: [`frontend/src/pages/users/RemoveMemberDialog.tsx`,
  `frontend/src/pages/Users.tsx`, `frontend/src/pages/Users.test.tsx`]
- **Tests**: `Users.test.tsx` (extend). Test this screen's **use** of `ConfirmByTyping`, not the
  component again — its disabled-until-match mechanics are already covered by
  `ConfirmByTyping.test.tsx` from spec 033.
- **Success Criteria**:
  - A mistyped address leaves the confirm inert and **fires no request** — asserted on the request,
    not only on the button's disabled attribute (TRUTH acceptance "Remove requires the exact
    address").
  - The target's exact address enables it; the admin's own address does **not**.
  - Success raises a toast reading "**sam@acme.com** was removed." and the row is gone without a
    full page reload.
  - Failure renders "Couldn't remove that person." plus a retry, once.
  - The own row exposes no `row-remove-{id}` at all.
  - `frontend/src/components/ConfirmByTyping.tsx` is **byte-identical** — no prop added for this
    call site.
  - Gate passes.

## Task 8: Revoke an invite
- **Description**: Build `RevokeDialog` and attach it to pending-invite rows per DESIGN.md §2.11
  and TRUTH rules 10 and 13. Single-click confirm, the same shape as `RoleChangeDialog` and
  deliberately not a `ConfirmByTyping`: nothing is deleted but an unused token, the invitee has no
  account yet, and a new invite can be issued at once. An invite's role is plain text — there is no
  endpoint that re-roles one.
- **Dependencies**: Task 3, Task 5
- **Target Files**: [`frontend/src/pages/users/RevokeDialog.tsx`, `frontend/src/pages/Users.tsx`,
  `frontend/src/pages/Users.test.tsx`]
- **Tests**: `Users.test.tsx` (extend).
- **Success Criteria**:
  - The dialog names the invited address and confirms in one click, with no text input.
  - Success raises a toast reading "The invite to **new@acme.com** was revoked." and the row is gone
    without a full page reload.
  - Failure renders "Couldn't revoke that invite." plus a retry, once.
  - An invite row exposes `row-revoke-{id}` and **no** `row-role-{id}` and **no** `row-remove-{id}`
    (TRUTH acceptance "Pending row cannot be re-roled").
  - In flight the confirm reads "Revoking…".
  - Gate passes.

## Task 9: Invite a user
- **Description**: Build `InviteDialog` per DESIGN.md §2.6–2.8 and TRUTH rules 15–17 — the form,
  the created state carrying the copyable link, and the three distinct errors. **The link is built
  client-side**: `InviteCreatedResponse` carries `{ invite_token, expires_at }` and no URL, so the
  dialog assembles `${window.location.origin}/invite?token=${invite_token}`
  (ARCHITECTURE.md §"The invite link is built client-side"). Render the expiry from the returned
  `expires_at` rather than a hardcoded 48, since the TTL is a backend setting. Viewer is the
  preselected role. This is the last implementation task — it also carries the feature's final
  gate.
- **Dependencies**: Task 5
- **Target Files**: [`frontend/src/pages/users/InviteDialog.tsx`, `frontend/src/pages/Users.tsx`,
  `frontend/src/pages/Users.test.tsx`]
- **Tests**: `Users.test.tsx` (extend).
- **Success Criteria**:
  - Success shows `invite-created` with the copyable link at `invite-link`, whose value is
    `{origin}/invite?token={invite_token}` — asserted against the token the handler returned, not a
    hardcoded host.
  - The once-only nudge renders: "This is the only time you'll see this link."
  - `invite-copy` reads "Copied" after a click.
  - **No toast is raised on invite success** (TRUTH rule 16) — asserted explicitly, since all three
    row actions do raise one.
  - `invite-done` closes the dialog and the table refetches, with the new pending invite present.
  - "Invite someone else" resets to an empty form.
  - `400 email_already_member` and `409 invite_already_pending` render **two different** messages,
    both asserted, with the form intact so the address can be corrected. Branching is on `status`
    **and** `code` via `readApiError` — a switch on status alone misses the `409`.
  - Anything else renders the generic "Couldn't create the invite." with a retry.
  - Viewer is preselected in the role field; in flight the button reads "Creating…".
  - **Final gate**: the full frontend gate passes across the whole suite, and every request and
    response type in the feature comes from the generated contract types (TRUTH acceptance "Gate").
  - Gate passes.

---

## Dependency graph

```
#1 ─┐
    ├──> #4 ──┐
#2 ─────────  ├──> #5 ──┬──> #6
              │         ├──> #7
#3 ───────────┴─────────┼──> #8
                        └──> #9
```

- **Unblocked now (no dependencies): #1, #2, #3** — three parallel tracks.
- #6, #7 and #8 are mutually independent once #5 lands; #9 needs only #5.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Directory merge helpers | COMPLETED |
| 2 | Role gates — `AdminOnly`, `RequireAdmin`, and the nav item | COMPLETED |
| 3 | `Toast` and `useToast` | COMPLETED |
| 4 | API functions and `useOrgDirectory` | COMPLETED |
| 5 | The Users page, the table, and the route | COMPLETED |
| 6 | Role change | COMPLETED |
| 7 | Remove a member | COMPLETED |
| 8 | Revoke an invite | COMPLETED |
| 9 | Invite a user | COMPLETED |

## Acceptance-criteria coverage

Every scenario in `TRUTH.md` §Acceptance criteria maps to at least one task:

| TRUTH scenario | Task |
|---|---|
| Viewer: no nav item · Admin: nav item works · Role gating is absence | #2 |
| Viewer: no route | #2, #5 |
| One merged table · Pending has no last-seen · Never-recorded member | #1, #5 |
| Only person in the org | #4, #5 |
| Partial load failure | #4, #5 |
| Own row is inert · Pending row cannot be re-roled | #5 |
| Role change asks once · Role change succeeds | #6 |
| Remove requires the exact address · Remove succeeds | #7 |
| Revoke succeeds | #8 |
| Row action failure | #6, #7, #8 |
| Invite shows a link · Invite refreshes the table · Invite raises no toast · Re-invite ×2 | #9 |
| Gate | every task; final sweep in #9 |

## Out of scope — no task exists for these

Per `TRUTH.md` §Out of scope and `DESIGN.md` §7: self-removal (Settings owns it), bulk invite or
CSV import, SSO, optimistic updates, search/filter/sort/pagination, audit of who changed whom,
re-sending an invite email, dark theme, and copy for `self_target` / `last_admin` on role change.
