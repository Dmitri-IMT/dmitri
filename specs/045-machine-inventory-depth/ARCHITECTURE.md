# ARCHITECTURE — Deepened machine inventory

> Linear: DMI-135. Implements `specs/045-machine-inventory-depth/TRUTH.md`.
> Supersedes `specs/042-design-system/DESIGN.md` §16 (four fenced-out items) and closes its §17 Q2.
> `DESIGN.md` is written in parallel by the frontend-design-agent and owns every visual decision;
> this document owns data, contracts, and the files that carry them.

## 0. Scope note — three layers, and the one that is untouched

| Layer | Changed? |
|---|---|
| `backend/` | Yes — two new tables, three new host columns, one new ingest step, read-path changes. |
| `contracts/openapi/openapi.yaml` | Yes — additive response and query-parameter changes. |
| `frontend/` | Yes — regenerated types, host/finding data layer, Network's quiet split. |
| `hardware-agent/` | **No.** See §9. |

**No `INTEGRATION.md`.** The scan payload (`ScanIngestRequest` / `HostPayload` /
`PortPayload` / `FindingPayload`, `backend/src/api/schemas/scan.py`) is unchanged, and so is its
producer, `hardware-agent/src/agent/normalize/contracts.py`. Every new fact is derived by the
backend from data the payload already carries. There is no cross-layer contract change between
agent and backend, so the only cross-layer document needed is the OpenAPI diff in §7.

---

## 1. System context — where this sits in the pipeline

```
discovery → port scan → NSE/deep inspection → ScanPayload (agent)
      │
      ▼  POST /api/v1/scans   (unchanged wire shape)
persist_scan()                                backend/src/api/services/persistence.py:81
  ├── _persist_scan_host / _persist_port      per-scan evidence: scan_hosts, ports, services, cpes
  ├── upsert_finding                          per-scan evidence: findings  (unique per scan+dedupe_key)
  ├── upsert_hosts_for_scan()                 machine identity: hosts row, first/last seen  ← exists
  ├── ★ reconcile_scan_inventory()            NEW — the machine's own life: host_ports,
  │                                           host_findings, machine_type, vulnerability_count
  ├── append_scan_activity
  └── _enqueue_enrichment_jobs                → worker → _process_cpe_job may ADD findings later,
                                                so it calls ★ again (§4.4)
      │
      ▼
GET /api/v1/hosts        list — server-side active/quiet split, vulnerability_count sort
GET /api/v1/hosts/{id}   detail — machine-level services with first/last seen
GET /api/v1/findings     list — problem life (first/last seen, fixed) + machine's current name
GET /api/v1/home         attention table reuses FindingRead, so it inherits the name for free
```

The whole feature is one new **reconcile step at ingest** plus the reads that consume what it
writes. Reconcile answers exactly one question — *what did this scan see, against what this
machine already has* — and both promoted ports and promoted findings are answers to it.

---

## 2. Data model

### 2.1 New columns on `hosts` (`HostRecord`, `backend/src/api/models/persistence.py:57`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `machine_type` | `str` | **yes** | none | Closed vocabulary, classified at ingest. `NULL` = never classified; the read maps `NULL` → `"unknown"`, so the wire vocabulary stays exactly nine values. |
| `vulnerability_count` | `int` | no | `0` (`server_default="0"`) | Problems present in this machine's most recent scan. Written only by reconcile. |
| `quiet` | — | — | — | **Not a column.** Quiet is derived on read from `last_seen_at` (§5.2). |

`vulnerability_count` is `NOT NULL DEFAULT 0` rather than nullable, and that does not violate
TRUTH's "nothing is stamped retroactively": there are no findings in production, so `0` is a true
count, not an invented one. `machine_type` is left `NULL` because a type *would* be an invention.

Existing `vendor`, `open_ports_count` and `highest_severity` are **kept** on `hosts` and in the
responses. TRUTH removes them from the *list's columns*, not from the machine's page; deleting the
fields would break `HostDetail` for no gain. `DESIGN.md` decides which columns are drawn.

### 2.2 `host_ports` — services promoted to machine level (new)

`HostPortRecord`, `backend/src/api/models/persistence.py` (added after `PortRecord`).

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `host_id` | `UUID` FK → `hosts.id`, indexed | |
| `port` | `int` | |
| `protocol` | `str` | `tcp` / `udp` |
| `service` | `str` | Name from the most recent scan that saw it open. |
| `version` | `str \| None` | Same. |
| `first_seen_at` | `timestamptz` | Set once, never moved backwards or forwards on re-detection except downwards by a late older scan (§4.3). |
| `last_seen_at` | `timestamptz` | Timestamp of the most recent scan that saw this port **open**. |

`UniqueConstraint("host_id", "port", "protocol")`.

A service is **still open** when `last_seen_at == hosts.last_seen_at`; it has **closed** when it is
older. No `state` column and no `closed_at`: the comparison is the fact, and a second stored copy
of it would be a second thing to keep true.

`PortRecord` (`persistence.py:80`) is **unchanged** and stays the per-scan evidence.

### 2.3 `host_findings` — problem life across scans (new)

`HostFindingRecord`, `backend/src/api/models/persistence.py` (added after `FindingRecord`).

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `host_id` | `UUID` FK → `hosts.id`, indexed | |
| `dedupe_key` | `str`, indexed | Same key `upsert_finding` computes (`finding_dedupe_key`, `services/persistence.py:262`). |
| `first_seen_at` | `timestamptz` | Written once on insert. Never changed by re-detection. |
| `last_seen_at` | `timestamptz` | Timestamp of the most recent scan that found it. |
| `fixed_at` | `timestamptz \| None` | Set when the machine's latest scan no longer finds it; cleared to `NULL` if it comes back. |

`UniqueConstraint("host_id", "dedupe_key")`.

**Deliberate simplification, stated so the next reader does not think it was missed.** The owner's
key is *(org, machine identity_key, dedupe_key)*. `hosts` is already unique on
`(org_id, identity_key)` (`persistence.py:58`), so `host_id` **is** that pair, normalised.
`(host_id, dedupe_key)` is the same key with one column instead of two and an FK that keeps it
honest. No org column is stored on `host_findings`; the org is reached through `hosts`.

`FindingRecord` keeps `UniqueConstraint("scan_id", "dedupe_key")` and gains **no** columns. The
hostname is **not** denormalised onto it (TRUTH rule 5), and neither are the three dates — a
finding row is per-scan evidence, and the life belongs to the machine.

**Neither new table carries `created_at`, and that is deliberate** (noted 2026-09-07, so the
omission is not read as an oversight). Every other table in `persistence.py` has one because its row
records *when we wrote it*. These two rows record *when the network was seen*, which is
`first_seen_at` — a scan timestamp, not a wall-clock insert time, and one a late-arriving older scan
may legitimately lower (§4.2). A `created_at` beside it would be a second date meaning almost the
same thing, and the first question every reader would ask is which of the two is the truth.

### 2.4 Machine type vocabulary

`backend/src/api/core/machine_type.py` (new):

```python
MachineType = Literal[
    "router", "computer", "camera", "storage",
    "tv", "phone", "printer", "sensor", "unknown",
]
```

Wire values are lower-case, matching `Severity`. `tv` renders as `TV`; that mapping is
`DESIGN.md`'s, not the API's.

`classify_machine_type(vendor: str, services: Sequence[tuple[int, str]]) -> MachineType` takes the
vendor string as nmap reported it and the `(port, service_name)` pairs of the machine's **open**
ports. It is a pure function with no I/O and no data file — `network_discovery.py:41` already reads
`vendor` out of nmap's XML, which has done the hardware-address lookup.

Resolution order, first match wins:

1. **Service signals**, tested in this fixed priority so the result is deterministic when two
   match: `camera`, `printer`, `storage`, `router`, `tv`, `sensor`, `computer`.

   | Type | Signal (open port, or service name containing) |
   |---|---|
   | camera | `554` / `rtsp`, `onvif`, `8554` |
   | printer | `631` / `ipp`, `9100` / `jetdirect`, `printer` |
   | storage | `2049` / `nfs`, `548` / `afp`, `3260` / `iscsi` |
   | router | `53` / `domain` **and** any of `80`, `443`, `8080`; or `1900` / `upnp` **and** `53` / `domain` |
   | tv | `8008`, `8009`, `7000` / `airplay`, `dial` |
   | sensor | `1883` / `mqtt`, `5683` / `coap` |
   | computer | `22` / `ssh`, `445` / `microsoft-ds`, `3389` / `ms-wbt-server`, `5900` / `vnc` |

2. **Vendor signals** (case-insensitive substring of `vendor`):

   | Type | Vendor contains |
   |---|---|
   | camera | `hikvision`, `dahua`, `axis communications`, `reolink`, `amcrest` |
   | router | `mikrotik`, `tp-link`, `netgear`, `d-link`, `zyxel`, `technicolor`, `sagemcom`, `arris`, `ubiquiti`, `cisco`, `asustek` |
   | printer | `brother`, `canon`, `epson`, `lexmark`, `xerox`, `kyocera`, `ricoh` |
   | storage | `synology`, `qnap`, `buffalo`, `western digital` |
   | tv | `roku`, `vizio`, `sony visual`, `lg electronics` |
   | phone | `apple`, `oneplus`, `xiaomi`, `motorola` — **only** when no service signal matched |
   | sensor | `espressif`, `tuya`, `shelly`, `sonoff` |

3. Otherwise `unknown`. `vendor == "unknown"` (the agent's own fallback,
   `network_discovery.py:31`) matches nothing.

Every cell reads *port number* **or** *service name containing that string*. Both clauses of the
router row therefore use the one DNS signal — port `53` or a service named `domain` — and neither
clause means the bare port alone. (Disambiguated 2026-09-07; the row previously wrote the second
clause as "with `53`", which read as port-only.)

Ambiguous vendors (Samsung, LG, Apple) are resolved by their services or not at all; guessing is
what TRUTH forbids.

### 2.5 Constants

| Constant | Where | Value |
|---|---|---|
| `QUIET_AFTER_DAYS` | `backend/src/api/services/read.py` | `7` |
| `MachineType`, the two signal tables | `backend/src/api/core/machine_type.py` | §2.4 |

The 7 days is fixed server-side. It is not a query parameter, not a setting, and the frontend no
longer owns a copy of it (§8.3 deletes the client-side 14-day constant).

---

## 3. The Alembic migration

`backend/alembic/versions/20260907_20_machine_inventory_depth.py`
(`revision = "20260907_20"`, `down_revision = "20260905_19"`).

`upgrade()`:

1. `op.add_column("hosts", sa.Column("machine_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True))`
2. `op.add_column("hosts", sa.Column("vulnerability_count", sa.Integer(), nullable=False, server_default="0"))`
3. `op.create_check_constraint("ck_hosts_machine_type", "hosts", "machine_type IS NULL OR machine_type IN (...)")` — **the nine values spelled out literally in the revision, not imported from `MACHINE_TYPES`.** Corrected 2026-09-07: the earlier wording said "built from `MACHINE_TYPES` the same way `_FINDING_SEVERITY_CHECK` is", which conflated two different places. `_FINDING_SEVERITY_CHECK` is a *model-level* constraint on the live domain and may derive; a *revision* may not. `20260727_12_finding_severity_domain.py` states the rule in its own comment — "a revision is a frozen historical snapshot, so its SQL must not shift when the live domain is edited" — and inlines its four severities. Importing `MACHINE_TYPES` here would mean that editing `core/machine_type.py` silently changes what this shipped migration emits on a fresh database, while every already-migrated database keeps the old constraint: two databases, same revision, different schema. Follow the precedent — inline the values, and let `tests/test_machine_inventory_migration.py` carry the agreement assertion (§11.1), the way `test_finding_severity_migration.py` does for severity.
4. `op.create_index("ix_hosts_org_id_last_seen_at", "hosts", ["org_id", "last_seen_at"])`
5. `op.create_index("ix_hosts_org_id_vulnerability_count", "hosts", ["org_id", "vulnerability_count"])`
6. `create_table("host_ports", ...)` + `ix_host_ports_host_id` + `uq_host_ports_host_port_protocol`
7. `create_table("host_findings", ...)` + `ix_host_findings_host_id` + `ix_host_findings_dedupe_key` + `uq_host_findings_host_dedupe_key` + index `ix_host_findings_host_id_fixed_at` on `(host_id, fixed_at)`. `ix_host_findings_dedupe_key` was missing from this list until 2026-09-07: §2.3 marks `dedupe_key` indexed and the model declares `Field(index=True)`, so without it `alembic revision --autogenerate` proposes it on every run.
8. For both new tables, the security fence copied verbatim from
   `20260905_19_home_activity_feed.py`: `ENABLE ROW LEVEL SECURITY`, revoke all from `anon` and
   `authenticated` (table **and** `_id_seq`), then
   `GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.<t> TO dmitri_runtime` and
   `GRANT USAGE, SELECT ON SEQUENCE public.<t>_id_seq TO dmitri_runtime`.
   `UPDATE` is required (`last_seen_at`, `fixed_at` are rewritten every scan); `DELETE` is required
   for the host cascade to stay possible and for the downgrade.

`downgrade()`: revoke the runtime grants, drop the two tables, drop the two indexes and the check
constraint, drop the two columns. `test_live_migration_round_trip_and_security` runs the round trip.

**No backfill, and this is the whole of it.** No `UPDATE` statement runs. Every existing machine
keeps `machine_type NULL` and `vulnerability_count 0`; `host_ports` and `host_findings` are created
empty. The next scan is the first thing that writes a date into them. This is the direct
implementation of TRUTH's "Nothing is stamped retroactively" row.

---

## 4. The ingest reconcile step

New module `backend/src/api/services/inventory.py`. It is its own module, not an addition to
`services/hosts.py`: `hosts.py` resolves *identity* (which machine is this?), reconcile resolves
*life* (what does this machine have now?), and the enrichment worker must import the second without
importing the first.

### 4.1 Public functions

```python
def reconcile_scan_inventory(session: Session, scan_record: ScanRecord) -> None
def reconcile_scan_host_inventory(session: Session, scan_host: ScanHostRecord) -> None
```

`reconcile_scan_inventory` loads every `ScanHostRecord` of the scan and calls the per-machine body
for each. `reconcile_scan_host_inventory` loads the scan and the host for one `scan_hosts` row and
calls the same body — it exists for the enrichment worker (§4.4). Neither commits; the caller owns
the transaction.

### 4.2 The per-machine body

Given `host`, `scan_record`, `scan_host`, with `ts = scan_record.timestamp`:

1. `is_latest = ts >= host.last_seen_at`. After `upsert_hosts_for_scan` this is true for every
   machine in the scan; it is false only for a late-arriving older scan.
2. **Ports.** Read the scan's `PortRecord`s for `scan_host.id` with `state == "open"`, and their
   `ServiceRecord`. For each, upsert `host_ports` on `(host_id, port, protocol)`:
   - insert → `first_seen_at = last_seen_at = ts`, service/version from the scan;
   - existing → `first_seen_at = min(first_seen_at, ts)`; and if `is_latest`,
     `last_seen_at = ts` plus service/version refreshed.
   Ports the machine has that this scan did not see open are **left alone** — their `last_seen_at`
   stays where it was, which is exactly how a closed service is told apart from an open one.
3. **Findings.** `seen = {f.dedupe_key for f in findings where scan_id == scan.scan_id and scan_host_id == scan_host.id}`.
   For each key, upsert `host_findings` on `(host_id, dedupe_key)`:
   - insert → `first_seen_at = last_seen_at = ts`, `fixed_at = None`;
   - existing → `first_seen_at = min(first_seen_at, ts)`; and if `is_latest`, `last_seen_at = ts`
     and `fixed_at = None` (a problem that came back is open again).
   `first_seen_at` is never raised — "finding the same problem again never changes when it first
   appeared".
4. **Fixed.** If `is_latest`: every `host_findings` row of this machine with `fixed_at IS NULL`
   whose `dedupe_key` is not in `seen` gets `fixed_at = ts`.
5. **Type.** If `is_latest`: `host.machine_type = classify_machine_type(scan_host.vendor, open_services)`
   where `open_services` are the `(port, service_name)` pairs from step 2.
6. **Count.** If `is_latest`: `host.vulnerability_count` = the machine's `host_findings` rows with `fixed_at is null`.

**Query shape.** Revised 2026-09-12 after the PR #143 review. The body loads the machine's
`host_ports` and its `host_findings` once each, keys them by `(port, protocol)` and `dedupe_key`,
applies steps 2–6 in memory, and flushes once. Steps 4 and 6 read the same loaded rows, so there
is no per-port or per-finding `SELECT` and no `COUNT` query. The enrichment worker runs this body
after every CPE job (§4.4), so its query count must not grow with a machine's ports or findings —
`tests/test_inventory_reconcile.py` asserts that.

Steps 4–6 are skipped entirely when `is_latest` is false, so an out-of-order older scan can lower a
`first_seen_at` — which is true — but can never stamp a `fixed_at`, retype a machine, or rewrite the
count from stale evidence.

**Two consequences of that, intended and recorded 2026-09-07 so neither is later read as a bug.**

*An older scan carrying a problem never seen before inserts an open `host_findings` row that
`vulnerability_count` does not yet include*, because step 6 is skipped with the rest. The row is
correct — the problem did first appear then — and the count corrects itself on the next latest scan.
The alternative is worse: recounting from an older scan's evidence would let a stale scan overwrite
a fresh number, which is the exact failure the guard exists to prevent. A momentarily low count that
converges beats a wrong one that persists.

*`machine_type` therefore holds two values that both read as unknown.* `NULL` means **never
classified** — no scan has looked at this machine since the migration (§3 writes no backfill).
The literal `"unknown"` means **classified, and nothing matched**. Step 5 stores whatever
`classify_machine_type` returns, and that function returns `"unknown"` rather than `None`. Both map
to the same wire value in `_to_host_summary` (§5.4), so the owner never sees the difference, and
§2.1's check constraint admits both by design. Keep it that way: collapsing them would throw away
the only signal that distinguishes a machine we could not identify from one we have not yet looked
at, and that distinction is what the security screen will need later.

Findings with no `scan_host_id` (host-less/global findings, `services/persistence.py:129`) belong to
no machine and get no `host_findings` row.

### 4.3 Every ingest call path that must run it

Grepped: `grep -rn --include="*.py" "persist_scan\|ingest_scan\|upsert_hosts_for_scan\|upsert_finding" backend/src`.

| Call site | Ref | Action |
|---|---|---|
| `persist_scan()` | `backend/src/api/services/persistence.py:81` | **Add** `reconcile_scan_inventory(session, scan_record)` immediately after `upsert_hosts_for_scan(...)` (`persistence.py:149`) and before `append_scan_activity`. Same transaction, so the case-A/case-C rollback tests still hold. |
| `ingest_scan()` | `services/persistence.py:36` | No change — it delegates to `persist_scan` for both the new-scan and the placeholder path, and returns early for an already-completed scan (nothing new was seen). |
| `POST /api/v1/scans` → `ingest_scan_route` | `backend/src/api/routers/scans.py:38` | No change. It is the only production ingest entry point. |
| `_process_cpe_job()` | `backend/src/api/services/enrichment.py:114` | **Add** `reconcile_scan_host_inventory(session, device)` before its `session.commit()` (§4.4). |
| `_process_cve_job` / `_process_kev_job` / `_process_epss_job` | `services/enrichment.py` | No change — they mutate an existing finding's severity/score, never create or delete one, so no count and no life changes. |

### 4.4 Why the enrichment worker calls reconcile too

`_process_cpe_job` calls `upsert_finding` (`enrichment.py:153`) and **creates new `findings` rows for
an already-committed scan**. Without a second reconcile, an NVD-matched CVE would never get a
`first_seen_at` and would never be counted, and the machine's `vulnerability_count` would silently
disagree with its findings list. It calls `reconcile_scan_host_inventory(session, device)` once, at
the end of the job, before the existing `session.commit()`. The `is_latest` guard means a job for an
older scan changes nothing but a `first_seen_at`.

This is not a stopgap: it is the same single reconcile mechanism, invoked wherever findings are
written. There is exactly one implementation.

---

## 5. Read path

### 5.1 `HostSortBy` gains `vulnerability_count`

`_HOST_SORT_COLUMNS` (`backend/src/api/services/read.py:49`) gains
`"vulnerability_count": HostRecord.vulnerability_count`. Because the count is a denormalised
indexed column, `sort_by=vulnerability_count` is a plain `ORDER BY` over the whole org — no
per-row finding count, no correlated subquery, and the first row on page 1 is the worst machine on
the network, not on the page (TRUTH's sorting criterion).

`machine_type` is deliberately **not** added to `HostSortBy`. TRUTH asks for one new sort. If
`DESIGN.md` makes the Type column sortable, adding the literal and the map entry is a two-line
follow-up on this same table.

### 5.2 `list_hosts()` — the server-side quiet split

`backend/src/api/services/read.py:59`. New keyword `group: HostGroup = "active"`.

```python
QUIET_AFTER_DAYS = 7
cutoff = utc_now() - timedelta(days=QUIET_AFTER_DAYS)
active_pred = HostRecord.last_seen_at >= cutoff
quiet_pred  = HostRecord.last_seen_at <  cutoff
```

- `total` counts the **requested group** (so `Pagination` pages that group correctly).
- `quiet_total` counts quiet machines across the whole org, on every response, for both groups. It
  is the number the group header shows, and it is a whole-inventory number by construction — this
  is what closes 042 §17 Q2.
- The rows returned are the requested group only, ordered and paged as today.

`GET /api/v1/hosts?group=quiet&page=2` therefore pages the quiet group on its own without touching
the active list.

**The one mechanism choice I had to make.** The owner fixed the *threshold* as "not a query
parameter"; the group still needs a selector, since the quiet list "is fetched separately". I chose
a `group` enum query parameter on the existing endpoint over a second route, because
`GET /api/v1/hosts/quiet` would collide with `GET /api/v1/hosts/{host_id}` (a `UUID` path converter
rejects `quiet` with a 422 unless route order is relied on) and would duplicate the sort/page
plumbing. The threshold itself remains uncontrollable from the wire.

### 5.3 `get_host_detail()` — machine-level services

`read.py:89`. `ports` no longer come from the latest `scan_hosts` row. They come from `host_ports`
for this `host_id`, ordered by `port`, each carrying `first_seen_at` and `last_seen_at`. The
`latest_scan_host` lookup is kept only where `scan_history` still needs it.

`HostDetailResponse` also gains `machine_type` and `vulnerability_count`.

### 5.4 `_to_finding_read()` — the hostname and the three dates

`read.py:382`. Signature becomes:

```python
def _to_finding_read(
    finding: FindingRecord,
    host_id: UUID | None,
    hostname: str | None,
    life: HostFindingRecord | None,
) -> FindingRead
```

- `host_hostname = hostname` — resolved **on read** through
  `findings.scan_host_id → scan_hosts.host_id → hosts.hostname`, so it is the machine's *current*
  name and a rename is reflected the moment it lands (TRUTH's "Renaming a machine" criterion).
  `scan_hosts.hostname` is the at-scan-time snapshot and is **not** used here.
- `first_seen_at`, `last_seen_at`, `fixed_at` come from `life`, and are `None` when there is no
  `host_findings` row (a host-less finding, or a finding from before this feature).
- `detected_at` keeps its current meaning (this scan's `created_at`) and is untouched.

Revised 2026-09-12 after the PR #143 review: no caller builds these joins or calls
`_to_finding_read` itself. `read.py` exposes two public functions:

- `finding_read_query()` — the select of `FindingRecord`, `ScanHostRecord.host_id`,
  `HostRecord.hostname` and `HostFindingRecord`, with `scan_hosts`, `hosts` and `host_findings`
  already outer-joined.
- `to_finding_reads(rows)` — maps those rows to `FindingRead` by name, not by tuple position.

Callers add only their own filters, joins, sort and paging.

| Caller | Ref |
|---|---|
| `list_findings()` | `read.py` — `base` starts from `finding_read_query()`; the `host_id` filter is `WHERE scan_hosts.host_id = :id` over the outer join, which returns the same rows as the old inner join. The `func.count()` over `base.subquery()` still works because the joins are outer and add no rows. |
| `get_scan_detail()` | `read.py:170` |
| `home.page_attention()` | `backend/src/api/services/home.py` — starts from `read.finding_read_query()` and adds only the attention filters and sort. It imports no `HostFindingRecord` and no private `read` helper. This is what gives Home the machine's name (user story 4) with no new request. |

`_to_host_summary()` (`read.py:368`) gains `machine_type=host.machine_type or "unknown"` and
`vulnerability_count=host.vulnerability_count`.

### 5.5 `routers/hosts.py`

`read_hosts` (`backend/src/api/routers/hosts.py:27`) gains
`group: HostGroup = Query("active")` and passes it through. Nothing else in the router changes;
`read_host` is untouched.

---

## 6. Response schemas — `backend/src/api/schemas/read.py`

| Symbol | Change |
|---|---|
| `MachineType` | **New** re-export from `api.core.machine_type` (the schema module is where the wire vocabulary is read from). |
| `HostGroup` | **New** — `Literal["active", "quiet"]`. |
| `HostSortBy` | `Literal["last_seen_at", "hostname", "vendor", "ip", "vulnerability_count"]`. |
| `HostSummary` | **+** `machine_type: MachineType`, **+** `vulnerability_count: Annotated[int, Field(ge=0)]`. `vendor` and `open_ports_count` stay. |
| `HostDetailResponse` | **+** the same two fields; `ports: list[HostPort]` (was `list[Port]`). |
| `HostPort` | **New** — `port`, `protocol`, `service`, `version`, `first_seen_at`, `last_seen_at`. No `state`: `host_ports` only ever holds ports observed open. |
| `Port` | **Unchanged.** It stays the per-scan evidence shape used by `ScanHostView`. Adding nullable dates to it would make one schema mean two things; a separate `HostPort` keeps both non-nullable and honest. |
| `FindingRead` | **+** `host_hostname: str \| None`, **+** `first_seen_at: datetime \| None`, **+** `last_seen_at: datetime \| None`, **+** `fixed_at: datetime \| None`. No field is removed. |
| `HostListResponse` | **+** `quiet_total: Annotated[int, Field(ge=0)]`. |
| `HostScanHistoryEntry` | Unchanged. |

Every model keeps `extra="forbid"`. All changes are additive except `HostDetailResponse.ports`,
whose item type widens by two fields — no consumer loses anything.

---

## 7. `contracts/openapi/openapi.yaml`

Edit the contract **by hand first**, then regenerate the frontend types. `test_contract_fidelity.py`
compares `app.openapi()` against this file schema-by-schema (`SCHEMA_NAMES`, line 33) and
parameter-by-parameter for `/api/v1/hosts` (`OPERATION_PATHS`, line 67), so a missed edit fails the
backend suite rather than shipping drift.

| Node | Change |
|---|---|
| `components/schemas/MachineType` | **New** — `type: string`, `enum: [router, computer, camera, storage, tv, phone, printer, sensor, unknown]`. |
| `components/schemas/HostPort` | **New** — mirrors §6, all six properties required except `version`. |
| `components/schemas/HostSummary` | `+ machine_type` (`$ref` MachineType, required), `+ vulnerability_count` (integer, minimum 0, required). |
| `components/schemas/HostDetailResponse` | Same two, plus `ports.items` → `$ref: HostPort`. |
| `components/schemas/HostListResponse` | `+ quiet_total` (integer, minimum 0, required). |
| `components/schemas/FindingRecord` | `+ host_hostname`, `+ first_seen_at`, `+ last_seen_at`, `+ fixed_at`, each `anyOf: [<type>, 'null']`, none required. (`FindingRecord` is this contract's name for `FindingRead`.) |
| `components/parameters/HostSortBy` | `+ vulnerability_count` to the enum. |
| `components/parameters/HostGroup` | **New** — `name: group`, `in: query`, `required: false`, `enum: [active, quiet]`, `default: active`. |
| `paths./api/v1/hosts.get.parameters` | `+ $ref: '#/components/parameters/HostGroup'`. |
| `paths./api/v1/hosts.get.description` | Say that the default page returns active machines and `quiet_total` counts the whole inventory. |

The unimplemented `q` parameter (contract line 294, `UNIMPLEMENTED_PARAMS` in
`tests/test_contract_fidelity.py:71`) is pre-existing drift from DMI-100 and stays out of scope —
do not remove it and do not implement it.

Then, in `frontend/`: `npm run gen:types`
(`openapi-typescript ../contracts/openapi/openapi.yaml -o src/types/openapi.d.ts`).
`src/types/openapi.d.ts` is **generated output** — regenerate it, never hand-edit it, and commit the
regenerated file in the same change as the YAML.

---

## 8. Frontend data layer — `frontend/src/`

`DESIGN.md` owns the columns, copy, and the quiet group's interaction. This section owns the types
and the queries under them.

### 8.1 `src/api/hosts.ts`

- `HostListParams` gains `group`: `Required<Pick<ListHostsQuery, 'page' | 'per_page' | 'sort_by' | 'sort_order' | 'group'>>`.
- `export type HostGroup = NonNullable<ListHostsQuery['group']>`.
- `HOST_SORT_DEFAULT_ORDER` gains `vulnerability_count: 'desc'` — a machine's *worst* is what you
  want first.
- `listHosts` is unchanged; `group` rides in `params`.

`src/api/queryKeys.ts` needs **no change**: `queryKeys.hosts.list(params)` already keys on the whole
params object, so the active and quiet queries get distinct cache entries automatically.

### 8.2 `src/pages/Network.tsx`

Two queries against one endpoint: the active page (`group: 'active'`, its own `page` state) in
`Network.tsx`, and the quiet page (`group: 'quiet'`) in `pages/hosts/QuietMachineGroup.tsx`, which
mounts only while the group is open. `Network.tsx` keeps the group's open state and its page number;
the page lives there because the table remounts the group whenever the active list loads. The
group header's count is `query.data.quiet_total` from the **active** response — a whole-inventory
number, not a page's. `Pagination` for each group uses that group's own `total`.

### 8.3 `src/lib/hostLastSeen.ts`

`QUIET_AFTER_MS` (14 days), `isQuietHost` and `partitionQuietHosts` are **deleted** — the split is
now the server's and the threshold is 7 days there. They are orphaned by this change and by nothing
else (`grep -rn "partitionQuietHosts\|isQuietHost" frontend/src` → `Network.tsx:17,94,112` and
`hostListColumns.tsx:5,11`, both rewritten here). `weeksSinceLastSeen` stays, used by the quiet
row's "Not seen for N weeks" line.

**§8.3 undercounted the callers.** `src/pages/hosts/HostIdentity.tsx` also imports `isQuietHost`;
found 2026-09-08 when the functions were deleted. It cannot simply lose the call — `DESIGN.md`
§3.2 and §3.6 require the quiet variant of the third identity line on a machine's own page
(`First seen {time} · not seen for {n} weeks`). **Owner's decision, 2026-09-08: derive it as
`weeksSinceLastSeen(...) >= 1`.** Seven days is exactly one week, so this needs no contract field
and no second constant, and it reuses the function that already renders the copy. The caveat,
recorded so it is not a surprise: the threshold is now expressed in two units — `QUIET_AFTER_DAYS = 7`
server-side for the list's split, and one week client-side for this one line. They agree today and
TRUTH fixes the threshold at 7 days with "make it an owner setting" explicitly out of scope, so
there is nothing to keep in sync yet. **If the threshold ever moves off 7 days, this line is the
thing that silently disagrees** — the fix at that point is `quiet` on `HostDetailResponse`, not a
client constant. `HostIdentity.tsx` belongs to Task 10, with `HostDetail.tsx`. `hostListColumns(now)` becomes `hostListColumns(now, quiet)` —
the caller knows which group it is rendering, so no row has to work it out from a date.

### 8.4 Other touched modules

| File | Change |
|---|---|
| `src/pages/hosts/hostListColumns.tsx` | Type column replaces Vendor; vulnerability-count column replaces Services; every column left-aligned (042 §6.1 override), numbers keep `tabular-nums`. Exact rendering is `DESIGN.md`'s. |
| `src/pages/hosts/portColumns.tsx` | Retyped to `components['schemas']['HostPort']`; gains a last-seen column so a closed service reads as closed. |
| `src/pages/hosts/HostPortsTable.tsx` | Same retype. |
| `src/pages/HostDetail.tsx` | Renders `machine_type`, keeps `vendor` and `open_ports_count` — TRUTH keeps both, on this page. |
| `src/pages/home/AttentionTable.tsx` | Machine column shows `finding.host_hostname ?? finding.host_ip`, falls back to `EmptyMark` when both are absent; the row's aria label follows. |
| `src/pages/scans/findingColumns.tsx` | `hostFindingColumns()` and `scanFindingColumns()` show the finding's `first_seen_at` ("is this new?"); `machineLabel()` is `finding.host_hostname || finding.host_ip` — the machine's current name, then the address (revised 2026-09-12: the `ScanHostView` snapshot fallback is gone, so a machine has one name across the app). Column set and copy are `DESIGN.md`'s. `FindingsTable.tsx` loses its `hosts` prop, which only fed that fallback. |
| `src/test/mswHandlers.ts` | `hostFixtures` gain `machine_type` and `vulnerability_count`; the `/hosts` handler implements the `group` split and returns `quiet_total`; finding fixtures gain the four new fields. |

No new Axios instance, no new query key namespace, no new provider.

---

## 9. `hardware-agent/` — not affected, with the evidence

Per `.claude/CLAUDE.md`'s integration rule, I grepped every constructor and call site of the
classes this feature could plausibly reach:

- `grep -rn "ScanRunner(" hardware-agent/src` → `hardware-agent/src/agent/headless.py:92` and
  `hardware-agent/src/agent/tui/screens/scan_progress.py:136`. Both are the two known call sites.
- `ScanRunner.__init__` (`hardware-agent/src/agent/scanner/runner.py:32`) takes
  `subnet, scan_mode, reporter, on_complete, on_error, workspace_root, runner`. **This feature adds
  no orchestrator or runner parameter**, so neither `ScanRunner` nor `ScanProgressScreen`
  (`tui/screens/scan_progress.py`) nor `headless.py` changes. The rule is satisfied vacuously, and
  the reason it is vacuous is that the feature adds nothing to the agent's call chain.
- `hardware-agent/src/agent/normalize/contracts.py:30` already carries `vendor` on the host payload,
  and `discovery/network_discovery.py:41` already reads it from nmap's `<address addrtype="mac"
  vendor=...>`. Machine type is classified **backend-side at ingest** from that string plus the open
  services the payload already carries. No OUI data file, no new nmap flag, no new NSE script.
- `ScanPayload` and every model under `hardware-agent/src/agent/normalize/` are unchanged, so
  `contracts/examples/` ingest fixtures are unchanged too.

Nothing in `hardware-agent/` is touched by this feature. That is also why there is no
`INTEGRATION.md`.

---

## 10. New files and naming (mandatory)

| Path | New / Changed | What |
|---|---|---|
| `backend/src/api/core/machine_type.py` | **New** | `MachineType`, `MACHINE_TYPES`, the two signal tables, `classify_machine_type()`. |
| `backend/src/api/services/inventory.py` | **New** | `reconcile_scan_inventory()`, `reconcile_scan_host_inventory()`, the per-machine body. |
| `backend/src/api/models/persistence.py` | Changed | `HostRecord` **+** `machine_type`, `vulnerability_count`; **new** `HostPortRecord`, `HostFindingRecord`. |
| `backend/alembic/versions/20260907_20_machine_inventory_depth.py` | **New** | §3. No backfill. |
| `backend/src/api/services/persistence.py` | Changed | One call to `reconcile_scan_inventory` in `persist_scan` (after line 149). |
| `backend/src/api/services/enrichment.py` | Changed | One call to `reconcile_scan_host_inventory` at the end of `_process_cpe_job`. |
| `backend/src/api/services/read.py` | Changed | `QUIET_AFTER_DAYS`; `group` in `list_hosts` + `quiet_total`; `vulnerability_count` sort column; `get_host_detail` reads `host_ports`; `_to_host_summary` and `_to_finding_read` widened; joins in `list_findings` and `get_scan_detail`. |
| `backend/src/api/services/home.py` | Changed | `page_attention`'s query gains the hostname/life joins and the new `_to_finding_read` arguments. |
| `backend/src/api/services/hosts.py` | **Unchanged** | Identity resolution is not part of this feature. |
| `backend/src/api/routers/hosts.py` | Changed | `group` query parameter on `read_hosts`. |
| `backend/src/api/schemas/read.py` | Changed | §6. |
| `contracts/openapi/openapi.yaml` | Changed | §7. |
| `frontend/src/types/openapi.d.ts` | Regenerated | `npm run gen:types`. Never hand-edited. |
| `frontend/src/api/hosts.ts` | Changed | `group` in params, `HostGroup`, sort default for the count. |
| `frontend/src/lib/hostLastSeen.ts` | Changed | 14-day constant, `isQuietHost`, `partitionQuietHosts` deleted; `weeksSinceLastSeen` kept. |
| `frontend/src/pages/Network.tsx` | Changed | Two grouped queries, `quiet_total` header, per-group pagination. |
| `frontend/src/pages/hosts/hostListColumns.tsx` | Changed | Type and vulnerability-count columns; left alignment. |
| `frontend/src/pages/hosts/portColumns.tsx` | Changed | `HostPort` type, last-seen column. |
| `frontend/src/pages/hosts/HostPortsTable.tsx` | Changed | `HostPort` type. |
| `frontend/src/pages/HostDetail.tsx` | Changed | Machine type on the machine's own page. |
| `frontend/src/pages/home/AttentionTable.tsx` | Changed | Name, then address. |
| `frontend/src/pages/scans/findingColumns.tsx` | Changed | First-seen column; `machineLabel` prefers `host_hostname`. |
| `frontend/src/test/mswHandlers.ts` | Changed | Fixtures + the `group` split handler. |
| `backend/tests/test_machine_type.py` | **New** | §11. |
| `backend/tests/test_inventory_reconcile.py` | **New** | §11. |
| `backend/tests/test_machine_inventory_migration.py` | **New** | §11. |
| `backend/tests/read_factories.py` | Changed | Host factories carry the two new columns. |
| `frontend/src/pages/Network.quiet.test.tsx` | **New** | §11. |

No path outside this table is created by this feature, **with these four corrections made
2026-09-08 during implementation** — §10 was written without reconciling against `DESIGN.md` §6.1
and §6.2, which name frontend files this table omitted:

| Path | New / Changed | Why the table missed it |
|---|---|---|
| `frontend/src/lib/machineType.ts` | **New** | `MACHINE_TYPE_LABELS`, the nine-value map with `unknown: null`. `DESIGN.md` §6.1 names it. Shared, not inlined: Task 9's list and Task 10's `HostIdentity` need the same labels, and two copies of a nine-value vocabulary is how the two drift. |
| `frontend/src/components/DataTable.tsx` | Changed | `DESIGN.md` §6.2 requires it. Unavoidable: the component owned the group's open state internally (so `Network` could not gate the quiet query's `enabled`) and **derived the group's count from `rows.length`** — the page-local count this feature exists to delete. |
| `frontend/src/components/ListSurface.tsx` | Changed | `DESIGN.md` §6.2 requires it. `partitionRows` gives way to a `collapsedGroup` slot plus `emptyRow`, so the blank state yields to a non-empty group (the **All quiet** state, §2.5). |
| `frontend/src/components/LoadingSkeleton.tsx` | Changed | Optional `id` / `testId` so the group's own skeleton can carry `aria-controls`' target and `network-quiet-loading` (§2.4). |

`frontend/src/pages/hosts/QuietMachineGroup.tsx`, which `DESIGN.md` §6.1 names, **is created**.
Revised 2026-09-12 after the PR #143 review: keeping the quiet read in `Network.tsx` pushed a
second async table protocol (`isPending`, `error`, `footer`, `columns`) into `DataTable`'s group.
The group now owns its query, skeleton, error row and pager, and `DataTable`'s group only hosts
that content (`DESIGN.md` §6.2).

---

## 11. Testing expectations

### 11.1 `backend/`

Gate, in this order: **`./database.sh --test`**, then `uv run ruff check src tests`.
**Never `ruff format`** — `backend/` is hand-formatted (`.claude/CLAUDE.md`). A run with a non-zero
skip count is not a green run: without a live `dmitri_test` the DB-backed tests are skipped, and
this feature is almost entirely DB-backed.

| New/changed test file | Mirrors | Must assert |
|---|---|---|
| `tests/test_machine_type.py` | `tests/test_error_codes.py` (pure-function table tests) | Hikvision + rtsp → `camera`; a vendor nothing matches with no service signal → `unknown`; the returned value is always in the nine; `vendor="unknown"` matches nothing; service signals beat vendor signals. |
| `tests/test_inventory_reconcile.py` | `tests/test_hosts_service.py` (two `ingest_scan` calls over one identity) | First-seen set once and unchanged on re-detection; a problem absent from the latest scan gets `fixed_at` and leaves the count; a problem that comes back clears `fixed_at`; a service absent from the latest scan keeps its older `last_seen_at`; `vulnerability_count` equals the open rows; an out-of-order older scan stamps no `fixed_at` and does not rewrite the count. |
| `tests/test_read_hosts.py` | itself | 45 hosts / 6 quiet / 20 per page → page 1 returns 20 active rows and `quiet_total == 6`; `group=quiet` pages its own rows without changing the active list; 8-days-ago is quiet and 6-days-ago is not; `sort_by=vulnerability_count&sort_order=desc` puts the network's worst machine first on page 1 across three pages. |
| `tests/test_read_findings.py` | itself | `host_hostname` is the machine's **current** name after a rename; a finding whose machine cannot be identified returns `host_hostname: null` and keeps `host_ip`; `first_seen_at` is present after reconcile and `null` before it. |
| `tests/test_home_snapshot.py` | itself | The attention page's rows carry `host_hostname`. |
| `tests/test_ingest_scan.py` | itself | `persist_scan` writes `host_ports` / `host_findings` / `machine_type` / `vulnerability_count` in the same transaction, and the existing case-A and case-C rollback tests still leave nothing behind. |
| `tests/test_machine_inventory_migration.py` | `tests/test_agents_target_subnet_migration.py`, plus `tests/test_finding_severity_migration.py` for the agreement assertion | Upgrade over a database holding a host **leaves `machine_type` NULL** and creates the two tables empty; downgrade drops them; the runtime grants exist and `anon`/`authenticated` hold none; and the revision's inlined nine values still agree with `MACHINE_TYPES` (§3 step 3) — the guard that lets the migration stay frozen without drifting from the live vocabulary unnoticed. |
| `tests/test_contract_fidelity.py` | itself | Passes unchanged — it is the gate that proves §6 and §7 agree. |
| `tests/test_read_schema.py` | itself | The new fields' bounds (`vulnerability_count >= 0`, `quiet_total >= 0`, `machine_type` closed). |

An enrichment test in `tests/` covering `_process_cpe_job` must also assert that a CVE the worker
adds after ingest lands in `host_findings` and is counted.

### 11.2 `frontend/`

Gate: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

| Test | Mirrors | Must assert |
|---|---|---|
| `src/pages/Network.quiet.test.tsx` | `src/pages/Network.test.tsx` | The group header shows `quiet_total`, not the page's quiet rows; opening the group issues a second request with `group=quiet`; paging the quiet group leaves the active table untouched. |
| `src/pages/Network.test.tsx` | itself | Type and vulnerability-count columns render; the count sorts on click and requests `sort_by=vulnerability_count`; an `unknown` type draws no guessed value. |
| `src/pages/Home.test.tsx` | itself | The attention row shows the machine's name, and its address only when there is no name. |
| `src/pages/HostDetail.test.tsx` | itself | A service last seen before the machine's `last_seen_at` reads as closed; vendor and open-port count are still on the page. |

Assert user-visible text and request parameters, not component internals. `npm run typecheck` is the
real guard on §7: if the YAML and the regenerated types disagree with the code, it fails there.

### 11.3 `hardware-agent/`

No change, so no new test. `uv run pytest` inside `hardware-agent/` must still be green after the
branch, as a regression check that nothing leaked into the agent.

---

## 12. `HUMAN_INFRA_REQUIRED`

None. No new hardware, daemon, external service, data file or credential. The migration runs
through the existing `./database.sh` path against Supabase Postgres, and the classifier is pure
Python over data the scan already returns.

---

## 13. Open items for the owner — decided (2026-09-07)

1. **`group` as a query parameter** (§5.2) — **confirmed**. `GET /api/v1/hosts?group=active|quiet`,
   default `active`. No second route: `GET /api/v1/hosts/quiet` would collide with
   `GET /api/v1/hosts/{host_id}`. The 7-day threshold stays server-fixed and off the wire.
   `DESIGN.md` §2.9 and §9/Q1 are reconciled to this name.
2. **Sorting the Type column** (§5.1) — **not sortable**. `DESIGN.md` §9/Q3 draws no sort control on
   `Type`, so `machine_type` stays out of `HostSortBy` and out of the `HostSortBy` OpenAPI enum.
   `vulnerability_count` is the only sort this feature adds.
