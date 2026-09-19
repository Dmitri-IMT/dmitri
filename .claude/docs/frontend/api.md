---
type: Module
title: frontend API layer
description: The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, prefix-shaped query keys, and the read, account and org-administration resource modules.
resource: frontend/src/api/client.ts
tags: [frontend, api, axios, auth, refresh, invites]
timestamp: 2026-09-13T16:40:00Z
---

# frontend API layer

## Purpose

`src/api/` requires `VITE_API_URL` and derives the `/api/v1` base URL from it; it scopes the
refresh cookie to auth requests structurally (two Axios instances), attaches the Bearer token, and
recovers an expired session with exactly one refresh — sharing that single refresh across concurrent
401s. Credential scoping is achieved **solely** by the two-instance split; no interceptor toggles
`withCredentials` by inspecting the URL (approach B from the research doc is deliberately rejected).
On top of that sit the thin, contract-typed read modules the screens call.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `apiClient` | Business Axios instance, `baseURL = ${VITE_API_URL}/api/v1`, with `withCredentials` left at the Axios default (`false`). Created bare; the interceptors are attached to it by `client.ts`. | `frontend/src/api/instances.ts:11` |
| `authClient` | Auth Axios instance, same baseURL, `withCredentials: true`. Carries **no** interceptors — so a refresh call's own 401 cannot recurse. | `frontend/src/api/instances.ts:13` |
| `client.ts` (side effects) | Attaches both interceptors to the shared `apiClient` **at import time**, then re-exports `apiClient`/`authClient`. Importing this module is what arms authentication — see the gotcha below. | `frontend/src/api/client.ts:24` |
| `performRefresh()` | Single-flight refresh: memoizes one in-flight `refresh()` in module-scoped `refreshPromise`; concurrent 401s await the same promise; `.finally` resets it. | `frontend/src/api/client.ts:13` |
| response interceptor | On a 401 for a not-yet-retried request: refresh once (guarded by per-request `_retry`), rewrite the header, retry via `apiClient(config)`; on refresh failure clear the token store and **`emitSessionExpired()`**, no second refresh. | `frontend/src/api/client.ts:44` |
| `onSessionExpired()` / `emitSessionExpired()` | Module-scoped handler `Set` — the seam that lets `client.ts` report an unrecoverable session without importing React or the router. | `frontend/src/api/authEvents.ts:5` |
| `login()` / `refresh()` / `logout()` | Callers of `authClient`, hitting `/auth/login`, `/auth/refresh`, `/auth/logout`. `login`/`refresh` write the returned `access_token` to the store; `logout` clears it. | `frontend/src/api/auth.ts:16` |
| `forgotPassword()` / `resetPassword()` | Thin typed wrappers on `authClient` for `POST /auth/forgot-password` and `POST /auth/reset-password`, both `204`. Neither touches the token store — a completed reset deliberately leaves the visitor signed out. | `frontend/src/api/auth.ts:36` |
| `lookupInvite()` / `acceptInvite()` | `POST /invites/lookup` (non-consuming; returns `org_name`, `role` and an `email` the UI never renders) and `POST /invites/accept` (`201 → LoginResponse`). `acceptInvite` writes `access_token` to the store exactly as `login` does, and posts on `authClient` so the httpOnly refresh cookie is received. | `frontend/src/api/auth.ts:48` |
| `changePassword()` | `POST /auth/change-password` for the voluntary change on Settings. Lives in its **own** module and imports `apiClient` from `./client` — the one authenticated write in the app. | `frontend/src/api/passwords.ts:6` |
| `getAccessToken()` / `setAccessToken()` / `clearAccessToken()` | The in-memory token store over a single module-scoped `let accessToken` — never `localStorage`/`sessionStorage`/cookies/React state. | `frontend/src/api/tokenStore.ts:3` |
| `getCurrentUser()` | `GET /users/me`. The **sole** source of identity and role — nothing decodes a JWT anywhere in the app. | `frontend/src/api/users.ts:6` |
| `deleteCurrentUser()` | `DELETE /users/me`, `204`. The self-service exit from the organization, called only by the session layer's `deleteAccount()`. No body either way, so no type alias. Deleting the account destroys its sessions server-side; the residual refresh cookie is deliberately left alone because it then authenticates nothing. | `frontend/src/api/users.ts:11` |
| `listOrgMembers()` | `GET /users` → `OrgMemberListResponse`. The admin-only org roster behind the Users screen; server-ordered, never re-sorted client-side. | `frontend/src/api/users.ts:21` |
| `updateUserRole(userId, role)` | `PATCH /users/{id}` with an `UpdateUserRoleRequest` body. The backend keeps the `self_target` and `last_admin` guards; neither is reachable from the Users screen, so the UI carries no copy for them. | `frontend/src/api/users.ts:28` |
| `deleteUser(userId)` | `DELETE /users/{id}`, `204` — removing *another* member, as distinct from `deleteCurrentUser()`'s self-exit. | `frontend/src/api/users.ts:37` |
| `listPendingInvites()` / `createInvite()` / `revokeInvite()` | `GET /invites`, `POST /invites` → `InviteCreatedResponse`, `DELETE /invites/{id}`. Thin typed wrappers on `apiClient` in their own module — the authenticated invite-admin half, kept apart from `auth.ts`'s unauthenticated `lookupInvite`/`acceptInvite` pair. | `frontend/src/api/invites.ts:9` |
| `getLatestScan()` / `getLatestSuccessfulScan()` | Two distinct reads (`LATEST_SCAN_QUERY`, and the same plus `status: 'completed'`), each `per_page: 1`. Return `null` on `{ data: [], total: 0 }`; a `404` is **not** treated as "no scans" and propagates as an error. | `frontend/src/api/scans.ts:40` |
| `listScans(params)` | `GET /scans` with required `page`, `per_page`, `sort_by`, `sort_order`. The scan list always sends `SCAN_LIST_SORT` (`timestamp`/`desc`) plus `SCANS_PER_PAGE` 20. | `frontend/src/api/scans.ts:48` |
| `getScan(scanId)` | `GET /scans/{id}` → `ScanDetailResponse` (findings and hosts embedded). Scan detail opens a finding without a second request. | `frontend/src/api/scans.ts:58` |
| `getScanAnalysis` / `requestScanAnalysis` | GET and POST `/scans/{id}/analysis`. See [scan-ai](./scan-ai.md). | `frontend/src/api/scans.ts:66`, `:75` |
| `askScanAI` / `getScanAIChat` | Legacy scan-scoped chat on `/scans/{id}/chat`. Used by `ScanChat` tests only; live UI uses [context-ai](./context-ai.md). | `frontend/src/api/scans.ts:84`, `:95` |
| `getAIUsage` / `askContextAI` / `getContextAIHistory` | Usage dashboard and unified contextual chat. See [ai-usage](./ai-usage.md) and [context-ai](./context-ai.md). | `frontend/src/api/ai.ts:10`, `:18`, `:31` |
| `listHosts(params)` / `getHost(hostId)` | `GET /hosts` with required page/sort/`group` params (`HostGroup`; `HOST_LIST_DEFAULT_SORT_BY` is `last_seen_at`; `HOST_SORT_DEFAULT_ORDER` starts `vulnerability_count` and `last_seen_at` at `desc`, text columns at `asc`); `GET /hosts/{id}` → `HostDetailResponse`. | `frontend/src/api/hosts.ts` |
| `listFindings(params)` | The **one** wrapper on `GET /findings`. `FindingListParams` is a two-member union — `{ scan_id, severity, per_page }` for the home deck, `{ host_id, per_page }` for host detail — so a caller cannot mix filters, and the object handed to the wrapper is the same one handed to the query key. One severity per call (never a list or comma-joined string); returns the **whole envelope** so `total` survives alongside `data`. | `frontend/src/api/findings.ts:26` |
| `FindingListParams` | The exact params sent to `GET /findings`, and the shape `queryKeys.findings.list` takes. `scan_id` stays optional because Home builds its key before the scan id lands; `skipToken` at that one call site is what keeps the unfiltered read unsent. | `frontend/src/api/findings.ts:14` |
| `getHome(pages)` | `GET /home` with the three page integers. Page sizes are server constants mirrored as `HOME_*_PER_PAGE`. | `frontend/src/api/home.ts:16` |
| `HOME_SEVERITIES` | `['critical','high'] as const satisfies readonly Severity[]`. Host-detail findings still load one severity at a time; Home no longer uses this list. | `frontend/src/api/findings.ts:19` |
| `listAgents()` / `getAgent(agentId)` / `updateAgentTargetSubnet(agentId, body)` / `createScanCommand(agentId, body)` | Agents resource module: list for the devices table and Home's first-agent read; PATCH returns full `AgentDetail` (written with `setQueryData`, not refetched); POST creates a scan command with caller-chosen `scan_mode` and the agent's `target_subnet`. | `frontend/src/api/agents.ts:10` |
| `getCommand(commandId)` | `GET /commands/{id}` → `CommandDetail`. Top-level resource, own module. | `frontend/src/api/commands.ts:8` |
| `COMMAND_POLL_INTERVAL_MS` | `5_000` — the Agents command poll interval. | `frontend/src/api/commands.ts:6` |
| `queryKeys` | Prefix-shaped TanStack keys: `home`, `scans`, `hosts`, `findings`, `agents`, `commands`, and `ai` (`ai.usage(limit)`). `home.snapshot(pages)` includes the three page integers. `agents.list()` is a no-arg function; `commands` is a separate top-level group (not nested under `agents`) so agent invalidation does not restart a stopped command poll. **First invalidation call site:** `useScanCommand` sweeps `scans.all`, `hosts.all`, `findings.all`, and `agents.detail` when a followed command reaches `done`. | `frontend/src/api/queryKeys.ts:8` |

## How it connects

- **Import direction is asymmetric and load-bearing.** `instances.ts` is the leaf: it requires a
  non-empty `VITE_API_URL`, creates both Axios objects, and imports nothing else. `client.ts`
  imports the bare instances plus `refresh` from `auth.ts`, and arms the interceptors. The read
  modules (`users`, `scans`, `hosts`, `findings`, `agents`, `commands`) import `apiClient` **from
  `client.ts`**, never from `instances.ts`. `auth.ts` is the one exception — it imports `authClient`
  from `instances.ts`,
  because `client.ts` depends on it and the other direction would be a genuine cycle.
  `passwords.ts` follows the ordinary rule (`./client`) and is deliberately **not** folded into
  `auth.ts`: doing so would either recreate that cycle or leave the change-password call bypassing
  the Bearer and refresh-retry interceptors.
- `emitSessionExpired()` is consumed by [auth](./auth.md)'s `SessionProvider`, which clears the
  token + query cache and navigates to `/login`.
- Home consumes [review](./review.md)'s `useHome()` / `getHome`. Scan/host list
  and detail screens call `listScans` / `getScan` / `listHosts` / `getHost` / `listFindings`
  directly. [devices-screen](./devices-screen.md) calls `agents.ts` and `commands.ts`. The six org
  calls in `users.ts`/`invites.ts` are consumed by [directory](./directory.md)'s
  `useOrgDirectory()` and by the Users screen's four dialogs.
- Consumes the generated types from `src/types/openapi.d.ts` (see [overview](./overview.md)).
- Behavioral proof lives in `src/api/client.test.ts` (one-refresh-on-401, refresh-failure→event,
  concurrent single-flight, cookie scoping) — MSW intercepts at the network layer so these real
  instances run untouched — and in `src/api/authHeader.test.ts`, which proves each read module
  reaches the interceptors *on its own*.

## Notes / gotchas

- **A read module that imports `apiClient` from `instances.ts` silently loses authentication.**
  The interceptors are a side effect of evaluating `client.ts`; if nothing imports that module, no
  `Authorization` header is ever attached and the 401→refresh chain never runs. This shipped
  broken — `users`/`scans`/`findings` all imported `./instances`, and the only importer of
  `./client` was its own test, so the suite stayed green while every authenticated request in the
  browser 401'd. Fixed 2026-07-31; `authHeader.test.ts` guards it.
- **Testing that guard requires module isolation.** `apiClient` is one shared object, so importing
  `./client` anywhere in a test file's graph arms the interceptors for every other module in that
  file. `authHeader.test.ts` therefore calls `vi.resetModules()` and dynamically imports exactly
  one read module per test; a naive version of the same test passes even with the bug present.
  `passwords.ts` has its own case there, added with a `captureAuthorizationPost` sibling helper —
  the original `captureAuthorization` registers `http.get` only, and the three GET cases were left
  unconverted.
- **`400` never reaches the response interceptor.** Both `wrong_current_password` and
  `password_policy_violation` are `400`s, so the change-password failures render as field errors
  with zero refresh calls and no logout. Only a genuine `401` drives the refresh-and-retry chain.
- **No `window.location` anywhere in `src/api/`.** The hard `window.location.href = '/login'` that
  spec 014 used on refresh failure was replaced by the `authEvents` bus, so the redirect is a
  router navigation and the module stays free of React/router imports.
- **All three read modules are typed exclusively from `components['schemas'][...]`.** A hand-written
  request/response interface is an ADR-008 violation even when it is correct today.
- **`VITE_API_URL` is required.** Both `vite.config.ts` and `instances.ts` fail fast when it is
  missing instead of silently defaulting to localhost. CI and the Railway frontend build provide
  explicit values; the deployed bundle therefore targets the intended public API.
- **Path tails are relative to the `/api/v1` baseURL** set in `instances.ts` — never repeat the prefix.
- The MSW `/scans` handler paginates and honours `sort_by`/`sort_order`; `/hosts` does the same
  (replacing the old bare-array `/hosts` handler). `/findings` still branches on `severity` for
  Home. `/agents`, `/agents/:id`, `PATCH /agents/:id`, `POST /agents/:id/commands`, and
  `GET /commands/:id` have default handlers in `mswHandlers.ts`; per-test overrides live in
  `src/test/agentsHarness.ts`. Scan/host fixtures remain in `scansHarness.ts` and `hostsHarness.ts`.
- **MSW handler order is load-bearing where a literal segment collides with a parameter.** `:userId`
  also matches `me`, and MSW resolves the first matching handler, so `DELETE /users/me` must stay
  above `DELETE /users/:userId`. Reversed, account deletion resolves against the remove-a-member
  handler and the failure reads as a wrong status, not a routing mistake. Pinned by a comment at the
  pair rather than a test.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [docs/research/axios-withcredentials-auth-scoping.md](../../../docs/research/axios-withcredentials-auth-scoping.md)
[3] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
