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

1. **`GET /api/v1/scans` *is* in the frozen contract.** `TRUTH.md`'s original blocked-reads note and line 119 state
   that "a scan *list* is not in the frozen contract, so it needs a contract amendment as well
   as an implementation". That is false: `contracts/openapi/openapi.yaml` line 164 defines
   `operationId: listScans` on `/api/v1/scans`, secured by `FrontendBearerAuth`, with
   `Page`/`PerPage`/`ScanStatusFilter`/`ScanSortBy`/`SortOrder` parameters (lines 173–178) and
   a `ScanListResponse` body (line 194, schema at line 1810). **The blocker was a missing backend
   implementation only — no contract amendment was required.**
   **Resolved 2026-07-28:** `TRUTH.md` was corrected, and DMI-82 shipped the route against the
   frozen contract with no shape change — `routers/scans.py:22` now registers `GET /api/v1/scans`
   alongside the detail route. Kept here as the record of why the blocking feature's scope was
   smaller than TRUTH originally claimed.
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
fed by `GET /users/me`, a session route guard, the `AppShell` top bar (no sidebar, and only the
`Home` item in v1 — `DESIGN.md` §Top bar), the real LOGIN screen, the HOME screen with its four
designed states and its one-at-a-time finding deck, a not-found page for unknown addresses, the
pure verdict/review-items derivation, the resource modules and query hooks for Home's reads, the
SCREENS.md-compliant token and font layer, and the tests for all of it.

**This feature does not build:** Scans, Hosts, Agents, Users, Settings, Scan detail, Host
detail (`TRUTH.md` §Out of scope); accept-invite / forgot / reset password; "Scan now"; polling
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
Status: ✅ implemented in the backend today · ⛔ in the contract but not implemented. Rows 5
and 6 flipped to ✅ on 2026-07-28 when DMI-82 landed (`specs/021-scan-list-and-finding-filters/`).

| # | Path | Method | Auth | Request | Response | Error branches the UI handles | Contract | Backend | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/api/v1/auth/login` | POST | `authClient`, `security: []` | `LoginRequest` `{ email, password }` (2178–2190) | `LoginResponse` `{ access_token, token_type: "bearer", expires_in }` (2191–2207) + httpOnly `Set-Cookie` | `401` → "That email and password don't match."; network/`5xx` → "Couldn't reach Dmitri. Try again in a moment." (SCREENS.md lines 350–351). **No other branch** — forced-rotation 403 is void (SCREENS.md lines 324–326) | `openapi.yaml:601` | `routers/auth.py:36` | ✅ |
| 2 | `/api/v1/auth/refresh` | POST | `authClient`, `RefreshCookieAuth` | none | `LoginResponse` + rotated cookie | `401` → no session; boot guard falls through to `/login` | `openapi.yaml:636` | `routers/auth.py:51` | ✅ |
| 3 | `/api/v1/auth/logout` | POST | `authClient`, `RefreshCookieAuth` | none | `204`, cookie cleared | Any failure still clears client state and navigates to `/login` (§5) | `openapi.yaml:670` | `routers/auth.py:68` | ✅ |
| 4 | `/api/v1/users/me` | GET | `apiClient` | none | `UserProfileResponse` `{ user_id, email, role }` (2208–2226) | `401` → interceptor refreshes once, then session failure → `/login`. A failure here is a **session** failure, not a Home data failure | `openapi.yaml:874` | `routers/users.py:12` | ✅ |
| 5 | `/api/v1/scans?per_page=1&sort_by=timestamp&sort_order=desc` | GET | `apiClient` | query only | `ScanListResponse` `{ data: ScanSummary[], total, page }` (1810–1827); `ScanSummary` = `scan_id, timestamp, subnet, scan_mode, status, host_count, finding_count, highest_severity?` (1718–1751) | `data: []` → Home **blank**; `4xx`/`5xx`/network → Home **error** + `[Retry]` | `openapi.yaml:164` | `routers/scans.py:22` `read_scans` — all five params honoured | ✅ |
| 6 | `/api/v1/findings?scan_id={id}&severity=critical` and `&severity=high` | GET | `apiClient` | query only | `FindingListResponse` `{ data: FindingRecord[], total, page }` (2388–2405); `FindingRecord` carries `finding_id, scan_id, severity, title, cve_id?, host_id?, host_ip?, detected_at` (2300–2387) | any failure → Home **error** (a partial verdict is forbidden, `TRUTH.md` AC 15) | `openapi.yaml:379`; `ScanIdFilter` 1005, `SeverityFilter` 991 | `routers/findings.py:17` `read_findings` — `severity` and `scan_id` land as conjunctive filters beside `host_id` | ✅ |
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

### 2.2 Read availability

Home's verdict is a function of three reads. **The two that gate acceptance criteria are now
served** — DMI-82 landed 2026-07-28 (`specs/021-scan-list-and-finding-filters/`, 12/12 tasks
complete, contract-fidelity test green). Only the agent read remains unserved, and it costs no
acceptance criterion.

| Read | What Home needs from it | State | Gates |
|---|---|---|---|
| `GET /api/v1/scans` (list) | The latest scan: `timestamp` (verdict recency + footer), `status: failed` (failed-scan review item), `host_count`, `scan_mode`, `finding_count`, `highest_severity` (context sentence), and `scan_id` (to fetch findings). Also `total === 0` → the blank state | ✅ `routers/scans.py:22`; `page`/`per_page`/`status`/`sort_by`/`sort_order` all honoured, newest-first by default | AC 9, 10, 11, 12, 13, 15, 16 |
| `GET /api/v1/findings?scan_id=&severity=` | Critical and high findings of the latest scan: `title`, `cve_id`, `host_ip`, `severity` | ✅ `routers/findings.py:17`; filters combine conjunctively with each other and with `host_id` | AC 10, 11 |
| `GET /api/v1/agents/{agent_id}` | `online`, `last_seen_at` for the Pi-status footer | ⛔ **DMI-78.** `routers/agents.py` still has no HTTP route; the endpoint is frozen in the contract (`openapi.yaml:526`) but unimplemented | footer only |
| **Agent discovery** | The SPA has no way to learn an `agent_id`: there is **no `/api/v1/agents` collection path anywhere in the contract** (only `/agents/{agent_id}` at 526 and `/agents/{agent_id}/commands` at 429). This is contract ask **C1**, `docs/roadmap/FRONTEND.md` §Direction | ⛔ **Contract gap, genuinely open** — DMI-78. This document does **not** pick a workaround (no `VITE_AGENT_ID`, no hardcoded UUID, no inference from a scan) | Pi-status footer; the `online: false` half of AC 13 |

`DESIGN.md` already removes the Pi-status footer line from this feature's build (§"The Pi-status
footer is blocked"). Nothing else waits on anything. **No fallback, client-side substitute, or
mock-backed data path is built** for the agent read — the footer line is simply absent.

**Consequence for AC 13 (stale coverage).** The 3-day rule (`TRUTH.md`) is computable from scan
timestamps alone and needs **no** agent read. Only the *"The Pi hasn't been seen since Tuesday."*
variant (SCREENS.md line 661) needs `AgentDetail`; leave that one behind DMI-78.

#### As-built properties of the two unblocked reads — binding on this feature

These are behaviours DMI-82 shipped that the query layer must be written against. Each is a
`TRUTH.md` rule of `specs/021-scan-list-and-finding-filters/`, verified by its test suite.

- **One severity per request.** `severity` takes a single value — not a list, not a
  comma-separated string, not a range. `HOME_SEVERITIES` therefore drives **two** requests, which
  is what §2.3 already specifies. Do not "optimise" it into one.
- **Findings have no caller-chosen sort.** The contract declares none and none was invented.
  Order is fixed and stable-for-paging but unspecified. `deriveReview()` must not assume the
  response arrives severity-ordered or newest-first; if review items need an order, `review.ts`
  imposes it.
- **Invalid paging is refused, not clamped.** `per_page` outside 1–100 or `page < 1` is a `422`,
  as is an unknown `sort_by`/`sort_order`. `LATEST_SCAN_QUERY` (`per_page: 1`) is inside the
  range; no other paging value is sent by this feature.
- **Empty is a `200`, never a `404`.** An organisation with no scans gets `{ data: [], total: 0 }`.
  Home's blank state is driven by that, and a `404` must **not** be treated as "no scans".
- **`highest_severity` is genuinely absent for a scan with zero findings** — not `"low"`, not
  `0`. The context sentence must handle the missing key rather than assume a floor value.
- **Per-scan aggregates are per-scan.** `host_count` and `finding_count` on a `ScanSummary`
  describe that scan, not the organisation's running totals — the context sentence can state them
  directly.

### 2.3 Constants

| Constant | Value | Where |
|---|---|---|
| `STALE_COVERAGE_DAYS` | `3` (`TRUTH.md` §Business rules, *Coverage is stale after 3 days*) | `frontend/src/lib/review.ts` — the only place the number appears |
| `LATEST_SCAN_QUERY` | `{ per_page: 1, sort_by: 'timestamp', sort_order: 'desc' }` (defaults confirmed at `openapi.yaml:968-978` and `951-960`) | `frontend/src/api/scans.ts` |
| `LATEST_SUCCESSFUL_SCAN_QUERY` | `{ ...LATEST_SCAN_QUERY, status: 'completed' }` — see §2.5 | `frontend/src/api/scans.ts` |
| `HOME_SEVERITIES` | `['critical', 'high']` (`TRUTH.md`; SCREENS.md line 647) | `frontend/src/api/findings.ts` |
| `HOME_FINDINGS_PER_PAGE` | `100` — the contract's maximum (`openapi.yaml` `PerPage`, and `Query(..., le=100)` at `routers/findings.py:20`). Fetched once so the deck never issues a request while stepping (§2.6) | `frontend/src/api/findings.ts` |
| Query keys | `['session']`, `['scans','latest']`, `['scans','latest','completed']`, `['findings', scanId, severity]`, `['agent', agentId]` | colocated with each hook |
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

### 2.5 Two scan reads, not one — staleness is measured against the last *successful* scan

`TRUTH.md` states the rule as: coverage is stale when **the most recent successful scan** finished
more than `STALE_COVERAGE_DAYS` ago. The most recent scan and the most recent *successful* scan
are not the same record. A scan that failed an hour ago is the latest scan, and reading staleness
off it would tell an operator their coverage is fresh at the exact moment it stopped being so —
the failure mode the rule exists to catch.

DMI-82 shipped the `status` filter on `GET /scans`, so this is one extra request:

| Read | Query | Feeds |
|---|---|---|
| Latest scan, any status | `LATEST_SCAN_QUERY` | The failed-scan review item (AC 12), and the `scan_id` the two finding reads filter on (AC 10, 11). Also `total === 0` → the blank state (AC 14) |
| Latest successful scan | `LATEST_SUCCESSFUL_SCAN_QUERY` | The stale-coverage review item (AC 13) and the context sentence's "when the last scan finished and what it covered" (AC 9) — which must describe a scan that actually completed |

`deriveReview()` therefore takes both:
`deriveReview({ latestScan, latestSuccessfulScan, criticalFindings, highFindings, now })`.

Consequences, all binding:

- **Both reads are part of the verdict.** If either fails, Home renders its error state — a
  verdict built on one of the two is a partial verdict, which `TRUTH.md` forbids.
- **`latestSuccessfulScan === null` while `latestScan !== null`** is a real state: an organisation
  whose only scans have failed. It is **not** the blank state (a scan has run). The failed-scan
  item covers it; the stale-coverage item is omitted rather than computed against nothing, since
  "stale since never" is not a sentence Home says.
- **Blank is keyed off `latestScan`,** the unfiltered read — "no scan has ever run", not "no scan
  has ever succeeded".
- **The two can be the same scan.** When the latest scan completed successfully, both reads return
  it. Home must not double-count it into two review items.
- `status: 'completed'` is the success value — `ScanStatus` is
  `pending | accepted | processing | completed | failed`, and there is no separate "success".

### 2.6 The count is not the render — and stepping is not paging

Two independent decisions, both easy to get subtly wrong and neither visible in a fixture with
fewer than twenty findings.

**The verdict's number comes from `total`, never from `data.length`.**
`GET /findings` pages, so a scan with 37 criticals returns 20 rows and `total: 37`. A verdict
built from the rows says *"20 things need your review"* while 37 do — a screen that under-reports
danger in exact proportion to how much of it there is, and one that passes every test written
against a small fixture. `deriveReview()` therefore receives the two `FindingListResponse`
envelopes rather than their `data` arrays, and:

```
reviewCount = criticalFindings.total
            + highFindings.total
            + (latestScan.status === 'failed' ? 1 : 0)
            + (coverageIsStale ? 1 : 0)
```

`review.test.ts` must include a case where `total` exceeds `data.length` (`TRUTH.md` AC 17).

**The deck steps through memory, never over the network.** Both finding reads are issued once, on
load, at `HOME_FINDINGS_PER_PAGE = 100` — the contract's maximum. `FindingDeck` holds an index
into the already-fetched array; `←`/`→` move the index and nothing else. No `useQuery` is keyed on
the deck index, no `page` parameter is ever sent after the first load, and no request is issued by
any interaction on Home except `[Retry]`.

This is what separates a deck from pagination wearing different chrome: an arrow that fetches
stutters on a slow link and can fail halfway through a review, leaving the operator unsure what
they have seen. The test asserts it structurally — `src/test/setup.ts` runs MSW with
`onUnhandledRequest: 'error'`, so `FindingDeck.test.tsx` steps through every card with no handler
registered beyond the initial load and fails if anything reaches the network.

**Consequence, stated rather than discovered:** past 100 findings of one severity, the deck holds
the first 100 while the verdict still counts all of them. `TRUTH.md` fences this as out of scope —
the screens that would list the remainder are later features.

**Arrow keys are bound to the deck, not the document.** `FindingDeck` is one tab stop with
`onKeyDown` on its own root. A `document`-level listener would hijack page scrolling and fight
screen-reader navigation everywhere else on the page — an accessibility defect no test catches
unless it is specified, so it is specified here and asserted in `FindingDeck.test.tsx`.

---

## 3. New files and naming (mandatory)

All paths relative to the repo root. Conventions follow the existing repo: `@/` alias
(`tsconfig.app.json` `paths`, `vitest.config.ts` `resolve.alias`), colocated `*.test.ts(x)`,
default exports for pages/components as in `src/pages/LoginStub.tsx`.

### Routing and app root

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/main.tsx` | touch | `BrowserRouter` → `QueryClientProvider` → `SessionProvider` → `App` |
| `frontend/src/App.tsx` | rewrite | The route table only: `/login` → `Login`; `/` → `RequireSession` → `AppShell` → `Home`; `*` → `NotFound`. **The catch-all renders, it does not redirect** — silently sending a mistyped URL to Home makes the app look like it ignored the operator (`DESIGN.md` §HOME — not found). `*` sits inside the `RequireSession`/`AppShell` branch so a signed-in operator keeps the top bar and can navigate away; signed-out, `RequireSession` sends them to `/login` first, which is correct — an unknown path is not a reason to skip the session check |
| `frontend/src/App.test.tsx` | new | Routing-level tests: guard redirect, boot-refresh no-flash, post-login landing |

### Session and role

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/auth/SessionProvider.tsx` | new | Owns boot silent refresh (`refresh()` from `@/api/auth`), then the `['session']` query over `GET /users/me`; exposes `{ status: 'booting' \| 'authenticated' \| 'anonymous', user, signIn, signOut }`; registers the `onSessionExpired` handler from decision (b) |
| `frontend/src/auth/useSession.ts` | new | `useSession()` hook; throws outside the provider. **The only** way any component reads identity or role |
| `frontend/src/auth/RequireSession.tsx` | new | Route guard. `booting` → renders nothing protected (§5); `anonymous` → `<Navigate to="/login" replace />`; `authenticated` → `<Outlet />` |
| `frontend/src/auth/SessionProvider.test.tsx` | new | Boot refresh success/failure, `/users/me` wiring, sign-out clearing |
| `frontend/src/api/authEvents.ts` | new | `onSessionExpired(handler)` / `emitSessionExpired()`; module-scoped, no React import |

### API resource modules (`frontend/src/api/`)

Each is a thin function over `apiClient`, typed from `@/types/openapi`, mirroring
`src/api/auth.ts`. Path tails are relative to the `/api/v1` baseURL already set in
`instances.ts` line 3 — never repeat the prefix.

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/api/users.ts` | new | `getCurrentUser(): Promise<UserProfileResponse>` → `GET /users/me` |
| `frontend/src/api/scans.ts` | new | `getLatestScan(): Promise<ScanSummary \| null>` → `GET /scans` with `LATEST_SCAN_QUERY`, and `getLatestSuccessfulScan(): Promise<ScanSummary \| null>` → the same call with `LATEST_SUCCESSFUL_SCAN_QUERY` (§2.5). Both return `null` when `data` is empty (a `200` with `total: 0`, never a `404` — §2.2) |
| `frontend/src/api/findings.ts` | new | `listFindings({ scan_id, severity }): Promise<FindingListResponse>` → `GET /findings` at `per_page: HOME_FINDINGS_PER_PAGE`. `severity` is a single value per call — two calls, one per entry in `HOME_SEVERITIES` (§2.2). Returns the whole envelope, **`total` included** — callers need it and it is not the same as `data.length` (§2.6) |
| `frontend/src/api/agents.ts` | new | `getAgent(agentId): Promise<AgentDetail>` → `GET /agents/{agent_id}` ⛔ — **written but not called** until agent discovery (C1) is resolved (§2.2) |

### Query hooks (`frontend/src/hooks/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/hooks/useHomeReview.ts` | new | Composes `getLatestScan` + `getLatestSuccessfulScan` (§2.5) + the two `listFindings` calls via TanStack Query, feeds `deriveReview()`, and returns one discriminated union: `{ state: 'loading' \| 'blank' \| 'clear' \| 'pending' \| 'error', … }` plus a `retry()`. Home renders a `switch` over it, so no partial-data path can leak into the verdict; any of the four reads failing means `error` |
| `frontend/src/hooks/useHomeReview.test.ts` | new | MSW-driven state matrix, including the error and retry paths |

### Pure derivation (`frontend/src/lib/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/lib/review.ts` | new | `deriveReview({ latestScan, latestSuccessfulScan, criticalFindings, highFindings, now })` → `{ reviewCount, deckFindings, scanItem, coverageItem }`. Takes the two **envelopes**, not their `data` arrays: `reviewCount` sums `total`s (§2.6), `deckFindings` is the concatenated `data` ordered critical→high then newest-first (the response has no caller-chosen sort — §2.2). Owns `STALE_COVERAGE_DAYS = 3` and the failed-scan rule. No React, no network — the whole verdict logic is unit-testable |
| `frontend/src/lib/review.test.ts` | new | The rule table: all-clear, items pending, medium/low hidden, failed scan, stale coverage, empty history, and **`reviewCount` from `total` when `total > data.length`** |
| `frontend/src/lib/utils.ts` | keep | Existing `cn()` helper, untouched |

### Shell and shared components (`frontend/src/components/`)

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/components/AppShell.tsx` | new | Inside-shell frame: `<TopBar />` + `<Outlet />` inside the fluid content column (`max-w-*`, never a fixed width — SCREENS.md lines 156–163). **No sidebar** |
| `frontend/src/components/TopBar.tsx` | new | Wordmark left, the single `Home` nav item, `[Log out]` right. `min-w-0` on flex children (SCREENS.md building rule 3). No role branch — it does not read `useSession().user.role` |
| `frontend/src/components/TopBar.test.tsx` | new | Renders identically for admin and viewer; the tree contains no `[disabled]` element; log-out calls `signOut` |
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
| `frontend/src/pages/Home.tsx` | new | Switches on `useHomeReview()`; renders exactly one of the four state components. Never renders a skeleton in the verdict's place (`TRUTH.md` §Business rules, *Every screen ships three designed states*) |
| `frontend/src/pages/Home.test.tsx` | new | The state matrix and retry |
| `frontend/src/pages/NotFound.tsx` | new | `That page doesn't exist.` + a link to Home. Copy from `DESIGN.md`; rendered inside the shell |
| `frontend/src/pages/NotFound.test.tsx` | new | An unknown path renders it with the top bar intact; the link returns to `/`; signed-out, an unknown path lands on `/login` instead |
| `frontend/src/pages/home/Verdict.tsx` | new | The one-sentence verdict + context sentence (all-clear and items-pending share it) |
| `frontend/src/pages/home/FindingDeck.tsx` | new | One finding at a time plus the `←`/`→` controls and the `{i} of {n}` line. Owns the index state, the end-stop logic, and the **deck-scoped** `onKeyDown` — never a `document` listener (§2.6). Renders the card alone, with no arrows and no position line, when there is exactly one finding. Renders nothing when there are none |
| `frontend/src/pages/home/FindingDeck.test.tsx` | new | Stepping both ways, both end-stops, arrow keys only while focused, the one-finding case, `aria-live` on the card region, and that no request is issued while stepping (MSW would fail the test under `onUnhandledRequest: 'error'`) |
| `frontend/src/pages/home/ReviewItemCard.tsx` | new | One square-edged card per item: label, severity badge (findings only), plain sentence. **No action button and no link** — every destination is out of scope, so none is rendered (`DESIGN.md` §The review-item buttons are drawn but not built). The component takes no `href`/`onAction` prop, so there is no API through which a dead control can be added without a visible diff |
| `frontend/src/pages/home/HomeBlank.tsx` | new | First-run copy plus the sentence naming where scanning lives. **No CTA and no role branch** — it does not import `useSession` (`DESIGN.md` §HOME — blank) |
| `frontend/src/pages/home/HomeError.tsx` | new | "Couldn't load the review." + `[Retry]` |
| `frontend/src/pages/home/HomeFooter.tsx` | new | Muted footer: last-scan line via `Timestamp`; the Pi-status line stays behind the blocked agent read (§2.2) |
| `frontend/src/pages/LoginStub.tsx`, `LoginStub.test.tsx`, `SignedInPlaceholder.tsx` | **delete** | Throwaways from DMI-20 |

### Styling, config, tests

| Path | New/Touch | Note |
|---|---|---|
| `frontend/src/index.css` | rewrite | Decisions (c) and (d): font imports, `@theme inline` tokens, locked neutrals, accent/severity token names, type scale; `.dark` and `@custom-variant dark` removed |
| `frontend/package.json` | touch | `+ react-router@^7`, `+ @fontsource/im-fell-english`, `+ @fontsource/ibm-plex-mono`, `− @fontsource-variable/geist`. **No new scripts** — `dev`/`build`/`gen:types`/`lint`/`format:check`/`typecheck`/`test` already exist and are unchanged |
| `frontend/src/test/mswHandlers.ts` | touch | Add `GET /users/me`, `GET /scans`, `GET /findings`, `GET /agents/:agentId` plus exported fixture objects (`adminProfile`, `viewerProfile`, `latestScan`, `criticalFinding`, …). The `/scans` handler must branch on the `status` query param so the two scan reads (§2.5) can return different records; the `/findings` handler must branch on `severity` so critical and high differ. Required: `setup.ts` line 9 runs with `onUnhandledRequest: 'error'`, so any unhandled call fails the test |
| `frontend/src/test/renderWithProviders.tsx` | new | One helper wrapping `MemoryRouter` + a per-test `QueryClient` + `SessionProvider`; used by every component/page test so provider wiring is not duplicated |
| `frontend/src/test/setup.ts` | keep | Unchanged; already clears the token store per test (lines 10–13) |
| `frontend/vitest.config.ts`, `eslint.config.js`, `tsconfig*.json` | keep | No change needed; the `@` alias and jsdom env already cover the new files |
| `.github/workflows/ci.yml` | keep | The `frontend` job from DMI-20 already runs the whole gate; no new step |

No `jwt-decode` (or equivalent) dependency is added — see §4.

---

## 4. Role: read from the server, gated nowhere yet

**Where the role comes from.** `useSession().user.role`, populated by `GET /users/me`
(`openapi.yaml:874`, `UserProfileResponse.role` enum `admin|viewer` at 2220–2226). **Never from
the access token.** ADR-008 §Papéis (line 193) says the role arrives "nas claims do JWT"; SCREENS.md
line 328–333 (open question **C16**) records that the contract documents no claims and that
decoding them would mean reading an undocumented payload. `TRUTH.md` §Business rules settles it:
the server is asked. **C16 is therefore resolved by `GET /users/me`** —
`docs/adr/ADR-008-frontend-stack.md` §Papéis and SCREENS.md §LOGIN should be reconciled to that
(documentation follow-up, not this feature's code). No `jwt-decode` or equivalent is added, and
its absence from `package.json` is asserted (AC 8).

**No `AdminOnly` component ships in this feature.** After the blank state's `[Run first scan]` was
dropped (`DESIGN.md` §HOME — blank) and the nav was reduced to `Home` alone (`DESIGN.md` §Top bar),
**this feature contains no admin-only affordance**. A role-gating primitive with zero call sites is
speculative code — `.claude/CLAUDE.md` §2, *no abstractions for single-use code, nothing
speculative* — so it is not built here. It arrives with the first screen that has something to
hide, together with the test that proves the hiding. Filed separately.

**What still enforces "absent, not disabled"** in the meantime:

1. **No component receives the role as a prop.** `useSession()` is the only reader, and nothing in
   this feature calls it for gating — so there is no path by which `role` reaches a `disabled`
   attribute.
2. **The tests assert the invariant directly, not a proxy for it.** `TopBar.test.tsx` and
   `Home.test.tsx` assert the rendered tree contains **no `[disabled]` element at all**, for both
   roles, and that both roles render identically. That is a stronger property than "the admin
   control is absent for viewers" and it holds even as pages are added — the day someone ships a
   greyed-out control, the suite fails.
3. **The one legitimate `disabled`** is the sign-in button while its request is in flight, owned
   and asserted by `Login.test.tsx` (AC 3). It is scoped to a screen that renders before any
   session exists, so it can never be confused with role gating.

Client-side gating is UX only; the backend remains the authority (ADR-008 line 196).

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
   with `replace: true` — so browser Back does not restore protected content (`TRUTH.md` AC 20).
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
  (SCREENS.md lines 39–57; `TRUTH.md` §Out of scope, *Dark mode*). Removing `@custom-variant dark` makes a stray
  `dark:` a build-time failure.
- **No backend, contract, or Pi change** (`TRUTH.md` §Out of scope, *Any backend, contract, or Pi-agent change*). `contracts/openapi/openapi.yaml`
  is read-only here; the generated types are the only thing derived from it, and `npm run gen:types`
  must produce a clean diff.
- **No hand-written API types**, per ADR-008 §Geração de Tipos.
- **No fallback for the one remaining blocked read** (the agent read, §2.2) — no mock-backed data
  path shipped in `src/`. MSW handlers live under `src/test/` and are test-only.
- **No new infrastructure.** Everything is local tooling already provisioned by the DMI-20 CI job.
  **No `HUMAN_INFRA_REQUIRED` items in this feature.** (The agent read is a software dependency
  on a backend feature, not an infrastructure need.)

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
| 7 | Nothing present-but-disabled | `src/components/TopBar.test.tsx` and `src/pages/Home.test.tsx` — each asserts `container.querySelectorAll('[disabled]')` is empty for both roles. `src/pages/Login.test.tsx` owns the one exception and asserts the submit button is disabled **only** while in flight, and enabled before and after | no |
| 8 | Role comes from the server | `src/auth/SessionProvider.test.tsx` — the role on the `GET /users/me` response is what `useSession()` exposes; a token whose payload claims a different role does not change it, and no token-decoding dependency exists in `package.json` | no |
| 9 | Home, all clear | `src/lib/review.test.ts` (rule) + `src/pages/Home.test.tsx` (render, MSW) | no |
| 10 | Home, items pending | `src/lib/review.test.ts` + `src/pages/Home.test.tsx` — the deck's first card names the CVE, host and IP | no |
| 11 | Home hides medium/low | `src/lib/review.test.ts` + `src/pages/Home.test.tsx` | no |
| 12 | Home, failed scan | `src/lib/review.test.ts` (`status: 'failed'`) + `src/pages/Home.test.tsx` | no |
| 13 | Home, stale coverage | `src/lib/review.test.ts` — both sides of the 3-day boundary, measured against `latestSuccessfulScan`; plus the case where a *recent failed* scan must not mask stale coverage, and `latestSuccessfulScan: null` with a non-null `latestScan` (§2.5) | no; only the Pi-not-seen *variant* stays gated on agent discovery (C1, DMI-78) |
| 14 | Home, blank | `src/pages/Home.test.tsx` — `total: 0` on a `200`, never a `404`; the blank note renders and no scan-triggering control exists in the tree for either role | no |
| 15 | Home, error | `src/pages/Home.test.tsx` + `src/hooks/useHomeReview.test.ts` — MSW 500; asserts copy + `[Retry]` and that no verdict text is present | no |
| 16 | Retry recovers | `src/hooks/useHomeReview.test.ts` — fail-then-succeed handler; asserts the correct terminal state | no |
| 17 | Count exceeds what is shown | `src/lib/review.test.ts` — `total: 37` with 20 rows; asserts `reviewCount` is 37. Plus `src/pages/Home.test.tsx` asserting the rendered verdict text | no |
| 18 | Stepping through findings | `src/pages/home/FindingDeck.test.tsx` — forward and back, `←` disabled on the first card and `→` on the last (no wrap), arrow keys act only while the deck has focus and not from `document`, `{i} of {n}` tracks the card, the one-finding case renders no arrows, and **no request is issued while stepping** | no |
| 19 | Unknown address | `src/pages/NotFound.test.tsx` + `src/App.test.tsx` — signed in, an unknown path renders the copy with the top bar intact and the link returns to `/`; signed out, the same path lands on `/login` | no |
| 20 | Sign out | `src/auth/SessionProvider.test.tsx` — asserts `POST /auth/logout` fired, token store cleared, query cache empty, navigation to `/login` with `replace` | no |
| 21 | Quality gates | The existing `frontend` CI job (`.github/workflows/ci.yml`) running the unchanged scripts in `frontend/package.json`; not a Vitest test | no |

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
