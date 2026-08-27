# ARCHITECTURE — Scans and Hosts read surfaces

Frontend-only. React 19 + TypeScript 6 + Vite 8 + Tailwind v4 + TanStack Query v5 +
React Router v7, all under `frontend/`.

**No backend, no contract, no `hardware-agent/` change.** Every endpoint this feature reads
already ships in `contracts/openapi/openapi.yaml` and in the generated
`frontend/src/types/openapi.d.ts`. An implementer editing either file, or `backend/**`, has gone
off-spec.

**No `INTEGRATION.md`.** Nothing here crosses a layer boundary — it is one layer consuming a
contract that is already complete.

Behaviour is fixed by [`TRUTH.md`](TRUTH.md). Copy and layout come from `docs/ui/SCREENS.md`
§§ Foundations, SCAN LIST, SCAN DETAIL, HOST INVENTORY, HOST DETAIL, AGENTS — **referenced, not
transcribed here**. Where this document and SCREENS.md disagree, the divergences are listed
explicitly in §8 and are doc deliverables of this feature.

Load the **`frontend-conventions`** skill before writing any file under `frontend/src/`. It is
binding and carries the API-type rule, the closed type scale, the nine-step spacing scale, the
absent-not-disabled rule, and the React 19 / TanStack v5 / Tailwind v4 traps.

---

## 1. System context

The pipeline this feature sits at the end of:

```
Pi scan → ingest → backend persistence + CVE enrichment → read API → THIS FEATURE → operator
```

Everything left of "read API" is built and shipped. This feature is the first render of the read
API's four list/detail endpoints.

The app shell is unchanged in shape; five routes are added inside it:

```
App.tsx
└── RequireSession                    (exists)
    └── AppShell                      (exists — TopBar + Outlet)
        ├── /                Home     (exists)
        ├── /scans           ScanList         ← NEW
        ├── /scans/:scanId   ScanDetail       ← NEW
        ├── /hosts           HostInventory    ← NEW
        ├── /hosts/:hostId   HostDetail       ← NEW
        ├── /agents          Agents           ← NEW
        ├── /settings        Settings (exists)
        ├── RequireAdmin → /users     (exists)
        └── *                NotFound (exists)

TopBar
└── Home · Scans · Hosts · Agents · Users · Settings · [Log out]
                  ^^^^^   ^^^^^   ^^^^^^  ← NEW nav items
```

**None of the five new routes is wrapped in `RequireAdmin`, and no control on them is role-gated.**
Both roles read everything here (TRUTH rule 1). `AdminOnly` does not appear in any new file. The
nav item order is fixed by SCREENS.md § Foundations — Scans and Hosts after Home, Agents before
Users — and the bar stays the `1fr auto 1fr` centred grid it already is; adding three items changes
nothing about that decision.

**`/agents` is a real screen, not a stub.** It renders the page header, its subtitle, and the
permanent statement that scanning is configured on the device itself. It performs **no fetch** —
`GET /agents` and the trigger belong to DMI-89, which grows this page rather than replacing it.
Every line it ships is a line that survives DMI-89 (`.claude/CLAUDE.md` § No temporary code).

---

## 2. Data model and contracts

### 2.1 The five reads

| Screen | Method + path | Query params sent | Response type |
|---|---|---|---|
| Scan list | `GET /api/v1/scans` | `page`, `per_page=20`, `sort_by=timestamp`, `sort_order=desc` | `ScanListResponse` |
| Scan detail | `GET /api/v1/scans/{scan_id}` | — | `ScanDetailResponse` |
| Host inventory | `GET /api/v1/hosts` | `page`, `per_page=20`, `sort_by`, `sort_order` | `HostListResponse` |
| Host detail | `GET /api/v1/hosts/{host_id}` | — | `HostDetailResponse` |
| Host findings | `GET /api/v1/findings` | `host_id`, `per_page=100` | `FindingListResponse` |

All five go over `apiClient` **imported from `@/api/client`** — never from `@/api/instances`.
`client.ts` is what attaches the `Authorization: Bearer` request interceptor and the single-flight
401-refresh; `instances.ts` exports the bare axios instance and every call made through it answers
`401`. Every business module in the repo already imports from `./client`.

**No `status` filter on the scan list** and **no `q` on the host list**, though the contract offers
both (TRUTH out of scope). **No `GET /findings?scan_id=` on scan detail** — the findings arrive
embedded in `ScanDetailResponse` (TRUTH rule 6).

### 2.2 Types — all generated

Every request and response type is read from `src/types/openapi.d.ts` via
`components['schemas'][…]`. The aliases stay inside `src/api/`, as `api/scans.ts` and
`api/findings.ts` already do:

```ts
type ScanSummary        = components['schemas']['ScanSummary']
type ScanListResponse   = components['schemas']['ScanListResponse']
type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type ScanHostView       = components['schemas']['ScanHostView']
type HostSummary        = components['schemas']['HostSummary']
type HostListResponse   = components['schemas']['HostListResponse']
type HostDetailResponse = components['schemas']['HostDetailResponse']
type HostScanHistoryEntry = components['schemas']['HostScanHistoryEntry']
type Port               = components['schemas']['Port']
type FindingRecord      = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']
type ScanStatus         = components['schemas']['ScanStatus']
type Severity           = components['schemas']['Severity']
```

**Two contract corrections against SCREENS.md — record them, do not code around them:**

1. **`FindingRead` does not exist.** SCREENS.md § SCAN DETAIL and § HOST DETAIL name
   `findings: FindingRead[]`; the contract's type is **`FindingRecord`**, and it is what
   `ScanDetailResponse.findings`, `FindingListResponse.data` and the existing
   `hooks/useHomeReview.ts` already use. Fixing the doc is a deliverable of this feature (§8).
2. **The finding's address field is `host_ip`, not `device_ip`.** SCREENS.md § SCAN DETAIL lists
   `device_ip` among the embedded fields. `FindingRecord` carries `host_id` (nullable) and
   `host_ip` (nullable). Same doc fix.

The full `FindingRecord` shape the panel renders: `finding_id`, `scan_id`, `host_id?`, `host_ip?`,
`port?`, `protocol?`, `service?`, `source?`, `source_script?`, `cve_id?`, `cvss_score?`,
`severity`, `title`, `description`, `recommendation`, `evidence`, `references`, `detected_at`.
Everything the panel needs is on it — **opening a finding fetches nothing** (TRUTH rule 6).

### 2.3 Pagination and sorting are server-driven

`page`, `per_page`, `sort_by`, `sort_order` go on the wire; the page in hand is **never** re-sorted
or re-sliced in the browser (TRUTH rules 14–16). The contract's closed sets:

- `ScanSortBy`: `timestamp | status | scan_mode` — this feature sends **only `timestamp`**.
- `HostSortBy`: `last_seen_at | hostname | vendor | ip` — this feature sends **all four**.
- `SortOrder`: `asc | desc`.

Constants live with the API modules:

```ts
export const SCANS_PER_PAGE = 20
export const HOSTS_PER_PAGE = 20
export const HOST_FINDINGS_PER_PAGE = 100   // mirrors HOME_FINDINGS_PER_PAGE in api/findings.ts
export const SCAN_LIST_SORT = { sort_by: 'timestamp', sort_order: 'desc' } as const
export const HOST_LIST_DEFAULT_SORT_BY = 'last_seen_at'
export const HOST_SORT_DEFAULT_ORDER: Record<HostSortBy, SortOrder> = {
  last_seen_at: 'desc', hostname: 'asc', vendor: 'asc', ip: 'asc',
}
```

**Page and sort state live in component `useState`, not in URL search params.** Decided by the
design session. Consequence, recorded so no reviewer reads it as an oversight: a reload or a shared
link returns to page 1 in the default order. Only `?finding=` is read from the URL (§4.2).

**Sorting rules on the host inventory** (TRUTH rules 15–16, locked):

- Clickable headers on `hostname`, `vendor`, `ip`, `last_seen_at` — and no others. `open_ports_count`
  and `highest_severity` are not in `HostSortBy`; a header the server cannot honour must not look
  clickable.
- Default `last_seen_at` desc.
- Clicking the **active** column flips `sort_order`. Clicking a different column switches `sort_by`
  and resets `sort_order` to that column's entry in `HOST_SORT_DEFAULT_ORDER` — `desc` for
  `last_seen_at` (newest first), `asc` for the three text columns (A–Z first). The map is the
  single source of the rule; there is no branch on a column name in the page.
- **Any sort change resets `page` to 1**, in the same state update as the sort change.

**The scan list has no sort UI at all.** It is fixed at `timestamp` desc (TRUTH rule 2). No column
on it is `sortable`.

### 2.4 Nothing polls

**No `refetchInterval` anywhere in this feature**, and no `setInterval` substitute (TRUTH rule 27).
This includes scan detail, whose `pending`/`accepted`/`processing` state renders as a fact and does
not chase a resolution. Live refresh belongs to DMI-89, together with the trigger that causes it.

**This is a deliberate divergence from SCREENS.md § SCAN DETAIL**, whose "Regular, unfinished"
bullet says the page "polls". Fixing that sentence is a doc deliverable (§8).

Unfinished and failed states are still fully rendered — no polling is not the same as no state.

### 2.5 The failure sentence

On `status: 'failed'`, `ScanDetailResponse.error_code` (`ScanErrorCode | null | undefined`) is
mapped through the shipped helper — **imported, never re-implemented, and never string-formatted
into the page**:

```ts
import { scanFailureReason } from '@/lib/scanFailureReasons'

const reason = scanFailureReason(scan.error_code)
```

`scanFailureReason()` already absorbs both `null` and `undefined` and falls back to the `unknown`
sentence, so **the page needs no null branch and no separate "no reason recorded" copy path** — the
helper is total. The raw `error_code` string is never rendered (TRUTH rule 4).

`ScanSummary` carries **no `error_code`**, so the scan **list** row shows only "Failed"; the
sentence lives on the detail page, which is where the contract puts the code.

### 2.6 Status rendering — `StatusPill`

`ScanStatus` is `pending | accepted | processing | completed | failed`. The mapping this feature
ships, drawn from SCREENS.md § SCAN LIST copy:

| `status` | Pill |
|---|---|
| `pending`, `accepted`, `processing` | "Running…", tone `running` |
| `failed` | "Failed", tone `failed` |
| `completed` | "Completed", tone `neutral` |

The completed pill **diverges from SCREENS.md**, which specifies `—` in that cell. Settled at the
visual gate 2026-08-26: an em dash means "looked, nothing there" everywhere else in this product,
which is the wrong sentence about a scan that succeeded. It is neutral ink, never green — a success
color would be a new Foundations token competing with the severity badge on the same row. See
`DESIGN.md` §3.7. The SCREENS.md copy-table correction is a doc deliverable (§8).

TRUTH rule 3 is the whole point: an unfinished scan shows the pill **in place of** its counts, and
its `host_count` / `finding_count` / `highest_severity` cells render "—", never `0` and never
"None". A `0` on an unfinished scan asserts "clean" about a scan that has not looked.

`StatusPill` takes a `tone` and a `label`, not a `ScanStatus` — DMI-89 renders the seven-state
`CommandStatus` through the same component (SCREENS.md § Shared components), and a component that
switches on `ScanStatus` internally cannot serve it:

```ts
type StatusPillTone = 'running' | 'failed' | 'neutral'
function StatusPill({ tone, label }: { tone: StatusPillTone; label: string }): ReactElement
```

The `ScanStatus → { tone, label } | null` mapping is a pure function in `src/lib/scanStatus.ts`,
unit-tested without React.

---

## 3. Query keys — `src/api/queryKeys.ts` (new)

Prefix-shaped, so `invalidateQueries({ queryKey: ['scans'] })` sweeps a whole domain:

```ts
export const queryKeys = {
  scans: {
    all: ['scans'] as const,
    latest: (scope: 'any' | 'completed') => ['scans', 'latest', scope] as const,
    list: (params: ScanListParams) => ['scans', 'list', params] as const,
    detail: (scanId: string) => ['scans', 'detail', scanId] as const,
  },
  hosts: {
    all: ['hosts'] as const,
    list: (params: HostListParams) => ['hosts', 'list', params] as const,
    detail: (hostId: string) => ['hosts', 'detail', hostId] as const,
  },
  findings: {
    all: ['findings'] as const,
    list: (params: FindingListParams) => ['findings', 'list', params] as const,
  },
} as const
```

`ScanListParams` / `HostListParams` / `FindingListParams` are the **exact param objects sent to the
server**, so a page change or a sort change is a different key and refetches by construction. They
are declared in the api modules and re-exported through `queryKeys.ts`.

**Home's existing keys migrate onto this hierarchy in the same feature** (locked decision 10). In
`hooks/useHomeReview.ts`:

| Today | Becomes |
|---|---|
| `['scans', 'latest']` | `queryKeys.scans.latest('any')` → `['scans','latest','any']` |
| `['scans', 'latest', 'completed']` | `queryKeys.scans.latest('completed')` |
| `['findings', scanId, severity]` | `queryKeys.findings.list({ scan_id: scanId, severity })` |

Two notes for the implementer:

- The bare `['scans','latest']` key is a **prefix of** `['scans','latest','completed']`, which is
  exactly the shape that makes a later `invalidateQueries` hit one query and silently miss its
  sibling's relationship. Giving both a leaf discriminator (`'any'` / `'completed'`) is the point of
  the migration, not cosmetics.
- The findings key is built with `scanId` possibly `undefined` (the query is gated by `skipToken`
  until the scan id lands). TanStack's key hash is `JSON.stringify` with sorted keys, which drops
  `undefined` members, so the key stays stable and the existing `skipToken` narrowing is unchanged.
  **Keep `skipToken`** — do not swap it for `enabled`, which does not narrow the type.

**This feature ships the hierarchy only.** No `invalidateQueries` call site is added, and **no
unused invalidation helper is written** — the first real invalidation is DMI-89's, when a completed
scan needs to sweep `['scans']`, `['hosts']` and `['findings']`.

---

## 4. Data flow per screen

Every screen follows the same discipline: **the page renders a state, never raw query flags.**
Loading, error, empty and not-found are decided once at the top of the page component and each
returns its own element. TanStack v5 spellings: **`isPending`, never `isLoading`**; **no
`onSuccess`/`onError`** on `useQuery` — they are removed and silently no-op.

Error precedence is `isError` → `isPending` → data, mirroring `useOrgDirectory` /`useHomeReview`:
a fast failure must not sit behind a slow success.

`retry` is `query.refetch`, wired to the `[Retry]` button of the page-level error state.

### 4.1 `/scans` — SCAN LIST

- **Query:** `queryKeys.scans.list({ page, per_page: 20, ...SCAN_LIST_SORT })` →
  `listScans(params)` → `GET /scans`.
- **State:** `const [page, setPage] = useState(1)`. No sort state — the order is a constant.
- **Loading (first load):** `DataTable` with `isPending`, which renders `LoadingSkeleton` rows in
  the table body **with the headings still in place**. `isPending` is true only on first load for a
  given key; a page change fetches a new key, so a new page *does* show the skeleton, which is
  correct — there are no rows for that page yet. A background refetch of a key that already has
  data never does (TRUTH rule 25).
- **Error:** page-level copy + `[Retry]`, per SCREENS.md § SCAN LIST copy table. The table is not
  rendered.
- **Empty (`total === 0`):** `EmptyState` with the SCREENS.md blank heading and body, **and no
  CTA** — see §8, divergence 1.
- **Regular:** `DataTable` with `rowAction: { kind: 'link', to: scan => /scans/${scan.scan_id} }`,
  plus `Pagination` beneath it. Columns per SCREENS.md § SCAN LIST ("When · Mode · Status · Hosts ·
  Findings · Highest severity"); unfinished rows follow §2.6.
- Pagination is hidden when `total <= per_page`; `[Previous]` is absent on page 1 and `[Next]`
  absent on the last page (`page * per_page >= total`) — **absent, not disabled**, per Foundations
  consistency rule 3, since a control that navigates nowhere is out of scope.

### 4.2 `/scans/:scanId` — SCAN DETAIL

- **Query:** `queryKeys.scans.detail(scanId)` → `getScan(scanId)` → `GET /scans/{scan_id}`. **One
  request; nothing else is fetched by this page** (TRUTH rule 6).
- **404:** `readApiError(err).status === 404` → the distinct not-found line + `[Back to scans]`,
  per SCREENS.md. Any other error → generic copy + `[Retry]`. `readApiError` is the shipped helper
  in `src/api/apiError.ts`; do not inspect `AxiosError` directly.
- **Branching on `status`, in this order:**
  1. `failed` → `ScanFailedNotice` carrying `scanFailureReason(scan.error_code)`. **The findings and
     hosts tables are not rendered at all** (TRUTH rule 10). SCREENS.md's `[Try another scan]`
     button is **not built** — `/agents` has no trigger yet, and the conventions forbid a control
     that navigates to an action its destination cannot perform.
  2. `pending | accepted | processing` → `ScanUnfinishedNotice` with the SCREENS.md "still running"
     copy. No findings table, no empty-findings claim (TRUTH rule 11).
  3. `completed`, `findings.length === 0` → the positive "every host came back clean" sentence, and
     the hosts table still renders and carries the page (TRUTH rule 9).
  4. `completed`, findings present → findings table, then hosts table.
- **Ordering:** findings are sorted **worst-first in the page**, by a pure
  `bySeverityDesc` comparator in `src/lib/severity.ts` over the `critical > high > medium > low`
  order. This is the one ordering this feature does client-side, and it is legitimate: the array is
  embedded in a single response, is not paginated, and the contract exposes no sort parameter for
  it. Ties keep the server's order (`Array.prototype.sort` is stable).
- **Findings table:** `rowAction: { kind: 'expand', panel: FindingPanel }`. **Controlled** open
  state — `const [openFindingId, setOpenFindingId] = useState<string | null>(null)`.
- **Hosts table:** `rowAction: { kind: 'expand', panel: HostPortsPanel }` with its own
  `openHostId` state. `ScanHostView` carries `host_id` and `ports: Port[]`, so the panel needs no
  fetch. **The "Host" cell contains a `Link` to `/hosts/:hostId`** (TRUTH rule 12) — see §5.4 for
  why a link inside an expand row is legal and how it is kept from toggling the row.
- **`?finding=:findingId`:** read with `useSearchParams()` from `react-router`. On mount, if the id
  matches a `finding_id` in the already-loaded `findings`, seed `openFindingId` with it; `DataTable`
  scrolls the newly-opened row into view (§5.3). An absent or unmatched id renders the page normally
  with nothing open. **No extra fetch, and no `GET /findings/{id}`** (TRUTH rule 13).
  `Element.prototype.scrollIntoView` is already stubbed in `src/test/setup.ts`; do not add a stub.

### 4.3 `/hosts` — HOST INVENTORY

- **Query:** `queryKeys.hosts.list({ page, per_page: 20, sort_by, sort_order })` →
  `listHosts(params)` → `GET /hosts`.
- **State:** `useState` for `page`, `sortBy`, `sortOrder`, defaulting to `1`,
  `HOST_LIST_DEFAULT_SORT_BY`, and that column's `HOST_SORT_DEFAULT_ORDER` entry. One handler owns
  the rules in §2.3:

  ```ts
  function handleSort(key: HostSortBy) {
    setSortOrder(
      key === sortBy
        ? sortOrder === 'desc' ? 'asc' : 'desc'
        : HOST_SORT_DEFAULT_ORDER[key],
    )
    setSortBy(key)
    setPage(1)          // never omit — rule 16
  }
  ```
- **Loading / error / empty:** identical treatment to §4.1, with § HOST INVENTORY copy and **no
  CTA** (§8).
- **Regular:** `DataTable` with `rowAction: { kind: 'link', to: host => /hosts/${host.host_id} }`
  and `sort={{ by: sortBy, order: sortOrder, onChange: handleSort }}`. Columns per SCREENS.md
  § HOST INVENTORY.
- **Absent identifiers (TRUTH rule 17):** `mac === null` renders "—"; `hostname === ''` renders
  "(unnamed)". Both keep their column. `hostname` is a **required non-nullable string** on
  `HostSummary`, so the empty case is `''`, not `null` — check truthiness, not nullness.

### 4.4 `/hosts/:hostId` — HOST DETAIL

- **Two queries**, because `HostDetailResponse` carries no findings (TRUTH rule 20):
  - `queryKeys.hosts.detail(hostId)` → `GET /hosts/{host_id}`
  - `queryKeys.findings.list({ host_id: hostId, per_page: 100 })` → `GET /findings?host_id=…`
- **Composition: none — the two reads stay independent.** The host query alone is the page state
  (`readDetailState` → `ReadDetailGate`); a 404 on it is `notFound`, and a 404 cannot come from the
  findings query (a filter that matches nothing returns an empty list). The findings query lives in
  `HostFindings`, which owns its own pending / error / empty states per DESIGN §5.6 and TRUTH rule
  23. **Do not fold them into one union.** A `useHostDetail` hook that did exactly that was built
  and deleted: it threw away a loaded host — identity, ports, scan history — whenever the findings
  read was pending or failed. The `useHomeReview` / `useOrgDirectory` fold is correct *there*
  because those reads compose into a single verdict; these two do not.
- **Sections:** identity header, findings, open ports, scan history.
  - **Findings** — same rows and same in-place panel as scan detail; the panel component is shared
    verbatim (`pages/scans/FindingPanel.tsx`). No findings → the positive sentence, no table.
    Pending → the skeleton body (`FindingsTable`'s `isPending`, checked **before** the empty branch,
    so a pending section never claims "No findings"). Failed → `host-findings-error` carrying
    "Couldn't load this host's findings." plus `[Retry]`, which refetches findings only.
  - **Ports** — `DataTable` with **`rowAction: undefined`**. An inert table: no link, no expand, no
    row cursor, no row focus target. `ports.length === 0` → the positive "isn't exposing anything"
    sentence and no table (TRUTH rule 21). Row identity is `${port}/${protocol}`; `Port` has no id.
  - **Scan history** — `DataTable` with `rowAction: { kind: 'link', to: e => /scans/${e.scan_id} }`
    (TRUTH rule 22).
- **Page title** is `hostname` or, when it is empty, the `ip` (SCREENS.md § HOST DETAIL).

### 4.5 `/agents` — AGENTS (minimal, permanent)

No query, no `useState`, no fetch, and therefore **no MSW handler needed**. Renders `PageHeader`
with the § AGENTS page title and subtitle, and one permanent line stating that scanning is set up
on the Pi itself — the same fact `pages/home/HomeBlank.tsx` already tells the operator, so the two
must not contradict each other. No `[Scan now]`, no status pill, no network chooser: DMI-89 adds
those to this file.

---

## 5. `DataTable` — the shared table

**One component, seven call sites.** It is *built* in the scan-list task and *designed here against
all seven*, so nothing about it is retrofitted later. It owns: the `colgroup` shares, the uppercase
`<thead>`, the sort-header affordance, the skeleton body, the empty body, row interaction, and the
expanded panel row. It owns **no** page state, **no** fetching, and **no** pagination.

### 5.1 Props

```ts
import type { ReactNode } from 'react'

export type SortOrder = 'asc' | 'desc'

export type DataTableColumn<Row> = {
  /** Stable identity. For a sortable column this MUST be the server's sort_by value. */
  key: string
  /** Heading text. Rendered uppercase by the component — pass it in sentence case. */
  label: string
  /** A named Tailwind fraction utility for the <colgroup>, e.g. 'w-1/4'. Never a pixel width. */
  width: string
  render: (row: Row) => ReactNode
  sortable?: boolean
}

export type DataTableSort = {
  by: string
  order: SortOrder
  /** Receives the clicked column's `key`. The caller owns flip-vs-switch and the page reset. */
  onChange: (key: string) => void
}

export type DataTableRowAction<Row> =
  | {
      kind: 'link'
      to: (row: Row) => string
      /** Accessible name of the row's link. Never "View" — name the destination. */
      label: (row: Row) => string
    }
  | {
      kind: 'expand'
      panel: (row: Row) => ReactNode
      /** Accessible name of the row's disclosure trigger. */
      label: (row: Row) => string
      openRowId: string | null
      onOpenRowChange: (rowId: string | null) => void
    }

export type DataTableProps<Row> = {
  columns: DataTableColumn<Row>[]
  rows: Row[]
  rowId: (row: Row) => string
  /** `data-testid` of the <table>; rows get `${testId}-row-${rowId(row)}`. */
  testId: string
  /** sr-only <caption> — the table's accessible name. Required. */
  caption: string
  /** First-load only. True renders skeleton rows in place of the body; `rows` is ignored. */
  isPending?: boolean
  skeletonRows?: number          // default 3, matching DirectoryTable
  /** Rendered in place of the body when `rows` is empty and `isPending` is false. */
  empty?: ReactNode
  sort?: DataTableSort
  /** Omit for an inert table. */
  rowAction?: DataTableRowAction<Row>
}

export default function DataTable<Row>(props: DataTableProps<Row>): ReactElement
```

`rowAction` is a **discriminated union on `kind`, and it is optional** — the three shapes locked by
the design session. There is no `onRowClick`, no `href` string, no `expandable` boolean: each of
those would let a call site build a fourth interaction the component does not specify states for.

### 5.2 The seven call sites

| # | Table | `rowAction` | Sort | Columns (`width`) |
|---|---|---|---|---|
| 1 | Scan list | `link` → `/scans/:scanId` | none | When `w-1/4` · Mode `w-1/8` · Status `w-1/8` · Hosts `w-1/8` · Findings `w-1/8` · Highest `w-1/4` |
| 2 | Host inventory | `link` → `/hosts/:hostId` | `hostname`, `vendor`, `ip`, `last_seen_at` | Host `w-1/5` · IP `w-3/20` · MAC `w-1/5` · Vendor `w-3/20` · Ports `w-1/10` · Highest `w-1/10` · Last seen `w-1/10` |
| 3 | Host detail → scan history | `link` → `/scans/:scanId` | none | When `w-2/5` · Mode `w-1/5` · Open ports `w-1/5` · Highest `w-1/5` |
| 4 | Scan detail → findings | `expand` → `FindingPanel` | none | Severity `w-3/20` · Finding `w-2/5` · Host `w-1/5` · Port `w-1/10` · CVE `w-3/20` |
| 5 | Scan detail → hosts | `expand` → `HostPortsPanel` | none | Host `w-1/4` · IP `w-1/5` · MAC `w-1/4` · Vendor `w-1/5` · Open ports `w-1/10` |
| 6 | Host detail → findings | `expand` → `FindingPanel` | none | Severity `w-3/20` · Finding `w-1/2` · Port `w-1/10` · CVE `w-1/4` |
| 7 | Host detail → open ports | **`undefined`** (inert) | none | Port `w-1/5` · Protocol `w-1/5` · Service `w-1/5` · Version `w-2/5` |

Every set of shares sums to 1, as `DirectoryTable`'s comment explains: shares, not pixel widths, so
the table scales with the 70rem frame. Cells that can carry a long value (`Finding`, `Host`, `MAC`,
`Service`, `Version`) use `max-w-0 truncate` with a `title`, matching `DirectoryTable`.

### 5.3 Behaviour

- **`isPending` wins over `empty`, and `empty` wins over rows.** The headings and the `colgroup`
  render in all three cases, so the table never collapses or jumps width between states.
- The `link` and `expand` rows specify the full interactive state set — cursor, hover, focus-visible,
  active — in **one place**, which is the reason this component exists (Foundations building rule 6,
  `local/no-bare-interactive`).
- **Scroll-into-view:** when `rowAction.kind === 'expand'` and `openRowId` changes to a non-null id,
  the component calls `scrollIntoView({ block: 'nearest' })` on that row. This is what makes the
  `?finding=` deep link land in view (TRUTH rule 13) without the page holding a DOM ref, and it is a
  no-op for an already-visible row, so a plain click is unaffected.
- **`sort` renders the affordance only on columns marked `sortable`.** The active column's `<th>`
  carries `aria-sort="ascending" | "descending"`; every other `<th>` carries
  `aria-sort="none"` when `sort` is supplied and no `aria-sort` when it is not.

### 5.4 Row activation — keyboard and accessibility

This is the part an implementer is most likely to get wrong, so it is specified rather than left to
"make the row clickable".

**`kind: 'link'`.** An `<a>` may not wrap a `<tr>`, and a row may not contain two competing link
targets. So:

- The row's **first cell** contains one `<Link>` (from `react-router`) whose text is the cell's
  content and whose accessible name is `label(row)`. That link is the row's single keyboard target
  and its single semantic destination — it is what a screen reader and a middle-click both get.
- The `<tr>` carries an `onClick` that calls `navigate(to(row))` so the *whole* row is a mouse
  target (Foundations consistency rule 4). It **returns early when the event originated inside an
  `<a>`** (`(event.target as HTMLElement).closest('a')`), so a real click on the link navigates once,
  through the link, and not twice.
- The `<tr>` gets **no `tabIndex` and no `role="button"`** — adding either creates a second keyboard
  stop announcing the same destination. Keyboard users reach the row through its link.
- No other interactive element is placed in a `link` row. That is what keeps the DOM legal.

**`kind: 'expand'`.** The row is a **disclosure**:

- The first cell contains a `Button` (`@/components/ui/button`, `variant="link"`) as the trigger,
  carrying `aria-expanded={isOpen}`, `aria-controls={panelId}` and the accessible name `label(row)`.
  `aria-controls` uses a `useId()`-derived id owned by `DataTable`, for the same reason
  `Disclosure.tsx` owns its own: the attribute has to survive the collapsed state.
- The panel is a **second `<tr>`** immediately after the row, containing one `<td colSpan={n}>`,
  rendered only when open, with `id={panelId}`.
- The `<tr>` `onClick` toggles the same state, giving the whole-row mouse target, and returns early
  when the event originated inside a `button` or an `a` — which is exactly what lets **scan detail's
  host row carry a `Link` to `/hosts/:hostId` inside an expandable row** (TRUTH rules 8 and 12
  together). Two interactive elements, two distinct actions, neither nested in the other, both
  keyboard-reachable in DOM order: trigger first, host link second.
- **`Disclosure.tsx` is not reused and not modified.** It renders a label-plus-caret block above its
  content and cannot be a `<tr>`; wedging a table row into it would change a shipped shared
  component for one call site.

**`rowAction: undefined`.** The row is inert: no handler, no cursor change, no hover treatment, no
focus target. The ports table must not look clickable.

---

## 6. The other three shared components

| Component | Props | Notes |
|---|---|---|
| `EmptyState` | `{ heading: string; body: string; testId: string }` | Heading is IM Fell (≥16px), body is muted Plex Mono. **No `action` / `cta` prop** — see §8, divergence 1. Its absence is the enforcement mechanism, not a preference; adding the prop later is DMI-89's change. |
| `LoadingSkeleton` | `{ rows: number; columns: number }` | The `<tbody>` of grey bars, generalised from `DirectoryTable`'s private `SkeletonRows`. Rendered only by `DataTable`. |
| `StatusPill` | `{ tone: 'running' \| 'failed' \| 'neutral'; label: string }` | §2.6. Tone-and-label, not `ScanStatus`, so DMI-89's `CommandStatus` reuses it unchanged. |
| `Pagination` | `{ page, perPage, total, onPageChange, testId }` | **A fifth shared file, needed by two call sites** (scan list, host inventory) and therefore qualifying under SCREENS.md § Shared components' own "two or more screens" rule. Renders the "Showing 1–20 of 47" line and `[Previous]`/`[Next]`; hides itself when `total <= perPage`. At a page boundary the unavailable control is **greyed and out of the tab order, not removed** — settled at the visual gate 2026-08-26, matching `DESIGN.md` §5.1. This is the §Consistency rule 3 *progress* carve-out, not the permission rule: the operator is permitted to page, there is simply no page there. Removing it would shift the footer's contents by a button width between pages. Adding it to the § Shared components table is a doc deliverable (§8). |

**No retrofit.** `pages/users/DirectoryTable.tsx` and `pages/home/HomeBlank.tsx` are **not** moved
onto `DataTable` / `EmptyState` in this feature (TRUTH out-of-scope, locked decision 8). This is a
deliberate decision with a separate tracked follow-up issue, **not an oversight** — a reviewer
seeing two table implementations and two blank-state implementations in the tree is seeing the
intended end state of *this* issue. Retrofitting Users would put a shipped admin screen's four
states inside a component being written in the same PR.

---

## 7. New files and naming (mandatory)

Every file an implementer creates or touches. **Paths not in this table are out of scope**, and no
file outside it may be invented.

### API layer

| Path | Change | Notes |
|---|---|---|
| `frontend/src/api/queryKeys.ts` | **new** | The key hierarchy in §3 and the three param types. No fetching, no invalidation helper. |
| `frontend/src/api/scans.ts` | **extend** | Add `listScans(params)`, `getScan(scanId)`, `SCANS_PER_PAGE`, `SCAN_LIST_SORT`, `ScanListParams`. Leave `getLatestScan` / `getLatestSuccessfulScan` and their two exported query constants untouched — Home depends on them. |
| `frontend/src/api/hosts.ts` | **new** | `listHosts(params)`, `getHost(hostId)`, `HOSTS_PER_PAGE`, `HOST_LIST_DEFAULT_SORT_BY`, `HOST_SORT_DEFAULT_ORDER`, `HostListParams`, `HostSortBy`. |
| `frontend/src/api/findings.ts` | **extend** | Add `HOST_FINDINGS_PER_PAGE` and widen the single `listFindings(params: FindingListParams)` wrapper to carry the host filter — `GET /findings` has one operation, so it keeps one wrapper. Leave `HOME_SEVERITIES` untouched. |

### Shared components

| Path | Change | Notes |
|---|---|---|
| `frontend/src/components/DataTable.tsx` | **new** | §5. Built in the scan-list task, designed against all seven call sites. |
| `frontend/src/components/EmptyState.tsx` | **new** | §6. No action prop. |
| `frontend/src/components/LoadingSkeleton.tsx` | **new** | §6. |
| `frontend/src/components/StatusPill.tsx` | **new** | §6, §2.6. |
| `frontend/src/components/Pagination.tsx` | **new** | §6. Two call sites. |
| `frontend/src/components/ErrorRetry.tsx` | **new** | §6. The error notice + Retry button, shared by both list and both detail surfaces. |
| `frontend/src/components/NotFoundNotice.tsx` | **new** | §6. The 404 notice + back link, shared by both detail surfaces. |
| `frontend/src/components/ListSurface.tsx` | **new** | The whole list-page state machine (error / pending / empty / rows + pagination) in one place. `/scans` and `/hosts` pass columns and copy; neither owns a branch. |
| `frontend/src/components/ReadDetailGate.tsx` | **new** | The detail-page counterpart: owns `notFound` / `error` / `loading` and the placeholder `PageHeader`, renders `children(data)` only when ready. `ScanDetail` and `HostDetail` own no read-state branch — the scan `failed` / unfinished split stays in `ScanDetail`, because that is domain, not read state. |
| `frontend/src/components/EmptyMark.tsx` | **new** | The `—` absence mark (TRUTH rule 17). One definition; every column module imports it. |

### Pure logic

| Path | Change | Notes |
|---|---|---|
| `frontend/src/lib/scanStatus.ts` | **new** | `ScanStatus → { tone, label } \| null`, and the `isUnfinished(status)` predicate the counts cells branch on. No React. |
| `frontend/src/lib/severity.ts` | **new** | `SEVERITY_ORDER` and `bySeverityDesc` (§4.2). No React. |
| `frontend/src/lib/detailState.ts` | **new** | `DetailState<T>` and `readDetailState(id, query)` — the one place a detail query becomes `notFound` / `error` / `loading` / `ready`. Consumed by `ReadDetailGate`, produced inline by `ScanDetail` and `HostDetail`. No React. |
| `frontend/src/lib/scanFailureReasons.ts` | **untouched** | Imported as-is (§2.5). Do not extend, do not re-map. |

### Screens

| Path | Change | Notes |
|---|---|---|
| `frontend/src/pages/Scans.tsx` | **new** | SCAN LIST. Owns `page` state, the query, and the four states. |
| `frontend/src/pages/scans/ScanRow.tsx` | **new** | The scan list's cell renderers, including the unfinished-vs-counts rule. |
| `frontend/src/pages/ScanDetail.tsx` | **new** | SCAN DETAIL. Owns the `status` branch, `openFindingId`, `openHostId`, and `?finding=`. |
| `frontend/src/pages/scans/ScanDetailHeader.tsx` | **new** | Title + the "quick mode · subnet · counts" line. |
| `frontend/src/pages/scans/FindingsTable.tsx` | **new** | `DataTable` call site 4 + the worst-first sort + the clean-scan sentence. |
| `frontend/src/pages/scans/FindingPanel.tsx` | **new** | The in-place panel. **Shared verbatim with host detail** (call site 6). |
| `frontend/src/pages/scans/ScanHostsTable.tsx` | **new** | `DataTable` call site 5 + `HostPortsPanel`. |
| `frontend/src/pages/scans/ScanFailedNotice.tsx` | **new** | The failure sentence from `scanFailureReason()`. No `[Try another scan]` button (§4.2). |
| `frontend/src/pages/scans/ScanUnfinishedNotice.tsx` | **new** | The still-running copy. |
| `frontend/src/pages/Hosts.tsx` | **new** | HOST INVENTORY. Owns `page` / `sortBy` / `sortOrder` and `handleSort`. |
| `frontend/src/pages/hosts/HostRow.tsx` | **new** | Cell renderers, including "(unnamed)" and the null-MAC "—". |
| `frontend/src/pages/HostDetail.tsx` | **new** | HOST DETAIL. One `getHost` query through `readDetailState` into `ReadDetailGate`; owns no read-state branch. |
| `frontend/src/pages/hosts/HostFindings.tsx` | **new** | The findings section's own query and its own three states (§4.4). |
| `frontend/src/pages/hosts/HostIdentity.tsx` | **new** | Title, the address line, the seen line. |
| `frontend/src/pages/hosts/HostFindingsTable.tsx` | **new** | `DataTable` call site 6, reusing `FindingPanel`. |
| `frontend/src/pages/hosts/HostPortsTable.tsx` | **new** | `DataTable` call site 7 (inert) + the no-ports sentence. |
| `frontend/src/pages/hosts/HostScanHistoryTable.tsx` | **new** | `DataTable` call site 3. |
| `frontend/src/pages/Agents.tsx` | **new** | §4.5. Permanent copy, no fetch, no state. |

`src/pages/<screen>/` sub-folders follow the existing `src/pages/home/` and `src/pages/users/`
precedent. Do not invent a different layout, and do not put screen-specific components in
`src/components/`.

### Hooks and wiring

| Path | Change | Notes |
|---|---|---|
| `frontend/src/hooks/useHomeReview.ts` | **extend** | **Key migration only** (§3). Three `queryKey` lines change; the `skipToken` narrowing, the resolution order and the returned union are untouched. |
| `frontend/src/App.tsx` | **extend** | Five `<Route>`s inside the existing `AppShell` route, **outside** `RequireAdmin`, above the `*` catch-all. |
| `frontend/src/components/TopBar.tsx` | **extend** | Three `NavLink`s — `nav-scans`, `nav-hosts`, `nav-agents` — in the Foundations order (Home · Scans · Hosts · Agents · Users · Settings). Not wrapped in `AdminOnly`. `/scans` and `/hosts` **must not** use `end`, so a detail route keeps its parent nav item active; `/` keeps its existing `end`. |

### Tests and harness

| Path | Change | Notes |
|---|---|---|
| `frontend/src/test/mswHandlers.ts` | **extend** | §9.1. **Replace** the bare-array `/hosts` handler. Add `paginate`, `/scans/:scanId`, `/hosts/:hostId`, host-filtered `/findings`, and the 25-row fixtures. |
| `frontend/src/test/scansHarness.ts` | **new** | Per-test overrides, following `test/usersHarness.ts`. |
| `frontend/src/test/hostsHarness.ts` | **new** | Same. |
| `frontend/src/components/DataTable.test.tsx` | **new** | §9.2. |
| `frontend/src/components/StatusPill.test.tsx` | **new** | §9.2. |
| `frontend/src/components/Pagination.test.tsx` | **new** | §9.2. |
| `frontend/src/lib/scanStatus.test.ts` | **new** | Pure. |
| `frontend/src/lib/severity.test.ts` | **new** | Pure. |
| `frontend/src/pages/Scans.test.tsx` | **new** | §9.3. |
| `frontend/src/pages/ScanDetail.test.tsx` | **new** | §9.4. |
| `frontend/src/pages/Hosts.test.tsx` | **new** | §9.5. |
| `frontend/src/pages/HostDetail.test.tsx` | **new** | §9.6. |
| `frontend/src/pages/Agents.test.tsx` | **new** | §9.7. |
| `frontend/src/components/TopBar.test.tsx` | **extend** | The three new nav items, present for **both** roles. |

### Deliberately not touched

| Path | Why |
|---|---|
| `frontend/src/pages/users/DirectoryTable.tsx` | No retrofit onto `DataTable` — tracked follow-up (§6). |
| `frontend/src/pages/home/HomeBlank.tsx` | No retrofit onto `EmptyState` — same follow-up. |
| `frontend/src/components/Disclosure.tsx` | Not reusable as a table row and not modified for one (§5.4). |
| `frontend/src/components/Timestamp.tsx`, `SeverityBadge.tsx`, `PageHeader.tsx` | Reused **as-is**. They already cover every cell this feature renders; adding a prop for one call site is a visible change to a shared component. |
| `frontend/src/api/instances.ts`, `client.ts` | One HTTP layer, already correct. |
| `frontend/src/test/setup.ts` | `scrollIntoView` is already stubbed. Do not add a second stub. |
| `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts` | The contract is complete and generated. Hand-editing either breaks `npm run gen:types`. |
| `backend/**`, `hardware-agent/**` | No work in this issue. |

---

## 8. Documentation deliverables

This feature amends `docs/ui/SCREENS.md`. These edits are part of the work, not follow-up:

1. **The blank-CTA divergence.** § SCAN LIST and § HOST INVENTORY copy tables specify a
   `[Run first scan]` CTA for admins and an "Ask your admin" line for viewers. **Neither ships.**
   Both blank states explain and offer no action (TRUTH rule 24). The reason is § Foundations
   consistency rule 8, *buttons say what they do*: `/agents` has no trigger until DMI-89, so a
   "Run first scan" button would name an action its destination cannot perform. Record the
   divergence in both copy tables with the condition that lifts it — the CTA returns when the
   trigger exists, and not before.
2. **`FindingRead` → `FindingRecord`**, in § SCAN DETAIL and § HOST DETAIL (§2.2). The named type
   does not exist in the contract.
3. **`device_ip` → `host_ip`** in § SCAN DETAIL's embedded-fields list (§2.2).
4. **The polling sentence.** § SCAN DETAIL's "Regular, unfinished" bullet says the page "polls".
   Nothing in this feature polls (TRUTH rule 27); the state renders once. Amend the bullet and note
   that live refresh arrives with the trigger.
5. **§ Shared components table.** `DataTable`'s "Used by" cell lists Users & invites; **Users is not
   retrofitted** (§6). Record the real call sites — scan list, host inventory, scan detail findings
   and hosts, host detail findings, ports and history — and note Users as a tracked follow-up. Add
   the `Pagination` row for its two call sites.
6. **The completed-scan Status cell.** § SCAN LIST's copy table specifies "(no pill; show the
   counts)" and renders `—`. A neutral "Completed" pill ships instead (§2.6, `DESIGN.md` §3.7),
   because an em dash means "looked, nothing there" everywhere else in the product. Record the new
   copy and the reason it is not a success color.

The screen index rows for Scan list, Scan detail, Host inventory, Host detail and Agents should
also record that the SPA screens are built (DMI-88), with Agents marked as the read-only surface
that DMI-89 grows.

---

## 9. Testing expectations

Vitest + Testing Library + MSW, mirroring the existing suites under `frontend/src/**/*.test.tsx`.
Assert on **user-visible text and `data-testid`**, never on query internals, never on a request
having been sent. Render through `renderWithProviders(ui, { route })`; `MemoryRouter` there already
accepts the initial route, which is how `/scans/:scanId?finding=…` is driven.

`server.listen({ onUnhandledRequest: 'error' })` is on, so **every new endpoint needs a default
handler in `mswHandlers.ts`** or unrelated suites fail.

### 9.1 MSW defaults — pagination- and sort-aware

The default handlers must answer the way the server does, so a paging test can assert **rows 21–25
appear and rows 1–20 do not**, rather than asserting "we sent `page=2`". One shared helper:

```ts
export function paginate<T>(rows: T[], url: string) {
  const params = new URL(url).searchParams
  const page = Number(params.get('page') ?? 1)
  const perPage = Number(params.get('per_page') ?? 20)
  const start = (page - 1) * perPage
  return { data: rows.slice(start, start + perPage), total: rows.length, page }
}
```

- **`scanFixtures`: 25 `ScanSummary` rows**, real subnets and modes, descending by `timestamp`, and
  including at least one `processing` row and one `failed` row. The `/scans` handler filters by
  `status` when present, then paginates.
- **`hostFixtures`: 25 `HostSummary` rows** with distinct `hostname`, `vendor` and `ip` values, plus
  **one row with `mac: null` and `hostname: ''`**. The `/hosts` handler sorts by `sort_by` /
  `sort_order` **before** paginating — a sort test that pages is otherwise untestable.
- **`GET /scans/:scanId`** resolves from the fixtures, and returns `404` for an unknown id.
- **`GET /hosts/:hostId`** the same, with `ports` and `scan_history` populated.
- **`GET /findings`** keeps its existing `severity` branch **unchanged** and gains a `host_id`
  branch; then paginates.

**Home's suite must stay green without edits.** `Home.test.tsx` and `useHomeReview.test.ts` depend
on the exported `latestScan`, `latestSuccessfulScan`, `criticalFinding` and `highFinding` constants
and on `/scans?per_page=1&sort_order=desc` answering with them. So: keep all four exports, make
`latestScan` the newest fixture and `latestSuccessfulScan` the newest `completed` fixture, and keep
the `severity` branch of the findings handler first. If Home's tests need changing, the fixtures are
wrong — not Home.

**Replace, do not work around, `http.get(\`${baseURL}/hosts\`, () => HttpResponse.json([]))`.** It
returns a bare array where the contract returns `HostListResponse`, so any code reading
`response.data.data` gets `undefined` from it. It is a latent lie in the harness.

`test/scansHarness.ts` and `test/hostsHarness.ts` follow `test/usersHarness.ts` exactly: export
`baseURL`, and export small `server.use(...)` helpers — `scansFail()`, `scanDetail(scan)`,
`scanNotFound()`, `hostsFail()`, `hostDetail(host, findings)`, `hostNotFound()`. Fixtures live in
`mswHandlers.ts`; overrides live in the harnesses.

### 9.2 Shared components

- **`DataTable.test.tsx`** — the component's own contract, driven with a tiny local row type:
  headings render uppercase from `label`; `isPending` renders skeleton rows **with the headings
  still present** and ignores `rows`; `empty` renders when `rows` is empty and `isPending` is false;
  `isPending` wins over `empty`. `link` rows: the row's link carries `label(row)` as its accessible
  name and the right `href`, and clicking the row navigates (assert with `LocationProbe`). `expand`
  rows: the trigger carries `aria-expanded` and `aria-controls`, activation via **keyboard**
  (`Tab` + `Enter`) opens the panel, the panel's `id` matches `aria-controls`, and clicking the row
  toggles. `rowAction: undefined`: **no button and no link in the row** — the assertion that keeps
  the ports table inert. `sort`: only `sortable` columns are clickable, the active column carries
  `aria-sort`, and clicking calls `onChange` with the column `key`.
- **`StatusPill.test.tsx`** — one render per tone; the label is the pill's text.
- **`Pagination.test.tsx`** — the range line for a middle page; `[Previous]` **absent** on page 1;
  `[Next]` **absent** on the last page; the whole component absent when `total <= perPage`.
- **`lib/scanStatus.test.ts` / `lib/severity.test.ts`** — pure, no React. Every `ScanStatus` maps;
  `completed` maps to `null`. `bySeverityDesc` orders critical → high → medium → low and is stable
  on ties.

### 9.3 `pages/Scans.test.tsx`

- 20 rows on first load; **advancing a page shows rows 21–25 and none of rows 1–20** (TRUTH
  acceptance "Run log paginates").
- An unfinished row shows "Running…" and **"—" in the Hosts, Findings and Highest cells** — assert
  the absence of `0` and of "None" on that row specifically. This is TRUTH rule 3 and it is the
  single most important assertion in the file.
- A failed row reads "Failed" and shows no counts.
- Activating a row navigates to `/scans/:scanId` (`LocationProbe`).
- `total: 0` → the blank state, and **no button and no link inside it** (divergence 1, asserted).
- `scansFail()` → the error copy and `[Retry]`; the retry re-reads and the rows appear.
- **No sort headers exist** — no `th` in this table is a button.
- Testids: `scans-table`, `scan-row-${scanId}`, `scans-blank`, `scans-error`,
  `scans-error-retry`, `scans-pagination`.

### 9.4 `pages/ScanDetail.test.tsx`

- Findings render **worst-first** from a deliberately shuffled fixture.
- Activating a finding row reveals description, recommendation, evidence, references and the CVSS
  line **in place**, and **the route does not change** (`LocationProbe` still reads
  `/scans/:scanId`).
- **`?finding=` deep link:** render at `/scans/:id?finding=<known>`; the panel is open on first
  paint and **no additional request is made** — assert by rendering with an override that would
  fail the test if `/findings` were called (an unhandled `/findings?scan_id=` request already errors
  under `onUnhandledRequest: 'error'` only if unmatched, so assert the panel's content came from the
  embedded array by using a fixture whose embedded finding differs from the `/findings` default).
- `?finding=<unknown>` → the page renders with **nothing open**.
- `completed` with no findings → the clean sentence, and **no findings table in the DOM**, with the
  hosts table still present.
- `failed` → the sentence from `scanFailureReason()` — assert the exact operator sentence for
  `device_offline` — and **neither the findings table nor the hosts table in the DOM**. Assert the
  raw code string `"device_offline"` does **not** appear.
- `failed` with `error_code: null` → the `unknown` sentence, still no code.
- `processing` → the still-running copy, no findings table.
- A host row's link navigates to `/hosts/:hostId`, and the host row's disclosure opens its ports —
  both, in one test, since the two interactions share a row (§5.4).
- 404 → the not-found line and a `[Back to scans]` link to `/scans`.
- Testids: `scan-detail`, `finding-row-${findingId}`, `finding-panel-${findingId}`,
  `scan-hosts-table`, `scan-host-row-${hostId}`, `host-ports-panel-${hostId}`, `scan-failed`,
  `scan-unfinished`, `scan-no-findings`, `scan-detail-error`, `scan-detail-error-retry`,
  `scan-detail-not-found`.

### 9.5 `pages/Hosts.test.tsx`

- Default order is `last_seen_at` desc — assert the **first row's hostname**, so the assertion
  fails if the request omits the sort.
- Clicking the Host heading orders by `hostname` ascending: assert the rows come back in the
  server's ascending order **and** that the view returned to page 1 (advance to page 2 first, then
  sort, then assert row 1 of the ascending fixture is visible). This covers TRUTH rules 15 and 16 in
  one test.
- Clicking the active heading again flips to descending.
- **The ordering is the server's:** the sort-aware handler returns a deliberately *unsorted* array
  for one `sort_by` value; the page renders it in the order received. A page that re-sorts locally
  fails this test, and nothing else catches it.
- Paging shows rows 21–25 and none of 1–20.
- The `mac: null` / `hostname: ''` row renders "—" and "(unnamed)", **and the row still has seven
  cells** (TRUTH rule 17 — the columns remain).
- Row activation navigates to `/hosts/:hostId`.
- Blank and error states as in §9.3, with the blank state again carrying no action.
- Testids: `hosts-table`, `host-row-${hostId}`, `hosts-sort-${key}`, `hosts-blank`, `hosts-error`,
  `hosts-error-retry`, `hosts-pagination`.

### 9.6 `pages/HostDetail.test.tsx`

- Identity header, findings, ports and history all render from the two reads.
- **Only that host's findings appear** — the findings handler is asserted through its `host_id`
  branch, with a second host's finding present in the fixture set and absent from the page.
- A finding row opens the **same panel** as scan detail — CVE, CVSS and reference links present.
- `ports: []` → the positive sentence and **no ports table in the DOM**.
- The ports table, when present, has **no interactive element in any row**.
- A history row navigates to `/scans/:scanId`.
- **Either** query failing → the page error state with `[Retry]`; assert once with the host read
  failing and once with the findings read failing.
- 404 on the host read → the not-found line and `[Back to hosts]`.
- Testids: `host-detail`, `host-findings-table`, `host-no-findings`, `host-ports-table`,
  `host-no-ports`, `host-history-table`, `host-history-row-${scanId}`, `host-detail-error`,
  `host-detail-error-retry`, `host-detail-not-found`.

### 9.7 `pages/Agents.test.tsx` and `components/TopBar.test.tsx`

- Agents renders its title, subtitle and the device statement, and contains **no button and no
  link** — the assertion that keeps a trigger from appearing before DMI-89 builds one.
- TopBar: `nav-scans`, `nav-hosts` and `nav-agents` are present **for a viewer as well as an
  admin**, pointing at `/scans`, `/hosts`, `/agents`. `nav-users` stays admin-only, unchanged.

### Not tested here

- `Timestamp`, `SeverityBadge`, `Disclosure` and `scanFailureReason` — each already has its own
  suite. Test this feature's *use* of them, not the components again.
- Anything about polling or live refresh. There is nothing to assert; a test asserting that no
  refetch happens on a timer would be testing the absence of code.

---

## 10. Gate

From `frontend/`:

```
npm run lint && npm run typecheck && npm test && npm run build
```

`npm run gen:types` is **not** run — the contract does not move in this feature, and a regenerated
diff would mean something went wrong. No `ruff`, no `pytest`, no `./database.sh`: nothing outside
`frontend/` changes.

## 11. `HUMAN_INFRA_REQUIRED`

None. No new hardware, daemon, service, environment variable or external tool. The feature runs
against the backend the frontend already talks to.
