# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-08-27

* **Update**: `frontend/tables.md`, `frontend/host-detail.md`, `frontend/screens.md`,
  `frontend/api.md`, `frontend/overview.md`, `frontend/index.md` — PR #128 third review pass. New
  `components/ReadDetailGate.tsx` takes a `DetailState<T>` and owns notFound / error / loading for
  both detail screens, so `ScanDetail` and `HostDetail` render only the ready view (the scan
  failed/unfinished split stays in `ScanDetail` — domain, not read state). `useHostDetail` now
  returns `DetailState<HostDetail>` instead of a second hand-written union. New
  `components/EmptyMark.tsx` replaces the seven copies of a local `dash()`. Host sorting moved off
  the nested `last_seen_at` ternary onto `HOST_SORT_DEFAULT_ORDER`, a per-column default-order map
  in `api/hosts.ts` (replacing `HOST_LIST_DEFAULT_SORT`); ARCHITECTURE §2.3 now documents that
  rule.
* **Update**: `frontend/tables.md`, `frontend/host-detail.md`, `frontend/screens.md`,
  `frontend/overview.md`, `frontend/index.md` — PR #128 second review pass. New
  `components/ListSurface.tsx` (the one list-page state machine, shared by Scans and Hosts),
  `components/NotFoundNotice.tsx` (the shared detail 404 block) and `lib/detailState.ts`
  (`readDetailState`, used by `ScanDetail` and by `useHostDetail`). `HostFindingsTable.tsx`
  **deleted** — `FindingsTable` now serves both screens. `DataTable` link rows became a single
  stretched anchor (no row `onClick`, no `useNavigate`), its columns and `sort` are generic over a
  `SortKey`, and its expand effect fires on a closed→open transition, focusing the caret only on
  the `?finding=` deep link's first render.
* **Update**: `frontend/screens.md`, `frontend/scan-status.md`, `frontend/tables.md` — PR #128
  review pass: `ScanRow.tsx`/`HostRow.tsx` renamed to `scanListColumns.tsx`/`hostListColumns.tsx`;
  new shared `findingColumns(hostColumn?)` and `portColumns` builders behind both findings and both
  ports tables. `getLatestScanByQuery` now typed `Partial<ListScansQuery>`; findings MSW handler
  ANDs its filters. Corrected the stale `scanListColumns` `path:line` ref.
* **Update**: `frontend/tables.md` — `DataTableColumn` gains `align: 'right'` (heading and cell
  together); the alignment convention and the findings tables' severity-last column order from the
  2026-08-27 screen review; stale `path:line` refs for `DataTable`, `DataTableRowAction` and
  `StatusPill` corrected.

## 2026-08-26

* **Creation**: `frontend/tables.md`, `frontend/scan-status.md`, `frontend/host-detail.md` — DMI-88
  shared `DataTable` set, status/severity helpers, and the host-detail read union.
* **Update**: `frontend/screens.md`, `frontend/app.md`, `frontend/api.md`, `frontend/overview.md`,
  `frontend/review.md`, `frontend/index.md`, root `index.md` and `overview.md` — scan/host/agent
  routes, prefix `queryKeys`, list/detail API wrappers, TopBar without `end` on Scans/Hosts, and
  the fetch-free Agents page. Home still has no loading skeleton; table screens do.

## 2026-08-25

* **Update**: `backend/routers.md`, `backend/schemas.md`, `backend/services.md` and `contracts.md`
  — DMI-100 gave `GET /api/v1/hosts` `sort_by`/`sort_order`. Re-pinned `read_hosts`/`read_host` and
  every `services/read.py` entry point to their shifted lines, added the `_HOST_SORT_COLUMNS` row,
  rewrote the "sort params are specific to scans/findings" gotcha, added the `HostSortBy` alias to
  the schema summary, and recorded two seams: `sort_by=ip` casts to `INET` and so is Postgres-only,
  and the contract-fidelity gate now covers `/api/v1/hosts` with a named `UNIMPLEMENTED_PARAMS`
  exemption for the deliberately unimplemented `q`.

* **Creation**: `infra/pi-simulator.md` — DMI-111's ephemeral full-wire harness: local Postgres,
  migration and seed jobs, real API/worker/agent, fixed Docker bridge and Samba target, plus the
  connect-only deployed mode. The map pins the root command dispatcher and each compose/image/seed
  file, the intentional lack of a PowerShell twin, capability and port requirements, ignored
  secrets, destructive `stop`, and the throwaway-org boundary.
* **Update**: `infra/deployment.md`, `infra/index.md` and root `index.md` — linked the dedicated
  simulator concept from the existing install/Railway map and added its frontmatter description to
  both indexes. `overview.md` now distinguishes the real-container software path from the still
  missing physical/operational Pi work.
* **Update**: `hardware-agent/daemon.md`, `command-channel.md`, `normalize.md`, `scanner/nmap.md`
  and their affected indexes — documented safe upload outcome logs, connection/loss visibility,
  shell-quoted Nmap argv plus failed stderr, and host-scoped SMB signing/SMBv1 extraction with null
  ports. Re-pinned changed symbol references, refreshed every edited timestamp/description, quoted
  one pre-existing colon-bearing transport description so its YAML parses, and repaired the
  deployment map's repo-doc citation depth.

## 2026-08-23

* **Update**: `backend/auth.md` — DMI-108. `ResendMailer` now posts a **`multipart/alternative`**
  message: `_send` carries an `html` field beside the unchanged `text`, so the doc's "plain-text
  message" claim is gone. Added rows for the new `INVITE_BODY_HTML` / `RESET_BODY_HTML` constants
  (bare semantic markup — paragraphs and one anchor whose visible text is the full URL; no
  `<table>`, `<img>`, `<link>`, colour or tracking pixel, because marketing-shaped HTML is itself a
  spam signal). Every `services/mailer.py` line reference shifted when the constants landed and was
  re-pinned. Noted that `invite_link()` / `reset_link()` are called once per send, so the two parts
  cannot carry different URLs.
* **Update**: `contracts/openapi/openapi.yaml` + the generated `frontend/src/types/openapi.d.ts` —
  the `Set-Cookie-Refresh` description and both cookie examples still documented `SameSite=None`.
  DMI-108 moved the refresh cookie back to `Lax`, so the contract was stale in three places. The
  `.d.ts` was edited to match rather than regenerated: `frontend/node_modules` is not installed in
  this worktree and `npx openapi-typescript` failed, but the change is one literal token inside a
  doc comment, so `npm run gen:types` should produce an identical file.
* **Note**: `backend/auth.md`'s cookie half (`set_refresh_cookie` / `clear_refresh_cookie`,
  `SameSite=Lax`, the closed ADR-005 deviation) was written by DMI-108 itself and reviewed — this
  run verified it rather than rewriting it.
## 2026-08-22

* **Creation**: `frontend/linting.md` — the repository-local ESLint plugin and its four
  authored-source foundation rules: no arbitrary Tailwind values, no raw framework type sizes,
  the closed spacing scale, and no bare native controls outside shared primitives. The map records
  the static class-string visitor, exact source exemptions, token authority and agent-convention
  connection.
* **Update**: `frontend/overview.md`, `frontend/screens.md`, `frontend/index.md` and root `index.md` — Spec 035's
  named 70rem frame and 24rem form containers, permanent three-column centred navigation,
  vector ornament, details-first Settings page, shared `Disclosure`, extracted `AccountDetails`
  and modal `PasswordDialog`, plus the new linting map and corrected source line references.
* **Update**: `backend/api.md` and `backend/auth.md` — `CORS_ALLOWED_ORIGINS` now defaults to the
  empty string and the middleware turns it into an empty allowlist, so browser access fails closed
  until each environment supplies its trusted origins. `infra/deployment.md`,
  `docs/DEV-SETUP.md` and both root installer mirrors now tell local operators to use the Vite
  origin for both the CORS allowlist and `APP_BASE_URL`.

## 2026-08-21

* **Update**: `frontend/screens.md` + `docs/ui/SCREENS.md` — the own-row " you" marker is gone from
  the Person cell. The design spec had called for "Active · you"; the shipped code had put it after
  the address instead, and it is now dropped in both. Self is identified by the controls the row
  does **not** render — no Remove, no role dropdown — plus the `user-row-self` testid, so the label
  was restating what the row already showed.
* **Update**: `frontend/screens.md` — the Users table declares its column widths in a `<colgroup>`
  as percentage shares, `sm`-responsive: 30·15·20·25·10 below `sm`, 35·15·20·20·10 above, always
  summing to 100. `table-fixed` had been splitting all five evenly, so Actions held a button plus a
  column of dead space while Person truncated. Shares rather than pixels because the table's own
  width range is only ~320–720px — a pixel set that fits the wide end overflows the narrow one.
  `RoleCell`'s trigger also needed an explicit `text-caption-md`: the `ui/select` primitive ships
  `text-body-md`, so stripping the border alone still left the editable roles two sizes larger than
  the plain-text ones in the same column.
* **Update**: `frontend/directory.md` — `mergeDirectory` no longer preserves server order for
  members. `byRoleThenLastSeen` pins admins above viewers, then sorts each group most-recently-seen
  first with never-signed-in last and email breaking a full tie, so the order is total and cannot
  swap between renders. Invites keep server order and still trail every member. The sort runs on a
  copy — the input array belongs to the query cache.
* **Update**: `frontend/screens.md` — the Users table is locked to `h-8` rows at `text-caption-md`,
  the smallest token in the scale. `h-8` on a `<tr>` is a minimum rather than a cap, so the rule
  holds only because every cell truncates and the row actions dropped to `size="xs"`; the role
  `Select` was what broke it. Person and Status carry `title` for the clipped case. `RoleCell`'s
  trigger lost its box (`border-0 px-0 py-0 h-auto`, chevron kept) because a bordered trigger
  indented its value relative to the plain-text rows and split the Role column into two left edges.
  `InviteDialog` moved to `size="sm"` with plain `Viewer`/`Admin` options and the explanation
  relocated to a `text-caption-md` note above the control, wired as `aria-describedby`.
  `DialogShell` grew the `size` prop that made that width change possible.
* **Creation**: `frontend/screens.md` gained `DialogShell` — the chrome all four modals share
  (`Dialog.Root`/`Portal`/`Overlay`/`Content`, the panel class string, the `locked` dismissal guard,
  and the focus save/restore). `ConfirmByTyping`, `RoleChangeDialog`, `RevokeDialog` and
  `InviteDialog` had each grown their own copy; the focus restore in particular is invisible to
  jsdom, so four copies were four places it could rot unobserved. Bodies and footers stayed with the
  callers — their confirm buttons differ in type, variant and disabled condition. The note claiming
  `RevokeDialog`/`RoleChangeDialog` were "deliberately left unextracted" is retired: the chrome was
  extracted, a `ConfirmDialog` over the two bodies still was not.
* **Update**: `frontend/directory.md` — `Role` and `ROLE_NOUN` are now exported from
  `lib/directory.ts`. `ROLE_NOUN` was duplicated verbatim in `Users.tsx` and `RoleChangeDialog.tsx`,
  so the heading and its success toast could name a role differently. Also recorded that the shared
  `['org']` key prefix is load-bearing: every Users mutation now refreshes both lists with one
  `invalidateQueries({ queryKey: ['org'] })` instead of a two-key `Promise.all`.
* **Update**: `frontend/api.md` — MSW handler order is load-bearing where a literal segment collides
  with a parameter: `:userId` also matches `me`, so `DELETE /users/me` has to stay above
  `DELETE /users/:userId` or account deletion silently resolves against the remove-a-member handler.
* **Creation**: `frontend/directory.md` — the org directory model. `DirectoryRow` is the display
  union merging `OrgMember[]` and `PendingInvite[]` (members first, nothing re-sorted, `kind`
  discriminating which fields exist), and `useOrgDirectory()` folds the two list reads into one
  `loading | error | blank | ready` union. **Error is resolved before loading**, so a fast failure
  on one list does not sit behind a slow success on the other.
* **Update**: `frontend/api.md` — six org-administration calls. `listOrgMembers`, `updateUserRole`
  and `deleteUser` join `users.ts`; the new `invites.ts` holds `listPendingInvites`, `createInvite`
  and `revokeInvite`. All import `apiClient` from `./client`, per the standing rule that importing
  `./instances` silently loses authentication. The authenticated invite-admin trio is deliberately
  separate from `auth.ts`'s unauthenticated `lookupInvite`/`acceptInvite`.
* **Update**: `frontend/auth.md` — `RequireAdmin` joins `RequireSession`. It **renders**
  `<NotFound />` in place for a non-admin rather than navigating, so the URL is unchanged and a
  gated route is indistinguishable from a missing one. Both role gates fail closed
  (`user?.role !== 'admin'`) and neither takes a `fallback` or `disabled` prop — the absent props
  are the enforcement mechanism for "absent, not disabled", not a style choice.
* **Update**: `frontend/app.md` — the route table gained a nested `RequireAdmin` segment inside the
  `AppShell` branch holding `/users`, so a refused viewer still sees the top bar.
* **Update**: `frontend/screens.md` — the Users surface: the page, `DirectoryTable` (five columns,
  four headings, members before invites, no row navigation), the four dialogs, `AdminOnly`,
  `PageHeader`, `ui/select.tsx`, and the shared `ToastProvider`/`useToast` mounted once in
  `AppShell`. Two stale claims corrected: `TopBar` **does** now carry a `Users` link (role-gated by
  wrapping, not by branching inside the component), and `ConfirmByTyping`'s "second caller not built
  yet" note is retired — the Users screen is that caller, passing the *target's* address where
  Settings passes the caller's own. Recorded gotchas: the table sizes to the 720px shell rather than
  DESIGN's 1120px column; the role `Select` is controlled by server state with no `useState` mirror;
  Radix `Select`/`Toast` need the jsdom pointer-capture stubs in `src/test/setup.ts`; and invite
  success raises no toast, alone among the screen's four actions.

## 2026-08-18

* **Update**: `backend/auth.md` — cross-site session fixes. The `dmitri_refresh` cookie moved from
  `SameSite=Lax` to `SameSite=None` (`f2836ba`), because `up.railway.app` is a public suffix and
  the SPA (`nspi.`) and API (`api-nspi.`) are therefore separate registrable domains, so a `Lax`
  cookie was never attached to `/auth/*` and refresh always answered 401 in production. The
  `set_refresh_cookie` / `clear_refresh_cookie` row also had the wrong `resource` path — the pair
  lives in `session_response.py:17`, not `routers/auth.py:38`. `NoContentCorsMiddleware` now
  rebuilds the preflight as a bodyless 204 instead of reassigning `status_code` on Starlette's
  `PlainTextResponse("OK", 200)`, which had been shipping `204` with `Content-Length: 2` — legal
  to Chrome and curl, rejected by WebKit, which answered the preflight and then never sent the
  real request. `build_cors_middleware_kwargs` moved to `middleware.py:53`. Two Notes entries
  record both, including the **unresolved conflict with ADR-005**, whose cookie clause still
  specifies `Lax` *ou mais restritivo*.

* **Update**: `frontend/api.md` and `frontend/overview.md` now map the required `VITE_API_URL`
  guard, CI build input, and Railway's Docker/Caddy static deployment.
* **Update**: `infra/deployment.md`, `infra/supabase.md`, `overview.md`, and the root/frontend/
  infra indexes now describe the three-service Railway topology and the frontend's HTTP-only
  relationship to the backend and Supabase.
* **Update**: `frontend/api.md`, `frontend/auth.md`, `frontend/screens.md` and the
  `frontend/index.md` listing for DMI-103 / spec 033 — leaving the organization from Settings.
  `deleteCurrentUser()` (`DELETE /users/me`) joins the users module; the session layer gains
  `deleteAccount()`, which deliberately neither reuses `signOut()` nor catches, so `Settings` can
  discriminate the `409` + `last_admin` refusal on the intact rejection. Settings grows a trailing
  leaving section for both roles, built on the new shared `ConfirmByTyping` modal (Radix `Dialog`,
  case-folded `matchesExpected`, component-owned greyed state). `Login`'s router-state read widens
  to `arrival: 'passwordReset' | 'accountDeleted' | null` over the **single** existing
  `role="status"` region. Three gotchas recorded in `screens.md`: the sanctioned `disabled` on the
  confirming action; the explicit `typed` reset on open, without which a cancelled attempt reopens
  already armed because the component outlives the `Dialog.Content` Radix unmounts (found by
  `/nuke`, 2026-08-18, and pinned by a regression test); and Radix's unconditional
  `onCloseAutoFocus` hijack — which jsdom cannot reproduce, so the component's own focus restore is
  unguarded by the suite.

## 2026-08-13

* **Creation**: `backend/error-codes.md` — maps `api/core/error_codes.py` (DMI-75 / spec 032):
  the closed eight-code `ScanErrorCode` set and the two pure helpers `normalise_error_code` /
  `scan_error_code`.
* **Creation**: `frontend/scan-failure-reasons.md` — maps `frontend/src/lib/scanFailureReasons.ts`,
  the operator copy deck keyed off the generated union; no caller until DMI-88.
* **Update**: `backend/schemas.md`, `backend/services.md`, `backend/api.md`, `contracts.md`,
  and the backend/frontend/`index.md` listings. Scan detail now carries a real `command_id` and a
  derived `error_code` from a read-time command join; the stale sweep writes `device_offline` /
  `agent_disconnected`; `_expire_queued_command` writes `device_offline` too, so both
  `queued → expired` writers record the same reason; inbound `AgentStatusFrame.error_code` stays
  `str | None`.
* **Update**: **delivery retries withdrawn** — `ADR-011` amended (2026-08-13), plus
  `roadmap/BACKEND.md`, `ui/FLOWS.md`, `ui/SCREENS.md`, the `DeviceOfflineError` description in
  `contracts/openapi/openapi.yaml` (types regenerated) and the `deliver()` row in
  `backend/services.md`. The docs claimed "2 delivery retries"; `_DELIVERY_RETRIES` never existed
  in source, and `deliver()` has always made **one** attempt. V1 is one try — the operator
  clicking "Scan now" again is the retry.
* **Update** (`docs/`): frontend contract ask **C10 closed** across `roadmap/BACKEND.md`,
  `ui/FLOWS.md` and `ui/status.md` — the contract publishes `ScanErrorCode` and the backend
  implements it on scan detail; the Scan Detail screen that renders the copy is DMI-88.

## 2026-08-12

* **Update**: **agent read surface and the Pi's target network** (spec 031 / DMI-78) — refreshed
  `backend/routers.md`, `backend/services.md`, `backend/schemas.md`, `backend/models.md`,
  `backend/migrations.md`, `backend/api.md`, `backend/index.md` and `contracts.md`. `GET
  /api/v1/agents` and `GET /api/v1/agents/{agent_id}` now serve the fleet to any authenticated
  caller, org-scoped; admins choose a Pi's network with `PATCH /api/v1/agents/{agent_id}`.
* **Update**: `backend/models.md` and `backend/migrations.md` map revision `20260811_17` and the
  nullable, unindexed `agents.target_subnet`. `online` and `available_subnets` remain **uncolumned**
  — both are read from the in-process connection registry on every request, so `last_seen_at:
  null` means exactly "never connected".
* **Update**: `backend/services.md` maps the new `services/agents.py` (one `_fields` builder behind
  both the list and detail shapes) and the `_claim_agent` check that refuses a scan naming a network
  the Pi is not currently reporting — exact string equality, and silence from the Pi is not
  treated as a contradiction.
* **Update**: `contracts.md` records the three published agent operations, four new schemas, and why
  `AgentOfflineConflict` / `TargetSubnetNotReported` / `ScanSubnetNotReported` must stay three
  separate components.
* **Update** (`docs/`, on the operator's instruction): frontend contract asks **C1 and C2 closed**
  across `roadmap/BACKEND.md`, `roadmap/FRONTEND.md`, `roadmap/PI.md`, `ui/SCREENS.md` and
  `ui/FLOWS.md` — an ask closes when the contract publishes and the backend implements it, not when
  a screen consumes it (that is DMI-89). `adr/ADR-011` no longer says the backend "caches"
  `available_subnets`, and carries a note that DMI-78 delivered the HTTP half it deferred.

## 2026-08-10

* **Update**: **users and invites admin API** (spec 030 / DMI-76) — refreshed
  `backend/auth.md`, `backend/routers.md`, `backend/schemas.md`, `backend/services.md`,
  `backend/errors.md`, `backend/api.md`, `backend/overview.md`, and `backend/index.md`. Admins can
  list org members and pending invites, change another member's role, and revoke a pending invite;
  foreign-org identifiers stay indistinguishable from missing rows.
* **Update**: user activity and migration coverage — `backend/models.md` and
  `backend/migrations.md` now map nullable, unindexed `last_login_at` / `last_seen_at`, the
  login-vs-refresh stamp split, revision `20260810_16`, and the runtime DELETE grant on `invites`.
  `backend/services.md` also maps the per-org transaction advisory lock that serializes
  admin-reducing role changes.
* **Update**: `contracts.md` records the four published admin operations, five new response/request
  schemas, `RoleChangeConflict`, and PATCH in the CORS method set. The hand-authored OpenAPI file
  remains authoritative; FastAPI's generated schema/docs stay disabled.
* **Update**: `frontend/screens.md` records Settings' keyboard-reachable Activity disclosure for
  both roles. Root and component indexes plus `overview.md` were refreshed to match the concept
  frontmatter and current wired state.

## 2026-08-09

* **Update**: **account removal** (spec 029 / DMI-102, ADR-017) — `backend/routers.md`,
  `backend/services.md`, `backend/models.md`, `backend/migrations.md`, `backend/errors.md`,
  `backend/auth.md`, `backend/index.md`, `contracts.md`. Two new routes:
  `DELETE /api/v1/users/me` behind `require_user_row` (any role may leave) and
  `DELETE /api/v1/users/{user_id}` behind `require_admin`. Both `204`, no body, no `Set-Cookie`.
* **Creation**: `backend/src/api/services/users.py` — `LastAdminError`, `count_org_admins`,
  `delete_self`, `delete_member`. Removal is a **hard delete**; the FK cascade added by migration
  `20260808_15` on `refresh_tokens` / `password_reset_tokens` **is** the session teardown, so
  nothing in `services/auth.py` is called and no revocation step exists.
* **Update**: `20260808_15_user_delete_cascade` also grants `DELETE ON public.users` to
  `dmitri_runtime` — `users` is now the second table (after `agent_nonces`) whose grant set differs
  from the append/update-only default, and `RUNTIME_GRANTS_BY_TABLE` had to gain the entry.
* **Update**: two new pinned error codes, both `409` raised literally in `routers/users.py` so the
  contract-fidelity AST scan can see them — `last_admin` and `self_target`. Self-targeting the
  admin route is `409`, deliberately **not** `404`; a foreign-org target stays `404`.
* **Update**: `build_cors_middleware_kwargs` `allow_methods` gained `DELETE`, without which the
  SPA's preflight would be rejected before either route was reached.

## 2026-08-07

* **Update**: the **frontend public auth surfaces** (spec 028) — `frontend/screens.md`,
  `frontend/app.md`, `frontend/api.md`, `frontend/auth.md`, `frontend/overview.md`,
  `frontend/index.md`. Four new screens: `ForgotPassword` and `ResetPassword` (public password
  recovery), `AcceptInvite` (public, consuming spec 027's lookup), and `Settings` (guarded,
  voluntary change-password only — **no profile section**). Routes `/forgot-password`,
  `/reset-password` and `/invite` sit outside `RequireSession`; `/settings` sits inside it.
* **Update**: `SessionProvider` gained `acceptInvitation`, and the post-authentication sequence
  (`setEnabled(true)` → invalidate `['session']` → `navigate('/', { replace: true })`) now exists
  **once** as the private `enterSession()` helper shared with `signIn`. No second context, token
  store or Axios instance. An accepted invite never routes through Login.
* **Creation**: `frontend/src/api/passwords.ts` — `changePassword`, deliberately its own module
  importing `apiClient` from `./client`; folding it into `auth.ts` would either recreate the
  `client.ts` → `auth.ts` cycle or bypass the Bearer and refresh-retry interceptors.
* **Update**: **the top bar's transitional centred nav is gone.** `Settings` is the second nav item,
  so `TopBar` reverted `1fr auto 1fr` to `flex justify-between` with `flex-1` on the nav, exactly as
  the 2026-07-31 note promised. Both roles see both items; there is still no `Users` link. Retire
  any memory of "the nav holds one centred item".
* **Update**: `frontend/overview.md` records two Windows-only environment conditions found during the
  feature — `format:check` failing repo-wide on a CRLF checkout, and the Vitest forks pool being
  unable to spawn workers. Neither is caused by feature code; both are open items.

## 2026-08-06

* **Update**: the **public invite lookup and the address-free acceptance** (DMI-86, spec 027,
  contract ask C14) — `backend/auth.md`, `backend/schemas.md`, `backend/errors.md`,
  `backend/api.md`, `backend/index.md`. New `POST /api/v1/invites/lookup` with **no auth
  dependency of any kind**, backed by a strictly read-only `read_invite()` returning exactly
  `{email, role, org_name}`; expired/accepted/unknown collapse into one `InviteTokenError` and
  reuse acceptance's own `AcceptInviteTokenGone` 410 component, so the two routes cannot drift
  into an enumeration oracle. `POST /api/v1/invites/accept` **no longer takes an address**:
  `accept_invite(session, *, token, password)` re-sources it from `invite.email` for both the
  duplicate check and `validate_policy`. `InviteEmailMismatchError` and the
  `invite_email_mismatch` code are **deleted** — retire that code if you half-remember it.
* **Update**: `backend/api.md` also lost a stale "no Pi client dials the WS channel" caveat that
  the DMI-66 sync missed; it contradicted the standing fact in `MAINTAINING.md`.
* **Creation**: `hardware-agent/daemon.md` and `hardware-agent/command-channel.md` — the Pi agent
  daemon (DMI-66, spec 026). Bare `dmitri agent` now starts `AgentDaemon`: it dials
  `GET /api/v1/agents/{device_id}/commands` over a signed WebSocket, sends a `hello` with its
  currently-enumerated subnets, executes one command at a time through the *existing*
  `run_headless_scan`, and uploads through the *existing* `ScanIngestClient` under the backend's
  `scan_id`. New modules: `transport/signing.py`, `transport/command_channel.py`, `daemon.py`.
* **Update**: **the device end of the link is wired** — `overview.md`, `index.md`,
  `contracts.md`, `MAINTAINING.md`, `hardware-agent/overview.md`, `hardware-agent/index.md`,
  `hardware-agent/transport.md`, `hardware-agent/cli.md`, `hardware-agent/utils.md`,
  `backend/schemas.md`. The long-standing "no Pi daemon posts results / no Pi client dials the WS
  channel (DMI-66)" caveat is **retired everywhere**; the remaining gap is physical (no Pi
  hardware, no service-manager packaging, no key provisioning), not code.

  Six facts worth not re-deriving:

  1. **The daemon is a third front door but not a third runner.** It calls `run_headless_scan`
     unchanged, in an `asyncio.to_thread` worker. No parameter was added to it or to `ScanRunner`,
     so the CLAUDE.md integration rule never fired.
  2. **Ed25519 envelope construction moved** out of `transport/ingest.py` into the shared
     `transport/signing.py`. The ingest `POST` and the WS `GET` upgrade now sign the same canonical
     string shape. Side effect: `ScanIngestClient.__init__` no longer builds the key object, so a
     hand-built bad `IngestConfig` raises on first `submit()` instead of at construction —
     unreachable in production because `load_ingest_config` already gates on 64 hex chars.
  3. **`AvailableSubnet.is_default_route` is now required** in OpenAPI, the backend Pydantic model
     and the generated frontend type. The model stays in Pydantic's **lax** mode like its
     neighbours, so `1` / `"true"` / `"yes"` coerce to bool and are accepted — only genuinely
     non-coercible values are rejected. That was a deliberate consistency call, not an oversight.
  4. **Hello is sent before the replay seam and before the first `recv()`**, on every reconnect,
     with a freshly enumerated list. That ordering is what makes the daemon's pending-status replay
     land after hello and before any newly delivered command.
  5. **The `>= 4000` close-code floor is a placeholder.** DMI-97 owns the concrete
     live-revocation close code; until then every 4xxx close parks. The only 4xxx the backend emits
     today is `4000/replaced`, so nothing over-parks in practice — but replace the floor when
     DMI-97 lands rather than leaving it.
  6. **`_check_nmap()` runs before the daemon module is imported**, so a missing scanner exits `20`
     without ever dialing. Exit `20` is now overloaded on that path (missing nmap *and* invalid
     ingest config), distinguishable only by stderr text.

  `websockets` is now a direct hardware-agent dependency.

## 2026-08-05

* **Creation**: `hardware-agent/transport.md` — the device-side ingest client (DMI-65, spec 025).
  New `agent.transport` package: `load_ingest_config` / `IngestConfig` / `IngestConfigError`,
  `ScanIngestClient`, `SubmissionOutcome`, `SubmissionResult`. It signs the same canonical string
  the backend's [device auth](./backend/device-auth.md) verifies, and is the opposite end of the
  wire from DMI-63's ingest route. Also updated `hardware-agent/overview.md`,
  `hardware-agent/index.md` (new "Upload" section) and `backend/device-auth.md`.
  Three facts worth not re-deriving: the client is **built but called by nothing** — no `src/agent/`
  module imports it, and wiring is DMI-66, so "no upload step yet" is now "no upload *caller* yet";
  the retry loop rebuilds the whole envelope per attempt because the backend burns a verified nonce
  *before* persisting, so reused headers would make a legitimate retry look like a replay `401`; and
  the client does **no file I/O**, taking an in-memory `ScanPayload` so the local artifact is
  untouched by success, failure, or a backend-assigned `scan_id` (applied to a `model_copy` only).
  `httpx` + `cryptography` are now direct hardware-agent dependencies.
* **Update**: `backend/device-auth.md` had a caveat left over from before DMI-63 — it said the HTTP
  `require_agent` adapter was "built but still unmounted". It has been mounted on
  `POST /api/v1/scans` since DMI-63; corrected while adding the DMI-65 cross-link.
* **Update**: **ingest is wired** (DMI-63, spec 024) — `backend/routers.md`, `backend/api.md`,
  `backend/overview.md`, `backend/index.md`, `contracts.md`. `POST /api/v1/scans` is mounted as
  `ingestScan` behind the HTTP `require_agent` adapter, returning the contract's `202`
  `ScanIngestAcceptedResponse`. This retires the long-standing "ingest is contract-defined only"
  caveat that ran through five docs; the remaining gap is now purely the **device** end — no Pi
  daemon posts results yet (DMI-66) — so ingest is exercised by signed test requests. Auth resolves
  **before** body validation (a sub-`Depends` beats body parsing), so an unsigned request with an
  invalid payload is a `401`, not a `422`; the exception is a body that is not valid JSON, which
  fails at decode time and is a `422`.
* **Update**: the ingest schemas took the contract's vocabulary — `backend/schemas.md`,
  `contracts.md`. `ScanResult`→`ScanIngestRequest`, `Host`/`Port`/`Finding`→
  `HostPayload`/`PortPayload`/`FindingPayload`, `ScanIngestResponse`→`ScanIngestAcceptedResponse`
  (plus a required `status: "accepted"`). `extra="forbid"` now applies at **every** ingest depth, so
  a nested unknown field like `hosts[0].os` is refused instead of silently dropped. The rename is
  load-bearing, not cosmetic: `scan.py` deliberately keeps **no** class named `Port`, because the
  short-name collision with `read.Port` made FastAPI mangle a published component to
  `api__schemas__scan__Port`. The contract's correction was a *new* ingest-only `PortPayload`
  component (`Port` plus `cpes`) with `HostPayload.ports` re-pointed at it — `Port` itself stayed
  byte-identical, since the read responses still fingerprint through it.
* **Deletion**: the artifact concept is gone end to end — `backend/models.md`, `backend/schemas.md`,
  `backend/migrations.md`, `contracts.md`. `ArtifactRecord`/`artifacts`, `Artifact`, `ArtifactKind`,
  `ScanResult.artifacts`, `PersistedArtifact` and `PersistedScanDetail.artifacts` all removed; the
  agent never populated them. An `artifacts` key in an ingest body is now a `422`.
* **Update**: `persist_scan` was reworked into an authenticated, atomic ingest — `backend/services.md`.
  New `ingest_scan` owns the authorisation and lifecycle rules (fill a requested placeholder, create
  an unrequested scan, refuse a foreign or written-off one) and `persist_scan` took the keyword
  signature `(session, scan, *, org_id, agent_id, command, now)`. Idempotency **moved up** into
  `ingest_scan`, which now checks ownership *first* — a foreign agent replaying a known `scan_id`
  gets a `403`, where the old early-return made it a silent no-op. Every write is `flush()`ed to a
  single commit point, so ingest is genuinely all-or-nothing.
* **Creation**: revision `20260804_14` (`scan_ingest_rework`) — `backend/migrations.md`,
  `backend/models.md`. Adds nullable `scans.agent_id` (FK → `agents.id`, no backfill) and drops
  `artifacts` with its owned `artifacts_id_seq`; the downgrade recreates the table exactly as the
  baseline declared it. Recorded the trap it exposed: a migration test that seeds through an **ORM
  model** while pinned at an older revision breaks the moment a later migration adds a column —
  `agent_id` broke `test_finding_severity_migration.py` this way. Seed with explicit `sa.text()`
  INSERTs naming only the columns that exist at that revision.
* **Update**: documented `test_contract_fidelity.py`'s comparator — `contracts.md`. `SCHEMA_NAMES`
  gained the five ingest components (a name is only listable once a mounted route makes it reachable
  from `app.openapi()`), and `_property_shape` now treats `type: [X, "null"]` ≡
  `anyOf: [X, {type: null}]` and `const: v` ≡ `enum: [v]`. Noted the standing blind spot: it reads
  neither `minLength` nor `maxLength`, so a changed `constr(min_length=…)` goes uncaught.

## 2026-08-03

* **Update**: `read_hosts`'s paging defaults stopped being written twice — `backend/routers.md`,
  `backend/services.md`. `services/read.py` exports `DEFAULT_PAGE = 1` / `DEFAULT_PER_PAGE = 20` and
  `routers/hosts.py` imports them into its `Query(...)` declarations, so the route's advertised
  default and the service's fallback can no longer drift apart silently — a mismatch would page
  differently depending on whether the caller omitted the param or another caller invoked the
  service directly. Behaviour is unchanged (`1`/`20` either way); `read_scans`/`read_findings` keep
  their inline literals, since their services take no defaults. Also re-synced the five drifted
  `services/read.py` line refs in `backend/services.md` (`get_host_detail` and below were four
  lines stale before this change, seven after it).
* **Update**: `dmitri_runtime` now **converges** instead of merely existing — `backend/migrations.md`.
  The baseline's role statement gained an `ELSE ALTER ROLE dmitri_runtime WITH LOGIN BYPASSRLS`.
  Checking only `IF NOT EXISTS` meant a pre-existing role kept whatever attributes it had, and since
  RLS is `ENABLE`d on every application table with **no policy anywhere**, a role without
  `BYPASSRLS` is denied every read and write — so migrations reported success against a database the
  app could not write to. Surfaced as an order-dependent failure in
  `test_runtime_role_allows_engine_work_and_rejects_privilege_expansion` (the test before it creates
  the role bare), which is why it passed in isolation. The `ALTER` names only `LOGIN` and
  `BYPASSRLS`: naming `NOSUPERUSER` even to clear it requires the executor to be `SUPERUSER`, which
  the migration runner is not under Supabase. Pinned by an `rolbypassrls` assertion in
  `test_live_migration_tolerates_preexisting_runtime_role`. Backend suite: 665 passed, 0 skipped.
* **Update**: index listings for `backend/migrations` re-synced to its frontmatter description
  ("eleven revisions" → "thirteen") in `index.md` and `backend/index.md`.
* **Update**: auth + invite error codes pinned, and the invite token left the URL (DMI-77, spec
  023) — `backend/auth.md`, `backend/errors.md`, `backend/schemas.md` and `contracts.md`.
  **Codes:** reset-password, accept-invite and create-invite join change-password in raising
  `ApiError` with a pinned `error.code`; ten codes across seven `components/responses` entries,
  replacing the `bad_request` default that made *"your link is dead"* and *"your password is too
  weak"* indistinguishable to the SPA. **Statuses split:** a dead reset token is now `410` (was
  `400`), matching accept-invite; re-inviting an address that already holds a live invite is `409`.
  **Token relocated:** `POST /api/v1/invites/{token}/accept` → `POST /api/v1/invites/accept` with
  the token in the body — as a path parameter it was written to access logs by uvicorn's default
  logger and any edge proxy. `invite_link()` moved to the query form to match `reset_link()`.
  **New guard:** `test_contract_fidelity.py` now AST-extracts each route's `code=` literals and
  asserts exact set equality against the contract enums, so a typo can no longer ship green.
  **New concurrency guard:** `create_invite` takes a `pg_advisory_xact_lock` before its checks —
  `Invite.role` is per-row, so two racing invites with different roles let the invitee choose their
  own privilege. No migration and no partial index (the predicate is not IMMUTABLE and nothing
  sweeps expired invites).
* **Update**: IPv4 narrowing threaded to the agent side — `hardware-agent/normalize.md`'s
  `HostPayload`/`FindingPayload` rows now read `IPv4Address` (was `IPvAnyAddress`) and note the
  nullable `mac`/`ip`. Both ends of the ingest contract agree again: the backend began rejecting
  IPv6 with a 422, so leaving the emitter on `IPvAnyAddress` would have turned an unreachable
  mismatch into a lost scan submission at HTTP time rather than a clean error at normalize time.
  Line refs shifted by one from the new `ipaddress` import.
* **Update**: read-path link fields + nullability landed (DMI-85) — `backend/schemas.md` records
  three changes to `schemas/read.py` and `schemas/scan.py`. **IPv4 only:** every address field is
  now `IPv4Address` rather than `IPvAnyAddress`, matching the contract's long-standing
  `format: ipv4` and the IPv4-only `SubnetCIDR` regex; ingest rejects an IPv6 host or finding with a
  422. **`mac` is required-but-nullable** on `ScanHostView`/`HostSummary`/`HostDetailResponse` — a
  routed host has no MAC, and the previous non-nullable `constr` meant any such host 500'd on
  `GET /hosts`. **Collection fields lost their `default_factory`** (`ports`, `scan_history`,
  `hosts`, `findings`): the service always passes them, and a default made FastAPI publish them as
  optional, which weakened the generated frontend types. `contracts.md` gains the matching
  `required`/nullability paragraph plus a note on what `test_contract_fidelity.py` does and does
  not guard — `/api/v1/hosts` query params stay unguarded until DMI-100 implements
  `sort_by`/`sort_order`. Line refs in both `read.py` and `scan.py` tables shifted by one from the
  new `ipaddress` import.

## 2026-08-02

* **Update**: `GET /hosts` paging landed (DMI-84) — `backend/routers.md`'s `read_hosts()` row now
  records the `page`/`per_page` query params, and the "`read_hosts` still ignores contract
  `page`/`per_page`" gotcha is **gone**: all three list routes now declare the same
  `Query(1, ge=1)` / `Query(20, ge=1, le=100)` constraints, so out-of-range paging is refused with a
  422 rather than clamped. `backend/services.md`'s `list_hosts()` row gains the `HostRecord.id`
  tie-breaker after `last_seen_at desc` (stable paging under tied timestamps, matching what
  `list_scans` already did). Also repaired drifted `path:line` refs in both tables — every
  `services/read.py` ref and the four router refs were stale by 1–22 lines.
* **Update**: transactional email landed (DMI-71) — `backend/auth.md`'s `Mailer` row rewritten: the
  `LogMailer` dev stand-in is **gone**, replaced by `ResendMailer` (plain-text POST to the Resend
  API, failures swallowed into a token-free `logger.error`), `NullMailer` for the unset-key case,
  `BackgroundMailer`, the `invite_link`/`reset_link` builders, and `get_mailer(tasks)`. Tokens still
  cross the service boundary raw; the mailer is now the one place a token becomes a URL, via
  `APP_BASE_URL`. Two new gotchas: the no-enumeration guarantee now covers **timing** (the send is a
  background task, so response latency no longer reveals whether mail went out, and the request's DB
  session is released before the provider is called), and email is best-effort — a Resend outage
  costs an email, never an invite.
* **Update**: `backend/api.md` — six new `Settings` fields (`RESEND_API_KEY`, `RESEND_API_BASE_URL`,
  `MAIL_FROM`, `MAIL_REPLY_TO`, `MAIL_TIMEOUT_SECONDS`, `APP_BASE_URL`), and an unset `RESEND_API_KEY`
  recorded as a supported production state rather than a boot failure.
* **Update**: `backend/management.md` — dropped the stale "`LogMailer` still logs the token on the
  HTTP invite path" risk, which DMI-71 resolved, and recorded why `_SilentMailer` is still not
  redundant with the new `NullMailer` (deliberate silence vs unconfigured).

## 2026-07-31

* **Update**: post-DMI-64 cleanup — `MAINTAINING.md`'s "current vs target state" standing fact
  rewritten (the backend is no longer "working code but nothing calls it"; ingest and the Pi daemon
  are the two remaining gaps), `backend/api.md` (`command_running_timeout_seconds` deleted from
  `Settings` — it had no consumer), `backend/services.md` (`apply_status` gains an
  `AND scan_id IS NOT NULL` predicate and `deliver` a zero-rowcount rollback, closing both races in
  the delivery `await` window; recorded that D9's "rank resolves the early-`running` race" claim is
  inaccurate once D1's CHECK exists).
* **Update**: backend command channel wired end to end (spec 022 / DMI-64) — `backend/services.md`
  (new `commands.py` rows for `enqueue`/`active_command_for`/`apply_status`/`sweep_stale_commands`/
  `deliver`, new `agent_presence.py` rows, `command_lifecycle`'s pairwise `_LEGAL_EDGES` replaced by
  `status_rank`/`is_terminal`, `agent_ws` now takes a session **factory** and opens one session per
  frame in a threadpool, `run_worker_once` sweeps before enriching; the "schema-only / not-yet-wired"
  notes are gone and are replaced by notes on owner-split transitions, silent zero-rowcount,
  written-not-derived staleness, and connection-loss rather than elapsed-time timeouts),
  `backend/routers.md` (`POST /agents/{id}/commands`, `GET /commands/{id}`, presence calls on the WS
  handler; 403-not-404 and the shared 409 body), `backend/models.md` (`commands.scan_id` nullable
  under `CHECK (scan_id IS NOT NULL OR status IN ('queued','expired'))`, the partial unique index,
  `agents.connected_at`), `backend/migrations.md` (rev `20260731_13`; the baseline's `CREATE ROLE`
  guard and why cluster-scoped roles vs database-scoped migrations made the whole DB suite skip),
  `backend/schemas.md` (new `schemas/commands.py` section; optional `scan_id`), `backend/api.md`
  (startup `reconcile_all`, the commands router, the two new settings — and that
  `command_running_timeout_seconds` has no consumer), `backend/index.md` and `contracts.md`. `apiClient`/
  `authClient` were documented at `client.ts:7`/`:9`; they are created in `instances.ts`, which the
  doc did not mention at all. The recorded "deliberate lazy circular import" between `client.ts` and
  `auth.ts` no longer exists. Both errors sat over a **live bug**: `users`/`scans`/`findings`
  imported `apiClient` from `instances.ts`, so nothing in the app imported `client.ts`, the
  interceptors were never attached, and every authenticated request in the browser 401'd while the
  suite stayed green (the only importer of `./client` was its own test). Fixed in code; the import
  direction and the isolation the guard test needs are now both recorded.
* **Update**: `frontend/overview.md` (`src/api/` layout row split `instances.ts` from `client.ts`;
  `agents.ts` + its MSW handler deleted as unused), `frontend/review.md` (`useQueries` over
  `HOME_SEVERITIES`; `skipToken` replaces `enabled` + the `scanId as string` cast),
  `frontend/screens.md` (`TopBar` three-track grid centring its lone nav item — transitional, see
  SCREENS.md §App shell; `cursor-pointer` added to the vendored shadcn button base because Tailwind
  v4 preflight sets `cursor: default`).
* **Update**: `backend/api.md`, `backend/schemas.md`, `backend/models.md` — `Severity` and
  `SEVERITY_ORDER` moved from `schemas/read.py` to a new dependency-free `core/severity.py`, so the
  model layer spells the `ck_findings_severity` constraint without importing the schema layer above
  it. Importers updated in `models/persistence.py`, `services/read.py`, `services/hosts.py`,
  `routers/findings.py`.

## 2026-07-29

* **Creation**: `frontend/auth.md` (SessionProvider / useSession / RequireSession),
  `frontend/review.md` (`deriveReview` + `useHomeReview`), `frontend/screens.md` (Login, Home,
  NotFound, the two shells, top bar, shared components).
* **Update**: spec 020 frontend vertical slice login → Home — the SPA is no longer stub-only.
  `frontend/overview.md` (real screens, light-only token layer, the blocked `GET /agents/{id}`
  read), `frontend/api.md` (`authEvents` replaces the hard `window.location` redirect; new
  `users`/`scans`/`findings`/`agents` read modules), `frontend/app.md` (rewritten: provider nest +
  route table only, no session state), `frontend/index.md`. Notable seams recorded: the boot
  refresh is a query, not an Effect (StrictMode × rotating refresh token); sign-out cannot use a
  bare `queryClient.clear()` while the `['session']` observer is live; end-stop deck arrows are
  absent rather than disabled.

## 2026-07-27

* **Update**: spec 021 (DMI-82) scan list + finding filters — `GET /api/v1/scans`
  (`list_scans`, `ScanSummary`/`ScanListResponse`), widened `GET /api/v1/findings`
  (`severity`/`scan_id` filters, stable `FindingRecord.id` paging), `ck_findings_severity`
  migration, `SEVERITY_ORDER` promotion, `test_contract_fidelity.py`. Updated
  `backend/routers.md`, `services.md`, `schemas.md`, `models.md`, `migrations.md`, `log.md`.
  Pre-push follow-up (nuke): `SEVERITY_ORDER` moved from `services/hosts.py` to
  `schemas/read.py`, derived from the `Severity` literal — `models/persistence.py` had been
  importing a *service* to build its check constraint, whose import cycle forced deferred
  model imports and an untyped `scan_record` param in `hosts.py`; both reverted. Migration
  `20260727_12` no longer imports `api.*` (a revision is frozen history), with a drift test
  in `test_finding_severity_migration.py`. `list_scans`/`list_findings` now take
  `ScanStatus`/`Severity` instead of `str`. `test_read_service.py` split — scan-list cases to
  `test_read_service_scans.py`, shared builders to `tests/read_factories.py`.
* **Update**: spec 019 (DMI-72) `GET /users/me` + global error envelope — `errors.py`
  (`ApiError`, `_DEFAULT_CODES_BY_STATUS`), global `StarletteHTTPException` + `Exception`
  handlers in `main.py`, WS denial envelope, C13 change-password codes, `routers/users.py`,
  `schemas/users.py`, contract + `openapi.d.ts` updates. Created `backend/errors.md`; updated
  `backend/api.md`, `routers.md`, `schemas.md`, `auth.md`, `index.md`.
  Pre-push follow-up: `http_exception_handler` now forwards `exc.headers` (the router's `405`
  had lost its RFC-required `Allow`); `validation_exception_handler` pulls `422` into the
  envelope and stops pydantic echoing the rejected password back via `input`; `errors.py` gained
  `error_envelope`/`field_path` and lost the underscore on `DEFAULT_CODES_BY_STATUS`; the four
  pinned-code responses in `openapi.yaml` gained `required:` so their `code` discriminator
  actually narrows in the generated TS.
* **Update**: spec 018 (DMI-62) agent WebSocket command channel — `routers/agents.py`
  (`connect_agent_commands`), `services/agent_connections.py` (in-process registry),
  `services/agent_ws.py` (frame dispatch), `schemas/agent_frames.py`, `require_agent_ws` adapter,
  `main.py` WS validation→403 handler, `websockets>=13` dependency. Updated
  `backend/routers.md`, `services.md`, `schemas.md`, `device-auth.md`, `api.md`, `index.md`.
  Device gate now mounted on WS; HTTP `require_agent` still unmounted; no command delivery yet.
* **Creation**: `backend/device-auth.md` — the spec 017 (DMI-61) device gate: Ed25519 canonical-string
  signing (`services/device_sig.py`, the repo's only `cryptography` importer), insert-or-replay nonce
  handling (`services/nonces.py`), and the transport-agnostic `authenticate_agent` core with its thin
  `require_agent` HTTP adapter (`dependencies/agent_auth.py`). Records the 8-step order, the
  403-for-revoked / 401-for-everything-else split, and the accepted "a burned nonce is not rolled
  back" property that DMI-62/63 must build against.
* **Creation**: `backend/management.md` — the two operator CLIs (`backend-bootstrap-org`,
  `backend-provision-agent`), including why `bootstrap_org` passes a local `_SilentMailer` rather than
  `LogMailer` (the raw admin invite token must never reach a log stream).
* **Update**: `backend/auth.md` — `require_admin` + `ROLE_ADMIN`/`ROLE_VIEWER`, the extracted
  `issue_session` / `login_response` / `set_refresh_cookie` seams, `Mailer.send_invite_link`, the
  invite service and routes, the error→status map (400/410/403), and three new gotchas: why
  `refresh_session` cannot reuse `issue_session` (refresh-token family semantics), the asymmetric
  two-scope duplicate rule, and same-commit `consumed_at` atomicity.
* **Update**: `backend/routers.md` — the four read routes now carry `Depends(require_user)` and pass
  `org_id=caller.org_id`; foreign rows are 404 not 403; `host_id` is not a tenant escape.
* **Update**: `backend/services.md` — `read.py`'s four entry points take a required keyword-only
  `org_id`, both count and page queries are scoped, and a `NULL org_id` row is visible to nobody.
* **Update**: `backend/migrations.md` — revisions `20260724_09` (`agent_nonces`), `_10`
  (`ix_users_email`, global email uniqueness), `_11` (`agents.public_key` replacing the three secret
  columns). Corrected the standing "no `DELETE` grant" note: `agent_nonces` is the deliberate
  exception (`SELECT/INSERT/DELETE`, no `UPDATE`).
* **Update**: `backend/models.md` (`AgentNonce`, `Agent.public_key` replacing the secret columns,
  global user-email uniqueness, `Invite` no longer dormant), `backend/schemas.md` (`schemas/invites.py`
  and why `extra="forbid"` is load-bearing), `backend/api.md` (`DEVICE_SIG_MAX_SKEW_SECONDS`,
  `INVITE_TTL_HOURS`), `backend/overview.md` + `backend/index.md` ("read path + auth + invites wired").
* Standing fact updated: the `orgs`/`invites` half of the "identity dormant" note is now wired.
  Ingest remains unwired, and the device gate is built but mounted on no route.

## 2026-07-24

* **Creation**: `backend/auth.md` — the spec 016 (DMI-60) auth subsystem, now wired in `main.py`:
  the 6 auth routes (`routers/auth.py`, `dmitri_refresh` cookie), the auth services (`auth.py`
  orchestration, `tokens.py` JWT + rotating refresh families, `passwords.py` argon2 + policy +
  HIBP screen, `mailer.py` seam), the `require_user` dependency (`dependencies/auth.py`), and the
  app middleware (`middleware.py` — `RequestIdMiddleware`, `NoContentCorsMiddleware` 204 preflight).
* **Update**: threaded auth through the neighboring docs — `models.md` (new `session.py`:
  `RefreshToken`/`refresh_tokens`, `PasswordResetToken`/`password_reset_tokens`; auth no longer <!-- pragma: allowlist secret -->
  dormant), `migrations.md` (rev `20260722_07_auth_sessions`), `schemas.md` (`schemas/auth.py`
  request/response models), `api.md` (required `JWT_SIGNING_SECRET` + the seven auth `Settings`
  fields, middleware + auth-router wiring in `main.py`), `services.md`/`routers.md` cross-links,
  `overview.md` + `index.md` ("read path + auth wired"). Standing fact updated: the auth half of
  the "identity dormant" note is now wired; `orgs`/`invites` and the ingest route remain unwired.

## 2026-07-23

* **Update**: Documented spec 016's command-channel data model (DMI-59) — schema + lifecycle only,
  not yet wired. New `backend/src/api/models/command.py` (`Agent`→`agents` with the AES-256-GCM
  recoverable-secret columns `secret_ciphertext`/`secret_nonce`/`secret_key_version`, `revoked_at`
  tombstone, `last_seen_at`; `Command`→`commands` with the 1:1 `scan_id` UNIQUE FK, VARCHAR `status`,
  four timestamps) — added to `backend/models.md`. New pure `services/command_lifecycle.py`
  (`next_status`, `scan_status_for`, `InvalidCommandTransition`) — added to `backend/services.md`.
  New migration `20260723_07_command_channel.py` (agents + commands with the RLS/revoke/grant fence)
  — added to `backend/migrations.md` (now seven revisions); `env.py` now imports `command`/`identity`
  explicitly. Refreshed `backend/index.md` listings. Cites ADR-011, ADR-015.

## 2026-07-22

* **Update**: Documented spec 015's read path. Backend: three new routers (`hosts.py`, `scans.py`,
  `findings.py`) mounted in `main.py` alongside `GET /api/v1/health` (new `backend/routers.md`
  doc); `services/read.py` (`list_hosts`/`get_host_detail`/`get_scan_detail`/`list_findings`) and
  `schemas/read.py` (nine read-response models, incl. `ScanHostView` with required `host_id` and
  `HostSummary` with `first_seen_at`). Persistence: `DeviceRecord`/`devices` renamed to
  `ScanHostRecord`/`scan_hosts` (a per-scan host observation); new durable `HostRecord`/`hosts`
  table (cross-scan identity, resolved by `services/hosts.py::upsert_hosts_for_scan`, ADR-014);
  `FindingRecord` gained a `finding_id` UUID; `ScanRecord` moved from `target_mode`/`scan_profile`
  to `scan_mode` + `status`. Four chained Alembic migrations (`20260722_03`–`_06`) implement this.
  Updated `backend/models.md`, `backend/schemas.md`, `backend/services.md`, `backend/migrations.md`,
  `backend/api.md`, `backend/overview.md`, `backend/index.md`. Contracts/Pi: ADR-013 retires
  `device`/`Device`/`DevicePayload` from the wire — `ScanIngestRequest.devices`→`hosts`,
  `DevicePayload`→`HostPayload`, `devices_received`→`hosts_received`; the prior `scan_mode` vs
  `target_mode`/`scan_profile` contract divergence is resolved (both sides now use `scan_mode`).
  Updated `contracts.md`, `hardware-agent/normalize.md`, `hardware-agent/scanner/stages.md`,
  `hardware-agent/scanner/runner.md`, `hardware-agent/scanner/models.md`,
  `hardware-agent/scanner/index.md`, `hardware-agent/tui.md`, `hardware-agent/overview.md`, and
  `glossary.md` (new `ScanHost` term; `Device` now "retired" not "deprecated, ingest-only").
  Refreshed `index.md` and `overview.md` at the repo root and `backend/index.md`.
* **Creation**: Added the `frontend/**` code-map section (`overview`, `api`, `app`, `index`) for the
  greenfield SPA scaffold shipped by spec 014 (frontend/): the two-Axios-instance auth client with
  the single-flight 401→refresh interceptor, the in-memory token store, the contract-typed API
  layer, and the boot-refresh + stub login/placeholder UI. Linked from the root `index.md` under a
  new "Frontend (scaffold only)" section; noted the new `frontend` CI job in `.github/workflows/ci.yml`.

## 2026-07-21

* **Update**: Corrected the README scan-modes table (Quick is default top-1000 + `vulners`, not
  `-F`) to match `discovery_arguments()`; removed the now-resolved divergence note from `overview.md`.
* **Initialization**: Created the OKF code-map bundle mapping the whole repo — top-level
  `overview` / `glossary` / `contracts`, the `hardware-agent/**` set (overview, cli, discovery,
  normalize, utils, tui, and the split `scanner/` package), the `backend/**` set (overview, api,
  models, schemas, services, migrations), the `infra/**` set (supabase, deployment), plus
  `MAINTAINING.md` and per-directory `index.md` files.
* **Note**: Corrected the scan-modes table in `overview.md` to match `discovery_arguments()` —
  Quick/Standard use the default top-1000 port set (not `-F`, as the README's product table states).
