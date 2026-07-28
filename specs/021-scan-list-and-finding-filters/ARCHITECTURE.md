# ARCHITECTURE — Scan list and finding filters (DMI-82)

> Implements `specs/021-scan-list-and-finding-filters/TRUTH.md` to the shapes already frozen in
> `contracts/openapi/openapi.yaml`. This extends the read path built by
> `specs/015-read-path/ARCHITECTURE.md` and hardened by DMI-61 (org scoping) and DMI-72 (error
> envelope).

## Preamble — scope and why the CLAUDE.md TUI rule does not apply

This is a **FastAPI backend feature**. It touches `backend/src/api/` only: two read services, two
routers, one schema module, and their tests. There is no `ScanOrchestrator`, no `ScanRunner`, no
`ScanProgressScreen`, no `ScanPayload`, no nmap invocation and no Textual screen anywhere in its
blast radius. The `.claude/CLAUDE.md` integration rule — "any new parameter added to the
orchestrator MUST also be threaded through `ScanRunner` and `ScanProgressScreen`" — is therefore
**N/A**: this feature adds no orchestrator/runner parameter, and `hardware-agent/` is not touched
at all. The rule's *spirit* (grep every call site of a changed signature) is honoured instead
against the Python call sites that do exist: `list_findings` gains parameters and its two callers
(`routers/findings.py:22` and `tests/test_read_service.py:247,251,256`) are listed in the naming
table, as is `tests/test_health.py`'s route-surface allowlist, which currently asserts
`/api/v1/scans` **404s** (`tests/test_health.py:27`) and will fail the moment the list route
mounts.

**No `INTEGRATION.md`.** Single layer (backend only), and the wire contract is already frozen and
agreed — there is no new cross-layer agreement to design. DMI-81 (frontend) consumes these
endpoints as published; nothing is negotiated here.

**No contract edit.** `contracts/openapi/openapi.yaml` is authoritative and is **not** modified by
this feature. Two genuine gaps were found while reading it; both are recorded under
[Open items](#open-items) rather than designed around.

## System context

Where these two reads sit:

```
Pi ingest (POST /api/v1/scans — still unmounted)
  → persist_scan writes ScanRecord / ScanHostRecord / PortRecord / FindingRecord
  → upsert_hosts_for_scan materialises HostRecord (services/hosts.py:23)
  → [ READ PATH ]  routers/*  →  services/read.py  →  schemas/read.py
       GET /api/v1/hosts            list_hosts          (read.py:29)   built
       GET /api/v1/hosts/{host_id}  get_host_detail     (read.py:51)   built
       GET /api/v1/scans/{scan_id}  get_scan_detail     (read.py:106)  built
       GET /api/v1/findings         list_findings       (read.py:154)  built, host_id only
       GET /api/v1/scans            list_scans                          ← THIS FEATURE
       GET /api/v1/findings         + severity/scan_id/page/per_page    ← THIS FEATURE
```

**Current state, verified:**

- `GET /api/v1/scans` **does not exist**. `backend/src/api/routers/scans.py:16` declares exactly
  one route, `GET /api/v1/scans/{scan_id}`. `tests/test_health.py:33-57`'s
  `EXPECTED_ROUTE_SURFACE` confirms the whole mounted surface and contains no `("/api/v1/scans",
  "GET")` entry.
- `GET /api/v1/findings` exists (`routers/findings.py:16`) but its handler takes **only**
  `host_id: UUID | None = None` (`routers/findings.py:18`). No `severity`, no `scan_id`, no
  `page`, no `per_page` reach the service, which defaults them internally
  (`services/read.py:158-160`).
- `ScanSummary` has **no** pydantic counterpart: `backend/src/api/schemas/read.py` defines nine
  models (`Port`, `ScanHostView`, `FindingRead`, `HostSummary`, `HostScanHistoryEntry`,
  `HostDetailResponse`, `ScanDetailResponse`, `HostListResponse`, `FindingListResponse`) and
  `tests/test_read_schema.py:49-61` asserts that count is exactly nine. `ScanSummary` and
  `ScanListResponse` are new.

**What this unblocks:** DMI-81's Home screen (`specs/020-frontend-vertical-slice-login-home/`).
Home asks for `GET /api/v1/scans?per_page=1` (the latest scan and its verdict fields) then
`GET /api/v1/findings?scan_id=<that>&severity=critical` and `&severity=high`. Both are impossible
today.

**What this does not touch:** ingest and `persist_scan`; `get_scan_detail`; `list_hosts` /
`get_host_detail` (the contract declares `HostSortBy` at `openapi.yaml:981` and `Page`/`PerPage`
for `/hosts`, but TRUTH scopes this feature to scans and findings — `read_hosts`'s missing
pagination params stay missing, see Open items); auth; the enrichment worker; the schema, beyond
the single severity check constraint of §Migrations.

## Data model / contracts

### Endpoint A — `GET /api/v1/scans` (`operationId: listScans`, `openapi.yaml:164`)

Security: `FrontendBearerAuth` (`openapi.yaml:168-169`) → `caller: CallerIdentity =
Depends(require_user)`, identical to the four neighbouring routes.

| Query param | Type in FastAPI | Default | Bounds | Contract |
|---|---|---|---|---|
| `page` | `int` | `1` | `ge=1` | `Page`, `openapi.yaml:932-941` |
| `per_page` | `int` | `20` | `ge=1, le=100` | `PerPage`, `openapi.yaml:941-951` |
| `status` | `ScanStatus \| None` | `None` | enum `pending\|accepted\|processing\|completed\|failed` | `ScanStatusFilter`, `openapi.yaml:961-968`; enum at `openapi.yaml:1456-1463` |
| `sort_by` | `ScanSortBy` | `"timestamp"` | enum `timestamp\|status\|scan_mode` | `ScanSortBy`, `openapi.yaml:968-978` |
| `sort_order` | `SortOrder` | `"desc"` | enum `asc\|desc` | `SortOrder`, `openapi.yaml:951-961` |

Response `200`: `ScanListResponse` (`openapi.yaml:1810`) = `{data: ScanSummary[], total: int≥0,
page: int≥1}` — the same three-key envelope as the existing `HostListResponse` /
`FindingListResponse` (`schemas/read.py:114-127`). **There is no `per_page` in the envelope**; the
caller already knows what it asked for.

`ScanSummary` (`openapi.yaml:1718`), `additionalProperties: false` → `ConfigDict(extra="forbid")`,
matching every model in `schemas/read.py`:

| Field | Type | Required | Source |
|---|---|---|---|
| `scan_id` | `UUID` | yes | `ScanRecord.scan_id` (`persistence.py:26`) |
| `timestamp` | `datetime` | yes | `ScanRecord.timestamp` (`persistence.py:28`) |
| `subnet` | `str` | yes | `ScanRecord.subnet` (`persistence.py:29`) |
| `scan_mode` | `ScanMode` literal | yes | `ScanRecord.scan_mode` (`persistence.py:30`) |
| `status` | `ScanStatus` literal | yes | `ScanRecord.status` (`persistence.py:31`) |
| `host_count` | `int` `ge=0` | yes | aggregate, below |
| `finding_count` | `int` `ge=0` | yes | aggregate, below |
| `highest_severity` | `Severity \| None` | **no** | aggregate, below; `anyOf [Severity, null]` at `openapi.yaml:1747-1750` |

`ScanMode`, `ScanStatus` and `Severity` literals already exist at `schemas/read.py:9-11` and are
reused verbatim — do not redeclare them.

> **`subnet` is a plain `str` here, deliberately.** The contract gives `ScanSummary.subnet` no
> pattern (`openapi.yaml:1732-1733`) while `ScanDetailResponse.subnet` *does*
> (`openapi.yaml:1772-1774`, mirrored by the `constr(pattern=...)` at `schemas/read.py:103`).
> Copying the stricter constraint into `ScanSummary` would be a contract deviation that could 500
> a list containing a scan whose subnet the detail regex rejects. Match the contract.

Error branches:

| Status | Cause | Mechanism |
|---|---|---|
| `401` | absent / malformed / expired bearer | `require_user` (`dependencies/auth.py:28-39`) → `HTTPException` → `http_exception_handler` (`main.py`) → `{"error":{"code":"unauthorized",...}}` |
| `422` | `per_page>100`, `page<1`, unknown `sort_by`/`sort_order`/`status` | FastAPI `RequestValidationError` → `validation_exception_handler` (`main.py`) → `{"error":{"code":"validation_error",...}}`. Contract publishes `400` here — see Open items |
| `500` | unhandled | `unhandled_exception_handler` (`main.py`) |

**No `404`, no `403`, ever.** An org with no scans returns `{"data": [], "total": 0, "page": N}`
(TRUTH AC 5, AC 7). A list is never "not found".

### Endpoint B — `GET /api/v1/findings` (`operationId: listFindings`, `openapi.yaml:379`)

| Query param | Type | Default | Bounds | Contract | State |
|---|---|---|---|---|---|
| `page` | `int` | `1` | `ge=1` | `Page`, `openapi.yaml:932` | **new on the route** |
| `per_page` | `int` | `20` | `ge=1, le=100` | `PerPage`, `openapi.yaml:941` | **new on the route** |
| `severity` | `Severity \| None` | `None` | enum `low\|medium\|high\|critical` | `SeverityFilter`, `openapi.yaml:991`; enum `openapi.yaml:1482-1488` | **new** |
| `scan_id` | `UUID \| None` | `None` | uuid | `ScanIdFilter`, `openapi.yaml:1005` | **new** |
| `host_id` | `UUID \| None` | `None` | uuid | `HostIdFilter`, `openapi.yaml:1045` | exists (`routers/findings.py:18`) |

**`severity` is a single value, not an array** (`openapi.yaml:991-994` `$ref`s the scalar
`Severity` schema). Do not accept a list, a comma-separated string, or a range. TRUTH's out-of-scope
list is explicit: "a caller wanting two asks twice."

Response `200`: `FindingListResponse` (`openapi.yaml:2388`), already implemented at
`schemas/read.py:122-127`. **Unchanged** — no field added, renamed or removed. Error branches are
identical to Endpoint A.

### Design problem 1 — per-scan aggregates without N+1

`get_scan_detail` computes `host_count`/`finding_count` with `len()` over fully materialised lists
(`services/read.py:149-150`). That is fine for one scan; it does not survive a page of 20. Two
things must **not** happen:

1. **A per-row loop.** Calling `open_ports_count`/`highest_severity`-style helpers per scan row
   (the pattern at `services/read.py:85-86`, which is itself an N+1 inside `get_host_detail`) would
   issue `2×per_page` extra queries per request.
2. **A naive multi-join.** Joining `scan_hosts` **and** `findings` onto `scans` in one query and
   counting produces a cartesian fanout: a scan with 12 hosts and 4 findings yields 48 rows, so
   `host_count` reports 48 and `finding_count` reports 48. TRUTH AC 9 requires 12 and 4.

**Strategy — page first, then two grouped aggregates restricted to the page's ids.** Four queries
total, constant in `per_page`:

```
Q1  total   = SELECT count(*) FROM scans WHERE org_id = :org AND (status = :status OR :status IS NULL)
Q2  page    = SELECT * FROM scans WHERE <same predicates> ORDER BY <sort> LIMIT :per_page OFFSET :off
    ids     = [row.scan_id for row in page]                 # ≤ per_page, ≤ 100
Q3  hosts   = SELECT scan_id, count(*) AS host_count
              FROM scan_hosts WHERE scan_id IN :ids GROUP BY scan_id
Q4  finds   = SELECT scan_id, count(*) AS finding_count, max(<severity_rank>) AS severity_rank
              FROM findings WHERE scan_id IN :ids GROUP BY scan_id
```

Then zip in Python: `host_count = hosts.get(scan_id, 0)`, `finding_count = finds.get(scan_id,
(0, None))[0]`, `highest_severity = rank_to_label(rank)` or `None`.

**Cost, plainly stated.** Four round trips per request regardless of page size (vs. `2 + 2N` for the
loop, i.e. 42 for a 20-row page). `Q3`/`Q4` are index-driven: `ScanHostRecord.scan_id` is indexed
(`persistence.py:52`) and `FindingRecord.scan_id` is indexed (`persistence.py:121`), so both are an
index scan over ≤100 ids plus a group-by. `Q1`'s count over `scans` uses `ix_scans_org_id`
(`persistence.py:27`). Nothing here needs a new index; ADR-009's materialised-view idea and TRUTH's
"no denormalised counters" both stay out.

Grouped-subquery-plus-outer-join in a single statement is an equivalent formulation and is
acceptable if the implementer prefers it — but **only** with each aggregate pre-grouped in its own
subquery before the join, never as two direct joins. The four-query form is specified because it is
the harder one to get wrong and reads better; either passes the same tests.

`ids` is empty when the page is past the end — skip `Q3`/`Q4` entirely rather than emitting
`IN ()`.

### Design problem 2 — ranking a string severity column

`FindingRecord.severity` is `str` (`persistence.py:134`) with domain `low|medium|high|critical`.
`max()` on that column is **lexical**: `'low' > 'critical' > 'high'`. Wrong for every input.

The ranking already exists, once, at `services/hosts.py:14`:

```python
_SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
```

**Where it lives:** a public `SEVERITY_ORDER` in `backend/src/api/schemas/read.py`, beside the
`Severity` literal, derived from it rather than restating it:

```python
SEVERITY_ORDER: dict[str, int] = {
    name: rank for rank, name in enumerate(get_args(Severity), start=1)
}
```

**Do not** define a second copy in `read.py`, in `services/hosts.py`, in a new `constants.py`, or
inline in a query.

> **As-built amendment.** This spec originally placed the constant in `services/hosts.py`,
> reasoning that `services/read.py` already imported that module so the import cost nothing. That
> missed the third reader: §Severity domain constraint makes `models/persistence.py` build its
> `CheckConstraint` from the same keys, and a *model* importing a *service* inverts the layering —
> models are the bottom layer every service imports. The cycle it created forced deferred model
> imports inside three `hosts.py` functions and cost `upsert_hosts_for_scan` its `scan_record:
> ScanRecord` annotation. `schemas/read.py` is a leaf (no `api.*` imports), so all three readers —
> model, `services/hosts.py`, `services/read.py` — reach it without inverting anything.

`services/read.py` derives two things from that single dict:

- a SQL rank expression, `case(SEVERITY_ORDER, value=FindingRecord.severity, else_=0)` — SQLAlchemy
  renders the dict as a `CASE WHEN severity='low' THEN 1 ... END`, so the mapping is never
  duplicated as literals in the module;
- the inverse `{1: "low", ..., 4: "critical"}` for turning `max(rank)` back into the contract label.

`else_=0` is defensive against a severity string outside the domain; such a row ranks below `low`
and never wins the max. That defence is belt-and-braces only: the check constraint of
§Severity domain constraint makes such a row unwritable in the first place. Keep both — the
`else_=0` also protects rows written before the constraint lands.

### Design problem 3 — `highest_severity` must be null, not defaulted (TRUTH AC 10)

The `Q4` grouped aggregate contains **no row at all** for a scan with zero findings. The lookup
therefore misses, and the summary is built with `finding_count=0, highest_severity=None`. There is
no `.get(..., "low")`, no `or "low"`, no `coalesce(..., 'low')` anywhere in the mapper. `ScanSummary
.highest_severity: Severity | None = None` and the contract's `anyOf [Severity, 'null']`
(`openapi.yaml:1747`) then serialise it as JSON `null`. A scan with findings but all of them `low`
correctly reports `"low"` — the two cases are distinguishable, which is the point of AC 10.

### Design problem 4 — total counts matches, never the page

`list_findings` today counts with `select(func.count()).select_from(base.subquery())`
(`services/read.py:176-178`) where `base` carries the org predicate and the `host_id` branch
(`services/read.py:162-174`), and pages with `.offset(...).limit(...)` applied **only** to the row
query (`services/read.py:179-181`). That structure is already correct and is what makes AC 18
hold; the requirement is to keep it correct as filters are added.

**Rule: build one `base` select carrying every predicate, then derive both `total` and the page from
it.** New filters compose onto `base` before either derivation:

```python
base = (select(FindingRecord, ScanHostRecord.host_id)
        .join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id)
        .where(ScanRecord.org_id == org_id))
if host_id is not None:  base = base.join(ScanHostRecord, ...).where(ScanHostRecord.host_id == host_id)
else:                    base = base.outerjoin(ScanHostRecord, ...)
if severity is not None: base = base.where(FindingRecord.severity == severity)
if scan_id  is not None: base = base.where(FindingRecord.scan_id == scan_id)
total = session.exec(select(func.count()).select_from(base.subquery())).one()
rows  = session.exec(base.offset((page - 1) * per_page).limit(per_page)).all()
```

Because the severity and scan filters are plain `WHERE` predicates on `FindingRecord`, they attach
to `base` regardless of which join branch ran, and conjunctive combination (TRUTH AC 14, 16) is
automatic. An omitted filter adds no clause (AC 17).

**The outer-vs-inner join branch, examined — it is safe, and here is why.** The concern is that
`base.subquery()` counts a different row set than the page query when the join flips. It does not,
for two reasons:

1. **Same `base` object.** `total` and `rows` are derived from the identical select; the only
   difference is `offset`/`limit`. Whatever the join is, both see it.
2. **The join cannot multiply rows.** `FindingRecord.scan_host_id` is a scalar FK to
   `ScanHostRecord.id`, the primary key (`persistence.py:122-124`, `persistence.py:51`) — a
   many-to-one join. One finding produces at most one row on either the inner or the outer side, so
   `count(*)` over the subquery equals the number of matching findings, never an inflated join
   count. This is the property that makes `select_from(base.subquery())` legitimate rather than
   accidental; if a future filter joins a one-to-many table it stops holding and the count must
   become `count(distinct FindingRecord.id)`.

What the branch *does* change is the **result set**, deliberately: with `host_id` set, the inner
join drops findings whose `scan_host_id IS NULL` (global / un-attributable findings). That is
correct — a finding attributed to no host is not that host's finding — and the total honestly counts
the narrowed set. AC 15 ("exactly as before this feature") is preserved because that branch is not
edited.

`ScanListResponse.total` obeys the same rule via `Q1`/`Q2` sharing predicates (AC 6, AC 7).

### Design problem 5 — org scoping with a nullable `org_id`

`ScanRecord.org_id` is `UUID | None` (`persistence.py:27`); `CallerIdentity.org_id` is a
non-nullable `UUID` (`dependencies/auth.py:21`). Consequences:

- **`ScanRecord.org_id == org_id` is the correct and sufficient predicate.** In SQL, `NULL = <uuid>`
  evaluates to `NULL`, not `TRUE`, so **pre-existing rows with a NULL `org_id` are invisible to
  every org** — they belong to nobody. This is established, tested behaviour, not a new decision:
  `tests/test_read_service.py:262` (`test_null_org_id_host_and_scan_visible_to_nobody`) asserts it
  for `get_host_detail`, `get_scan_detail` and `list_hosts`. `list_scans` inherits it by using the
  same predicate; add the equivalent assertion for `list_scans`.
- **Never write `IS NOT DISTINCT FROM` here.** `services/hosts.py:35` uses that on the *ingest* path
  where a NULL org must self-match for identity collapsing. On the read path it would make orphan
  rows visible to every tenant. The two are not interchangeable.
- **A cross-org id leaks nothing (TRUTH AC 20)** because the org predicate is applied **on the org's
  own anchor table, independently of the id filter** — never as an `OR`, never as an alternative
  branch:
  - `?scan_id=<other org's scan>`: `base` already joins `ScanRecord` and requires
    `ScanRecord.org_id == org_id` (`services/read.py:164-166`). The extra
    `FindingRecord.scan_id == scan_id` narrows further, so the conjunction is empty. Not a 404, not
    a 403 — an empty page with `total: 0`.
  - `?host_id=<other org's host>`: same shape, already covered by
    `tests/test_read_service.py:256-259` and `test_list_findings_filtered_by_foreign_host_id_returns_empty`
    (`tests/test_read_endpoints.py:434`).
  - `list_scans` filters `ScanRecord.org_id == org_id` before anything else, so no `status`, sort or
    page value can widen it (AC 11).

Answering 404/403 for a foreign id would confirm the row exists in another tenant. Empty is the
answer, consistent with the existing note in `.claude/docs/backend/routers.md`.

### Design problem 6 — validation is FastAPI's, not hand-rolled (TRUTH AC 22, 23)

No `if per_page > 100: per_page = 100`, no `min(...)`, no manual `raise HTTPException(400)`. The
constraints are declared on the handler signature so FastAPI refuses the request before any handler
code runs:

```python
# routers/scans.py
@router.get("/api/v1/scans", response_model=ScanListResponse)
def read_scans(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: ScanStatus | None = Query(None),
    sort_by: ScanSortBy = Query("timestamp"),
    sort_order: SortOrder = Query("desc"),
    session: Session = Depends(get_session),
    caller: CallerIdentity = Depends(require_user),
) -> ScanListResponse: ...
```

where `ScanStatus` is the existing literal (`schemas/read.py:10`) and `ScanSortBy` /
`SortOrder` are two new `Literal` aliases in `schemas/read.py`. A `Literal` renders as an OpenAPI
enum, so an unknown value is a validation failure rather than a silent fallthrough — this is what
makes AC 23 automatic. `page`/`per_page` bounds are `ge`/`le` on `Query`, which is what makes AC 22
a refusal rather than a clamp.

The **service layer keeps its own defensive defaults** (`page: int = 1, per_page: int = 20`, as at
`services/read.py:159-160`) so it is callable from tests without a request, but performs **no**
bounds checking — validation has exactly one home.

**Which status code?** FastAPI raises `RequestValidationError` for query-parameter failures, which
`main.py`'s `validation_exception_handler` turns into **`422`** with the DMI-72 envelope
(`{"error": {"code": "validation_error", "message": ..., "details": {"field": ...}}}`). The
contract's `BadRequest` response (`openapi.yaml:1165-1178`) implies **`400`** with `code:
bad_request`, and neither endpoint lists a `422`. **Ship the native `422`** — it satisfies TRUTH
("the request is refused as a bad request … not silently clamped"), it matches how every other
mounted route already behaves, and coercing it to 400 would mean hand-rolling the very validation
this section forbids. The divergence is recorded in [Open items](#open-items) as a contract
observation, not patched.

### Design problem 7 — sorting: safe column mapping and a total order

**No string interpolation into SQL.** `sort_by` is a `Literal`, and it indexes a module-level dict
of **column objects** in `services/read.py`:

```python
_SCAN_SORT_COLUMNS = {
    "timestamp": ScanRecord.timestamp,
    "status":    ScanRecord.status,
    "scan_mode": ScanRecord.scan_mode,
}
```

Never `text(f"ORDER BY {sort_by}")`, never `getattr(ScanRecord, sort_by)`. The dict is closed: a
value outside it cannot reach the query because FastAPI already rejected it, and even if the service
is called directly a `KeyError` is a crash, not an injection.

**The order must be total.** `status` and `scan_mode` are low-cardinality strings — a page of scans
sorted by `status` has many ties, and Postgres gives no stable order for tied rows across two
`LIMIT/OFFSET` queries. Page 1 and page 2 could then repeat a row and drop another (TRUTH AC 6
requires "none repeated from the first page"). So **always append a deterministic tie-breaker**:

```python
column = _SCAN_SORT_COLUMNS[sort_by]
direction = column.desc() if sort_order == "desc" else column.asc()
query = query.order_by(direction, ScanRecord.scan_id.asc())
```

`scan_id` is the primary key (`persistence.py:26`), so `(sort column, scan_id)` is unique and the
order is total. The tie-breaker is always ascending regardless of `sort_order` — its only job is
determinism, and the contract does not describe it.

`timestamp` desc + `scan_id` asc is the default and satisfies AC 1 (`per_page=1` → the newest scan)
and AC 2. AC 3 is `sort_order=asc`. AC 4 is `sort_by=status|scan_mode`, where the assertion must be
on the sort *column's* order, not on full row identity, precisely because ties exist.

### Migrations

**Exactly one revision: `20260727_12_finding_severity_domain`**, `down_revision = "20260724_11"`
(verified current head, `20260724_11_agents_public_key.py:6`). Its entire scope is the
`findings.severity` check constraint required by TRUTH AC 27–28; see §Severity domain constraint
for the rationale and the guard. Nothing else about the store changes.

**No other schema change is needed.** Every column read by the two list queries already exists:
`ScanRecord.scan_id/org_id/timestamp/subnet/scan_mode/status` (`persistence.py:26-31`),
`ScanHostRecord.scan_id` (`persistence.py:52`), `FindingRecord.scan_id/scan_host_id/severity`
(`persistence.py:121-134`). No column is added, renamed, retyped or backfilled.

**No new index**, per TRUTH ("no new indexes unless a criterion above cannot otherwise be met").
Checked against the actual query plan needs: `scans.org_id` is indexed (`persistence.py:27`),
`scan_hosts.scan_id` is indexed (`persistence.py:52`), `findings.scan_id` is indexed
(`persistence.py:121`). The only unindexed predicates introduced are `scans.status` and
`findings.severity`, both low-cardinality filters over a table that holds one scan per day per org
(ADR-009's volume estimate: 1 scan/day, /24 subnet) — a sequential filter there is not a criterion
failure. Revisit only with real volume.

## New files and naming (mandatory)

Every file an implementer creates or touches. Paths are exact.

| Path | New/Touch | Notes |
|---|---|---|
| `backend/src/api/schemas/read.py` | Touch | Add `ScanSortBy = Literal["timestamp","status","scan_mode"]` and `SortOrder = Literal["asc","desc"]` beside the existing literals (`schemas/read.py:9-11`). Add `ScanSummary` (8 fields, `extra="forbid"`, `subnet: str` with **no** pattern, `highest_severity: Severity \| None = None`) and `ScanListResponse` (`data/total/page`, mirroring `HostListResponse` at `schemas/read.py:114`). Reuse `ScanMode`/`ScanStatus`/`Severity` — do not redeclare. Also add `SEVERITY_ORDER` here, derived from `Severity` (§Design problem 2). |
| `backend/src/api/services/hosts.py` | Touch | Delete `_SEVERITY_ORDER` (`services/hosts.py:14`) and import `SEVERITY_ORDER` from `api.schemas.read` instead; update its one reader (`services/hosts.py:83`). No behaviour change. Keep the module's model imports at top level and `upsert_hosts_for_scan`'s `scan_record: ScanRecord` annotation — see the as-built amendment under §Design problem 2 for why. |
| `backend/src/api/services/read.py` | Touch | Add `_SCAN_SORT_COLUMNS`, a severity `case()` rank expression + inverse map built from `SEVERITY_ORDER`, and `list_scans(session, *, org_id, page=1, per_page=20, status=None, sort_by="timestamp", sort_order="desc") -> ScanListResponse` (4-query aggregate strategy). Extend `list_findings` (`services/read.py:154`) with keyword-only `severity: Severity \| None = None` and `scan_id: UUID \| None = None`, composed onto `base` before `total`/`rows` (`list_scans` likewise takes `status: ScanStatus \| None` — the filter params are typed to the domain, matching `sort_by`/`sort_order`, not left as bare `str`). `org_id` stays keyword-only and required on both (asserted by `tests/test_read_service.py:105`). Add a `_to_scan_summary(...)` mapper next to `_to_host_summary` (`services/read.py:211`). |
| `backend/src/api/routers/scans.py` | Touch | Add `read_scans()` for `GET /api/v1/scans` with the five `Query(...)`-constrained params above, `Depends(get_session)` + `Depends(require_user)`, `response_model=ScanListResponse`. Leave `read_scan` (`routers/scans.py:16`) untouched. Declaration order vs. `/{scan_id}` is irrelevant — the paths are literal-vs-param and do not collide. |
| `backend/src/api/routers/findings.py` | Touch | Widen `read_findings` (`routers/findings.py:17`) to accept `page`, `per_page`, `severity`, `scan_id` alongside the existing `host_id`, and forward all five to `list_findings`. |
| `backend/src/api/models/persistence.py` | Touch | Add a named `CheckConstraint` on `findings.severity` to `FindingRecord.__table_args__` (`persistence.py:110`, which already holds a `UniqueConstraint`) restricting it to the four `SEVERITY_ORDER` keys, imported from `api.schemas.read` (**not** from `services/hosts.py` — see the as-built amendment under §Design problem 2). Constraint name must match the migration's exactly, so downgrade can drop it. Model-side change only — no column type change, no default. |
| `backend/alembic/versions/20260727_12_finding_severity_domain.py` | **New** | The one migration in scope. `down_revision = "20260724_11"` (current head, `20260724_11_agents_public_key.py:7`). `upgrade()` adds the check constraint; `downgrade()` drops it by name. **Import nothing from `api.*`** — spell the four severities out as literals. A revision is a frozen historical snapshot, so binding its SQL to a live constant means a later edit to `SEVERITY_ORDER` silently rewrites already-applied history, and a module move breaks replay from base. No sibling revision imports application code; do not be the first. The drift this trades for is caught by a test instead (see the `test_finding_severity_migration.py` row). **Guard the upgrade:** if any existing row is out of domain, constraint creation fails mid-migration — the migration must assert the table is clean first and fail with a message naming the offending values, or AC 28 ("existing data survives, upgrade is reversible") cannot be met. **Alembic only ever runs against Postgres** — the app rejects any non-Postgres `DATABASE_URL` (asserted at `tests/test_db_session.py:45` and `tests/test_settings.py:51`, both of which parametrise `sqlite://` as a URL that must be refused) — so plain `op.create_check_constraint` / `op.drop_constraint` work; no batch mode needed. Note this is *not* the same as "no SQLite anywhere": three HTTP-level test files build an in-memory SQLite fixture engine via `SQLModel.metadata.create_all()` (`tests/test_read_endpoints.py:30`, `tests/test_error_envelope.py:43`, `tests/test_users_routes.py:32`). Those never run migrations, but they **will** now emit the model-side constraint into their schema, and SQLite does enforce `CHECK` — so any fixture seeding an out-of-domain severity would start failing. **Audited: none does.** Every `FindingRecord.severity` in the test tree is `"high"` or `"low"`. One near-miss to leave alone: `highest_severity="none"` (`tests/test_error_envelope.py:77`) is out of domain but sits on `HostRecord`, which this constraint does not cover. Precedent for the constraint expression: `sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role")` (`20260716_02_identity_schema.py:54`) — note that one is inline in a `create_table`, so this is the first ALTER-added constraint in the repo. |
| `backend/tests/test_finding_severity_migration.py` | **New** | Covers AC 27, 28 and the guard, plus one test asserting the revision's spelled-out severity set still equals `SEVERITY_ORDER` — the safety net for the migration's deliberate non-import above. The repo's convention is **one test file per revision** — seven exist (`test_agents_public_key_migration.py`, `test_identity_migration.py`, `test_users_email_unique_migration.py`, …), each with an importlib `_load_migration()`, a revision-chain test, monkeypatched `op.*` assertions and a live `_migrate` round trip. Follow that shape. |
| `backend/tests/test_migrations.py` | **Not touched** | Verified: it owns the alembic env, config, the **baseline** shape/security fence, the destructive-DB guard and the base→head chain round trip — nothing revision-specific after the baseline. Its `TableShape` helper (`tests/test_migrations.py:84-122`) does not inspect `CheckConstraint`, so the new constraint cannot break `test_baseline_matches_model_metadata_and_security_fence`. |
| `backend/tests/test_contract_fidelity.py` | **New** | AC 24. See §Contract fidelity. |
| `backend/pyproject.toml` | Touch | Add `pyyaml` to the `dev` extra (`pyproject.toml:33`, currently `dev = ["pytest", "ruff"]`). Test-only — **not** added to the runtime `dependencies` list. Required by §Contract fidelity; no YAML parser is currently installed. |
| `backend/tests/conftest.py` | **Not touched** | The seeds below (`scan_history_org`, `mixed_severity_findings`) stayed module-level helpers in the test files, matching `tests/test_read_service.py:20-102` — no seeder ended up shared. The shared *record builders* went to `tests/read_factories.py` instead of here, being plain functions rather than fixtures. |
| `backend/tests/test_read_schema.py` | Touch | Add `ScanSummary`/`ScanListResponse` cases. **Must update `test_all_nine_read_models_importable` (`tests/test_read_schema.py:49-61`)** — its `assert len(models) == 11` and name. |
| `backend/tests/test_read_service.py` | Touch | Add the new `list_findings` filter cases. Its three existing `read.list_findings(...)` call sites (`tests/test_read_service.py:247,251,256`) keep passing unchanged — the new params are optional keywords. |
| `backend/tests/test_read_service_scans.py` | **New** | The `list_scans` service cases (AC 1–11, 26). Split out because they would have taken `test_read_service.py` past 1000 lines — see the amendment under §Testing expectations. |
| `backend/tests/read_factories.py` | **New** | The five record builders (`make_org`, `make_host`, `make_scan`, `make_scan_host`, `make_finding`) the two service-tier test files share. Not a `conftest.py` addition: they are plain functions, not fixtures. |
| `backend/tests/test_read_endpoints.py` | Touch | Add route-level cases for `GET /api/v1/scans` and the new findings params, including the 401 and 422 branches. |
| `backend/tests/test_health.py` | Touch | **Blocking.** `EXPECTED_ROUTE_SURFACE` (`tests/test_health.py:33-57`) gains `("/api/v1/scans", "GET")`, and `"/api/v1/scans"` is **removed** from `DISCARDED_BUSINESS_PATHS` (`tests/test_health.py:27`) — the assertion at `tests/test_health.py:106` expects it to 404 and will fail the moment the route mounts. `"/scans"` and `"/findings"` (unprefixed) stay discarded. |

**Explicitly not touched:** `backend/src/api/main.py` (`scans.router` and `findings.router` are
already mounted); `contracts/openapi/openapi.yaml`; `backend/src/api/services/persistence.py`;
`backend/src/api/routers/hosts.py`; anything under `hardware-agent/` or `frontend/`.

### Deterministic ordering (TRUTH AC 25, 26)

Both list queries end in a **total order**, so paging cannot repeat or drop a row when many
records tie on the ordered column:

- **Scans:** the requested `sort_by`/`sort_order`, then `ScanRecord.scan_id` **always ascending**
  as the tie-breaker. Sorting by `status` or `scan_mode` produces large tie groups, which is
  exactly where an unstable order corrupts paging.
- **Findings:** `FindingRecord.id` ascending — an integer primary key (`persistence.py:114`),
  so it is unique, non-null and already the physical order. This is the only ordering findings
  have; the contract declares no finding sort and none is exposed. It is invisible to callers
  except that paging now works, which is why TRUTH permits it while still excluding
  caller-chosen sorting.

The tie-breaker is appended **after** the caller's ordering, never before it, so it can never
change the order the caller actually asked for.

### Severity domain constraint (TRUTH AC 27, 28)

`FindingRecord.severity` is a bare `str` (`persistence.py:134`) with no domain enforcement, while
`FindingRead.severity` is a strict `Literal` (`schemas/read.py:49`). A row outside the four known
values therefore serialises into a **500** — the caller cannot be told about a finding that
exists. The `case(..., else_=0)` severity rank tolerates such a row, which means it would rank
below `low` and silently distort `highest_severity` rather than failing loudly.

Fixed with a `CheckConstraint` on the column, restricted to the `SEVERITY_ORDER` keys so the
allowed set is defined **once** and the constraint cannot drift from the ranking. This is the
reader that forces `SEVERITY_ORDER` out of `services/hosts.py` and into `schemas/read.py` — see
the as-built amendment under §Design problem 2. The *migration* is the one exception: it spells
the four values out, because a frozen revision must not import live code. Ingest already
prevents bad values; this makes that guarantee structural rather than a property of one code
path. One reversible migration, no column type change, no data rewrite.

### Contract fidelity (TRUTH AC 24)

**Nothing in this repo currently compares the app's schema to the frozen contract.** A grep for
`openapi.yaml` across `backend/src` and `backend/tests` returns one hit, and it is a comment
(`main.py:98`). The app does not even serve a schema — `main.py:38` sets `openapi_url=None`.
So AC 24's "published schema" does not exist as a runtime artefact today.

Asserting pydantic model shape alone does **not** satisfy AC 24. Those assertions encode what a
human transcribed while reading the YAML; if the transcription is wrong, or the contract moves,
the tests stay green and the drift ships. The one AC whose purpose is catching drift would catch
none.

`app.openapi()` still works in-process despite `openapi_url=None`, so the real comparison is
testable. `backend/tests/test_contract_fidelity.py`:

1. parses `contracts/openapi/openapi.yaml` (repo root, `parents[2]` from the test file);
2. calls `app.openapi()`;
3. compares, **field by field**, only what this feature touches — the `ScanSummary` and
   `ScanListResponse` schemas (property names, types, required set, `additionalProperties`) and
   the query parameters of `listScans` and `listFindings` (name, type, enum values, defaults,
   bounds).

**Scoped deliberately, not lazily.** A whole-document diff fails immediately on the pre-existing
`400`-vs-`422` divergence (Open item 1) and on every other endpoint's gaps, none of which this
feature owns. Widening it to the full document is its own cleanup ticket.

Response *status codes* are excluded from the comparison for the same reason, and the exclusion
is asserted explicitly with a comment naming Open item 1 — so a reader knows it was decided, not
forgotten.

**Call-site sweep (the CLAUDE.md rule's spirit, applied to what exists here).** Changed signatures
and every caller:

| Changed | Callers, all accounted for |
|---|---|
| `list_findings` (+2 optional kwargs) | `routers/findings.py:22`; `tests/test_read_service.py:247,251,256`. No other module imports it (`services/read.py` is imported by the three routers only). |
| `_SEVERITY_ORDER` (`services/hosts.py`) → `SEVERITY_ORDER` (`schemas/read.py`) | `services/hosts.py:83` (the sole reader at spec time), plus the two readers this feature adds: `services/read.py` (rank + inverse map) and `models/persistence.py` (check constraint). Grep for `_SEVERITY_ORDER` across `backend/` before finishing; if a test references it by name, update that too. |
| `list_scans` (new) | `routers/scans.py` and `tests/test_read_service_scans.py` only. |
| Route surface | `tests/test_health.py:27,33`. |

## Constraints

- **No contract edit.** `contracts/openapi/openapi.yaml` is read-only for this feature. Gaps go to
  Open items.
- **Reuse the existing read path.** New code lands *inside* `services/read.py` and the existing
  routers. No parallel query layer, no repository abstraction, no query-builder class, no new
  `services/` module. `ScanSummary` goes in `schemas/read.py` beside the other nine models, not in a
  new file.
- **`require_user` scoping like the neighbours.** `caller: CallerIdentity = Depends(require_user)`
  and `org_id=caller.org_id` passed into the service, exactly as `routers/hosts.py:19-21`,
  `routers/scans.py:20-22`, `routers/findings.py:20-22`. Tenant boundary in SQL, never in the
  handler. `viewer` and `admin` both read — no `require_admin`.
- **Error envelope from DMI-72.** Nothing constructs an error body by hand; `HTTPException` /
  `RequestValidationError` flow through the handlers in `main.py`, which own the
  `{"error": {"code", "message", "details"}}` shape (`errors.py:27-30`).
- **No new runtime dependencies.** SQLAlchemy `case`, `func.count`, `func.max` and FastAPI `Query`
  are all already in use; the `dependencies` list at `pyproject.toml:11-25` is untouched. **One
  test-only addition:** `pyyaml` joins the `dev` extra (`pyproject.toml:33`) because
  §Contract fidelity must parse the contract and no YAML parser is currently installed
  (`uv run python -c "import yaml"` fails). Nothing shipped to production gains a dependency.
- **Style:** no comments, no docstrings in new code including tests (`docs/README.md` global
  conventions).
- **No `HUMAN_INFRA_REQUIRED`.** No new hardware, daemon, service, index or external tool. The
  feature runs entirely inside the existing FastAPI app. Its one migration (§Migrations) is a
  check constraint applied by the standard `alembic upgrade head` already in the deploy path —
  no human step.

## Testing expectations

Gates: `uv run pytest` and `uv run ruff check`, both inside `backend/`, both green (AC 29). The
service/route split already established is preserved: **`test_read_service.py`** drives
`api.services.read` functions directly against a real Postgres session
(`administrative_session`, `tests/conftest.py:157`) and owns query correctness; **`test_read_endpoints.py`**
drives HTTP through `TestClient` with `app.dependency_overrides[get_session]` over an in-memory
SQLite engine (`tests/test_read_endpoints.py:27-36`) and owns status codes, auth and wire shape;
**`test_read_schema.py`** owns pydantic model shape with no DB at all. Two files join them:
**`test_finding_severity_migration.py`** (new) owns the severity constraint and its migration, on
Postgres; **`test_contract_fidelity.py`** (new) owns the `app.openapi()`-vs-contract comparison,
with no DB.

> **As-built amendment.** The AC map below names `test_read_service.py` for every service-level
> row. As built, the service tier is two files: adding all of `list_scans` plus the new
> `list_findings` filters pushed `test_read_service.py` past 1000 lines, so the scan-list cases
> (AC 1–11, 26) live in **`test_read_service_scans.py`** and the finding cases stay in
> `test_read_service.py`. Both are service-tier tests on `administrative_session`; the split is
> file size only, and every AC row still means "a service test", whichever of the two holds it.
> The five record builders both files need (`make_org`, `make_host`, `make_scan`,
> `make_scan_host`, `make_finding`) live in **`tests/read_factories.py`**; the `_seed_*` seeders
> stay with the tests that use them, since no seeder is shared.

**On the Postgres fixtures skipping locally.** `postgres_engine` calls
`pytest.skip("DATABASE_URL_TEST not set")` (`tests/conftest.py:117-118`), so a bare local
`uv run pytest` does not exercise the constraint test. That is not a hole: CI provisions Postgres,
sets the variable (`.github/workflows/ci.yml:74-88`) and **fails the job if pytest reports any
skip** (`ci.yml:102-106`). Run the gate with `DATABASE_URL_TEST` set before claiming AC 27 or 28.

### Fixtures

Two new seeds. Follow the existing local-helper style (`_make_org`, `_make_scan`, `_make_finding` at
`tests/test_read_service.py:20-102`; `_seed` at `tests/test_read_endpoints.py:51`) and promote to
`conftest.py` only if both files need the same one. *(As built: the record builders are shared by
the two service-tier files and moved to `tests/read_factories.py` — a plain helper module, not
`conftest.py`, since they are ordinary functions rather than fixtures. See the amendment above.)*

| Fixture | Shape | Serves |
|---|---|---|
| `scan_history_org` | one org, **25** scans with strictly increasing `timestamp`s and a mix of `status` (`completed`/`failed`) and `scan_mode`; plus a **second org** with its own scans | AC 1–8, 11, 22, 23 |
| `mixed_severity_findings` | two orgs; per org two scans; per scan one host and findings covering `low`/`medium`/`high`/`critical`; **one scan with zero findings**; one finding with `scan_host_id = NULL` | AC 9, 10, 12–20 |

The zero-finding scan and the NULL-`scan_host_id` finding are load-bearing, not decoration: they are
the only rows that prove AC 10 and the outer-join branch respectively.

### Acceptance criteria → test map

| AC | File | Kind of test |
|---|---|---|
| 1 Latest scan | `test_read_service.py` | `list_scans(per_page=1)` returns exactly one row and its `scan_id` is the max-`timestamp` scan |
| 2 Default order | `test_read_service.py` | `list_scans()` with no sort args → `[r.timestamp for r in data]` is non-increasing |
| 3 Reversed order | `test_read_service.py` | `sort_order="asc"` → `data[0].scan_id` is the oldest |
| 4 Sort by another field | `test_read_service.py` | parametrised over `sort_by="status"` and `"scan_mode"` × `asc`/`desc`; assert the **sort column's** sequence is monotonic (not full row order — ties are broken by `scan_id` and that is not contract behaviour) |
| 5 No scans | `test_read_service.py` + `test_read_endpoints.py` | fresh org → `total == 0`, `data == []`, HTTP **200** (explicitly assert not 404) |
| 6 Scan paging | `test_read_service.py` | 25 scans, `per_page=20`: page 1 → 20 rows, page 2 → 5 rows, `total == 25` on both, and `set(page1_ids) & set(page2_ids) == set()`, `len(page1_ids \| page2_ids) == 25` (proves the total order — the tie-breaker's real test) |
| 7 Page past the end | `test_read_service.py` + `test_read_endpoints.py` | 3 scans, `page=5, per_page=20` → `data == []`, `total == 3`, HTTP 200 |
| 8 Filter by status | `test_read_service.py` | `status="failed"` → every row `.status == "failed"`, count matches the seed, and `total` reflects the filter not the org |
| 9 Per-scan aggregates | `test_read_service.py` | seed scan A with 12 scan-hosts / 4 findings (worst `critical`) and scan B with different numbers; assert A reports `host_count==12, finding_count==4, highest_severity=="critical"` and B reports its own. **The regression test for the cartesian-fanout trap** |
| 10 Scan with no findings | `test_read_service.py` + `test_read_endpoints.py` | the zero-finding scan reports `finding_count == 0` **and `highest_severity is None`**; over HTTP the JSON key is present with value `null` (`assert body["highest_severity"] is None`, not `not in`) |
| 11 Scan isolation | `test_read_service.py` | org A's `list_scans` never contains an org-B `scan_id`, asserted across the cross-product of `status`, `sort_by`, `sort_order` and pages; plus a `list_scans` twin of `test_null_org_id_host_and_scan_visible_to_nobody` (`tests/test_read_service.py:262`) proving a NULL-`org_id` scan is invisible |
| 12 Findings by severity | `test_read_service.py` | `severity="critical"` → every row `.severity == "critical"`; `total` equals the seeded critical count |
| 13 Findings by scan | `test_read_service.py` | `scan_id=A` → every row `.scan_id == A` |
| 14 Filters combine | `test_read_service.py` | `severity="critical", scan_id=A` → only rows satisfying both; count strictly less than either filter alone |
| 15 Existing filter unchanged | `test_read_service.py` | `test_list_findings_scopes_count_and_page_by_org` (`tests/test_read_service.py:227`) and `test_list_findings_filtered_by_host_id` (`tests/test_read_endpoints.py:399`) pass **unmodified** — regression, do not edit them |
| 16 Host + scan together | `test_read_service.py` | a host with findings in two scans; `host_id=H, scan_id=A` → only the intersection |
| 17 No filter | `test_read_service.py` | no `severity` → all four severities present in `data` |
| 18 Paging and total | `test_read_service.py` | 25 matching findings, `per_page=20`, page 1 → `len(data) == 20` **and `total == 25`** (the total-vs-page assertion) |
| 19 Empty filter result | `test_read_service.py` + `test_read_endpoints.py` | a scan with no criticals, `scan_id=X&severity=critical` → 200, `data == []`, `total == 0` |
| 20 Finding isolation | `test_read_service.py` + `test_read_endpoints.py` | org A asks with org B's `scan_id`, then org B's `host_id`, then both → `total == 0` and **HTTP 200**, explicitly asserting neither 404 nor 403 and that no org-B `finding_id` appears. Mirror `test_list_findings_filtered_by_foreign_host_id_returns_empty` (`tests/test_read_endpoints.py:434`) |
| 21 Unauthenticated | `test_read_endpoints.py` | add `/api/v1/scans` to the parametrised `path` lists at `tests/test_read_endpoints.py:275` (no bearer), `:284` (garbage bearer) and `:449` (expired bearer) → 401 with `body["error"]["code"] == "unauthorized"` |
| 22 Invalid paging | `test_read_endpoints.py` | parametrised over both endpoints × `per_page=101`, `per_page=0`, `page=0`, `page=-1` → **422**, and assert `body["error"]["code"] == "validation_error"`. Add a non-clamping assertion: `per_page=100` succeeds while `101` is refused, so the bound is a refusal not a cap |
| 23 Invalid sort | `test_read_endpoints.py` | `sort_by=nope`, `sort_order=sideways`, `status=bogus`, `severity=urgent`, `scan_id=not-a-uuid` → 422 with the envelope |
| 24 Contract fidelity | **`test_contract_fidelity.py`** (new) + `test_read_schema.py` | See §Contract fidelity below. The real comparison — `app.openapi()` against the parsed `contracts/openapi/openapi.yaml` — lives in the new file. `test_read_schema.py` keeps the pydantic-shape cases (`extra="forbid"`, `highest_severity` optional, `subnet` unpatterned) as fast unit coverage, and updates the model-count test at `tests/test_read_schema.py:49` |
| 25 Stable finding paging | `test_read_service.py` | seed 25 findings that **all tie** on severity and timestamp, `per_page=10`; request pages 1–3 in turn; assert the union of returned ids is all 25, every pairwise intersection is empty, and `total == 25` on each page. This is the direct test for the `FindingRecord.id` tie-breaker — it fails if the tie-breaker is dropped |
| 26 Stable scan paging under ties | `test_read_service.py` | several scans sharing one `status`, `sort_by="status"`, paged a few at a time; the union of pages covers every scan exactly once. The `scan_id` tie-breaker's test — the low-cardinality sort column is what makes ties certain |
| 27 Severity domain enforced | **`test_finding_severity_migration.py`** (new) | `pytest.raises(sa.exc.IntegrityError)` around `session.commit()` of a `FindingRecord` with `severity="urgent"`, on `administrative_session`; the four valid values all commit. **Copy the shape of `test_invalid_role_is_rejected` (`tests/test_identity_migration.py:168-179`)** — the repo's existing CHECK-rejection test, which lives in the migration file that introduced its constraint. Carry over its trailing `session.rollback()`, or the poisoned session breaks the next test |
| 28 Existing data survives | **`test_finding_severity_migration.py`** (new) | step down **exactly one** revision — `_migrate(engine, "20260724_11")`, **never `base`**, which drops the tables — seed findings, upgrade to `20260727_12`, assert every seeded row is byte-identical, then downgrade and restore to `head`. Also assert the revision chain and that `downgrade()` drops the constraint **by the same name** `upgrade()` created |
| 28b Migration guard | **`test_finding_severity_migration.py`** (new) | the pre-flight guard: with an out-of-domain row already present, `upgrade()` fails loudly naming the offending value rather than dying inside `create_check_constraint`. Not a TRUTH AC, but the guard is specified in the naming table and is otherwise untested |
| 29 Quality gates | CI | `uv run pytest` + `uv run ruff check` in `backend/` |

### Additional non-AC tests worth having

- **N+1 guard for AC 9** — assert the query count for a 20-scan page is constant (e.g. a SQLAlchemy
  `before_cursor_execute` counter, or simply seeding 20 scans and asserting the page still returns
  correct aggregates). Optional, but it is the only thing that stops the per-row-loop regression.
- **Severity ranking unit test** — a scan whose findings are `{low, critical}` reports `critical`,
  and one with `{low, medium}` reports `medium`. Both fail under lexical `max()`, so this is the
  direct regression test for Design problem 2.
- **`SEVERITY_ORDER` has one definition** — grep-style assertion, or simply that
  `api.services.read`, `api.services.hosts` and `api.models.persistence` all import it from
  `api.schemas.read` rather than defining their own. The migration's spelled-out copy is the
  sanctioned exception and has its own drift test.

## Open items

Genuinely undecided or genuinely divergent. Not designed around.

1. **`400` vs `422` for invalid query parameters — settled: ship `422`, no decision needed here.**
   The contract publishes `400 BadRequest` on both `listScans` and `listFindings` and lists no
   `422`; FastAPI natively returns `422` with `code: validation_error`. TRUTH AC 22/23 require only
   "refused as a bad request", which `422` satisfies.

   **This is not a choice this feature makes.** `main.py:73-86` already returns `422` with the
   standard envelope for *every* validation failure in the application — that handler is DMI-72's
   and is shared by all routes. And `'422'` appears in `contracts/openapi/openapi.yaml` exactly
   once, at line 154 (scan ingest); every other endpoint publishes only `400`. `POST /invites` and
   `POST /auth/change-password` already answer `422` against contract entries that do not mention
   it — asserted today at `tests/test_invite_routes.py:149` and `tests/test_error_envelope.py:147`.

   So the divergence is **app-wide and pre-existing**. This feature behaves like every other
   endpoint and adds nothing new. Forcing `400` on just these two routes would make them
   inconsistent with the rest of the API to satisfy a contract that is already understated
   everywhere else. **The contract's missing `422` entries are one cleanup ticket covering the
   whole API — not a gate on this spec.** Tests here assert `422` + `code: validation_error`.
2. **The validation error message is body-shaped.** `validation_exception_handler` (`main.py`)
   returns `"Request body validation failed."` for *query* failures too. Cosmetic and pre-existing;
   fixing it would touch a DMI-72 handler shared by every route. Flagged, not fixed here. If a
   test asserts on that string, it asserts on `code`, not `message`.
3. **`GET /api/v1/hosts` still ignores `page`/`per_page`.** The contract declares them for `/hosts`
   and `read_hosts` (`routers/hosts.py:17-21`) does not accept them — `list_hosts` hard-defaults to
   page 1 / 20 rows (`services/read.py:30`), so an org with more than 20 hosts silently loses the
   rest. Out of scope per TRUTH (scans and findings only). Should be its own ticket; noting it so it
   is not mistaken for something this feature fixed.
4. **Findings tie-breaker — decided 2026-07-27: fix it here.** Resolved into scope; see
   §Deterministic ordering below. TRUTH's exclusion was narrowed to *caller-chosen* sorting, which
   this is not.
5. **Severity domain constraint — decided 2026-07-27: fix it here.** Resolved into scope; see
   §Severity domain constraint below. TRUTH now permits exactly one reversible migration.
6. **Test homes for AC 27 and AC 28 — closed 2026-07-27.** Both live in one new file,
   `backend/tests/test_finding_severity_migration.py`, per the repo's one-file-per-revision
   convention. Evidence and the full survey:
   `docs/research/finding-severity-constraint-test-placement.md`. Three findings changed the
   design and are folded into the sections above:
   - **Every CHECK-rejection test in this repo already lives in a migration file.** Eleven
     constraint-rejection tests exist; all use `pytest.raises(sa.exc.IntegrityError)` on a
     Postgres session, and the direct analogue — `test_invalid_role_is_rejected`
     (`tests/test_identity_migration.py:168-179`, for `ck_users_role`) — sits in the migration
     that introduced the constraint. The earlier proposal to put AC 27 in `test_read_service.py`
     was wrong: that file is Postgres-backed and *would* have run, but it is read-path only and
     contains no write-rejection test.
   - **Postgres tests cannot silently no-op in CI.** `postgres_engine` skips when
     `DATABASE_URL_TEST` is unset (`tests/conftest.py:117-118`) — but CI provisions Postgres and
     sets it (`.github/workflows/ci.yml:74-88`) and **fails the job on any skip at all**
     (`ci.yml:102-106`). Locally, a bare `uv run pytest` does skip these
     (`backend/README.md:131`); that is expected, not a gap.
   - **AC 28 is new ground.** No existing migration test asserts *row-level* data survival across
     an upgrade; the closest is column-metadata survival
     (`tests/test_agents_public_key_migration.py:202-217`). Hence the explicit "step down exactly
     one revision, never `base`" instruction — `base` drops the tables and would make the test
     vacuous.
7. **The `dev` extra gains `pyyaml`.** Required by §Contract fidelity; test-only. Noted here
   because the spec previously promised no `pyproject.toml` change at all.
