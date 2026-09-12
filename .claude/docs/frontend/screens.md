---
type: Module
title: frontend screens, shells and shared components
description: The public and guarded screens, 70rem app frame, 24rem auth shell, centred navigation, two-group Settings surface, password reveal fields, and shared presentation and interaction components.
resource: frontend/src/pages/
tags: [frontend, ui, screens, react, accessibility]
timestamp: 2026-09-12T00:00:00Z
---

# frontend screens, shells and shared components

## Purpose

The visible surface of the app: two frames (signed-out and signed-in), the public auth routes, the
guarded reads (Home, scans, network, devices, Settings, Users), and the small set of components they
share. The governing principle throughout is **absent, not disabled** — an operator never meets a
control that looks live and isn't. Scan/network/Home blank states carry `FirstScanCta` for admins;
the no-device Devices blank is the one blank state with no action.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `AuthShell` | Outside-shell frame: wordmark + one centred card in the named 24rem `max-w-form` column. No top bar, no ornament. | `frontend/src/components/AuthShell.tsx:3` |
| `AppShell` | Inside-shell frame: `<TopBar />` + `<Outlet />` in the fluid named 70rem `max-w-frame` column. **No sidebar.** | `frontend/src/components/AppShell.tsx:5` |
| `TopBar` | Wordmark left, the nav centred on the 70rem frame, signed-in email + `[Log out]` right through a `1fr auto 1fr` grid. Home uses `end`; Scans, Network and Devices omit `end` so a detail route keeps the parent item active. Nav order: Home · Scans · Network · Devices · Users (admin) · Settings. Test ids: `nav-network`, `nav-devices`. | `frontend/src/components/TopBar.tsx:13` |
| `AdminOnly` | Renders `children` for an admin and `null` for anyone else. Props are `{ children }` — no `fallback`, no `disabled`; the missing props are what make "absent, not disabled" unbypassable. Pairs with [auth](./auth.md)'s `RequireAdmin`, which closes the route the hidden link would have led to. | `frontend/src/components/AdminOnly.tsx:4` |
| `navLinkClass` | The one active/muted `NavLink` className callback shared by every nav destination; the dedicated `text-nav` size stays on the label spans. | `frontend/src/components/TopBar.tsx:7` |
| `Login` | Real `<form>` in `AuthShell`; labelled email plus `PasswordInput`, email autofocused, Enter submits from either field. Carries the `Forgot password?` link and renders the transient arrival note. In-flight the button reads `Signing in…` and is `disabled`. | `frontend/src/pages/Login.tsx:11` |
| `arrival` | The router state snapshotted once at mount as `'passwordReset' \| 'accountDeleted' \| null`, switching the copy of the **single** `role="status"` region (`data-testid="login-success"`). One region, two notes — a second status element would break `getByRole('status')`. The same Effect that focuses the note runs `navigate(location.pathname, { replace: true })`, so neither note survives a reload. | `frontend/src/pages/Login.tsx:19` |
| `ForgotPassword` | The recovery request form in `AuthShell`. A `204` **replaces** the form with a confirmation that is byte-for-byte identical for known and unknown addresses — the anti-enumeration boundary. Posts exactly `{ email }`. | `frontend/src/pages/ForgotPassword.tsx:10` |
| `ResetPassword` | Reads `token` from the query string with `useSearchParams` and never renders it. Both password fields are `PasswordInput`. Posts `{ token, new_password }` — the confirmation value stays client-side. On `204` it creates **no session** and navigates to `/login` with `replace` plus a `{ passwordReset: true }` marker. | `frontend/src/pages/ResetPassword.tsx:16` |
| `Settings` | Guarded surface with two headed groups separated by a solid `<hr>`: **Your account** (read-only email/role, change-password trigger with inline success, activity disclosure) and **Leave this organisation** (destructive copy and delete trigger). | `frontend/src/pages/Settings.tsx:18` |
| `Settings` — account group | Inline read-only identity in a `<dl>` — `AccountDetails` was folded in. Email and role render `ValuePlaceholder` skeleton bars until `user` arrives so the finished page shape draws immediately and never shifts as the profile loads. | `frontend/src/pages/Settings.tsx:44` |
| `Settings` — leaving section | The second group is always mounted: explanation, a `settings-leave-trigger` that stays `disabled` until `user` is known, and a `ConfirmByTyping` rendered only when `user` is non-null, gated on `user.email`. `handleLeave()` reads `readApiError(err)` and shows the last-admin refusal only on `409` + `last_admin`, a generic retry message otherwise; the dialog stays open on both, so the still-live confirm button *is* the retry. | `frontend/src/pages/Settings.tsx:101` |
| `PasswordDialog` | Owns the change-password form — three `PasswordInput` fields — and its client/server error routing inside the shared small `DialogShell`. Success clears the three secrets, closes the modal and leaves an inline confirmation on Settings; submitting locks dismissal and removes Cancel. | `frontend/src/pages/settings/PasswordDialog.tsx:22` |
| `PasswordInput` | Shared password field: `Input` plus a ghost icon button whose `EyeMark` SVG toggles `type` between `password` and `text`. Accessible name flips `Show password` ↔ `Hide password`; each field toggles independently and reveal state resets when a dialog remounts. Used on Login, AcceptInvite, ResetPassword and `PasswordDialog`. | `frontend/src/components/ui/password-input.tsx:24` |
| `Disclosure` | Shared controlled Radix `Collapsible` for expandable information: link-styled button, rotating caret, generated content id and force-mounted content hidden while closed. Settings Activity is its first caller. | `frontend/src/components/Disclosure.tsx:13` |
| `ConfirmByTyping` | The shared type-to-confirm modal, rendered inside `DialogShell` (which owns the portal, overlay, panel and focus restore) so this file holds only the gate. `expectedValue` is both the gate and the prompt that serves as the input's `<label htmlFor>`. The confirming button's greyed state is owned by the component — derived from the typed value and its own in-flight flag, never a caller-supplied variant — so both call sites behave identically. Everything else in the dialog stays live; Cancel is *absent* while submitting. The typed value is cleared explicitly when `open` goes true — the component outlives the dialog Radix unmounts, so the gate would otherwise hold only on the first open. The Users screen is now the second caller and passes the **target's** address as `expectedValue` — the only difference from Settings, which passes the caller's own. | `frontend/src/components/ConfirmByTyping.tsx:23` |
| `matchesExpected` | Module-local, `trim()` + `toLowerCase()` on both sides: the account identity in this system is `lower(email)` (ADR-017 §1), so case and stray whitespace do not defeat a correct address. | `frontend/src/components/ConfirmByTyping.tsx:19` |
| `DialogShell` | The chrome every modal shares: `Dialog.Root`/`Portal`/`Overlay`/`Content`, the panel class string with a `size` of `sm` (`max-w-sm`) or `md` (`max-w-md`, default), the `locked` guard that blocks overlay/Escape/Cancel dismissal while a request is in flight, and the focus save/restore. `testId` names the content node so each caller keeps its own `data-testid`; the optional `initialFocusRef` moves opening focus to a confirm button. All four modals — `ConfirmByTyping`, `RoleChangeDialog`, `RevokeDialog`, `InviteDialog` — render through it, so the dismissal and focus rules cannot drift per dialog. Bodies and footers stay with the caller: the confirm buttons differ in type, variant and disabled condition. | `frontend/src/components/DialogShell.tsx:18` |
| `AcceptInvite` | One TanStack Query keyed `['invite','lookup',token]`, `retry: false`, enabled only when the token is non-empty **and** status is `anonymous`. A single derived `view` ladder picks among dead / signed-in / loading / lookup-error / ready. Both password fields are `PasswordInput`. Accepts with `{ token, password }` and lands on Home via `acceptInvitation`. | `frontend/src/pages/AcceptInvite.tsx:23` |
| `Home` | Three page `useState`s and one `useHome()` call. Loading and error return early; the other three states share **one** shell and one `HomeSidePanels` mount, switching only the attention column: blank (first-run), clear (title, no table), pending (title, notices, paged attention table). No `showAttentionBlock` guard — `AttentionTable` omits the table when empty and `Pagination` returns null on a single page. | `frontend/src/pages/Home.tsx:34` |
| `Scans` | SCAN LIST at `/scans`. `page` in component state (not the URL). Always sends `sort_by=timestamp&sort_order=desc`. Owns the query, columns and copy; the error → skeleton → blank → table+pagination ladder is `ListSurface`'s (see [tables](./tables.md)). Unfinished/failed rows dash Hosts/Findings/Highest; completed rows show the neutral Completed pill. Blank state carries `FirstScanCta` + `FirstScanNote`. Headings are not sortable. | `frontend/src/pages/Scans.tsx:9` |
| `scanListColumns` / `hostListColumns` | Column defs for the run log and the inventory; `hostListColumns` is typed `DataTableColumn<HostSummary, HostSortBy>`, so only real API sort keys can be marked sortable. Unfinished count hiding lives in [scan-status](./scan-status.md). | `frontend/src/pages/scans/scanListColumns.tsx:42`, `frontend/src/pages/hosts/hostListColumns.tsx:13` |
| `scanFindingColumns()` / `hostFindingColumns()` / `portColumns` | Shared column builders. Findings name the machine by `host_hostname`, then address, and show `first_seen_at`. Ports are typed `HostPort` with `Last seen`. | `frontend/src/pages/scans/findingColumns.tsx`, `frontend/src/pages/hosts/portColumns.tsx` |
| `ScanDetail` | One `getScan` read through `readDetailState` (see [host-detail](./host-detail.md)) handed straight to `ReadDetailGate`, which owns notFound / error / loading. The screen's own body starts at `ready` and branches failed (operator sentence, no tables) → unfinished (`Check again` refetch, no `refetchInterval`) → completed empty findings (sentence, hosts table still) → findings worst-first plus hosts. `?finding=` seeds the open row. | `frontend/src/pages/ScanDetail.tsx:15` |
| `FindingsTable` | The **one** findings surface. `variant: 'scan' | 'host'` picks the column set: `'scan'` has a Machine column and no Severity; `'host'` has Severity and no Machine. No `hosts` prop. `isPending` renders the skeleton body ahead of the empty check, so a pending section never claims "No findings"; `testId` / `caption` carry the per-screen strings. Sorts worst-first and opens `FindingPanel` in an expand row. | `frontend/src/pages/scans/FindingsTable.tsx:22` |
| `FindingPanel` | In-place finding body (description, recommendation, evidence, references, CVSS). Default export reused verbatim by host detail. | `frontend/src/pages/scans/FindingPanel.tsx:135` |
| `Network` | NETWORK INVENTORY at `/network`. Owns `page`/`quietPage`/`isQuietOpen`/`sortBy`/`sortOrder`. Reads the active `listHosts` page; the group's `content` is `QuietMachineGroup`. `quietPage` stays here because the table remounts the group whenever the active list loads; closing the group resets it to 1. Group header count is `quiet_total` from the active response. Columns: Type (unsortable), vulnerability count (first click `desc`), not Vendor/Services. Quiet is 7 days, server-side. | `frontend/src/pages/Network.tsx:23` |
| `QuietMachineGroup` | The open "Not seen recently" group: its own `group: 'quiet'` query (mounted only while open), `network-quiet-loading` skeleton, error row with Retry, muted rows via `hostListColumns(now, true)`, and the `Quiet machine pages` pager. Page number comes from `Network`. | `frontend/src/pages/hosts/QuietMachineGroup.tsx:35` |
| `HostDetail` | One `getHost` read through `readDetailState` into `ReadDetailGate` at `/network/:hostId`. Identity shows vendor, classified `machine_type`, and open-port count; ports are `HostPort` with Last seen. `backTo="/network"`. | `frontend/src/pages/HostDetail.tsx` |
| `HostFindings` | The findings section's own query and own three states, so a failed or pending findings read leaves identity, ports and history standing. Shares `FindingsTable` with scan detail. | `frontend/src/pages/hosts/HostFindings.tsx:11` |
| `Devices` / `DeviceDetail` | Device list at `/devices` and scan trigger at `/devices/:agentId`. See [devices-screen](./devices-screen.md). | `frontend/src/pages/Devices.tsx:13` |
| `FirstScanCta` / `FirstScanNote` | Admin link to `/devices` (`first-scan-cta`) and viewer line (`first-scan-note`) for Home, Scans and Network blank states. `FirstScanNote` reads `useSession()` for the inverse guard. | `frontend/src/components/FirstScanCta.tsx:6` |
| `DataTable` / `ListSurface` / `ReadDetailGate` / `Pagination` / `EmptyState` / `NotFoundNotice` / `EmptyMark` / `SeverityWord` / `LoadingSkeleton` | Shared table and page-state set — see [tables](./tables.md). | `frontend/src/components/DataTable.tsx:104` |
| `Users` | The admin org directory at `/users`, nested under `RequireAdmin`. Switches over [directory](./directory.md)'s `useOrgDirectory()` and renders exactly one of loading / blank / error / ready, holds the pending state for all four dialogs, and raises the toast on each row action's success. | `frontend/src/pages/Users.tsx:24` |
| `DirectoryTable` | Five columns, **four** headings — Person · Role · Status · Last seen — with the fifth header carrying `sr-only` text for the actions cell. One `<tr>` per person; members before invites, never interleaved. No row navigates anywhere: there is no per-person detail screen to navigate to. | `frontend/src/pages/users/DirectoryTable.tsx:179` |
| `RoleCell` | Single early return: an invite row or the caller's own row renders `row-role-text-{id}` as plain text, everyone else gets the Radix `Select` at `row-role-{id}`. The two testids are mutually exclusive by construction. The trigger is stripped to `h-auto rounded-none border-0 px-0 py-0`, leaving only the chevron: a bordered trigger indented its value relative to the plain-text rows, so the Role column read as two different left edges. | `frontend/src/pages/users/DirectoryTable.tsx:35` |
| `RoleChangeDialog` | Single-click confirm naming the person and the new role, with per-direction body copy. No text input. Carries **no** copy for `self_target` or `last_admin` — neither refusal is reachable from this screen, so both stay backend guards. Heading copy reads the shared `ROLE_NOUN`, so the dialog and the toast name a role identically. | `frontend/src/pages/users/RoleChangeDialog.tsx:21` |
| Own row | Marked only by what it **lacks** — no Remove button, no role dropdown — plus the `user-row-self` testid. It carries no "you" label: the Person cell is the address and nothing else, so every row in the column starts the same way. | `frontend/src/pages/users/DirectoryTable.tsx:108` |
| `RemoveMemberDialog` | A thin wrapper over the shared `ConfirmByTyping`, passing the **target's** email as `expectedValue`. Adds no props to the shared component. | `frontend/src/pages/users/RemoveMemberDialog.tsx:11` |
| `RevokeDialog` | Single-click confirm naming the invited address — deliberately *not* a `ConfirmByTyping`: nothing is destroyed but an unused token, the invitee has no account yet, and a fresh invite can be issued at once. | `frontend/src/pages/users/RevokeDialog.tsx:14` |
| `InviteDialog` | The invite form (Viewer preselected) at `size="sm"`, then the created state carrying the one-time link. The role options read plainly — `Viewer`, `Admin` — with what each one can do moved into `invite-role-note` above the control, at `text-caption-md` and wired as its `aria-describedby`. Sentence-long option labels made the listbox the widest thing in the dialog and put the explanation somewhere it could only be read one line at a time. Owns its own `createInvite` call because it needs the response to build that link. Branches on `status` **and** `code` via `readApiError`, so `400 email_already_member` and `409 invite_already_pending` read differently. | `frontend/src/pages/users/InviteDialog.tsx:40` |
| `inviteLink()` / `expiryPhrase()` | The link is assembled **client-side** as `${window.location.origin}/invite?token=${token}` — `InviteCreatedResponse` carries `{ invite_token, expires_at }` and no URL. The expiry sentence is computed from `expires_at`, never a hardcoded TTL. | `frontend/src/pages/users/InviteDialog.tsx:232` |
| `ToastProvider` / `useToast` | The app's one transient-confirmation channel: `show(message)` renders a single `data-testid="toast"`, a second `show()` **replaces** rather than queues, it self-dismisses after 5s, and a "Dismiss" control closes it early. Mounted once in `AppShell`, so the public auth screens raise none. The context lives in its own module for Fast Refresh, exactly as `SessionContext.ts` does. | `frontend/src/components/Toast.tsx:11` |
| `PageHeader` | A title, optional `subtitle`, and a rule. Presentational only. | `frontend/src/components/PageHeader.tsx:9` |
| `ui/select.tsx` | The shadcn-shaped wrapper over Radix `Select` — `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`, and nothing more. Its first and only caller is the role cell. | `frontend/src/components/ui/select.tsx:1` |
| `NotFound` | `That page doesn't exist.` plus a real `Go to Home` **link**, inside the shell. | `frontend/src/pages/NotFound.tsx:3` |
| `Verdict` | Title from `review_count` plus last-scan `Timestamp`. Clear and pending are both left-aligned. | `frontend/src/pages/home/Verdict.tsx:11` |
| `AttentionNotices` | Prints `notices[].text` verbatim. `failed_scan` → `home-item-scan`; `stale_coverage` → `home-item-coverage`. | `frontend/src/pages/home/AttentionNotices.tsx:18` |
| `AttentionTable` | Findings table plus `Pagination` labelled `Attention pages`. Machine cell is `host_hostname` → `host_ip` → `EmptyMark`; no extra host fetch. | `frontend/src/pages/home/AttentionTable.tsx` |
| `HomeFeedPanel` | The one feed-panel chrome: card `section`, heading, blank `<p>`, `<ul>`, `Pagination`. Derives the panel DOM `id` and every test id from `testId`, so `#home-events-panel` / `#home-activity-panel` — which `Home.test.tsx` selects on — keep working. Exports `HOME_PANEL_CHROME`, which Home's loading skeleton reuses so the card class cannot drift. | `frontend/src/pages/home/HomeFeedPanel.tsx:21` |
| `EventsPanel` / `ActivityPanel` | Row rendering only, inside `HomeFeedPanel`: verbatim `text` rows, Activity adding a `Timestamp` cell. Labels `Events pages` / `Activity pages`. | `frontend/src/pages/home/EventsPanel.tsx:14`, `frontend/src/pages/home/ActivityPanel.tsx:16` |
| `HomeSidePanels` | Two-column Events and Activity cards. | `frontend/src/pages/home/HomeSidePanels.tsx:16` |
| `HomeBlank` / `HomeError` | First-run copy (`No scans yet` + body sentence), `FirstScanCta` + `FirstScanNote`; error copy + `[Try again]`. | `frontend/src/pages/home/HomeBlank.tsx:3` |
| `Timestamp` / `formatTimestamp` | Relative inside 7 days, absolute beyond, exact value in `title`. | `frontend/src/components/Timestamp.tsx:21` |
| `SeverityWord` | Severity as semibold text (`Critical`, `High`, …). Null renders `EmptyMark`. Replaces `SeverityBadge`. | `frontend/src/components/SeverityWord.tsx:13` |
| `isQuietHost()` / `weeksSinceLastSeen()` | Pure helpers for machines not seen in 14+ days. Drive Network's quiet group and muted row tone. | `frontend/src/lib/hostLastSeen.ts:10` |

## How it connects

- `Home` consumes [review](./review.md)'s `useHome()`; device list and detail consume
  [devices-screen](./devices-screen.md)'s `useScanCommand()`. `Users`
  consumes [directory](./directory.md)'s `useOrgDirectory()` and the six org calls in [api](./api.md).
  Scan/network screens consume [api](./api.md), [tables](./tables.md) and [scan-status](./scan-status.md);
  `HostDetail` consumes [host-detail](./host-detail.md).
  `Login`, `TopBar`, `AcceptInvite` and `Settings` consume [auth](./auth.md)'s `useSession()` —
  `Settings` for `user` and `deleteAccount`, and `TopBar` by way of `AdminOnly`.
  `ForgotPassword` and `ResetPassword` call [api](./api.md) directly and touch the session layer not
  at all; `PasswordDialog` owns Settings' direct `changePassword()` call.
- Both shells are mounted from [app](./app.md)'s route table.
- Visual tokens come from `src/index.css`, and authored source is checked by
  [linting](./linting.md); both follow [docs/ui/FOUNDATIONS.md](../../../docs/ui/FOUNDATIONS.md).

## Notes / gotchas

- **Home loading is a skeleton**, `data-testid="home-loading"`: attention-shaped bars plus two
  panel cards. Scan and host **tables** still use [tables](./tables.md)'s `LoadingSkeleton`
  under live headings.
- **Blank and all-clear are distinct states** and are never collapsed.
- **Navigation is permanently centred on the frame, not in leftover space.** `TopBar` uses the
  named `grid-cols-bar` utility (`1fr auto 1fr`), so unequal wordmark and Log out widths cannot
  move the nav off the frame's centre line.
- **Buttons carry an explicit `cursor-pointer`.** Tailwind v4's preflight sets `cursor: default` on
  `<button>` (changed from v3), so without it every button in the app shows an arrow. The class is
  a local addition to the vendored shadcn `buttonVariants` base and would be lost if the shadcn CLI
  re-adds the component; a comment in `ui/button.tsx` records why it is there.
- **Attention paging is server-side.** `AttentionTable` renders the current snapshot page and
  `Pagination`; changing page refetches `GET /home` with a new `attention_page`. Rows still
  link out to scan detail.
- **Error regions are rendered always, empty when clean.** An `aria-live`/`role="alert"` region must
  pre-exist in the DOM to be announced; a conditionally-mounted error is silent to a screen reader.
  Every auth form follows this. On Login the 401 and network messages are distinct and name neither
  field.
- **Message lifetime is uniform across the auth forms.** Every message clears at the *top of the
  submit handler* and never on typing, so a settled error or success line survives the user editing
  the field it refers to. Each form also guards duplicate submits inside the handler rather than by
  unmounting the control.
- **Dead is not the same as failed.** `ResetPassword` and `AcceptInvite` both distinguish a terminal
  dead token (absent token, or a `410` carrying the matching error code) — one state, no retry
  control, because only a new link or a new invite can help — from a network/`5xx` failure, which is
  a *different*, retryable state. Presenting the latter as dead would strand a user whose link is
  fine.
- **`AcceptInvite` never shows the invited address.** The lookup response's `email` is typed contract
  data that is neither rendered nor echoed back: `AcceptInviteRequest` is `additionalProperties:
  false` (spec 027 dropped the field), so sending it returns `422`. The screen has no email input.
  Its password form is not mounted until lookup succeeds, so a `410` cannot flash a form.
- **An authenticated visitor cannot accept an invite.** Acceptance returns a fresh session, so
  letting one through would silently re-identify and possibly demote them. That branch issues zero
  lookup and zero accept requests — leaving the invitation untouched — and offers `signOut`.
- **Wrong current password never ends the session.** On Settings it is contractually a `400`, so it
  renders as a field error with no refresh, no logout and no navigation.
- **Activity disclosure is information, not a preference.** Settings nests the shared `Disclosure`
  inside the account group — label `What's recorded about me?`, no section heading of its own —
  with persistent force-mounted content. There is no opt-out or pointer-hover dependency.
- **Password reveal is local and ephemeral.** `PasswordInput` owns per-field reveal state; closing
  `PasswordDialog` remounts the fields hidden. The composite's `data-slot="password-input"` wrapper
  scopes browser reveal suppression (`::-ms-reveal`, `::-webkit-credentials-auto-fill-button`) so
  only these fields hide the native control — plain `Input` fields are untouched.
- **Settings loads as a whole shape.** Skeleton bars stand in for email and role until `user`
  arrives; the delete trigger stays `disabled` until then. The leave section and headings always
  render — only the confirm dialog waits on a non-null `user`.
- The role-invariance sweep (`TopBar.test.tsx`, repeated across every Home state) asserts
  `queryAllByRole(...)` elements are `toBeEnabled()` with no `aria-disabled` — never a
  `container.querySelectorAll('[disabled]')` sweep, which misses `fieldset[disabled]` inheritance
  and `aria-disabled` and violates Testing Library's `no-container`/`no-node-access` rules.
- **Absent, not disabled — and the one sanctioned exception.** `ConfirmByTyping`'s confirm button
  is genuinely `disabled` until the typed address matches, and again while the request is in
  flight. That is not a "you may not do this" statement — it reports the person's own progress and
  the product's own work — so it is excluded from the absent-not-disabled sweep by `data-testid`,
  while every other element in the dialog stays live. Cancel, by contrast, is *absent* while
  submitting rather than disabled.
- **Closing the dialog does not reset the typed value on its own.** Radix unmounts
  `Dialog.Content`, but `ConfirmByTyping` sits beside the trigger in its caller and stays mounted,
  so `typed` survives a dismissal. The component clears it on the false → true edge of `open`,
  using the `wasOpen` render-phase mirror rather than an effect — `react-hooks` errors on
  `setState` inside an effect, and the field has to be empty on the reopened dialog's first
  render. Drop the reset and a cancelled attempt reopens with the address prefilled and the
  destructive action already live, so the typing gate holds only the first time. Pinned by the
  "reopens clean after a dismissal" test.
- **Radix hijacks the modal's focus restore.** `DialogContentModal` unconditionally
  `preventDefault()`s `onCloseAutoFocus` and focuses `context.triggerRef` itself. Every modal here
  is fully controlled and renders no `Dialog.Trigger`, so that ref is always `null` and focus would
  land on `document.body` on every dismissal. `DialogShell` therefore restores focus itself, guarded
  on `isConnected` so a trigger unmounted by the success navigation is skipped. **jsdom cannot
  reproduce Radix's deferred restore**, so no Vitest test guards this: deleting the handler leaves
  the suite green. Only a real-browser run would catch its removal — do not remove it on the
  strength of a green suite. It now lives in one place precisely because a green suite cannot
  defend four copies of it.
- **The leaving copy names no organization.** A member's profile is `{ user_id, email, role }` and
  carries no organization name; the copy is generic by design and no lookup was added for it.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/DESIGN.md](../../../specs/020-frontend-vertical-slice-login-home/DESIGN.md)
[2] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[3] [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md)
[4] [specs/028-frontend-public-auth-surfaces/DESIGN.md](../../../specs/028-frontend-public-auth-surfaces/DESIGN.md)
[5] [specs/028-frontend-public-auth-surfaces/ARCHITECTURE.md](../../../specs/028-frontend-public-auth-surfaces/ARCHITECTURE.md)
[6] [specs/030-users-invites-admin-api](../../../specs/030-users-invites-admin-api/TRUTH.md)
[7] [specs/033-settings-leave-organization](../../../specs/033-settings-leave-organization/TRUTH.md)
[8] [docs/adr/ADR-017-account-removal.md](../../../docs/adr/ADR-017-account-removal.md)
[9] [specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md](../../../specs/039-frontend-scans-hosts-read-surfaces/TRUTH.md)
[10] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
- **Column widths are declared as shares, never as pixels.** A `<colgroup>` assigns percentages
  summing to 100 — below `sm` 30·15·20·25·10, at `sm` and up 35·15·20·20·10 — so every column is a
  fraction of whatever the table currently is and the row scales with the shell. Person yields
  share on narrow viewports, where Last seen would otherwise clip `Not recorded yet`. `table-fixed`
  otherwise splits five columns evenly, which gave the actions cell a `size="xs"` button plus most
  of a column of dead space while Person truncated addresses that would have fitted. Pixel widths
  were rejected: the four content columns need roughly 60–176px, the table's own range is only
  ~320–720px, and fixed widths that fit at 720 overflow the shell at 320. `<colgroup>` carries no
  ARIA role, so the `getAllByRole('rowgroup')[1]` lookups still resolve to `<tbody>`.
- **Every row is locked to `h-8`, and nothing in a cell may exceed it.** `h-8` on a `<tr>` is a
  *minimum*, not a cap, so the constraint holds only because each cell keeps its content short:
  `text-caption-md` (0.75rem, the smallest token in the scale), `truncate` on the four content
  cells, and row actions at `size="xs"` (`h-6`). The role `Select` was the real offender — its
  default `h-8` trigger plus border sat exactly at the row height and pushed past it. Raise any of
  these and rows stop matching each other, which is the one thing this table must not do.
- **Truncation is visual only, so `title` is the whole tooltip story.** The Person and Status cells
  carry `title`, and the full value is still the cell's text content — a screen reader reads it
  whole regardless of the ellipsis. A Radix `Tooltip` would add a provider, a portal and jsdom
  stubs to restate what the DOM already says.
- **The Users table sizes to the 720px shell, not DESIGN's 1120px column.** `AppShell`'s `<main>`
  caps content at `max-w-[45rem]`, and a child cannot exceed it; widening it would also widen Home
  and Settings. Left as-is when spec 034 shipped — an open item for a human decision, not a bug in
  the table.
- **The role `Select` is controlled by server state.** Its `value` is `row.role` straight from the
  query, never mirrored into `useState`. That is what makes cancelling a role change free: nothing
  local was ever changed, so nothing has to be rolled back.
- **Radix `Select` needs jsdom stubs.** `hasPointerCapture`, `setPointerCapture`,
  `releasePointerCapture` and `scrollIntoView` are unimplemented in jsdom and are stubbed in
  `src/test/setup.ts`. Without them any `user.click` inside a Radix `Select` or `Toast` throws.
  Tests open a dropdown by clicking the trigger then the option — `userEvent.selectOptions` does not
  work on Radix, which renders a listbox rather than a native `<select>`.
- **Invite success raises no toast**, alone among the screen's four actions: the created state
  already holds the one-time link, and a toast over it would compete with the thing the admin has to
  copy before it disappears.
- **The dialog chrome is extracted; the dialog bodies are not.** Four modals had grown identical
  portal/overlay/panel markup, dismissal locking and focus save/restore, so that layer moved into
  `DialogShell`. What stayed with each caller is what genuinely differs: `ConfirmByTyping` submits a
  form gated on a typed value, `InviteDialog` is a two-state form whose button label is a three-way
  ternary, and `RoleChangeDialog`/`RevokeDialog` are single-click confirms. A further `ConfirmDialog`
  over those last two would have exactly two users and would fold together copy that reads
  differently on purpose — revisit if a third single-click confirm appears.
