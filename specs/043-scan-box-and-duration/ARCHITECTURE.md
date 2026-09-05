# ARCHITECTURE — Attribute every scan to the box that ran it, and record its duration (DMI-134)

Spec: `specs/043-scan-box-and-duration/`. Truth: `TRUTH.md`. Layout this completes:
`specs/042-design-system/DESIGN.md` §4 Scans, §5 Scan detail, §9 Device detail.

This feature lives in `backend/` and `frontend/`. `hardware-agent/src` is **not touched**; the Pi
already reports `metadata.elapsed_seconds` on ingest and the column exists on `scans`. The
CLAUDE.md `ScanRunner` / `ScanProgressScreen` integration rule does **not** apply — no orchestrator
parameter is added and the TUI is out of scope (TRUTH v1).

---

## 1. System context

The pipeline this feature sits in is **scan ingest and read**, not discovery or nmap:

```
operator clicks Scan now
  → POST /api/v1/agents/{agent_id}/commands   (commands.enqueue_for_agent → deliver)
      → commands.deliver → _record_delivery
          → stub scans row (status pending)     ← must stamp agent_id here (gap today)
  → Pi runs scan locally (hardware-agent; out of scope)
  → POST /api/v1/scans   (persistence.ingest_scan → persist_scan)
      → scans.agent_id from AgentIdentity       ← must match stub agent_id (gap today)
      → scans.metadata_json.elapsed_seconds     ← already stored; not exposed on read
  → operator reads:
      GET /api/v1/scans?agent_id=…   (read.list_scans)
      GET /api/v1/scans/{scan_id}    (read.get_scan_detail)
      Device detail history          (frontend listScans filtered by agent_id)
```

Three gaps make box and duration unreachable today:

1. `_record_delivery` (`services/commands.py:242-250`) creates the stub `ScanRecord` with no
   `agent_id`, so commanded runs are unattributed until ingest — and ingest's ownership check keys
   off the command, not the stub column.
2. `persist_scan` (`services/persistence.py:102-109`) overwrites `agent_id` on update without
   checking an existing non-null value, so a mismatch is not refused at the persistence layer.
3. `list_scans` / `get_scan_detail` (`services/read.py`) never join `agents` for `display_name`
   and never derive `duration` from `metadata_json.elapsed_seconds`.

The fix is: **stamp at delivery**, **refuse mismatch at persist**, **derive box name and duration
at read**, **one-time backfill** for historical rows with a command, and **expose on the contract**
so the frontend can render Box and Duration.

Scope fences from TRUTH: no Box field on scan detail UI; no duration for failed or unfinished scans;
no invented box for scans without a command. Device-detail history columns were decided at the
2026-09-05 review (TRUTH rule 18, DESIGN §4.1): **When · Mode · Status · Duration** — the findings
columns stay off that table.

---

## 2. Data model and contracts

### 2.1 Storage — no new columns

`ScanRecord` (`api/models/persistence.py:29-40`) already has:

```python
agent_id: UUID | None = Field(default=None, foreign_key="agents.id")
metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
```

**No `duration` column.** Duration is derived at read from `metadata_json["elapsed_seconds"]` when
`status == "completed"`. The Pi may store a float in metadata (see
`hardware-agent/src/agent/scanner/runner.py:98`); the API publishes **whole seconds** as `int | null`.

**No `box_name` column.** `box_name` is `Agent.display_name` (`api/models/command.py:17`) joined at
read when `scans.agent_id` is non-null. Renaming a box updates every read without a backfill.

### 2.2 Pure read helpers — `api/core/scan_read.py` (new)

Leaf module (imports nothing from `api.schemas` / `api.services`), mirroring
`api/core/error_codes.py` from spec 032:

```python
from __future__ import annotations

from typing import Any
from uuid import UUID

from api.models.command import Agent


def scan_duration_seconds(
    status: str, metadata: dict[str, Any] | None
) -> int | None:
    """Whole seconds for a completed scan that reported elapsed_seconds; else None."""
    if status != "completed":
        return None
    if not metadata:
        return None
    raw = metadata.get("elapsed_seconds")
    if raw is None:
        return None
    if not isinstance(raw, (int, float)):
        return None
    seconds = int(raw)
    return seconds if seconds >= 0 else None


def box_name_for_agent(agent: Agent | None) -> str | None:
    return agent.display_name if agent is not None else None
```

`scan_duration_seconds` is the single duration rule: failed, pending, processing, accepted →
`None`; completed without the key → `None`; completed with a non-numeric value → `None`.

### 2.3 Response schemas — `api/schemas/read.py`

Add to **both** `ScanSummary` (line 121-131) and `ScanDetailResponse` (line 104-118):

```python
agent_id: UUID | None = None
box_name: str | None = None
duration: Annotated[int | None, Field(default=None, ge=0)] = None
```

Flat, optional, not in `required` — same pattern as `highest_severity` / `error_code`. TRUTH rule
11 requires list and detail to **carry** box id, display name, and duration in the API even though
scan detail UI does not render Box (rule 16).

### 2.4 Write path — stamp and refuse mismatch

**`services/commands.py` — `_record_delivery` (line 242-250).** Add `agent_id` to the stub:

```python
ScanRecord(
    scan_id=scan_id,
    org_id=command.org_id,
    agent_id=command.agent_id,
    timestamp=now,
    subnet=command.subnet,
    scan_mode=command.scan_mode,
    status=scan_status_for("delivered"),
)
```

Commanded runs belong to the box as soon as the command is delivered (TRUTH rule 2). Unfinished
stubs included in `GET /scans?agent_id=…` (acceptance: "Stub already belongs").

**`services/persistence.py` — `persist_scan` (line 102-109).** Before mutating an existing row,
refuse agent mismatch:

```python
else:
    scan_record = existing
    if (
        scan_record.agent_id is not None
        and scan_record.agent_id != agent_id
    ):
        raise ScanOwnershipError
    scan_record.timestamp = scan.timestamp
    ...
```

`ingest_scan` already maps `ScanOwnershipError` → 403 in `routers/scans.py:39-40`. No new
exception type. `ingest_scan`'s command-level check (`persistence.py:60-66`) stays; this adds the
stub-column check for the `persist_scan` path and commandless re-uploads.

New-scan branch (`existing is None`, line 90-100) unchanged: `agent_id=agent_id` from identity.
Completed-scan idempotent path (`ingest_scan` line 55-58) already compares `agent_id`.

### 2.5 Read path — `services/read.py`

**`list_scans` (line 194-260).** New optional parameter:

```python
def list_scans(
    session: Session,
    *,
    org_id: UUID,
    page: int = 1,
    per_page: int = 20,
    status: ScanStatus | None = None,
    agent_id: UUID | None = None,
    sort_by: ScanSortBy = "timestamp",
    sort_order: SortOrder = "desc",
) -> ScanListResponse:
```

Filter (after `org_id` predicate):

```python
if agent_id is not None:
    predicates.append(ScanRecord.agent_id == agent_id)
```

After loading the page of scans, batch-load agents (one query, same pattern as `host_counts`):

```python
from api.models.command import Agent

agent_ids = {s.agent_id for s in scans if s.agent_id is not None}
agents_by_id: dict[UUID, Agent] = {}
if agent_ids:
    agents_by_id = {
        a.id: a
        for a in session.exec(
            select(Agent).where(Agent.id.in_(agent_ids))
        ).all()
    }
```

Extend `_to_scan_summary` signature:

```python
def _to_scan_summary(
    scan: ScanRecord,
    *,
    host_count: int,
    finding_count: int,
    highest_severity: str | None,
    agent: Agent | None = None,
) -> ScanSummary:
    return ScanSummary(
        ...
        agent_id=scan.agent_id,
        box_name=box_name_for_agent(agent),
        duration=scan_duration_seconds(scan.status, scan.metadata_json),
    )
```

Pass `agent=agents_by_id.get(scan.agent_id) if scan.agent_id else None` from `list_scans`.

**`get_scan_detail` (line 142-191).** After resolving `scan`, load agent once:

```python
from api.core.scan_read import box_name_for_agent, scan_duration_seconds
from api.models.command import Agent

agent = session.get(Agent, scan.agent_id) if scan.agent_id else None
```

Add to `ScanDetailResponse(...)`:

```python
agent_id=scan.agent_id,
box_name=box_name_for_agent(agent),
duration=scan_duration_seconds(scan.status, scan.metadata_json),
```

### 2.6 Router — `api/routers/scans.py`

`read_scans` (line 54-72) gains a query parameter:

```python
agent_id: UUID | None = Query(None),
```

Pass through to `list_scans(..., agent_id=agent_id)`. Org scoping remains on `caller.org_id`; a
foreign org's `agent_id` returns an empty list, not an error.

### 2.7 Alembic — `alembic/versions/20260904_18_scan_box_and_duration.py` (new)

`down_revision = "20260811_17"`. Two operations in `upgrade()`:

1. **Index** for org + box filter (list by agent within tenant):

```python
op.create_index(
    "ix_scans_org_id_agent_id",
    "scans",
    ["org_id", "agent_id"],
)
```

2. **One-time backfill** (TRUTH rules 6, acceptance "Backfill from command"):

```sql
UPDATE scans AS s
SET agent_id = c.agent_id
FROM commands AS c
WHERE s.scan_id = c.scan_id
  AND s.agent_id IS NULL
  AND c.agent_id IS NOT NULL
```

`downgrade()` drops the index only. Do not reverse the backfill.

**Migration ownership:** Alembic owns `dmitri_test` (`database.sh` line 19; `conftest.py` migrates
to head). Never run `supabase db reset`, `supabase db push`, or `supabase migration` against
`dmitri_test`.

### 2.8 Published contract — `contracts/openapi/openapi.yaml`

Hand-maintained; gated by `backend/tests/test_contract_fidelity.py`. `ScanSummary` and
`ScanDetailResponse` are already in `SCHEMA_NAMES` — fingerprints move; YAML must move with them.

**New parameter** (beside `ScanStatusFilter`, ~line 1240):

```yaml
    ScanAgentIdFilter:
      name: agent_id
      in: query
      required: false
      description: Limit scans to those produced by this box.
      schema:
        type: string
        format: uuid
```

Wire into `GET /api/v1/scans` `parameters` (~line 173), after `ScanStatusFilter`:

```yaml
        - $ref: '#/components/parameters/ScanAgentIdFilter'
```

**`ScanSummary`** (~line 2415): add to `properties` (not `required`):

```yaml
        agent_id:
          anyOf:
            - type: string
              format: uuid
            - type: 'null'
        box_name:
          anyOf:
            - type: string
            - type: 'null'
        duration:
          anyOf:
            - type: integer
              minimum: 0
            - type: 'null'
```

**`ScanDetailResponse`** (~line 2449): same three properties after `error_code`.

Do not add `agent_id` to `ScanIngestRequest` — ingest identity comes from the signed agent headers.

### 2.9 Frontend — duration copy and columns

Per `frontend-conventions`: types from `src/types/openapi.d.ts` via `components['schemas'][...]`;
regenerate with `npm run gen:types` after the YAML edit.

**New `frontend/src/lib/scanDuration.ts`:**

```ts
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

/** TRUTH rules 8–10: human copy from API whole seconds; null → render EmptyMark in cells. */
export function formatScanDuration(
  seconds: ScanSummary['duration'],
): string | null {
  if (seconds == null) return null
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)} min`
}
```

No hours form (TRUTH rule 10). Under 60 seconds: `45s`. At 60 or more: whole minutes, `8 min` for
500 seconds.

**`scanListColumns.tsx`.** Reorder per TRUTH rule 15: When · Box · Mode · Status · Duration ·
Machines · Vulnerabilities · Highest severity. Box cell: `Link` to `/devices/${scan.agent_id}` with
`scan.box_name`; unattributed (`agent_id` / `box_name` null) → `EmptyMark`. Duration cell:
`formatScanDuration(scan.duration)` or `EmptyMark` when null. Failed / unfinished scans get `—`
because API returns `duration: null`.

**`ScanDetailHeader.tsx` — `ScanSummaryStrip`.** Add Duration as the fifth strip entry (after
Machines seen and Vulnerabilities when counts are shown), per TRUTH rule 16. Use
`formatScanDuration(scan.duration)` or `EmptyMark`. Do **not** add a Box field on this screen.

**`DeviceDetail.tsx` — scan history section.** New child component (see naming table). Data path:

```ts
const params = {
  agent_id: agent.agent_id,
  page,
  per_page: SCANS_PER_PAGE,
  ...SCAN_LIST_SORT,
}
useQuery({
  queryKey: queryKeys.scans.list(params),
  queryFn: () => listScans(params),
})
```

`ScanListParams` / `ListScansQuery` pick up optional `agent_id` from the regenerated OpenAPI
types; no hand-written duplicate. Pagination matches the run log (`SCANS_PER_PAGE`, same
`ListSurface` pattern as `Scans.tsx`). Blank copy: `No scans from this box yet.` (TRUTH rule 19).
**Columns:** When · Mode · Status · Duration (TRUTH rule 18, DESIGN §4.1). Define them in
`deviceScanHistoryColumns.tsx` as a `DataTableColumn<ScanSummary>[]`, reusing `Timestamp`,
`SCAN_MODE_LABEL`, `scanStatusLabel`, `formatScanDuration` and `EmptyMark` — do not duplicate the
cell logic from `scanListColumns.tsx`. Do not filter the query to completed scans: a pending or
running scan already belongs to the box and belongs in this table.

---

## 3. New files and naming (mandatory)

| Path | New/Touched | What |
|------|-------------|------|
| `backend/src/api/core/scan_read.py` | **New** | `scan_duration_seconds(status, metadata) -> int \| None`, `box_name_for_agent(agent) -> str \| None`. Leaf module. |
| `backend/src/api/schemas/read.py` | Touched | `ScanSummary` and `ScanDetailResponse` each gain `agent_id`, `box_name`, `duration` (all optional, `duration` ge=0). |
| `backend/src/api/services/read.py` | Touched | `list_scans`: `agent_id` filter, batch `Agent` load, pass into `_to_scan_summary`. `get_scan_detail`: load agent, populate three fields. `_to_scan_summary`: new `agent` kwarg. Imports from `api.core.scan_read` and `api.models.command.Agent`. |
| `backend/src/api/services/persistence.py` | Touched | `persist_scan`: `ScanOwnershipError` when `existing.agent_id` is set and differs from upload `agent_id`. |
| `backend/src/api/services/commands.py` | Touched | `_record_delivery`: set `agent_id=command.agent_id` on stub `ScanRecord`. |
| `backend/src/api/routers/scans.py` | Touched | `read_scans`: `agent_id: UUID \| None = Query(None)` → `list_scans`. |
| `backend/alembic/versions/20260904_18_scan_box_and_duration.py` | **New** | Index `ix_scans_org_id_agent_id`; backfill `UPDATE scans … FROM commands …`. |
| `contracts/openapi/openapi.yaml` | Touched | `ScanAgentIdFilter` parameter; `agent_id`, `box_name`, `duration` on `ScanSummary` and `ScanDetailResponse`; wire filter on `GET /api/v1/scans`. |
| `backend/tests/test_scan_read.py` | **New** | Unit tests for pure helpers (§4.1). |
| `backend/tests/test_read_service_scans.py` | Touched | `list_scans` filter, duration, box_name, unattributed; mirror `make_scan` / `_seed_command`. |
| `backend/tests/test_read_scans.py` | Touched | HTTP: `agent_id` query param; JSON body fields on list and detail. |
| `backend/tests/test_ingest_scan.py` | Touched | Mismatch when stub `agent_id` set and uploader differs; commandless upload sets `agent_id`. |
| `backend/tests/test_command_delivery.py` | Touched | `test_deliver_success_sets_delivered_at_and_stub_scan`: assert `scan.agent_id == provisioned_agent.id`. |
| `backend/tests/test_scan_box_migration.py` | **New** | Backfill: scan with command, null `agent_id` → after upgrade, `agent_id` matches command; scan without command stays null. |
| `frontend/src/types/openapi.d.ts` | **Generated** | `npm run gen:types`; commit diff. |
| `frontend/src/lib/scanDuration.ts` | **New** | `formatScanDuration(seconds) -> string \| null`. |
| `frontend/src/lib/scanDuration.test.ts` | **New** | Vitest beside source; 45s, 8 min, null cases. |
| `frontend/src/api/scans.ts` | Touched | No signature change if types flow from OpenAPI; confirm `ScanListParams` includes optional `agent_id`. |
| `frontend/src/pages/scans/scanListColumns.tsx` | Touched | Column order TRUTH rule 15; Box link; Duration cell. |
| `frontend/src/pages/scans/ScanDetailHeader.tsx` | Touched | `ScanSummaryStrip`: Duration entry. |
| `frontend/src/pages/agents/DeviceScanHistory.tsx` | **New** | `ListSurface` + `listScans({ agent_id })` + `queryKeys.scans.list(params)`; blank copy; loading, error and pagination. |
| `frontend/src/pages/agents/deviceScanHistoryColumns.tsx` | **New** | `DataTableColumn<ScanSummary>[]` for When · Mode · Status · Duration. |
| `frontend/src/pages/DeviceDetail.tsx` | Touched | Render `DeviceScanHistory` below scan controls (step 12 gap). |
| `frontend/src/test/mswHandlers.ts` | Touched | `ScanSummary` fixtures gain `agent_id`, `box_name`, `duration` so MSW stays type-aligned. |
| `frontend/src/pages/ScanDetail.test.tsx` | Touched | Strip shows Duration when present. |
| `frontend/src/pages/DeviceDetail.test.tsx` | Touched | History section: empty copy; with scans, list request includes `agent_id`. |
| `hardware-agent/**` | **Unchanged** | Out of scope. TUI, `ScanRunner`, `ScanProgressScreen` not threaded. |

Nothing outside this table is created or edited unless a gate fails and requires a fixture fix.

---

## 4. Testing expectations

Mapped to TRUTH acceptance criteria. Each row names the gate and the file to mirror.

### 4.1 Pure helpers — `backend/tests/test_scan_read.py` (new)

No DB. Mirror `backend/tests/test_error_codes.py`.

| Test | Asserts | TRUTH row |
|------|---------|-----------|
| completed + integer metadata | `scan_duration_seconds("completed", {"elapsed_seconds": 45}) == 45` | Completed duration |
| completed + float metadata | `scan_duration_seconds("completed", {"elapsed_seconds": 187.9}) == 187` | Completed duration |
| completed, key missing | `… == None` | Completed without report |
| failed / pending / processing | `… == None` for each status | Failed / unfinished duration |
| non-numeric metadata | `… == None` | — |
| `box_name_for_agent(None)` | `None` | Unattributed |
| `box_name_for_agent(agent)` | `agent.display_name` | Scans list Box |

### 4.2 Backend service and ingest

| Area | File | Mirror | Cases |
|------|------|--------|-------|
| `_record_delivery` | `test_command_delivery.py` | `test_deliver_success_sets_delivered_at_and_stub_scan` | stub `agent_id == command.agent_id` |
| `persist_scan` mismatch | `test_ingest_scan.py` | `test_ingest_scan_rejects_placeholder_owned_by_another_agent` | stub with `agent_id=A`, upload identity B → `ScanOwnershipError`, row unchanged |
| commandless ingest | `test_ingest_scan.py` | `test_ingest_scan_accepts_enriched_findings_example` | new scan → `agent_id` from identity |
| `list_scans` filter | `test_read_service_scans.py` | `test_list_scans_filters_by_status` | two agents, filter `agent_id` → only that box's scans including pending stub |
| duration on list | `test_read_service_scans.py` | `test_list_scans_per_scan_aggregates` | completed + `metadata_json={"elapsed_seconds": 500}` → `duration == 500`; failed → `null` |
| box_name on list | `test_read_service_scans.py` | — | attributed scan → `box_name == Agent.display_name`; no agent → both null |
| `get_scan_detail` | `test_read_service_scans.py` | `test_get_scan_detail_failed_published_code_from_one_request` | same three fields on detail |
| unattributed old scan | `test_read_service_scans.py` | `test_null_org_id_scan_invisible_in_list_scans` pattern | scan, no command, no agent → read succeeds, `agent_id`/`box_name` null |
| backfill | `test_scan_box_migration.py` | `test_command_delivery_migration.py` style | run upgrade SQL; command-linked scan gains `agent_id`; orphan stays null |
| contract | `test_contract_fidelity.py` | — | **no edit**; `ScanSummary` / `ScanDetailResponse` fingerprints must pass |

### 4.3 Backend HTTP

| Area | File | Cases |
|------|------|-------|
| List filter | `test_read_scans.py` | `GET /api/v1/scans?agent_id=` → 200, only matching rows |
| List fields | `test_read_scans.py` | body `data[0]` includes `agent_id`, `box_name`, `duration` |
| Detail fields | `test_read_scans.py` | `GET /api/v1/scans/{id}` includes the three fields |
| Ingest mismatch | `test_scan_ingest_route.py` | wrong box uploads commanded scan → 403 |

### 4.4 Frontend

| File | Asserts | TRUTH row |
|------|---------|-----------|
| `scanDuration.test.ts` | `45` → `'45s'`; `500` → `'8 min'`; `null` → `null` | Scans list Duration / minutes |
| `ScanDetail.test.tsx` | strip contains Duration when `duration` set | Scan detail Duration |
| `DeviceDetail.test.tsx` | no scans → `No scans from this box yet.`; with scans → fetch used `agent_id` | Device history empty / filter by box |
| MSW fixtures | compile after `gen:types` | — |

`DeviceDetail.test.tsx` also asserts the history column headings are exactly When, Mode, Status, Duration, and that a failed row's Duration cell is `EmptyMark`.

### 4.5 Gates

**Backend** — from `backend/`:

```
./database.sh --test          # zero skips; dmitri_test required
uv run ruff check src tests
uv run pytest
```

Never `ruff format` in `backend/`.

**Frontend** — from `frontend/`:

```
npm run gen:types
npm run lint
npm run typecheck
npm test
npm run build
```

`test_contract_fidelity.py` must stay green after the YAML edit alone.

---

## 5. Constraints and things that will bite

1. **Stub before ingest.** After `_record_delivery` ships `agent_id`, filter-by-box must include
   pending stubs (acceptance "Stub already belongs"). Do not filter on `status=completed` in the
   frontend history query.
2. **`persist_scan` mismatch and `ingest_scan` command check are complementary.** Both must ship;
   neither alone covers commandless re-upload vs stub stamped at delivery.
3. **`elapsed_seconds` in metadata may be float; API `duration` is int.** Coerce with `int()` at
   read only; do not rewrite stored metadata on ingest.
4. **`box_name` is read-time.** Renaming a box changes list rows without migrating scans. Tests must
   not assert a stored name on `ScanRecord`.
5. **Device-detail history is four columns, not seven.** When · Mode · Status · Duration. Adding
   Machines, Vulnerabilities or Highest severity back needs TRUTH rule 18 amended first.
6. **`HUMAN_INFRA_REQUIRED`: none.** No new hardware, daemon, or env var. Index + backfill only.

---

## 6. Not in this feature

New-versus-known result column (DMI-70); daily scan schedule / default scan type (DMI-133); inventing
`agent_id` without a command; duration on failed or unfinished scans; hardware-agent TUI and
`ScanRunner` / `ScanProgressScreen`; Box field on scan detail UI; renaming owner-facing "Box" or
`agent_id`; status copy changes (`Complete` vs `Completed`); Supabase CLI schema commands on
`dmitri_test`.
