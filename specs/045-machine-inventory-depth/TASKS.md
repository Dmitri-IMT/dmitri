# TASKS — Deepened machine inventory (DMI-135)

> Specs: [`TRUTH.md`](TRUTH.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DESIGN.md`](DESIGN.md).
> Approval gate closed 2026-09-07 — `DESIGN.md` §9 (Q1–Q5) and `ARCHITECTURE.md` §13 all carry a
> decision. No task is built against a guessed contract name.

## Agents

| Task's Target Files | Coder | Tests | Review | Gate |
|---|---|---|---|---|
| `backend/`, `contracts/` | `agent-developer` | `test-engineer` | `code-reviewer` | `./database.sh --test` then `uv run ruff check src tests` — **never `ruff format`** |
| `frontend/` | `agent-developer` | `frontend-test-engineer` | `frontend-code-reviewer` | `npm run lint && npm run typecheck && npm test && npm run build` |

A backend run with a non-zero skip count is **not** a green run — this feature is almost entirely
DB-backed.

**Tasks 8, 9 and 10 share one review gate.** Same shape, found 2026-09-08: Task 8 deletes
`isQuietHost` / `partitionQuietHosts`, whose callers live in Task 9's two files and Task 10's
`HostIdentity.tsx`, and it retypes `ports` to `HostPort`, which Task 10's `HostDetail.tsx` consumes.
`npm run typecheck`, `npm test` and `npm run build` are therefore red between them by construction.
Run coder 8, coder 9, coder 10 in sequence — never two coders at once — then one
`frontend-test-engineer` and one `frontend-code-reviewer` over all three. All three are marked
`COMPLETED` together or none is. Task 11 is independent and gates on its own.

**Tasks 7 and 6 share one review gate.** Discovered 2026-09-08, mid-flight: `test_contract_fidelity.py`
compares the contract against the live app in both directions, so schemas-first leaves the `group`
parameter declared and unimplemented, while read-path-first leaves the response fingerprints wrong.
Neither task can be green alone; the pair is green together. This was a decomposition error in this
file — the two should have been one task from the start. They are run as one now: coder 7, coder 6,
tests, then a **single** reviewer over both, and both are marked `COMPLETED` together or neither is. `hardware-agent/` is untouched (`ARCHITECTURE.md` §9); Task 12 is the regression proof.

> **Paused after Task 5, 2026-09-07; resumed at Task 7, 2026-09-08.**
> **Resumed 2026-09-11 at the joint 8+9+10 gate.** All 13 tasks COMPLETED 2026-09-11.

## Dependency graph

```
1 machine_type ──> 2 models ──> 3 migration ──> 4 reconcile ──> 5 ingest wiring
                       │                                              │
                       └──> 7 schemas + OpenAPI ──┬───────────────────┴──> 6 read path
                                                  │
                                                  └──> 8 frontend data layer
                                                             │
                             ┌───────────────────┬───────────┴──────────┐
                             ▼                   ▼                      ▼
                        9 Network           10 Host detail          11 Home +
                        quiet split         + service life          finding columns
                             │                   │                      │
                             └───────────────────┴──────────┬───────────┘
                                                            ▼
                                              12 agent regression ──> 13 FOUNDATIONS
```

Backend order 1 → 2 → 3 → 4 → 5 → 7 → 6, then frontend 8 → 9 → 10 → 11, then 12 → 13. Task 6 needs
Task 7's schemas to return the new fields, which is why 7 lands before it.

## Status table

| # | Task | Layer | Status |
|---|---|---|---|
| 1 | Machine type classifier | backend | COMPLETED |
| 2 | Persistence models | backend | COMPLETED |
| 3 | Alembic migration | backend | COMPLETED |
| 4 | Reconcile service | backend | COMPLETED |
| 5 | Ingest + enrichment wiring | backend | COMPLETED |
| 6 | Read path | backend | COMPLETED |
| 7 | Response schemas + OpenAPI contract | backend/contracts | COMPLETED |
| 8 | Frontend data layer + generated types | frontend | COMPLETED |
| 9 | Network — Type, count, quiet split | frontend | COMPLETED |
| 10 | Network detail — type and service life | frontend | COMPLETED |
| 11 | Home + finding columns — the machine's name | frontend | COMPLETED |
| 12 | `hardware-agent/` regression proof | hardware-agent | COMPLETED |
| 13 | `FOUNDATIONS.md` §Tables alignment amendment | docs | COMPLETED |

---

## Task 1: Machine type classifier
- **Description**: Add the closed nine-value machine-type vocabulary and the pure classifier
  `classify_machine_type(vendor, services)`. Service signals resolve first, in the fixed priority
  `camera, printer, storage, router, tv, sensor, computer`; vendor signals second; otherwise
  `unknown`. `vendor == "unknown"` (the agent's own fallback) matches nothing. No I/O, no data file.
  Exact signal tables are `ARCHITECTURE.md` §2.4.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/core/machine_type.py`]
- **Success Criteria**:
  - `MachineType` is the `Literal` of exactly the nine lower-case values; `MACHINE_TYPES` exposes
    them for the migration's check constraint, built the way `_FINDING_SEVERITY_CHECK` is.
  - Both signal tables match `ARCHITECTURE.md` §2.4 entry for entry.
  - `classify_machine_type("Hikvision", [(554, "rtsp")])` → `camera`; a service signal beats a
    vendor signal; `phone` is reachable only when no service signal matched.
  - The return value is always one of the nine, for any input.
  - Module is pure: no imports from `api.models`, `api.services`, or the session.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Persistence models
- **Description**: Add `machine_type` (nullable) and `vulnerability_count` (`NOT NULL`,
  `server_default="0"`) to `HostRecord`, and the two new tables `HostPortRecord` and
  `HostFindingRecord` per `ARCHITECTURE.md` §2.1–§2.3. `PortRecord` and `FindingRecord` are
  unchanged — they stay per-scan evidence, and no hostname or date is denormalised onto them.
- **Dependencies**: 1
- **Target Files**: [`backend/src/api/models/persistence.py`]
- **Success Criteria**:
  - `HostPortRecord`: `id`, `host_id` (FK → `hosts.id`, indexed), `port`, `protocol`, `service`,
    `version | None`, `first_seen_at`, `last_seen_at`; `UniqueConstraint("host_id","port","protocol")`.
    No `state`, no `closed_at`.
  - `HostFindingRecord`: `id`, `host_id` (FK, indexed), `dedupe_key` (indexed), `first_seen_at`,
    `last_seen_at`, `fixed_at | None`; `UniqueConstraint("host_id","dedupe_key")`. No `org_id` —
    the org is reached through `hosts`.
  - `HostRecord` keeps `vendor`, `open_ports_count` and `highest_severity`.
  - Existing persistence tests still pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Alembic migration
- **Description**: Write revision `20260907_20` (down_revision `20260905_19`) implementing
  `ARCHITECTURE.md` §3 exactly: two host columns, the `machine_type` check constraint, two host
  indexes, the two new tables with their indexes and unique constraints, and the RLS + grant fence
  copied verbatim from `20260905_19_home_activity_feed.py` (table **and** `_id_seq`,
  `SELECT/INSERT/UPDATE/DELETE` to `dmitri_runtime`). **No backfill — no `UPDATE` runs.**
- **Dependencies**: 2
- **Target Files**: [`backend/alembic/versions/20260907_20_machine_inventory_depth.py`, `backend/tests/test_migrations.py` (the `RUNTIME_GRANTS_BY_TABLE` entries for the two new tables)]
- **Success Criteria**:
  - Upgrade over a database holding a host leaves that host's `machine_type` `NULL` and its
    `vulnerability_count` `0`, and creates both tables empty — TRUTH's "nothing is stamped
    retroactively".
  - The check constraint admits `NULL` and the nine values, and rejects a tenth.
  - Both tables have RLS enabled; `anon` and `authenticated` hold no privilege on either table or
    sequence; `dmitri_runtime` holds all four verbs.
  - `downgrade()` revokes, drops both tables, both indexes, the constraint and both columns, and the
    round trip is clean.
  - Alembic has exactly one head after this revision.
  - The nine values are **spelled out literally** in the revision, not imported from
    `MACHINE_TYPES` — a revision is a frozen historical snapshot (`ARCHITECTURE.md` §3 step 3,
    corrected 2026-09-07; the precedent is `20260727_12_finding_severity_domain.py`). The agreement
    between the revision's list and the live vocabulary is a test, not an import.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Reconcile service
- **Description**: New module `backend/src/api/services/inventory.py` with
  `reconcile_scan_inventory(session, scan_record)` and
  `reconcile_scan_host_inventory(session, scan_host)` over one shared per-machine body
  (`ARCHITECTURE.md` §4.1–§4.2). Neither commits; the caller owns the transaction. It is its own
  module, not an addition to `services/hosts.py` — identity and life are different questions, and
  the enrichment worker must import the second without the first.
- **Dependencies**: 3
- **Target Files**: [`backend/src/api/services/inventory.py`]
- **Success Criteria**:
  - `is_latest = ts >= host.last_seen_at` guards steps 4–6; when it is false the run may only lower
    a `first_seen_at` — it stamps no `fixed_at`, retypes no machine, rewrites no count.
  - Ports: upsert on `(host_id, port, protocol)` from the scan's `state == "open"` rows;
    `first_seen_at = min(first_seen_at, ts)`; `last_seen_at` and service/version refresh only when
    `is_latest`. Ports this scan did not see open are **left untouched**.
  - Findings: upsert on `(host_id, dedupe_key)`; `first_seen_at` is never raised; a re-found problem
    clears `fixed_at`.
  - Fixed: when `is_latest`, every open `host_findings` row whose key is absent from this scan gets
    `fixed_at = ts`.
  - Type and count are written only when `is_latest`; the count is the open `host_findings` rows.
  - A finding with no `scan_host_id` gets no `host_findings` row.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Ingest and enrichment wiring
- **Description**: Call reconcile from **every** path that writes findings (`ARCHITECTURE.md`
  §4.3–§4.4): `persist_scan` after `upsert_hosts_for_scan` and before `append_scan_activity`, in the
  same transaction; and `_process_cpe_job` before its existing `session.commit()`, because it
  creates findings for an already-committed scan. `ingest_scan`, `POST /api/v1/scans`, and the
  CVE/KEV/EPSS jobs are unchanged — they create and delete no findings.
- **Dependencies**: 4
- **Target Files**: [`backend/src/api/services/persistence.py`, `backend/src/api/services/enrichment.py`, `backend/tests/test_ingest_scan.py` (extended — this task's tests belong where both call paths were already covered)]
- **Success Criteria**:
  - `persist_scan` writes `host_ports`, `host_findings`, `machine_type` and `vulnerability_count`
    inside its existing transaction; the case-A and case-C rollback tests still leave nothing behind.
  - A CVE the enrichment worker adds after ingest lands in `host_findings` with a `first_seen_at`
    and is included in the machine's `vulnerability_count`.
  - No second reconcile implementation exists — both call sites reach the Task 4 module.
  - `grep -rn "persist_scan\|ingest_scan\|upsert_finding" backend/src` shows no writing call path
    left unwired.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Read path
- **Description**: `ARCHITECTURE.md` §5. Add `QUIET_AFTER_DAYS = 7` and the server-side
  active/quiet split with a whole-org `quiet_total`; add `vulnerability_count` to
  `_HOST_SORT_COLUMNS` (and **not** `machine_type`); read `get_host_detail`'s ports from
  `host_ports`; widen `_to_host_summary` and `_to_finding_read`; add the hostname and life outer
  joins to `list_findings`, `get_scan_detail` and `home.page_attention`; add the `group` query
  parameter to `read_hosts`.
- **Dependencies**: 5, 7
- **Target Files**: [`backend/src/api/services/read.py`, `backend/src/api/services/home.py`, `backend/src/api/routers/hosts.py`]
- **Success Criteria**:
  - 45 hosts / 6 quiet / 20 per page → page 1 returns 20 **active** rows and `quiet_total == 6`;
    `total` counts the requested group; `group=quiet&page=2` pages the quiet group alone.
  - Last seen 8 days ago is quiet; 6 days ago is not.
  - `sort_by=vulnerability_count&sort_order=desc` puts the network's worst machine first on page 1
    across three pages — a plain `ORDER BY`, no correlated subquery.
  - `host_hostname` resolves through `scan_host_id → hosts.hostname` and is therefore the machine's
    **current** name after a rename; `scan_hosts.hostname` is not used.
  - A finding whose machine cannot be identified returns `host_hostname: null` and keeps `host_ip`;
    `first_seen_at` is `null` where there is no `host_findings` row.
  - `_to_host_summary` maps `machine_type NULL` → `"unknown"`.
  - `detected_at` keeps its current meaning; the Home attention rows carry `host_hostname`.
  - **The whole of `test_contract_fidelity.py` passes** once this task lands, including
    `test_query_parameters_match_contract[/api/v1/hosts]` — that case fails between Task 7 and this
    one by construction, and closing it is this task's job.
  - The full backend suite is green with **0 skipped**. The ~22 read-path failures Task 7 leaves
    behind are this task's to clear; none may be silenced by weakening a test.
- **Status**: COMPLETED (gated jointly with Task 7)
- **Review Rejections**: 0

## Task 7: Response schemas and the OpenAPI contract
- **Description**: `ARCHITECTURE.md` §6 and §7. Widen the Pydantic read schemas, then edit
  `contracts/openapi/openapi.yaml` **by hand** to match. `test_contract_fidelity.py` is the gate that
  proves the two agree. The unimplemented `q` parameter is pre-existing DMI-100 drift — do not
  remove it, do not implement it.
- **Dependencies**: 2
- **Target Files**: [`backend/src/api/schemas/read.py`, `contracts/openapi/openapi.yaml`]
- **Success Criteria**:
  - New `MachineType` (re-exported from `api.core.machine_type`), `HostGroup`
    (`Literal["active","quiet"]`) and `HostPort` (six fields, `version` optional, **no `state`**).
  - `HostSortBy` = `last_seen_at | hostname | vendor | ip | vulnerability_count` — no `machine_type`
    (`DESIGN.md` §9/Q3).
  - `HostSummary` and `HostDetailResponse` gain `machine_type` + `vulnerability_count` and keep
    `vendor` + `open_ports_count`; `HostDetailResponse.ports` is `list[HostPort]`; `Port` unchanged.
  - `FindingRead` gains `host_hostname`, `first_seen_at`, `last_seen_at`, `fixed_at`, all nullable
    and none required; no field removed. `HostListResponse` gains `quiet_total`.
  - Every model keeps `extra="forbid"`; bounds hold (`vulnerability_count >= 0`, `quiet_total >= 0`).
  - The YAML carries the new schemas, the `HostGroup` parameter on `paths./api/v1/hosts.get`, the
    widened `HostSortBy` enum, and a description saying the default page is active machines and
    `quiet_total` counts the whole inventory.
  - `test_contract_fidelity.py`'s schema fingerprints match for `HostSummary`,
    `HostDetailResponse`, `HostListResponse` and `FindingRecord`. Its
    `test_query_parameters_match_contract[/api/v1/hosts]` case is **expected to fail until Task 6
    lands the router parameter** — `group` is declared in the contract and not yet accepted by
    `read_hosts`. The fix is the router parameter in Task 6, **not** an entry in
    `UNIMPLEMENTED_PARAMS`: `group` is implemented work in flight, not permanent drift like `q`.
    The two tasks are gated together (see *Agents*).
- **Status**: COMPLETED (gated jointly with Task 6)
- **Review Rejections**: 0

## Task 8: Frontend data layer and generated types
- **Description**: `ARCHITECTURE.md` §8.1 and §8.3. Regenerate the types from the Task 7 contract,
  add `group` to the host list params, add the count's sort default, and delete the client-side
  quiet split now that the server owns it.
- **Dependencies**: 7
- **Target Files**: [`frontend/src/types/openapi.d.ts`, `frontend/src/api/hosts.ts`, `frontend/src/lib/hostLastSeen.ts`, `frontend/src/test/mswHandlers.ts`, `frontend/src/lib/hostLastSeen.test.ts` (deletion of the orphaned blocks this task created, per `.claude/CLAUDE.md` §3)]
- **Success Criteria**:
  - `openapi.d.ts` is produced by `npm run gen:types` and committed in this change. **Never
    hand-edited** — a hand edit is a rejection.
  - `HostListParams` gains `group`; `export type HostGroup = NonNullable<ListHostsQuery['group']>`;
    `HOST_SORT_DEFAULT_ORDER` gains `vulnerability_count: 'desc'`. `listHosts` itself is unchanged,
    and `queryKeys.ts` needs no change.
  - `QUIET_AFTER_MS`, `isQuietHost` and `partitionQuietHosts` are **deleted**; `weeksSinceLastSeen`
    is kept. No orphaned import remains (`grep -rn "partitionQuietHosts\|isQuietHost" frontend/src`
    is empty).
  - `mswHandlers.ts`: host fixtures carry `machine_type` and `vulnerability_count`, finding fixtures
    carry the four new fields, and the `/hosts` handler implements the `group` split and returns
    `quiet_total`.
  - `npm run typecheck` is green — it is the real guard that the YAML, the types and the code agree.
- **Status**: COMPLETED (gated jointly with Tasks 9 and 10)
- **Review Rejections**: 2 (joint gate, 2026-09-08 DataTable uncontrolled group; 2026-09-11 unused `baseURL` in `hosts.test.ts`)

## Task 9: Network — Type, vulnerability count, and the server-side quiet split
- **Description**: `DESIGN.md` §2 and §5. `Type` replaces `Vendor`, the vulnerability count replaces
  `Services`, every column left-aligns with `tabular-nums` on the numbers, and the quiet group
  becomes two grouped queries against one endpoint — the quiet one `enabled` only once opened, each
  group paging on its own `total`, the header showing the active response's `quiet_total`.
- **Dependencies**: 8
- **Target Files**: [`frontend/src/pages/Network.tsx`, `frontend/src/pages/hosts/hostListColumns.tsx`, `frontend/src/lib/machineType.ts` (new), `frontend/src/components/DataTable.tsx`, `frontend/src/components/ListSurface.tsx`, `frontend/src/components/LoadingSkeleton.tsx`, `frontend/src/pages/Network.test.tsx`, `frontend/src/components/DataTable.test.tsx`, `frontend/src/components/ListSurface.test.tsx` — the shared components are required by `DESIGN.md` §6.2 and were missing from `ARCHITECTURE.md` §10, corrected 2026-09-08]
- **Success Criteria**:
  - The group header's count is `quiet_total` from the active response — a whole-inventory number.
    On 45 machines with 6 quiet at 20 per page, page 1 reads `6`, and it reads `6` on every page.
  - Opening the group issues a second request with `group=quiet`; paging the quiet group leaves the
    active table untouched, and vice versa.
  - The count column sorts on click and requests `sort_by=vulnerability_count&sort_order=desc`
    first. `Type` has **no** sort control (`DESIGN.md` §9/Q3).
  - An `unknown` type draws no guessed value.
  - `hostListColumns(now, quiet)` takes the group from its caller; no row derives quiet from a date.
  - States per `DESIGN.md` §2.5 — including **All quiet**: the table renders its headings, one inert
    full-width row, then the group. A table never renders bare. The group's own error reads `Retry`
    (`DESIGN.md` §9/Q5).
  - `data-testid`s match `DESIGN.md` §7.1, including `network-table-sort-vulnerability_count`.
  - `DataTable`'s collapsed group takes its count from a `count` prop, **not** from `rows.length`.
    Deriving it from the rendered rows is the page-local bug this feature exists to delete.
  - Opening the quiet group is what enables its query; a sort or a page change on the active list
    does **not** re-collapse it (`DESIGN.md` §2.1, and §2.5 corrected to agree 2026-09-08).
- **Status**: COMPLETED (gated jointly with Tasks 8 and 10)
- **Review Rejections**: 2 (joint gate, 2026-09-08 DataTable uncontrolled group; 2026-09-11 unused `baseURL` in `hosts.test.ts`)

## Task 10: Network detail — machine type and service life
- **Description**: `DESIGN.md` §3. The identity line takes `vendor` and the open-port count and
  gains the machine's type; the Services table is
  retyped to `HostPort` and gains `Last seen`; Scan history's `Services` count left-aligns.
  **§3.3's Vulnerabilities `First seen` column is Task 11's**, not this one — it is declared in
  `findingColumns.tsx`, which is Task 11's Target File and whose criteria already claim it
  (corrected 2026-09-08; this description previously named it here, which would have had two tasks
  editing one file).
- **Dependencies**: 8
- **Target Files**: [`frontend/src/pages/hosts/HostIdentity.tsx`, `frontend/src/pages/hosts/portColumns.tsx`, `frontend/src/pages/hosts/HostPortsTable.tsx`, `frontend/src/pages/hosts/HostScanHistoryTable.tsx` (the §3.5 `Services` left-align is declared only there — added 2026-09-08), `frontend/src/pages/HostDetail.tsx` (needed no edit: the retype fixes its one error at the declaration)]
- **Success Criteria**:
  - `machine_type` renders on the machine's own page; `vendor` and `open_ports_count` are **still**
    there — TRUTH removes them from the list, not from this page.
  - Ports are typed `components['schemas']['HostPort']`; nothing reads a `state` field, because the
    schema has none.
  - A service whose `last_seen_at` is older than the machine's `last_seen_at` is distinguishable —
    **by its date alone**: no state word, no muted row, no strikethrough (`DESIGN.md` §9/Q4).
  - Every column left-aligns; numbers keep `tabular-nums`.
  - `HostIdentity.tsx` no longer imports the deleted `isQuietHost`. Its quiet variant of the third
    identity line (`DESIGN.md` §3.2, §3.6) derives from `weeksSinceLastSeen(...) >= 1` — seven days
    is exactly one week, so **no client-side threshold constant is reintroduced** and no contract
    field is added (owner's decision 2026-09-08, `ARCHITECTURE.md` §8.3).
  - `data-testid`s match `DESIGN.md` §7.2.
- **Status**: COMPLETED (gated jointly with Tasks 8 and 9)
- **Review Rejections**: 2 (joint gate, 2026-09-08 DataTable uncontrolled group; 2026-09-11 unused `baseURL` in `hosts.test.ts`)

## Task 11: Home and finding columns — the machine's name
- **Description**: `DESIGN.md` §4 and `ARCHITECTURE.md` §8.4. Home's attention table names the
  machine; the finding column sets show the problem's first-seen moment and prefer the machine's
  current name.
- **Dependencies**: 8
- **Target Files**: [`frontend/src/pages/home/AttentionTable.tsx`, `frontend/src/pages/scans/findingColumns.tsx`]
- **Success Criteria**:
  - The attention row shows `host_hostname`, falls back to `host_ip`, and falls back to `EmptyMark`
    only when both are absent; the row's aria label follows the same order.
  - Home issues **no** second request for the name — it is a field on the record.
  - A machine renamed since its problem appeared shows its **current** name.
  - `machineLabel()` prefers `finding.host_hostname`, then the `ScanHostView` snapshot, then the
    address. `hostFindingColumns()` and `scanFindingColumns()` show `first_seen_at`.
  - `FindingsTable.tsx` is not modified — it only picks between the two column sets.
  - `data-testid`s match `DESIGN.md` §7.3.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 12: `hardware-agent/` regression proof
- **Description**: `ARCHITECTURE.md` §9. This feature adds no orchestrator or `ScanRunner`
  parameter, so `.claude/CLAUDE.md`'s integration rule is satisfied vacuously — but the vacuum must
  be proved, not assumed. Verify and report; write no agent code.
- **Dependencies**: 11
- **Target Files**: [`hardware-agent/` (verification only — no file is changed)]
- **Success Criteria**:
  - `grep -rn "ScanRunner(" hardware-agent/src` returns exactly `agent/headless.py:92` and
    `agent/tui/screens/scan_progress.py:136`, and neither needs a new argument.
  - `ScanRunner.__init__` and `ScanProgressScreen` are unchanged; `git diff --name-only` shows no
    path under `hardware-agent/`.
  - `normalize/contracts.py` and `ScanPayload` are unchanged, so `contracts/examples/` fixtures are
    unchanged.
  - `cd hardware-agent && uv run pytest` is green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 13: `FOUNDATIONS.md` §Tables alignment amendment
- **Description**: `DESIGN.md` §9/Q2, owner's decision 2026-09-07. §Tables currently reads "numbers
  right-align in tabular figures". Amend it product-wide to *every column left-aligns; numbers keep
  tabular figures*, and record the restyle of the four screens that still right-align as a named
  follow-up. Documentation only — no screen outside this feature is restyled here.
- **Dependencies**: 12
- **Target Files**: [`docs/ui/FOUNDATIONS.md`]
- **Success Criteria**:
  - §Tables states the left-align rule product-wide; the old right-align sentence is gone, not
    merely contradicted elsewhere.
  - The four screens still on the old rule are named, with the follow-up recorded so the drift is
    tracked rather than forgotten.
  - No file under `frontend/src/` is touched by this task.
- **Status**: COMPLETED
- **Review Rejections**: 0
