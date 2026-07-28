# ARCHITECTURE — Frontend vertical slice: login → Home (DMI-81)

> **Frontend-layer feature.** Nothing under `hardware-agent/` or `backend/` changes. The
> `CLAUDE.md` integration rule about `ScanRunner` (`scanner/runner.py`) and
> `ScanProgressScreen` (`tui/screens/scan_progress.py`) **does not apply here**: this layer has
> no orchestrator, no `ScanPayload`, no nmap flags, and no Textual screens. The equivalent
> discipline for this layer is that the stack is already locked by
> [`ADR-008`](../../docs/adr/ADR-008-frontend-stack.md) and the *screens* — shell, theme,
> typography, color, viewport, building rules, consistency rules — are locked and **binding**
> by [`docs/ui/SCREENS.md`](../../docs/ui/SCREENS.md) §Foundations. This document does not
> re-decide any of that; it turns those decisions into exact file paths, plus the mechanics
> (router, session context, role gating) that DMI-20 deliberately deferred.
>
> No `INTEGRATION.md`: single layer, frozen contract, no cross-layer contract change.
> `DESIGN.md` (written separately) owns layout, copy, and the accent/severity **hex values**;
> this document owns only the **token names** those hexes will fill.

---

## 0. Two corrections to the inputs, verified against the sources

Both change what the implementer must build. Neither is a judgement call.

1. **`GET /api/v1/scans` *is* in the frozen contract.** `TRUTH.md` line 28 and line 119 state
   that "a scan *list* is not in the frozen contract, so it needs a contract amendment as well
   as an implementation". That is false: `contracts/openapi/openapi.yaml` line 164 defines
   `operationId: listScans` on `/api/v1/scans`, secured by `FrontendBearerAuth`, with
   `Page`/`PerPage`/`ScanStatusFilter`/`ScanSortBy`/`SortOrder` parameters (lines 173–178) and
   a `ScanListResponse` body (line 194, schema at line 1810). **The blocker is a missing backend
   implementation only — no contract amendment is required.** `backend/src/api/routers/scans.py`
   line 16 registers only `GET /api/v1/scans/{scan_id}`. This should be corrected in `TRUTH.md`
   and in the blocking backend feature's scope (it is smaller than TRUTH claims).
2. **`GET /api/v1/users/me` does not return `display_name`.** `UserProfileResponse`
   (`contracts/openapi/openapi.yaml` lines 2208–2226) has exactly three required properties —
   `user_id`, `email`, `role` (`enum: [admin, viewer]`) — with `additionalProperties: false`.
   The backend agrees: `backend/src/api/schemas/users.py` declares only those three fields with
   `extra="forbid"`, and `backend/src/api/routers/users.py` line 16 constructs it from
   `user.id / user.email / user.role`. **Nothing in this feature may render a display name.**
   Where the shell needs to identify the signed-in user, it uses `email`.

---

## 1. System context

```
Pi agent → backend ingest (POST /api/v1/scans) → Postgres
                                   ↓
   frontend SPA (this feature) ← read API /api/v1/... (frozen contract, Bearer)
```

The SPA is a React 19 + TypeScript + Vite client with no server of its own; every byte of data
comes through the contract at [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).
DMI-20 (spec `014-frontend-scaffold`) already built and tested the plumbing this feature stands
on, and none of it is re-litigated here:

- two Axios instances — `apiClient` (Bearer only) and `authClient` (`withCredentials: true`),
  `frontend/src/api/instances.ts` lines 5–7;
- the single-flight 401→refresh interceptor, `frontend/src/api/client.ts` lines 10–49;
- the in-memory token store, `frontend/src/api/tokenStore.ts`;
- `login` / `refresh` / `logout`, `frontend/src/api/auth.ts` lines 8–26;
- contract-generated types, `frontend/src/types/openapi.d.ts` (`npm run gen:types`).

**This feature builds:** React Router v7 (library mode) and the route table, a session context
fed by `GET /users/me`, a session route guard, the `AppShell` top bar (no sidebar), the real
LOGIN screen, the HOME screen with its four designed states, the pure verdict/review-items
derivation, the resource modules and query hooks for Home's reads, the SCREENS.md-compliant
token and font layer, and the tests for all of it.

**This feature does not build:** Scans, Hosts, Agents, Users, Settings, Scan detail, Host
detail (`TRUTH.md` lines 99–110); accept-invite / forgot / reset password; "Scan now"; polling
or websockets; dark mode; tablet/mobile layouts; any backend, contract, or Pi change.

**Nav destinations that do not exist yet.** SCREENS.md §App shell (lines 21–24) fixes the top
bar's items as *Home · Scans · Hosts · Agents · Users · Settings*. Only Home is routed in this
feature. `DESIGN.md` decides whether the unbuilt items render as inert text or are omitted;
this document only fixes that **`Users` is omitted for viewers** (§4) and that no nav item is
rendered `disabled` (SCREENS.md consistency rule 3, line 211).

---

## 2. Data model / contracts

### 2.1 Endpoints consumed

Auth column: `authClient` = credentialed cookie call; `apiClient` = `Authorization: Bearer`.
Status: ✅ implemented in the backend today · ⛔ in the contract but not implemented.

| # | Path | Method | Auth | Request | Response | Error branches the UI handles | Contract | Backend | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/api/v1/auth/login` | POST | `authClient`, `security: []` | `LoginRequest` `{ email, password }` (2178–2190) | `LoginResponse` `{ access_token, token_type: "bearer", expires_in }` (2191–2207) + httpOnly `Set-Cookie` | `401` → "That email and password don't match."; network/`5xx` → "Couldn't reach Dmitri. Try again in a moment." (SCREENS.md lines 350–351). **No other branch** — forced-rotation 403 is void (SCREENS.md lines 324–326) | `openapi.yaml:601` | `routers/auth.py:36` | ✅ |
| 2 | `/api/v1/auth/refresh` | POST | `authClient`, `RefreshCookieAuth` | none | `LoginResponse` + rotated cookie | `401` → no session; boot guard falls through to `/login` | `openapi.yaml:636` | `routers/auth.py:51` | ✅ |
| 3 | `/api/v1/auth/logout` | POST | `authClient`, `RefreshCookieAuth` | none | `204`, cookie cleared | Any failure still clears client state and navigates to `/login` (§5) | `openapi.yaml:670` | `routers/auth.py:68` | ✅ |
| 4 | `/api/v1/users/me` | GET | `apiClient` | none | `UserProfileResponse` `{ user_id, email, role }` (2208–2226) | `401` → interceptor refreshes once, then session failure → `/login`. A failure here is a **session** failure, not a Home data failure | `openapi.yaml:874` | `routers/users.py:12` | ✅ |
| 5 | `/api/v1/scans?per_page=1&sort_by=timestamp&sort_order=desc` | GET | `apiClient` | query only | `ScanListResponse` `{ data: ScanSummary[], total, page }` (1810–1827); `ScanSummary` = `scan_id, timestamp, subnet, scan_mode, status, host_count, finding_count, highest_severity?` (1718–1751) | `data: []` → Home **blank**; `4xx`/`5xx`/network → Home **error** + `[Retry]` | `openapi.yaml:164` | **not registered** — `routers/scans.py:16` has only the detail route | ⛔ |
| 6 | `/api/v1/findings?scan_id={id}&severity=critical` and `&severity=high` | GET | `apiClient` | query only | `FindingListResponse` `{ data: FindingRecord[], total, page }` (2388–2405); `FindingRecord` carries `finding_id, scan_id, severity, title, cve_id?, host_id?, host_ip?, detected_at` (2300–2387) | any failure → Home **error** (a partial verdict is forbidden, `TRUTH.md` line 92) | `openapi.yaml:379`; `ScanIdFilter` 1005, `SeverityFilter` 991 | **partial** — `routers/findings.py:17-22` accepts `host_id` only; `scan_id` and `severity` are silently ignored | ⛔ |
| 7 | `/api/v1/agents/{agent_id}` | GET | `apiClient` | path param | `AgentDetail` `{ agent_id, display_name, online, last_seen_at, active_command_id? }` (2039–2065) | failure → the Pi-status footer line and the stale-coverage item are omitted; it must **not** take the whole page to error (footer is chrome, not the verdict) | `openapi.yaml:526` | **not registered** — `routers/agents.py:17` has only the WebSocket route | ⛔ |
| 8 | `/api/v1/scans/{scan_id}` | GET | `apiClient` | path param | `ScanDetailResponse` (1752–1809) | — | `openapi.yaml:213` | `routers/scans.py:16` | ✅ (not consumed by this feature; scan detail is out of scope — listed because review-item links target `/scans/:scanId`, a route this feature does not build) |

**Two notes on `ScanSummary` (`openapi.yaml:1718-1751`), both binding on the implementer:**

- **The field is `host_count`, not `device_count`.** SCREENS.md §HOME line 632 lists
  `device_count` in Home's context footer; that name predates the B7 device→host rename
  (`docs/roadmap/FRONTEND.md` §Direction, "Host inventory: discovered machines → `/hosts`
  (OpenAPI `/devices` rename per B7)"). The contract has `host_count` (line 1739) and no
  `device_count` anywhere. **Implement against the contract**; SCREENS.md §HOME needs a
  documentation fix (follow-up, not this feature's code).
- **There is no failure-reason field.** `ScanSummary` has `status` (`ScanStatus`, line 1456) and
  nothing describing *why* a scan failed. Home's failed-scan review item can therefore state
  only *that* the last scan didn't finish, with `[See why]` linking to scan detail — exactly the
  copy SCREENS.md line 660 already specifies. Recorded as a **known limitation of the shipped
  screen, not a gap for this feature or the blocking backend feature to fill.**

`LoginResponse` never carries the refresh token (2191–2207) — it lives only in the httpOnly
cookie, and the SPA never reads it. No hand-written type may model any body above; all come
from `frontend/src/types/openapi.d.ts` via `components['schemas'][...]`, the pattern already set
by `frontend/src/api/auth.ts` lines 3–6.

### 2.2 Blocked reads

Home's verdict is a function of three reads; **none is served today**. All three are already
frozen in the contract — `GET /api/v1/scans` (line 164), the `scan_id`/`severity` filters on
`GET /api/v1/findings` (parameters at lines 1005 and 991), and `GET /api/v1/agents/{agent_id}`
(line 526). **Every one of them is an implementation gap in the backend, not a contract gap: no
contract amendment is needed by anyone**, and this feature still touches no backend code.

**Ownership of the blockers (filed 2026-07-27):**
- **DMI-82** — `GET /scans` (list) and the `severity`/`scan_id`/`page`/`per_page` filters on
  `GET /findings`. The two reads Home's verdict actually needs. Blocks this feature.
- **DMI-78** — the whole agents surface, including `GET /agents/{agent_id}` and the missing
  `/agents` collection (contract ask C1). Costs only the Pi-status footer, which `DESIGN.md`
  removes from this feature's build. **Not** a blocker on any acceptance criterion.

This document designs
against the contract shapes and **does not build a fallback, a client-side substitute, or a
mock-backed data path.** Against the current backend, Home's query layer fails and Home renders
its designed error state (`TRUTH.md` AC 15) — that is the specified behaviour, not a workaround.

| Blocked read | What Home needs from it | Nature of the block | Gates |
|---|---|---|---|
| `GET /api/v1/scans` (list) | The latest scan: `timestamp` (verdict recency + footer), `status: failed` (failed-scan review item), `host_count`, `scan_mode`, `finding_count`, `highest_severity` (context sentence), and `scan_id` (to fetch findings). Also `total === 0` → the blank state | **Implementation only.** Contract already defines it (`openapi.yaml:164`, §0.1). Backend must register the route and honour `page/per_page/status/sort_by/sort_order` | AC 9, 10, 11, 12, 13, 15, 16 |
| `GET /api/v1/findings?scan_id=&severity=` | Critical and high findings of the latest scan: `title`, `cve_id`, `host_ip`, `severity` | **Implementation only.** Contract defines both filters (`ScanIdFilter` 1005, `SeverityFilter` 991); `routers/findings.py:17` accepts neither | AC 10, 11 |
| `GET /api/v1/agents/{agent_id}` | `online`, `last_seen_at` for the Pi-status footer and, with the scan timestamp, the stale-coverage item | **Implementation only** for the endpoint (`openapi.yaml:526`); `routers/agents.py` has no HTTP route at all | AC 13 (partially — see below), footer |
| **Agent discovery** | The SPA has no way to learn an `agent_id`: there is **no `/api/v1/agents` collection path anywhere in the contract** (only `/agents/{agent_id}` at 526 and `/agents/{agent_id}/commands` at 429). This is contract ask **C1**, `docs/roadmap/FRONTEND.md` §Direction | **Contract gap, genuinely open.** This document does **not** pick a workaround (no `VITE_AGENT_ID`, no hardcoded UUID, no inference from a scan). The blocking backend feature must either add `GET /agents` or the ambiguity must be resolved before the footer/Pi item is implementable | Pi-status footer; the `online: false` half of AC 13 |

**Consequence for AC 13 (stale coverage).** The 3-day rule (`TRUTH.md` line 44) is computable
from the latest scan's `timestamp` alone and needs **no** agent read. Only the *"The Pi hasn't
been seen since Tuesday."* variant (SCREENS.md line 661) needs `AgentDetail`. Implement the
timestamp-based rule in `src/lib/review.ts`; leave the agent-based one behind the blocked read.

### 2.3 Constants

| Constant | Value | Where |
|---|---|---|
| `STALE_COVERAGE_DAYS` | `3` (`TRUTH.md` line 44) | `frontend/src/lib/review.ts` — the only place the number appears |
| `LATEST_SCAN_QUERY` | `{ per_page: 1, sort_by: 'timestamp', sort_order: 'desc' }` (defaults confirmed at `openapi.yaml:968-978` and `951-960`) | `frontend/src/api/scans.ts` |
| `HOME_SEVERITIES` | `['critical', 'high']` (`TRUTH.md` line 41; SCREENS.md line 647) | `frontend/src/api/findings.ts` |
| Query keys | `['session']`, `['scans','latest']`, `['findings', scanId, severity]`, `['agent', agentId]` | colocated with each hook |
| `VITE_API_URL` | unchanged, `http://localhost:8000` | `frontend/.env.example` |

No new environment variable is introduced.

### 2.4 Decisions this document fixes

**(a) Router — `react-router` v7, library mode.** `frontend/package.json` has **no router
dependency today** (verified: neither `react-router` nor `react-router-dom` appears in
`dependencies`), despite ADR-008 §Roteamento (lines 87–107) naming React Router v7 library
mode. Add exactly one package, **`react-router` (v7)**, as a caret range matching the file's
existing style (e.g. `"react-router": "^7.x"` at the latest 7 minor at install time). Do **not**
install `react-router-dom` — v7 merged it into `react-router`. Do **not** adopt framework mode
(ADR-008 line 93 rejects it explicitly). `BrowserRouter` wraps the app in `src/main.tsx`; the
route table lives in `src/App.tsx` (ADR-008 line 277 permits either `main.tsx` or a dedicated
`routes.tsx`; a 4-entry table does not earn its own file).

**(b) The 401 hard redirect must become router-aware.** `frontend/src/api/client.ts` line 45
does `window.location.href = '/login'`. Under React Router this is a full document reload: it
discards the router history, the TanStack Query cache, and the in-memory token — and it is
already awkward to test (`src/api/client.test.ts` lines 53–57 has to redefine `window.location`).
**Replace it** with a module-level callback so `client.ts` stays free of any React or router
import: a new `frontend/src/api/authEvents.ts` exports `onSessionExpired(handler)` and
`emitSessionExpired()`; `client.ts` line 45 becomes `emitSessionExpired()`; the session provider
registers a handler that calls `navigate('/login', { replace: true })` and clears session state.
`clearAccessToken()` (line 44) stays exactly where it is. `src/api/client.test.ts` must be
updated to assert the emitted event instead of the stubbed `location.href`.

**(c) Fonts — Geist is removed.** `frontend/package.json` depends on
`@fontsource-variable/geist`, imported at `src/index.css` line 4 and bound to `--font-sans` at
line 50. SCREENS.md §Typography (lines 59–80) mandates **IM Fell English** for titles (never
below 16px) and **IBM Plex Mono** for everything else, with **no third face**. Therefore:
remove `@fontsource-variable/geist` from `package.json` and its `@import` from `index.css`; add
`@fontsource/im-fell-english` (regular + italic) and `@fontsource/ibm-plex-mono` (the weights
`DESIGN.md` actually uses). *Open, minor:* whether a variable build of IBM Plex Mono exists on
fontsource — the implementer uses `@fontsource-variable/ibm-plex-mono` if published, otherwise
the static package; this changes the package name only, not the token names. Tokens:
`--font-title: 'IM Fell English', serif` and `--font-mono: 'IBM Plex Mono', monospace` inside
the `@theme inline` block, yielding the `font-title` / `font-mono` utilities. `--font-sans` and
`--font-heading` (`index.css` lines 49–50) are deleted; the base layer's `@apply font-sans`
(line 133) becomes `font-mono`.

**(d) Theme layer — light-only rebuild, shadcn tokens remapped (not deleted).**
`src/index.css` currently ships the shadcn default palette (`:root` lines 8–42), a full `.dark`
block (lines 91–123) and `@custom-variant dark` (line 6). SCREENS.md §Theme (lines 39–57) is
light-only and forbids authoring `dark:` variants. Decisions:

- **Delete** `@custom-variant dark` (line 6) and the entire `.dark` block (lines 91–123). With
  the custom variant gone, a stray `dark:` utility fails to compile — enforcement, not policy.
- **Delete** the chart tokens (lines 28–32, 59–63) — no charts in the MVP (ADR-008 line 214) —
  and the sidebar tokens (lines 34–41, 51–58) — no sidebar (SCREENS.md line 21).
- **Keep and remap** the remaining shadcn semantic tokens rather than replacing them:
  `src/components/ui/button.tsx` and `input.tsx` consume `bg-primary`, `border-input`,
  `text-destructive` etc., so deleting the names breaks the two shadcn components already in the
  repo. Each is redefined in terms of the locked neutrals or an accent/severity token:

  | shadcn token | Redefined as |
  |---|---|
  | `--background` | `--paper` `#FAF8F4` |
  | `--card`, `--popover` | `--card` `#FFFFFF` |
  | `--foreground`, `--card-foreground`, `--popover-foreground` | `--ink` `#1A1917` |
  | `--muted-foreground` | `--ink-muted` `#6B6862` |
  | `--border` | `--rule` `#E5E0D8` (decoration) |
  | `--input`, `--ring` | `--edge` `#8C8880` (control boundary, 3:1 — SCREENS.md lines 104–106) |
  | `--primary`, `--accent` | `--accent` (**hex owned by `DESIGN.md`**) |
  | `--destructive` | `--sev-critical` (**hex owned by `DESIGN.md`**) |

- **Add** the product tokens by name only: `--paper`, `--card`, `--ink`, `--ink-muted`,
  `--rule`, `--edge` (hexes above, locked at SCREENS.md lines 95–102) and `--accent`,
  `--sev-critical`, `--sev-high`, `--sev-medium`, `--sev-low` (**hexes deferred to `DESIGN.md`**,
  SCREENS.md lines 108–143). This document does not pick a single accent or severity hex.
- **Add** the type-scale tokens so the 16px IM Fell floor is enforced by the scale, not by
  memory (SCREENS.md building rule 5, line 178): every `--text-title-*` token resolves to
  ≥ `1rem`; sizes below that exist only as `--text-body-*` / `--text-caption-*` on `font-mono`.
  Exact steps are `DESIGN.md`'s.
- `color-scheme: light` (line 9) stays. No `prefers-color-scheme` branch is added.

**(e) Disposition of every existing file touched.**

| File | Disposition |
|---|---|
| `frontend/src/pages/LoginStub.tsx` | **Deleted**, replaced by `src/pages/Login.tsx` |
| `frontend/src/pages/LoginStub.test.tsx` | **Deleted**, replaced by `src/pages/Login.test.tsx` |
| `frontend/src/pages/SignedInPlaceholder.tsx` | **Deleted**, replaced by `src/pages/Home.tsx` |
| `frontend/src/App.tsx` | **Rewritten.** Its boot refresh + three-way `status` state (lines 7–27) move into `SessionProvider`; `App` becomes the route table only |
| `frontend/src/main.tsx` | **Edited.** Adds `BrowserRouter` and `SessionProvider` around the existing `QueryClientProvider` (lines 11–13) |
| `frontend/src/api/client.ts` | **Edited** — line 45 only (decision (b)). The interceptor logic (lines 10–42) is untouched |
| `frontend/src/api/client.test.ts` | **Edited** — the refresh-failure test's redirect assertion only |
| `frontend/src/api/{instances,auth,tokenStore}.ts` | **Kept unchanged** |
| `frontend/src/index.css` | **Rewritten** per decision (d) |
| `frontend/src/components/ui/{button,input}.tsx` | **Kept**; they inherit the remapped tokens with no edit |
| `frontend/src/test/mswHandlers.ts` | **Edited** — new handlers (§7) |
| `frontend/src/types/openapi.d.ts` | **Unchanged** — the contract does not move |

---

## 3. New files and naming (mandatory)

All paths relative to the repo root. Conventions follow the existing repo: `@/` alias
(`tsconfig.app.json` `paths`, `vitest.config.ts` `resolve.alias`), colocated `*.test.ts(x)`,
default exports for pages/components as in `src/pages/LoginStub.tsx`.

### Routing and app root

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/main.tsx` | touch | `BrowserRouter` → `QueryClientProvider` → `SessionProvider` → `App` |
| `frontend/src/App.tsx` | rewrite | The route table only: `/login` → `Login`; `/` → `RequireSession` → `AppShell` → `Home`; `*` → `<Navigate to="/" replace />`. SCREENS.md specs no 404 screen, so the catch-all redirects rather than inventing one |
| `frontend/src/App.test.tsx` | new | Routing-level tests: guard redirect, boot-refresh no-flash, post-login landing |

### Session and role

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/auth/SessionProvider.tsx` | new | Owns boot silent refresh (`refresh()` from `@/api/auth`), then the `['session']` query over `GET /users/me`; exposes `{ status: 'booting' \| 'authenticated' \| 'anonymous', user, signIn, signOut }`; registers the `onSessionExpired` handler from decision (b) |
| `frontend/src/auth/useSession.ts` | new | `useSession()` hook; throws outside the provider. **The only** way any component reads identity or role |
| `frontend/src/auth/RequireSession.tsx` | new | Route guard. `booting` → renders nothing protected (§5); `anonymous` → `<Navigate to="/login" replace />`; `authenticated` → `<Outlet />` |
| `frontend/src/auth/AdminOnly.tsx` | new | `<AdminOnly>{children}</AdminOnly>` — renders children when `role === 'admin'`, otherwise **`null`**. No `fallback` prop, no `disabled` prop (§4) |
| `frontend/src/auth/SessionProvider.test.tsx` | new | Boot refresh success/failure, `/users/me` wiring, sign-out clearing |
| `frontend/src/auth/AdminOnly.test.tsx` | new | Admin renders children; viewer renders nothing (asserted by absence, not by `disabled`) |
| `frontend/src/api/authEvents.ts` | new | `onSessionExpired(handler)` / `emitSessionExpired()`; module-scoped, no React import |

### API resource modules (`frontend/src/api/`)

Each is a thin function over `apiClient`, typed from `@/types/openapi`, mirroring
`src/api/auth.ts`. Path tails are relative to the `/api/v1` baseURL already set in
`instances.ts` line 3 — never repeat the prefix.

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/api/users.ts` | new | `getCurrentUser(): Promise<UserProfileResponse>` → `GET /users/me` |
| `frontend/src/api/scans.ts` | new | `getLatestScan(): Promise<ScanSummary \| null>` → `GET /scans` with `LATEST_SCAN_QUERY`; returns `null` when `data` is empty ⛔ |
| `frontend/src/api/findings.ts` | new | `listFindings({ scan_id, severity }): Promise<FindingListResponse>` → `GET /findings` ⛔ |
| `frontend/src/api/agents.ts` | new | `getAgent(agentId): Promise<AgentDetail>` → `GET /agents/{agent_id}` ⛔ — **written but not called** until agent discovery (C1) is resolved (§2.2) |

### Query hooks (`frontend/src/hooks/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/hooks/useHomeReview.ts` | new | Composes `getLatestScan` + the two `listFindings` calls via TanStack Query, feeds `deriveReview()`, and returns one discriminated union: `{ state: 'loading' \| 'blank' \| 'clear' \| 'pending' \| 'error', … }` plus a `retry()`. Home renders a `switch` over it, so no partial-data path can leak into the verdict |
| `frontend/src/hooks/useHomeReview.test.ts` | new | MSW-driven state matrix, including the error and retry paths |

### Pure derivation (`frontend/src/lib/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/lib/review.ts` | new | `deriveReview({ latestScan, criticalFindings, highFindings, now })` → verdict + ordered review items. Owns `STALE_COVERAGE_DAYS = 3`, the failed-scan rule, and the critical/high-only filter. No React, no network — the whole verdict logic is unit-testable |
| `frontend/src/lib/review.test.ts` | new | The rule table: all-clear, items pending, medium/low hidden, failed scan, stale coverage, empty history |
| `frontend/src/lib/utils.ts` | keep | Existing `cn()` helper, untouched |

### Shell and shared components (`frontend/src/components/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/components/AppShell.tsx` | new | Inside-shell frame: `<TopBar />` + `<Outlet />` inside the fluid content column (`max-w-*`, never a fixed width — SCREENS.md lines 156–163). **No sidebar** |
| `frontend/src/components/TopBar.tsx` | new | Wordmark left, nav centre, `[Log out]` right. `Users` wrapped in `<AdminOnly>`. `min-w-0` on flex children (SCREENS.md building rule 3) |
| `frontend/src/components/TopBar.test.tsx` | new | Viewer sees no `Users`; admin does; log-out calls `signOut` |
| `frontend/src/components/AuthShell.tsx` | new | Outside-shell frame (SCREENS.md lines 290–311): wordmark + `Ornament` + one centered card in the 720px prose column. No top bar |
| `frontend/src/components/Ornament.tsx` | new | The engraving detail; used by `AuthShell` and Home |
| `frontend/src/components/Timestamp.tsx` | new | Owns consistency rule 7 (relative inside 7 days, absolute beyond, exact value in `title`) |
| `frontend/src/components/Timestamp.test.tsx` | new | Both sides of the 7-day boundary and the `title` attribute |
| `frontend/src/components/SeverityBadge.tsx` | new | Severity → `--sev-*` token; text, so it owes 4.5:1 (SCREENS.md line 127) |
| `frontend/src/components/ui/label.tsx` | new | shadcn `label`, via `npx shadcn@latest add label` — LOGIN needs real `<label>`s for password managers (SCREENS.md lines 308–310) |

### Pages

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/pages/Login.tsx` | new | Real `<form>`, `autocomplete="email"` / `"current-password"`, autofocus, submit on Enter; in-flight button copy; inline error above the button distinguishing 401 from network/`5xx`. Copy from SCREENS.md lines 344–351 via `DESIGN.md`. Redirects to `/` when already authenticated |
| `frontend/src/pages/Login.test.tsx` | new | Replaces `LoginStub.test.tsx` |
| `frontend/src/pages/Home.tsx` | new | Switches on `useHomeReview()`; renders exactly one of the four state components. Never renders a skeleton in the verdict's place (`TRUTH.md` line 45) |
| `frontend/src/pages/Home.test.tsx` | new | The state matrix, role gating, and retry |
| `frontend/src/pages/home/Verdict.tsx` | new | The one-sentence verdict + context sentence (all-clear and items-pending share it) |
| `frontend/src/pages/home/ReviewItemCard.tsx` | new | One square-edged card per item: label, plain sentence, link to where it is dealt with |
| `frontend/src/pages/home/HomeBlank.tsx` | new | First-run copy; `[Run first scan]` wrapped in `<AdminOnly>`; the viewer line rendered only when `role === 'viewer'` |
| `frontend/src/pages/home/HomeError.tsx` | new | "Couldn't load the review." + `[Retry]` |
| `frontend/src/pages/home/HomeFooter.tsx` | new | Muted footer: last-scan line via `Timestamp`; the Pi-status line stays behind the blocked agent read (§2.2) |
| `frontend/src/pages/LoginStub.tsx`, `LoginStub.test.tsx`, `SignedInPlaceholder.tsx` | **delete** | Throwaways from DMI-20 |

### Styling, config, tests

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/index.css` | rewrite | Decisions (c) and (d): font imports, `@theme inline` tokens, locked neutrals, accent/severity token names, type scale; `.dark` and `@custom-variant dark` removed |
| `frontend/package.json` | touch | `+ react-router@^7`, `+ @fontsource/im-fell-english`, `+ @fontsource/ibm-plex-mono`, `− @fontsource-variable/geist`. **No new scripts** — `dev`/`build`/`gen:types`/`lint`/`format:check`/`typecheck`/`test` already exist and are unchanged |
| `frontend/src/test/mswHandlers.ts` | touch | Add `GET /users/me`, `GET /scans`, `GET /findings`, `GET /agents/:agentId` plus exported fixture objects (`adminProfile`, `viewerProfile`, `latestScan`, `criticalFinding`, …). Required: `setup.ts` line 9 runs with `onUnhandledRequest: 'error'`, so any unhandled call fails the test |
| `frontend/src/test/renderWithProviders.tsx` | new | One helper wrapping `MemoryRouter` + a per-test `QueryClient` + `SessionProvider`; used by every component/page test so provider wiring is not duplicated |
| `frontend/src/test/setup.ts` | keep | Unchanged; already clears the token store per test (lines 10–13) |
| `frontend/vitest.config.ts`, `eslint.config.js`, `tsconfig*.json` | keep | No change needed; the `@` alias and jsdom env already cover the new files |
| `.github/workflows/ci.yml` | keep | The `frontend` job from DMI-20 already runs the whole gate; no new step |

No `jwt-decode` (or equivalent) dependency is added — see §4.

---

## 4. Role gating mechanism

**Where the role comes from.** `useSession().user.role`, populated by `GET /users/me`
(`openapi.yaml:874`, `UserProfileResponse.role` enum `admin|viewer` at 2220–2226). **Never from
the access token.** ADR-008 §Papéis (line 193) says the role arrives "nas claims do JWT"; SCREENS.md
line 328–333 (open question **C16**) records that the contract documents no claims and that
decoding them would mean reading an undocumented payload. `TRUTH.md` line 34 settles it: the
server is asked. **C16 is therefore resolved by `GET /users/me`** — `docs/adr/ADR-008-frontend-stack.md`
§Papéis and SCREENS.md §LOGIN should be reconciled to that (documentation follow-up, not this
feature's code).

**Structural enforcement of "absent, not disabled"** (SCREENS.md consistency rule 3, line 211;
`TRUTH.md` line 24) rests on three properties, in order of strength:

1. **`AdminOnly` has no disabled path.** It is the single exported role primitive, and its only
   two outcomes are *children* or *`null`*. It accepts no `fallback` and no `disabled` prop, so
   there is no API through which a developer can produce a greyed-out control. Adding one is a
   visible change to a shared component, reviewable in a diff — as opposed to a `disabled={!isAdmin}`
   scattered across pages, which is invisible.
2. **`useSession()` exposes `role`, not booleans on props.** No component receives `isAdmin` as
   a prop, so no component can thread it into a `disabled` attribute at a distance.
3. **The tests assert absence.** `TopBar.test.tsx` and `Home.test.tsx` render as a viewer and
   assert `queryByRole(...)` is `null` for every admin affordance, *and* assert that the rendered
   tree contains no `[disabled]` element — a `disabled` fallback fails the suite rather than
   passing it silently.

Client-side gating is UX only; the backend remains the authority (ADR-008 line 196).

---

## 5. Session lifecycle

1. **Boot.** `SessionProvider` mounts in `status: 'booting'` and calls `refresh()`
   (`src/api/auth.ts:17`) exactly once — the same silent-refresh mechanism `App.tsx` lines 11–15
   runs today, relocated. On success it sets the in-memory token and fetches `GET /users/me`.
2. **Guard while booting.** `RequireSession` renders **neither** protected content **nor** a
   redirect while `status === 'booting'`. Redirecting during boot is what flashes the login page
   on reload (`TRUTH.md` AC 6). `/login` behaves symmetrically: it does not render the form while
   booting, so a valid session never sees a form it is about to be navigated away from.
   `DESIGN.md` decides what, if anything, occupies the booting frame — SCREENS.md forbids a
   skeleton standing in for a verdict (line 211), which is a Home-data rule, not a boot rule.
3. **Sign-in.** `Login` calls `login()` (`src/api/auth.ts:8`), which writes the token store; the
   provider then invalidates `['session']` and navigates to `/` on `authenticated`.
4. **Access-token expiry.** Unchanged: `apiClient`'s interceptor refreshes once, single-flight
   (`client.ts` lines 31–49).
5. **Refresh failure.** `clearAccessToken()` (line 44) then `emitSessionExpired()` (decision (b));
   the provider drops to `anonymous`, clears the TanStack Query cache, and navigates to `/login`
   with `replace: true` — so browser Back does not restore protected content (`TRUTH.md` AC 17).
6. **Sign-out.** `signOut()` calls `logout()` (`src/api/auth.ts:23`, server-side revoke + cookie
   clear), then — **whether or not the call succeeds** — clears the token store, clears the query
   cache, sets `anonymous`, and navigates to `/login` with `replace: true`. What is cleared: the
   in-memory access token, the `['session']` entry, and every Home query. Nothing was ever written
   to `localStorage`/`sessionStorage`, so there is nothing else to clear.

---

## 6. Constraints

- **SCREENS.md §Building rules (lines 165–179) are binding.** No magic numbers — every spacing,
  size, color, radius and border width is a token; components size to their container, never the
  viewport; flex/grid with `min-w-0` on flex children; long values truncate/wrap/scroll; the type
  scale enforces the 16px IM Fell floor. A raw hex or a raw pixel value in a component is a bug.
- **The page body never scrolls horizontally** (SCREENS.md line 162). Home has no table, so this
  binds the top bar and the review cards.
- **Light only.** No `dark:` utility, no `prefers-color-scheme` branch, no theme toggle
  (SCREENS.md lines 39–57; `TRUTH.md` line 108). Removing `@custom-variant dark` makes a stray
  `dark:` a build-time failure.
- **No backend, contract, or Pi change** (`TRUTH.md` line 110). `contracts/openapi/openapi.yaml`
  is read-only here; the generated types are the only thing derived from it, and `npm run gen:types`
  must produce a clean diff.
- **No hand-written API types**, per ADR-008 §Geração de Tipos.
- **No fallback for the blocked reads** — no client-side scan-list emulation, no mock-backed data
  path shipped in `src/`. MSW handlers live under `src/test/` and are test-only.
- **No new infrastructure.** Everything is local tooling already provisioned by the DMI-20 CI job.
  **No `HUMAN_INFRA_REQUIRED` items in this feature.** (The blocked reads are a software
  dependency on a backend feature, not an infrastructure need.)

---

## 7. Testing expectations

Vitest + Testing Library + MSW, mirroring the two files DMI-20 established:
`frontend/src/api/client.test.ts` (network-level MSW, real Axios instances, per-test
`server.use(...)` overrides) and `frontend/src/pages/LoginStub.test.tsx` (`render` +
`userEvent`, assertions on visible text and roles). Tests are colocated with the module they
exercise. `src/test/mswHandlers.ts` gains handlers and exported fixtures for `/users/me`,
`/scans`, `/findings`, `/agents/:agentId`; because `src/test/setup.ts` line 9 sets
`onUnhandledRequest: 'error'`, **every** request a test triggers must have a handler — adding the
Home reads to `mswHandlers.ts` is not optional. Fixtures use real hostnames, IPs and CVE ids
(SCREENS.md consistency rule 9).

| AC | Scenario | Verified in | Blocked? |
|---|---|---|---|
| 1 | Sign in succeeds → Home | `src/pages/Login.test.tsx` + `src/App.test.tsx` (lands on `/`) | no |
| 2 | Sign in fails, no session | `src/pages/Login.test.tsx` — MSW 401; error visible, still on `/login`, `getAccessToken()` null | no |
| 3 | Submit is a state | `src/pages/Login.test.tsx` — delayed MSW response; button copy changes and is `disabled` **while in flight** (the one legitimate `disabled`, unrelated to role gating) | no |
| 4 | Network down ≠ bad credentials | `src/pages/Login.test.tsx` — `HttpResponse.error()`; asserts the *other* copy | no |
| 5 | Protected route without a session | `src/App.test.tsx` — render at `/` with a failing refresh; asserts redirect to `/login` and that no Home text ever appears | no |
| 6 | Session recovery on reload | `src/App.test.tsx` + `src/auth/SessionProvider.test.tsx` — successful refresh; asserts the login form is **never** rendered (no flash) | no |
| 7 | Viewer gating | `src/components/TopBar.test.tsx`, `src/pages/Home.test.tsx` — absence assertions + no `[disabled]` element | no |
| 8 | Admin gating | same two files, admin profile | no |
| 9 | Home, all clear | `src/lib/review.test.ts` (rule) + `src/pages/Home.test.tsx` (render, MSW) | ⛔ end-to-end gated on `GET /scans` |
| 10 | Home, items pending | `src/lib/review.test.ts` + `src/pages/Home.test.tsx` | ⛔ gated on `GET /scans` + `/findings` filters |
| 11 | Home hides medium/low | `src/lib/review.test.ts` + `src/pages/Home.test.tsx` | ⛔ same |
| 12 | Home, failed scan | `src/lib/review.test.ts` (`status: 'failed'`) + `src/pages/Home.test.tsx` | ⛔ gated on `GET /scans` |
| 13 | Home, stale coverage | `src/lib/review.test.ts` — both sides of the 3-day boundary | ⛔ gated on `GET /scans`; the Pi-not-seen variant additionally gated on agent discovery (C1) |
| 14 | Home, blank | `src/pages/Home.test.tsx` — `total: 0`; admin sees the CTA, viewer sees the line and **no** CTA | ⛔ needs `GET /scans` to answer "no scans"; the render logic is testable now under MSW |
| 15 | Home, error | `src/pages/Home.test.tsx` + `src/hooks/useHomeReview.test.ts` — MSW 500; asserts copy + `[Retry]` and that no verdict text is present | ⛔ end-to-end gated |
| 16 | Retry recovers | `src/hooks/useHomeReview.test.ts` — fail-then-succeed handler; asserts the correct terminal state | ⛔ end-to-end gated |
| 17 | Sign out | `src/auth/SessionProvider.test.tsx` — asserts `POST /auth/logout` fired, token store cleared, query cache empty, navigation to `/login` with `replace` | no |
| 18 | Quality gates | The existing `frontend` CI job (`.github/workflows/ci.yml`) running the unchanged scripts in `frontend/package.json`; not a Vitest test | no |

Additionally, `src/api/client.test.ts` is updated (not extended in scope): its refresh-failure
case asserts `emitSessionExpired` fired instead of inspecting the stubbed `window.location`
(current lines 53–57). Its other three cases — one-refresh-on-401, single-flight, cookie
scoping — stay untouched, and must still pass unchanged. That is the regression signal that
decision (b) did not disturb the interceptor.

---

## 8. Open items this document deliberately does not decide

1. **Agent discovery (contract ask C1).** No `/api/v1/agents` collection exists. Without it the
   SPA cannot obtain an `agent_id`, so the Pi-status footer and the "Pi hasn't been seen" review
   item are unimplementable. Not worked around here.
2. **The accent and the four severity hexes.** `DESIGN.md` owns them; this document fixes only
   the token names `--accent`, `--sev-critical`, `--sev-high`, `--sev-medium`, `--sev-low`.
3. **The `--radius` value.** SCREENS.md line 683 shows square-edged review cards, which implies a
   near-zero radius, but no radius value is locked in Foundations. `DESIGN.md` sets the token.
4. **Rendering of unbuilt nav destinations** (Scans, Hosts, Agents, Settings) — `DESIGN.md`.
5. **The variable-vs-static fontsource package for IBM Plex Mono** — implementer confirms at
   install; token names are unaffected.
