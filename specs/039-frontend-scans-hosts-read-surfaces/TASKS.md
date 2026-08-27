# Tasks — Scans and Hosts read surfaces (`039-frontend-scans-hosts-read-surfaces`)

9 tasks. **Unblocked now: #1, #2, #3**

Issue: **DMI-88**. Specs: [TRUTH.md](./TRUTH.md), [ARCHITECTURE.md](./ARCHITECTURE.md),
[DESIGN.md](./DESIGN.md). Screen copy and layout: `docs/ui/SCREENS.md`.

## Agents and gate — read this before spawning

**The blast radius is `frontend/` only.** No task touches `backend/` or `hardware-agent/`, so the
Python agents and the Python gate do not apply.

| Step | Agent |
|---|---|
| 1 — code | `agent-developer` (loads the `frontend-conventions` skill first) |
| 2 — tests | **`frontend-test-engineer`**, not `test-engineer` |
| 3 — review | **`frontend-code-reviewer`**, not `code-reviewer` |

Gate, run from `frontend/`:

```bash
npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
```

Never run a repo-wide formatter, and never touch `contracts/openapi/openapi.yaml` or
`frontend/src/types/openapi.d.ts` — the contract is complete and the types are generated
(`ARCHITECTURE.md` §7, "Deliberately not touched").

## One deviation from ARCHITECTURE.md, recorded

`ARCHITECTURE.md` §5 says `DataTable` is "built in the scan-list task", which came from the design
session's rule: **do not design the abstraction without a consumer in view.** That rule is already
satisfied — §5.1 specifies the full props API and §5.2 maps it against all seven call sites, so the
component is designed against every consumer before a line is written.

Task 4 therefore builds it on its own, because `DataTable.test.tsx` is a specified deliverable with
a rich contract of its own (§9.2) and it can be verified without a page around it. This is a
granularity change, not a design change. If the reviewer finds Task 4 producing an API that Task 5
immediately fights, that is the signal the original ordering was right — say so in the rejection
rather than working around it.

---

## Task 1: Pure status and severity logic

- **Description**: The two React-free modules the tables branch on, per `ARCHITECTURE.md` §2.6 and
  §4.2. `scanStatus.ts` maps `ScanStatus → { tone, label } | null` and exports the
  `isUnfinished(status)` predicate the counts cells use; `severity.ts` exports `SEVERITY_ORDER` and
  the `bySeverityDesc` comparator. `bySeverityDesc` is **load-bearing, not belt-and-braces** — no
  endpoint guarantees finding order, so this comparator is the only thing delivering TRUTH rule 7
  (`DESIGN.md` §14.6).
- **Dependencies**: —
- **Target Files**: [`frontend/src/lib/scanStatus.ts`, `frontend/src/lib/scanStatus.test.ts`,
  `frontend/src/lib/severity.ts`, `frontend/src/lib/severity.test.ts`]
- **Tests**: `scanStatus.test.ts`, `severity.test.ts` — every `ScanStatus` member maps,
  `completed` maps to the neutral "Completed" pill, `bySeverityDesc` orders critical → high →
  medium → low and is stable on ties.
- **Success Criteria**:
  - Every one of the five `ScanStatus` values has a mapping; the test enumerates the union rather
    than sampling it.
  - `isUnfinished` is true for `pending`, `accepted`, `processing` and false for the other two.
  - `bySeverityDesc` is stable on equal severities (assert with a fixture where two criticals must
    keep their input order).
  - Neither file imports React.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: API layer, query keys, and the test fixtures

- **Description**: Every read this feature makes, the key hierarchy behind it, and the MSW
  handlers the four page suites will run against. Per `ARCHITECTURE.md` §3, §7 (API layer, Tests
  and harness) and §9.1.
- **Absorbed**: `queryKeys.ts`, the `useHomeReview.ts` key migration, and the MSW fixtures and
  harnesses. None can carry a test alone — key builders have no branching, and fixtures are only
  observable through the suites that consume them. Their verification is that **the entire existing
  suite still passes**: the `/hosts` handler being replaced (`ARCHITECTURE.md` §7) and Home's keys
  being rewritten are both changes that break existing tests if done wrong.
- **Dependencies**: —
- **Target Files**: [`frontend/src/api/queryKeys.ts`, `frontend/src/api/scans.ts`,
  `frontend/src/api/hosts.ts`, `frontend/src/api/findings.ts`,
  `frontend/src/hooks/useHomeReview.ts`, `frontend/src/test/mswHandlers.ts`,
  `frontend/src/test/scansHarness.ts`, `frontend/src/test/hostsHarness.ts`]
- **Tests**: No new suite. The gate is the **existing** suites passing unchanged —
  `hooks/useHomeReview.test.ts`, `pages/Home.test.tsx` and the five `pages/Users.*.test.tsx` files.
  A required edit to any of them means this task changed behaviour it must not have.
- **Success Criteria**:
  - `queryKeys.ts` is prefix-shaped, so `invalidateQueries({ queryKey: ['scans'] })` would sweep
    both the list and the detail keys. No invalidation helper is added — that is DMI-89's.
  - `useHomeReview.ts` changes **only** its three `queryKey` lines. The `skipToken` narrowing, the
    resolution order and the returned union are untouched.
  - `scans.ts` keeps `getLatestScan`, `getLatestSuccessfulScan`, `LATEST_SCAN_QUERY` and
    `LATEST_SUCCESSFUL_SCAN_QUERY` exported and unmodified — Home imports them.
  - `findings.ts` keeps `listFindings` and `HOME_SEVERITIES` unmodified.
  - The bare-array `/hosts` handler is **replaced**, not supplemented; no handler returns a shape
    that is not its contract response type.
  - `paginate(rows, url)` honours `page` and `per_page`; the `/hosts` handler honours `sort_by` and
    `sort_order`; fixtures are ≥25 rows for both scans and hosts.
  - The scan fixtures keep `latestScan` and `latestSuccessfulScan` as the newest and
    newest-completed rows (`ARCHITECTURE.md` §9.1) — Home's suite depends on it.
  - Every request/response type comes from `src/types/openapi.d.ts`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: EmptyState, LoadingSkeleton, StatusPill, Pagination

- **Description**: The four small shared components, per `ARCHITECTURE.md` §6 and `DESIGN.md` §3.4
  through §3.7. `StatusPill` is tone-and-label, never a `ScanStatus`, so DMI-89's seven-state
  `CommandStatus` reuses it unchanged. `LoadingSkeleton` uses `--rule`, **not** `bg-muted` —
  `--muted` resolves to white on this palette (the defect tracked in DMI-113).
- **Dependencies**: —
- **Target Files**: [`frontend/src/components/EmptyState.tsx`,
  `frontend/src/components/LoadingSkeleton.tsx`, `frontend/src/components/StatusPill.tsx`,
  `frontend/src/components/StatusPill.test.tsx`, `frontend/src/components/Pagination.tsx`,
  `frontend/src/components/Pagination.test.tsx`]
- **Tests**: `StatusPill.test.tsx` — one render per tone, label is the pill's text.
  `Pagination.test.tsx` — the range line on a middle page, `[Previous]` greyed and out of the tab
  order on page 1, `[Next]` likewise on the last page, and the whole component absent when
  `total <= perPage`.
- **Success Criteria**:
  - `EmptyState` has **no** `action` or `cta` prop. Its absence is what enforces the no-CTA
    divergence until DMI-89 (`ARCHITECTURE.md` §8, divergence 1) — adding one is out of scope.
  - `Pagination` greys the unavailable edge control and removes it from the tab order; it does not
    unmount it (`DESIGN.md` §14.7).
  - `StatusPill` is outline-only, never filled, so a red `Failed` cannot read as a severity badge.
  - No arbitrary Tailwind values and no raw type sizes — the lint rules gate this.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: DataTable

- **Description**: The shared table, per `ARCHITECTURE.md` §5 and `DESIGN.md` §3.1–§3.3. One
  component, a discriminated optional `rowAction` (`link` | `expand` | absent), sortable headings,
  and the loading and empty bodies. Read §5.4 before writing row activation: the `link` variant
  puts a single `<Link>` in the first cell as the sole keyboard target with a `<tr>` mouse handler
  that ignores events originating in an anchor, and the `expand` variant is a real disclosure with
  `aria-expanded` / `aria-controls` over a `<td colSpan>` panel row. That split is what lets scan
  detail's host row carry both a ports disclosure and a link to the host without nesting them.
- **Dependencies**: Task 3
- **Target Files**: [`frontend/src/components/DataTable.tsx`,
  `frontend/src/components/DataTable.test.tsx`]
- **Tests**: `DataTable.test.tsx`, driven with a tiny local row type — headings uppercase from
  `label`; `isPending` renders skeleton rows with headings still present and ignores `rows`;
  `isPending` wins over `empty`; link rows carry `label(row)` as accessible name and navigate on
  row click (`LocationProbe`); expand rows open by keyboard (`Tab` + `Enter`) with `aria-controls`
  matching the panel id; `rowAction: undefined` renders **no button and no link in any row**; only
  `sortable` columns are clickable and the active one carries `aria-sort`.
- **Success Criteria**:
  - The props API matches `ARCHITECTURE.md` §5.1 exactly. No `onRowClick`, no `href` string, no
    `expandable` boolean — each would allow a fourth interaction the component specifies no states
    for.
  - Column widths are named Tailwind fraction utilities, never pixel widths (`SCREENS.md`
    Foundations rule 2).
  - The inert case is asserted, not assumed — this is the test that keeps the ports table inert.
  - Sorting calls `onChange` with the column `key` and decides nothing itself; flip-versus-switch
    and the page reset belong to the caller.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 5: Scan list

- **Description**: SCAN LIST at `/scans`, per `SCREENS.md` § SCAN LIST, `ARCHITECTURE.md` §4.1 and
  `DESIGN.md` §5.1. Owns `page` in component state — **not** in the URL (locked decision 3) — the
  query, and the four states. Adds its own `<Route>` inside the existing `AppShell` route, outside
  `RequireAdmin`, above the `*` catch-all.
- **Dependencies**: Task 1, Task 2, Task 3, Task 4
- **Target Files**: [`frontend/src/pages/Scans.tsx`, `frontend/src/pages/scans/ScanRow.tsx`,
  `frontend/src/pages/Scans.test.tsx`, `frontend/src/App.tsx`]
- **Tests**: `Scans.test.tsx` per `ARCHITECTURE.md` §9.3.
- **Success Criteria**:
  - Advancing a page shows rows 21–25 and **none** of rows 1–20 (TRUTH "Run log paginates").
  - An unfinished row shows "Running…" and `—` in the Hosts, Findings and Highest cells. The test
    asserts the **absence** of `0` and of "None" on that row. This is TRUTH rule 3 and the single
    most important assertion in the file.
  - A completed row shows the neutral "Completed" pill, not `—` (`DESIGN.md` §3.7).
  - The blank state contains **no button and no link** (divergence 1, asserted not assumed).
  - No `th` in this table is a button — the run log has no sort UI.
  - Sends `sort_by=timestamp&sort_order=desc` explicitly rather than relying on a server default.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Scan detail

- **Description**: SCAN DETAIL at `/scans/:scanId`, per `SCREENS.md` § SCAN DETAIL,
  `ARCHITECTURE.md` §4.2 and `DESIGN.md` §5.3–§5.4. One request, everything embedded — opening a
  finding fetches nothing. Owns the four-way `status` branch, `openFindingId`, `openHostId` and the
  `?finding=` deep link. The failure sentence is `scanFailureReason(scan.error_code)`, called once;
  the function already absorbs `null` and `undefined`, so **no null branch is needed** and
  `SCREENS.md`'s separate "no `command_id`" copy line is dead. `[Try another scan]` is **not built**
  — `/agents` has no trigger yet.
- **Dependencies**: Task 1, Task 2, Task 4
- **Target Files**: [`frontend/src/pages/ScanDetail.tsx`,
  `frontend/src/pages/scans/ScanDetailHeader.tsx`, `frontend/src/pages/scans/FindingsTable.tsx`,
  `frontend/src/pages/scans/FindingPanel.tsx`, `frontend/src/pages/scans/ScanHostsTable.tsx`,
  `frontend/src/pages/scans/ScanFailedNotice.tsx`,
  `frontend/src/pages/scans/ScanUnfinishedNotice.tsx`, `frontend/src/pages/ScanDetail.test.tsx`,
  `frontend/src/App.tsx`]
- **Tests**: `ScanDetail.test.tsx` per `ARCHITECTURE.md` §9.4.
- **Success Criteria**:
  - Findings render worst-first from a **deliberately shuffled** fixture.
  - Opening a finding reveals description, recommendation, evidence, references and the CVSS line
    in place, and the route does not change (`LocationProbe`).
  - `?finding=<known>` opens the panel on first paint with **no additional request**;
    `?finding=<unknown>` renders normally with nothing open.
  - `failed` renders the exact operator sentence for `device_offline` and the raw string
    `"device_offline"` appears **nowhere**; neither the findings nor the hosts table is in the DOM.
  - `completed` with no findings renders the clean sentence with **no findings table in the DOM**,
    hosts table still present.
  - `processing` renders the still-running copy plus `Check again`, which re-reads on click. It does
    **not** poll — no `refetchInterval` anywhere in this feature.
  - One test covers both interactions on a host row: the link navigates to `/hosts/:hostId` and the
    disclosure opens its ports.
  - `FindingPanel` is written so host detail can import it verbatim (Task 8 reuses it).
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 7: Host inventory

- **Description**: HOST INVENTORY at `/hosts`, per `SCREENS.md` § HOST INVENTORY,
  `ARCHITECTURE.md` §4.3 and `DESIGN.md` §5.5. Owns `page`, `sortBy`, `sortOrder` in component
  state and the `handleSort` flip-versus-switch rule. Sorting is the server's answer, consuming the
  parameters DMI-100 shipped.
- **Dependencies**: Task 2, Task 3, Task 4
- **Target Files**: [`frontend/src/pages/Hosts.tsx`, `frontend/src/pages/hosts/HostRow.tsx`,
  `frontend/src/pages/Hosts.test.tsx`, `frontend/src/App.tsx`]
- **Tests**: `Hosts.test.tsx` per `ARCHITECTURE.md` §9.5.
- **Success Criteria**:
  - Default order asserts the **first row's hostname**, so the test fails if the request omits the
    sort parameters.
  - Sorting by Host ascending returns to page 1 — the test advances to page 2 first, then sorts,
    then asserts row 1 of the ascending fixture is visible (TRUTH rules 15 and 16 in one test).
  - Clicking the active heading flips direction.
  - **The ordering is the server's**: the handler returns a deliberately unsorted array for one
    `sort_by` value and the page renders it in the order received. A page that re-sorts locally
    fails this and nothing else catches it.
  - The `mac: null` / `hostname: ''` row renders `—` and `(unnamed)` **and still has seven cells**
    (TRUTH rule 17 — the columns remain).
  - Paging shows rows 21–25 and none of 1–20; the blank state carries no action.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Host detail

- **Description**: HOST DETAIL at `/hosts/:hostId`, per `SCREENS.md` § HOST DETAIL,
  `ARCHITECTURE.md` §4.4 and `DESIGN.md` §5.6. Two reads folded into one union by `useHostDetail`,
  mirroring `useOrgDirectory`. Findings are the second read, filtered by `host_id`, and render
  through the **same `FindingPanel`** Task 6 built — import it, do not reimplement it.
- **Dependencies**: Task 2, Task 4, Task 6
- **Target Files**: [`frontend/src/pages/HostDetail.tsx`, `frontend/src/hooks/useHostDetail.ts`,
  `frontend/src/pages/hosts/HostIdentity.tsx`, `frontend/src/pages/hosts/HostFindingsTable.tsx`,
  `frontend/src/pages/hosts/HostPortsTable.tsx`,
  `frontend/src/pages/hosts/HostScanHistoryTable.tsx`, `frontend/src/pages/HostDetail.test.tsx`,
  `frontend/src/App.tsx`]
- **Tests**: `HostDetail.test.tsx` per `ARCHITECTURE.md` §9.6.
- **Success Criteria**:
  - **Only that host's findings appear** — a second host's finding is in the fixture set and absent
    from the page.
  - A finding row opens the same panel as scan detail, with CVE, CVSS and reference links present.
  - `ports: []` renders the positive sentence with **no ports table in the DOM**; when present, the
    ports table has **no interactive element in any row**.
  - A history row navigates to `/scans/:scanId`.
  - **Either** read failing produces the page error state with `[Retry]` — asserted twice, once per
    failing read.
  - 404 on the host read renders the not-found line and `[Back to hosts]`.
  - The page title falls back to the IP when `hostname` is empty.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Agents screen, navigation, and the SCREENS.md amendments

- **Description**: The minimal `/agents` screen and the three new nav items, per
  `ARCHITECTURE.md` §4.5 and `DESIGN.md` §5.7–§5.8. Agents is **permanent, not a placeholder**: one
  state, no fetch, no controls, and copy written so DMI-89 grows it rather than deleting it. This
  task runs last because its nav links must not point at routes that do not exist yet.
- **Absorbed**: the six `docs/ui/SCREENS.md` corrections (`ARCHITECTURE.md` §8) and the screen-index
  rows. Doc write-backs carry no test of their own and belong to the last implementation task; a
  reviewer verifies them by reading the diff against §8's list.
- **Dependencies**: Task 5, Task 6, Task 7, Task 8
- **Target Files**: [`frontend/src/pages/Agents.tsx`, `frontend/src/pages/Agents.test.tsx`,
  `frontend/src/components/TopBar.tsx`, `frontend/src/components/TopBar.test.tsx`,
  `frontend/src/App.tsx`, `docs/ui/SCREENS.md`]
- **Tests**: `Agents.test.tsx` and the extended `TopBar.test.tsx`, per `ARCHITECTURE.md` §9.7.
- **Success Criteria**:
  - Agents renders its title, subtitle and device statement and contains **no button and no link** —
    the assertion that keeps a trigger from appearing before DMI-89 builds one.
  - `nav-scans`, `nav-hosts` and `nav-agents` are present **for a viewer as well as an admin** and
    point at `/scans`, `/hosts`, `/agents`. `nav-users` stays admin-only and unchanged.
  - `/scans` and `/hosts` nav links do **not** use `end`, so a detail route keeps its parent item
    active; `/` keeps its existing `end`.
  - All six SCREENS.md corrections from `ARCHITECTURE.md` §8 are applied: `FindingRead` →
    `FindingRecord`; `device_ip` → `host_ip`; the polling sentence; the blank-state CTA divergence
    with the condition that lifts it; the shared-components table including `Pagination` and the
    real `DataTable` call sites; and the completed-scan Status cell.
  - The full gate passes from a clean install.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ─┐
#2 ─┼─────────────┬──→ #5 ──┐
#3 ─┴──→ #4 ──────┤         ├──→ #9
                  ├──→ #6 ──┼──→ #8 ──┘
                  └──→ #7 ──┘
```

Three tracks open immediately — pure logic (#1), the API and fixtures (#2), and the small
components (#3). #4 gates every screen. #5, #6 and #7 are independent of each other once #4 lands;
#8 waits on #6 only for `FindingPanel`.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Pure status and severity logic | COMPLETED |
| 2 | API layer, query keys, and the test fixtures | COMPLETED |
| 3 | EmptyState, LoadingSkeleton, StatusPill, Pagination | COMPLETED |
| 4 | DataTable | COMPLETED |
| 5 | Scan list | COMPLETED |
| 6 | Scan detail | COMPLETED |
| 7 | Host inventory | COMPLETED |
| 8 | Host detail | COMPLETED |
| 9 | Agents screen, navigation, and the SCREENS.md amendments | COMPLETED |
