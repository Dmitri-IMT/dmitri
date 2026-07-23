# ARCHITECTURE — Read path: hosts, scan detail, and findings

> Implements `specs/015-read-path/TRUTH.md` to the shapes fixed in
> `contracts/openapi/openapi.yaml`. Source issue DMI-74 (expanded scope — see TRUTH header).
> **Scope locked 2026-07-22 (option B, single PR):** the read path + durable `Host` model +
> BOTH folded ingest corrections — the `scan_mode`/`status` source fix, and the ADR-013
> `devices`→`hosts` wire-vocabulary rename. This is **cross-layer**: `backend/`,
> `contracts/`, and `hardware-agent/` all change in this one PR. No `INTEGRATION.md` — the
> layers don't share a runtime boundary this feature has to design (Pi and backend already
> talk over the existing HMAC-signed `POST /api/v1/scans`; only the field names inside that
> payload change), so this stays one flat `ARCHITECTURE.md`.
>
> The CLAUDE.md TUI rule (`ScanRunner`/`ScanProgressScreen` threading) is **N/A for new
> orchestrator parameters** — this feature adds no new `ScanRunner`/`ScanOrchestrator`
> parameter. It **does** touch `hardware-agent/` for the ADR-013 contract rename, and the
> rename's blast radius reaches into `scanner/stages.py`, `scanner/runner.py`, and three TUI
> screens (`tui/screens/scan_view.py`, `tui/screens/scan_progress.py`, `tui/screens/home.py`)
> that read `payload.devices` for display — see the naming table and "Rename blast radius"
> below. `hardware-agent`'s own suite (`uv run pytest` and `uv run ruff check`, run inside
> `hardware-agent/`) must pass in addition to `backend/`'s.

## System context

Where this sits in the pipeline: `Pi ingest (POST /api/v1/scans, wire vocabulary renamed by
this feature — see ADR-013)` → `persist_scan` writes the per-scan records (`ScanRecord`,
`ScanHostRecord` — renamed from `DeviceRecord`, `PortRecord`, `FindingRecord`, …) → **this
feature adds a durable `HostRecord` projection materialised during `persist_scan`** → the
enrichment `worker` continues to enrich findings unchanged → **this feature adds four read
routers** that serve the frontend HOME / SCAN DETAIL / HOST DETAIL screens.

Today `backend/src/api/main.py` mounts exactly one route: `GET /api/v1/health`. There are no
routers and no persistent host identity — a physical machine seen in two scans is two
unrelated `DeviceRecord` rows (`UniqueConstraint(scan_id, ip)`) with no shared id and no
"first seen". This feature introduces the persistent **Host**, renames the per-scan
observation record to **ScanHost** (per `CONTEXT.md`'s glossary — "in storage this is the
record formerly named `DeviceRecord`"), and serves the read surface that exposes both.

The four endpoints built (and only these — `GET /api/v1/scans` list is out of scope per
TRUTH):

| Endpoint | operationId | Response schema | Screen |
|----------|-------------|-----------------|--------|
| `GET /api/v1/hosts` | listHosts | `HostListResponse` (`HostSummary[]`) | HOME |
| `GET /api/v1/hosts/{host_id}` | getHostById | `HostDetailResponse` | HOST DETAIL |
| `GET /api/v1/scans/{scan_id}` | getScanById | `ScanDetailResponse` | SCAN DETAIL |
| `GET /api/v1/findings` | listFindings | `FindingListResponse` | HOST DETAIL findings |

Sessions are obtained exactly as `read_health` does today: `session: Session =
Depends(get_session)` (`api.db.session.get_session`). Read routers run read-only queries in
that sync session; they never write. Host materialisation is the only write and happens
inside the existing `persist_scan` transaction on the ingest path.

## Central design decision 1 — ADR-013 wire rename: "device" retired end to end

Per [`ADR-013`](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md), the ingest
vocabulary is unified to **host** across all three layers in this one PR (no live Pi and no
mounted ingest route today, so this is a same-PR rename, not a coordinated OTA):

| Layer | Before | After |
|-------|--------|-------|
| `contracts/openapi/openapi.yaml` | `ScanIngestRequest.devices`, schema `DevicePayload`, `ScanIngestAcceptedResponse.devices_received` | `ScanIngestRequest.hosts`, schema `HostPayload`, `hosts_received` |
| `hardware-agent` contract layer | `ScanPayload.devices: list[DevicePayload]` | `ScanPayload.hosts: list[HostPayload]` |
| `backend` ingest schema | `ScanResult.devices: list[Device]` | `ScanResult.hosts: list[Host]` |

`X-Device-Id` is **not** touched anywhere (it identifies the agent/Pi, frozen by ADR-005;
unrelated word overlap per `CONTEXT.md`).

### Rename blast radius (flagged — bigger than ADR-013's text implies)

ADR-013 frames this as "a rename of one serialization boundary" because
`network_discovery.py`/`HostInfo` already speaks host internally. That is true for
*discovery*, but the **TUI display code reads the contract layer's field names directly**, so
the blast radius is larger than the contracts file alone:

- `hardware-agent/src/agent/scanner/stages.py` — `build_device_payload(host) -> DevicePayload`
  is the function that *produces* the field being renamed; both the function name and its
  return type change.
- `hardware-agent/src/agent/scanner/runner.py` — constructs `ScanPayload(devices=devices, …)`
  (line ~100) and a local variable `devices = [stages.build_device_payload(h) for h in
  hosts]`.
- `hardware-agent/src/agent/tui/screens/scan_view.py` — reads `payload.devices` three times
  (device count, iterating rows, summing ports).
- `hardware-agent/src/agent/tui/screens/scan_progress.py` — reads `payload.devices` three
  times (progress summary).
- `hardware-agent/src/agent/tui/screens/home.py` — reads `payload.devices` twice (dashboard
  tile).
- `hardware-agent/src/agent/normalize/__init__.py` — re-exports `DevicePayload` by name.
- **Nine** test files reference `DevicePayload` and/or `.devices` on `ScanPayload`:
  `tests/test_contract_models.py`, `tests/unit/test_tui_scan_view.py`,
  `tests/unit/test_headless.py`, `tests/unit/test_scan_runner_partial.py`,
  `tests/unit/test_scan_runner_cancel.py`, `tests/unit/test_scan_progress_screen.py`,
  `tests/integration/test_tui_flows.py`, plus construction-only `ScanPayload(...)` call sites
  in `tests/unit/test_workspace.py` and `tests/unit/test_quick_mode_argv.py` and
  `tests/integration/test_extensive_e2e.py` that don't reference `.devices` by name but do
  pass `devices=[...]` as a keyword argument and must be updated to `hosts=[...]`.

None of this is scanning/normalization/scoring logic (out of scope per TRUTH) — it is a
mechanical field/keyword rename repeated at every read site of the renamed field. List every
touched file explicitly in the naming table below; do not assume `contracts.py` alone covers
it.

`headless.py` and `scanner/workspace.py` import `ScanPayload` as a type only and do not
reference `.devices` — no change needed beyond the import still resolving (it does; only the
field inside the model changes, not the model's name).

## Central design decision 2 — durable host identity

### (a) New `hosts` table + a `host_id` FK on the renamed `scan_hosts` table

A new `HostRecord` (table `hosts`) holds the durable identity. Each per-scan `ScanHostRecord`
(table `scan_hosts`, renamed from `devices`/`DeviceRecord` — see decision 3) gains a nullable
`host_id` FK pointing at the host it resolved to. That single column is the join that makes
scan-detail `host_id`, host scan-history, and `?host_id=` findings all work off one
identifier.

`hosts` columns:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK (`default_factory=uuid4`) | **this is the contract `host_id`** — stable, URL-safe |
| `org_id` | UUID \| None, FK `orgs.id`, indexed | mirrors `ScanRecord.org_id` nullability (auth epic populates it) |
| `identity_key` | str, indexed | resolution key (see below) |
| `ip` | str | latest observation |
| `mac` | str \| None | latest observation |
| `hostname` | str | latest observation |
| `vendor` | str | latest observation |
| `open_ports_count` | int | latest observation (denormalised for list speed) |
| `highest_severity` | str \| None | latest observation's max finding severity |
| `first_seen_at` | datetime | earliest observing scan's `timestamp`; never increases |
| `last_seen_at` | datetime | most recent observing scan's `timestamp` |
| `created_at` / `updated_at` | datetime | `default_factory=utc_now` |

Uniqueness: `UniqueConstraint("org_id", "identity_key")` with
`postgresql_nulls_not_distinct=True` so the transitional NULL `org_id` (ingest does not set it
yet) still collapses same-identity rows instead of Postgres treating each NULL as distinct.
This is the org-scoped identity guarantee from
[`ADR-014`](../../docs/adr/ADR-014-host-identity-resolution.md).

**`identity_key`** = `f"mac:{mac.upper()}"` when the observation has a MAC, else `f"ip:{ip}"`
(ADR-014, adopted as-is — resolved, see Open questions). The `mac:` / `ip:` prefix prevents a
MAC value from ever colliding with an IP value in the same key column.

### (b) Materialise at ingest, not on read (ADR-014, resolved)

`persist_scan` upserts hosts in the same transaction that writes the scan-hosts. Reasoning:

- `first_seen_at` "never moves once set" is durable state; a read-time projection would have
  to re-derive it from the full scan-host history on every HOME load.
- A stable `host_id` a URL points at must be assigned once and persist; projecting it on read
  gives no fixed id to link to.
- The upsert is incremental and cheap (one host row per scan-host per scan); HOME/HOST DETAIL
  then read a single indexed table instead of grouping all historical scan-host rows.

Tradeoff (accepted, per ADR-014): identity logic runs on the write path, so a rule change
(e.g. IP→MAC) needs a backfill/re-materialisation migration rather than just new read code.

Materialisation algorithm (`upsert_hosts_for_scan`, called near the end of `persist_scan`
after scan-hosts+ports are flushed and have ids):

```
for each ScanHostRecord sh in this scan:
    key = identity_key(sh.mac, sh.ip)
    host = SELECT hosts WHERE org_id IS NOT DISTINCT FROM scan.org_id AND identity_key = key
    if host is None:
        host = HostRecord(org_id=scan.org_id, identity_key=key,
                          first_seen_at=scan.timestamp, last_seen_at=scan.timestamp, <latest attrs>)
    else:
        host.first_seen_at = min(host.first_seen_at, scan.timestamp)   # older backfilled scan
        if scan.timestamp >= host.last_seen_at:                        # this scan is most recent
            host.last_seen_at = scan.timestamp
            host.<mutable attrs> = <this scan's values>                # ip, mac, hostname, vendor,
                                                                       # open_ports_count, highest_severity
    sh.host_id = host.id
```

`open_ports_count` = count of the scan-host's ports with `state == "open"`.
`highest_severity` = max severity across this scan's findings whose `scan_host_id == sh.id`
(mapped via the existing per-scan index/finding loop, renamed from `device_index` — see
naming table). Both are written only when this scan is the most recent, honouring "mutable
attributes reflect the most recent observation".

### (c) Findings → host mapping (`?host_id=`)

`FindingRecord` keeps its own columns but its FK is renamed: `device_id` → `scan_host_id` (FK
`scan_hosts.id`), consistent with decision 3. `/findings?host_id=<id>` joins
`FindingRecord.scan_host_id → ScanHostRecord.id → ScanHostRecord.host_id == host_id`. Findings
with `scan_host_id IS NULL` (global / un-attributable findings) are correctly excluded from a
host filter. Because a host owns one scan-host row per scan, this returns the host's findings
across **all** scans, which is what HOST DETAIL needs to explain `highest_severity`. No
`host_id` column is added to `findings` directly; the scan-host join is sufficient and
minimal.

### (d) `host_id` on scan detail — via a split read-only schema

`HostPayload` (renamed `DevicePayload`, decision 1) is shared by **both**
`ScanIngestRequest.hosts` (what the Pi POSTs) and would-be `ScanDetailResponse.hosts` (what
the frontend reads), and it is `additionalProperties: false`. Adding a required `host_id` to
it would force the Pi's ingest request to carry a server-owned identity it cannot know —
corrupting MAC-else-IP resolution or forcing ingest validation to be weakened. So
**`HostPayload` is left untouched for ingest**, and a new response-only schema
**`ScanHostView`** (all `HostPayload` fields **plus required `host_id`**) is introduced;
`ScanDetailResponse.hosts` is repointed at it. Each host row's `host_id` =
`ScanHostRecord.host_id`, populated purely server-side. This is contract ask **C9** (see
contract deltas). Decision confirmed at the approval gate 2026-07-22.

## Central design decision 3 — rename `DeviceRecord` → `ScanHostRecord` (table `devices` → `scan_hosts`)

Per `CONTEXT.md`'s ScanHost definition ("in storage this is the record formerly named
`DeviceRecord`") and the 2026-07-22 scope decision, the backend model layer is renamed to
match the retired-"device" doctrine, not just extended with a `host_id` FK:

| Before | After |
|--------|-------|
| `DeviceRecord` (class), table `devices` | `ScanHostRecord` (class), table `scan_hosts` |
| `PortRecord.device_id` (FK `devices.id`) | `PortRecord.scan_host_id` (FK `scan_hosts.id`) |
| `FindingRecord.device_id` (FK `devices.id`) | `FindingRecord.scan_host_id` (FK `scan_hosts.id`) |
| `services/persistence.py` `_persist_device()`, `device_index`, `device_record` | `_persist_scan_host()`, `scan_host_index`, `scan_host_record` |
| `schemas/scan.py` `Device` (ingest model) | `Host` |
| `schemas/scan.py` `ScanResult.devices` | `ScanResult.hosts` |

**Checked for other "device"-named references that must cascade** (per the CLAUDE.md/task
instruction to grep before assuming): `ArtifactRecord` has no device reference
(`host_ip` only — unrelated word, already host-named). `EnrichmentJobRecord` has no device
reference (`port_id`/`finding_id` only) — **no change needed there**. `ServiceRecord` and
`CPERecord` key off `port_id`, not device — **no change needed**. `schemas/persistence.py`'s
`PersistedDevice`/`PersistedScanDetail.devices` are **not** renamed by this feature: grep
confirms they are unused (no router or service imports them — see the "unused internal
views" note below); renaming them is out of scope surgical-change creep and is flagged, not
fixed.

**Unused internal views, left as-is (flagged, not fixed):** `schemas/persistence.py`'s
`PersistedDevice`, `PersistedScanSummary`, `PersistedScanDetail`, `PersistedScanRiskSummary`
are exported from `schemas/__init__.py` but consumed by no router or service today. This
feature touches only the two fields that would otherwise reference now-dropped `ScanRecord`
columns (`target_mode`/`scan_profile` → `scan_mode` + `status`, decision 4) so the file
doesn't reference removed columns; `PersistedDevice`'s "device" naming is intentionally left
alone — it is dead code, not part of any wire contract, and renaming it is not required to
make anything correct.

**Sequence naming (flagged, cosmetic only):** the `devices` table's PK sequence
(`devices_id_seq`, granted to `dmitri_runtime` at baseline) is not automatically renamed by
`op.rename_table`. The rename migration additionally issues
`ALTER SEQUENCE devices_id_seq RENAME TO scan_hosts_id_seq` for naming hygiene; this is
optional (Postgres privileges/rename survive on the sequence regardless of its name) but
avoids a permanently mismatched sequence name after the table rename. No new grant is needed
either way — renaming preserves existing privileges.

## Data model / contracts

Schema is Alembic's, never `create_all`. **Three** new dated migrations, single-purpose each,
chained after the current head `20260716_02`. Assume an **empty database** — no backfill (the
ingest route was never mounted, so no real `scans`/`devices` rows exist).

#### Migration 1 — `20260722_03_scan_mode_status` (`down_revision = "20260716_02"`)

- **`scans`**: drop columns `target_mode` and `scan_profile`; add `scan_mode` (str, NOT NULL)
  and `status` (str, NOT NULL, `server_default='completed'`). Because the table is assumed
  empty, `scan_mode` can be added `NOT NULL` directly (no need to backfill first); `status`
  additionally carries a `server_default` so it is well-defined even if a row existed.
- `downgrade`: drop `scan_mode`/`status`; re-add `target_mode`/`scan_profile` (NOT NULL
  requires a `server_default` on the way back, e.g. `'subnet'`/`'lan'`, to satisfy any rows).
- No grant changes (`scans` is already granted to `dmitri_runtime`; column edits need no new
  grant).

#### Migration 2 — `20260722_04_scan_host_rename` (`down_revision = "20260722_03"`)

- `op.rename_table("devices", "scan_hosts")`.
- `op.alter_column("ports", "device_id", new_column_name="scan_host_id")` (the FK target
  `devices.id`/`scan_hosts.id` follows the table rename automatically since Postgres FKs
  reference the table by its current name internally via OID, not by the constraint's
  original name — the constraint continues to enforce the same relationship).
- `op.alter_column("findings", "device_id", new_column_name="scan_host_id")`.
- Rename the index that enforced `UniqueConstraint("scan_id", "ip")` on the renamed table if
  Alembic/Postgres auto-named it after the old table (verify the actual constraint name in
  the running schema; rename it to keep names consistent, or leave the underlying constraint
  name alone if only the table/column identifiers functionally matter — cosmetic, not
  required for correctness).
- Cosmetic: `op.execute("ALTER SEQUENCE devices_id_seq RENAME TO scan_hosts_id_seq")` (see
  "Sequence naming" above).
- `downgrade`: reverse column renames, reverse table rename, reverse sequence rename.
- No grant changes — renaming a table/column preserves existing Postgres privileges; no new
  `GRANT`/`REVOKE` needed.

#### Migration 3 — `20260722_05_host_identity` (`down_revision = "20260722_04"`)

- **New table `hosts`** as specified above (UUID PK, no sequence to grant).
- **`scan_hosts.host_id`** — new `sa.Uuid()` column, nullable, FK `hosts.id`, plus
  `ix_scan_hosts_host_id` index (drives the `?host_id=` join and scan-history lookups).
- Unique index / constraint `uq_hosts_org_identity` on `(org_id, identity_key)` with
  `NULLS NOT DISTINCT`; index `ix_hosts_org_id`.
- Security fence identical to the baseline/identity migrations: `ENABLE ROW LEVEL SECURITY`
  on `hosts`, revoke `anon`/`authenticated`,
  `GRANT SELECT, INSERT, UPDATE ON hosts TO dmitri_runtime`. No sequence grant (UUID PK). No
  `DELETE` grant. Do **not** re-create the `dmitri_runtime` role (baseline owns it).
  `scan_hosts` already carries its (renamed, unaffected) grant from baseline, so the new
  `host_id` column needs no separate grant.
- No backfill step — empty-DB assumption (resolved, see Open questions).
- `downgrade`: revoke `hosts` grant, drop `ix_scan_hosts_host_id`, drop FK + `scan_hosts.host_id`,
  drop `hosts` (its indexes drop with it).

### API response schemas (new pydantic models, matching `openapi.yaml` exactly)

These are **new** and distinct from the internal `schemas/persistence.py` `Persisted*` views,
which use internal vocabulary (`device_count`, and now `scan_mode`/`status`) and must not be
reused on the wire. New contract-shaped models (in `schemas/read.py`):

- `Port` (contract `Port`: port, protocol, state, service, version).
- `ScanHostView` — response-only host row for scan detail: contract `HostPayload`'s fields
  (ip, mac, hostname, vendor, ports) **plus required `host_id: UUID`** (C9). The ingest
  `HostPayload` is **not** reused here and is not modified.
- `FindingRead` — contract `FindingRecord` (read): finding_id, scan_id, `host_id`, `host_ip`,
  port, protocol, service, source, source_script, cve_id, cvss_score, severity, title,
  description, recommendation, evidence, references, detected_at. Mapping from DB
  `FindingRecord`: `id`→`finding_id`, `ip`→`host_ip`, resolved scan-host's `host_id`→
  `host_id`, `created_at`→`detected_at`.
- `HostSummary` — contract `HostSummary` **plus `first_seen_at: datetime`** (C6): host_id, ip,
  mac, hostname, vendor, first_seen_at, last_seen_at, open_ports_count, highest_severity.
- `HostScanHistoryEntry` — scan_id, timestamp, scan_mode, open_ports_count, highest_severity.
- `HostDetailResponse` — host_id, ip, mac, hostname, vendor, first_seen_at, last_seen_at,
  open_ports_count, highest_severity, ports (`Port[]` from the latest observation's
  scan-host), scan_history (`HostScanHistoryEntry[]` from `scan_hosts`⋈`scans` where
  `host_id == id`).
- `ScanDetailResponse` — scan_id, timestamp, subnet, scan_mode, hosts (`ScanHostView[]`),
  findings (`FindingRead[]`), metadata, status, command_id, host_count, finding_count.
- Envelopes `HostListResponse` / `FindingListResponse`: `{ data, total, page }`.

### Contract deltas to `contracts/openapi/openapi.yaml` (apply during implementation)

Four wire renames (ADR-013, decision 1) plus two schema gaps (C6, C9) must be closed:

1. **ADR-013 renames**: `ScanIngestRequest.devices` → `hosts` (property name and `required`
   entry); schema `DevicePayload` → `HostPayload` (rename the component and every `$ref` to
   it, including from `ScanIngestRequest.hosts.items` and the `ScanIngestRequestExample`);
   `ScanIngestAcceptedResponse.devices_received` → `hosts_received` (property + `required`
   entry + the `202` response example at line ~138).
2. **C6 — add `first_seen_at`** to `components.schemas.HostSummary`: add
   `first_seen_at: { type: string, format: date-time }` to `properties`, and add
   `first_seen_at` to the schema's `required` list (currently ends at `open_ports_count`).
3. **C9 — add a response-only `ScanHostView` schema; do NOT modify `HostPayload`.** Add
   `components.schemas.ScanHostView` = the fields of `HostPayload` (ip, mac, hostname,
   vendor, ports) **plus** `host_id: { type: string, format: uuid }` in `properties` and in
   `required` (`additionalProperties: false`). Repoint `ScanDetailResponse.hosts.items` from
   `#/components/schemas/HostPayload` to `#/components/schemas/ScanHostView`. `HostPayload`
   stays exactly as-is (post-rename) because `ScanIngestRequest.hosts` still uses it and the
   Pi does not send a `host_id`. (Decision confirmed at the approval gate 2026-07-22; the
   shared-schema/required alternative was rejected because it corrupts the Pi ingest
   contract.)

C11 is already resolved in the yaml (`/findings?host_id=` via `HostIdFilter`); this feature
only implements it.

### `scan_mode` + `status` — ingest-schema correction (decision 4, folded in)

`ScanDetailResponse` requires `scan_mode` (enum quick/standard/extensive/nspi/max) and
`status` (enum pending/accepted/processing/completed/failed), but `ScanRecord` stores
neither — it stores `target_mode` + `scan_profile` and no lifecycle column. Investigation
showed these two fields are **vestigial**: nothing branches on their values, and the real
scanner upload (`hardware-agent/src/agent/normalize/contracts.py` `ScanPayload`) and the
contract `ScanIngestRequest` both carry `scan_mode`, not `target_mode`/`scan_profile`. The
backend's `ScanResult` is in fact **incompatible** with a real Pi upload today (it is only
inert because the ingest route is unmounted). So instead of translating at read time, the fix
is at the source:

- **`schemas/scan.py` `ScanResult`**: remove `TargetMode`/`ScanProfile` literals and the
  `target_mode`/`scan_profile` fields; add `scan_mode: Literal["quick","standard","extensive",
  "nspi","max"]`. This makes the backend ingest schema equal to the scanner's `ScanPayload`
  and the contract's `ScanIngestRequest`. No `status` on ingest (the scanner does not send
  it).
- **`models/persistence.py` `ScanRecord`**: replace the `target_mode`/`scan_profile` columns
  with `scan_mode: str`; add `status: str = Field(default="completed")`.
- **`services/persistence.py` `persist_scan`**: write `scan_mode=scan.scan_mode` and rely on
  the `status` default (`completed`).
- **Read layer**: `ScanDetailResponse.scan_mode`/`status` and
  `HostScanHistoryEntry.scan_mode` come **directly** from the stored columns — no lookup, no
  synthesis.
- **Internal views** `PersistedScanSummary`/`PersistedScanDetail` (`schemas/persistence.py`)
  already expose `target_mode`/`scan_profile`; update them to `scan_mode` (+ `status` where a
  detail view warrants it) so they do not reference dropped columns.

`status` values other than `completed` (the command-lifecycle) are out of scope; `completed`
is the only value this feature writes.

## New files and naming (mandatory)

Implementers create/touch exactly these. Paths are exact.

| Layer | Path | New/Touch | Notes |
|-------|------|-----------|-------|
| Model | `backend/src/api/models/persistence.py` | Touch | rename `DeviceRecord`→`ScanHostRecord` (table `devices`→`scan_hosts`); `PortRecord.device_id`→`scan_host_id` (FK `scan_hosts.id`); `FindingRecord.device_id`→`scan_host_id` (FK `scan_hosts.id`); add `HostRecord` (table `hosts`); add `ScanHostRecord.host_id: UUID \| None` FK `hosts.id`; on `ScanRecord` drop `target_mode`/`scan_profile`, add `scan_mode: str` + `status: str` (default `"completed"`) |
| Ingest schema | `backend/src/api/schemas/scan.py` | Touch | `ScanResult`: remove `TargetMode`/`ScanProfile` + their fields; add `scan_mode` literal (quick/standard/extensive/nspi/max); rename `Device`→`Host`, `ScanResult.devices`→`hosts`; `ScanIngestResponse.devices_received`→`hosts_received` |
| Ingest service | `backend/src/api/services/persistence.py` | Touch | `persist_scan`: write `scan_mode=scan.scan_mode` (drop `target_mode`/`scan_profile`); rely on `status` default; rename `_persist_device`→`_persist_scan_host`, `device_index`→`scan_host_index`, `device_record`→`scan_host_record`; iterate `scan.hosts` (not `.devices`); **also** call `upsert_hosts_for_scan(...)` after scan-hosts/ports flushed and assign `scan_host.host_id` |
| Internal views | `backend/src/api/schemas/persistence.py` | Touch | `PersistedScanSummary`/`PersistedScanDetail`: replace `target_mode`/`scan_profile` with `scan_mode` (+`status` on detail); `PersistedDevice` naming left as-is (unused, flagged — see decision 3) |
| Schemas export | `backend/src/api/schemas/__init__.py` | Touch | export `Host` instead of `Device`; export the new `schemas/read.py` models (optional, match existing pattern) |
| Migration 1 | `backend/alembic/versions/20260722_03_scan_mode_status.py` | New | `scans`: drop `target_mode`/`scan_profile`, add `scan_mode`+`status`(server_default `completed`); `down_revision="20260716_02"` |
| Migration 2 | `backend/alembic/versions/20260722_04_scan_host_rename.py` | New | rename `devices`→`scan_hosts`; rename `ports.device_id`→`scan_host_id`, `findings.device_id`→`scan_host_id`; cosmetic sequence rename; `down_revision="20260722_03"` |
| Migration 3 | `backend/alembic/versions/20260722_05_host_identity.py` | New | create `hosts`, add `scan_hosts.host_id`+FK+index, RLS/grants; `down_revision="20260722_04"` |
| Schemas | `backend/src/api/schemas/read.py` | New | contract response models: `Port`, `ScanHostView`, `FindingRead`, `HostSummary`, `HostScanHistoryEntry`, `HostDetailResponse`, `ScanDetailResponse`, `HostListResponse`, `FindingListResponse` (ingest `Host`/`HostPayload` is NOT reused here) |
| Service (write) | `backend/src/api/services/hosts.py` | New | `identity_key()`, `upsert_hosts_for_scan(session, scan_record, scan)` |
| Service (read) | `backend/src/api/services/read.py` | New | `list_hosts()`, `get_host_detail()`, `get_scan_detail()`, `list_findings()` |
| Router pkg | `backend/src/api/routers/__init__.py` | New | package marker (see test note below) |
| Router | `backend/src/api/routers/hosts.py` | New | `GET /api/v1/hosts`, `GET /api/v1/hosts/{host_id}` |
| Router | `backend/src/api/routers/scans.py` | New | `GET /api/v1/scans/{scan_id}` (list `/scans` is out of scope) |
| Router | `backend/src/api/routers/findings.py` | New | `GET /api/v1/findings` |
| App | `backend/src/api/main.py` | Touch | `app.include_router(...)` for the three routers |
| Contract | `contracts/openapi/openapi.yaml` | Touch (outside `backend/`) | ADR-013 renames (`devices`→`hosts`, `DevicePayload`→`HostPayload`, `devices_received`→`hosts_received`) + C6 + C9 deltas above |
| Example | `contracts/examples/scan_result.example.json` | Touch (outside `backend/`) | replace `target_mode`/`scan_profile` with `scan_mode` (e.g. `"lan"`→`"standard"`) and `devices`→`hosts` so the retained engine/ingest tests validate against the corrected + renamed schema |
| Pi contract | `hardware-agent/src/agent/normalize/contracts.py` | Touch (outside `backend/`) | `DevicePayload`→`HostPayload`; `ScanPayload.devices`→`ScanPayload.hosts` |
| Pi exports | `hardware-agent/src/agent/normalize/__init__.py` | Touch | re-export `HostPayload` in place of `DevicePayload` |
| Pi stages | `hardware-agent/src/agent/scanner/stages.py` | Touch | `build_device_payload(host) -> DevicePayload` → `build_host_payload(host) -> HostPayload` |
| Pi runner | `hardware-agent/src/agent/scanner/runner.py` | Touch | `devices = [stages.build_device_payload(h) ...]` → `hosts = [stages.build_host_payload(h) ...]`; `ScanPayload(devices=devices, ...)` → `ScanPayload(hosts=hosts, ...)` |
| Pi TUI | `hardware-agent/src/agent/tui/screens/scan_view.py` | Touch | 3 reads of `payload.devices` → `payload.hosts` |
| Pi TUI | `hardware-agent/src/agent/tui/screens/scan_progress.py` | Touch | 3 reads of `payload.devices` → `payload.hosts` |
| Pi TUI | `hardware-agent/src/agent/tui/screens/home.py` | Touch | 2 reads of `payload.devices` → `payload.hosts` |
| Pi test | `hardware-agent/tests/test_contract_models.py` | Touch | `DevicePayload`→`HostPayload` import/usage; `.devices`→`.hosts` |
| Pi test | `hardware-agent/tests/unit/test_tui_scan_view.py` | Touch | same |
| Pi test | `hardware-agent/tests/unit/test_headless.py` | Touch | `.devices`→`.hosts` (equality assertion) |
| Pi test | `hardware-agent/tests/unit/test_scan_runner_partial.py` | Touch | `.devices`→`.hosts` |
| Pi test | `hardware-agent/tests/unit/test_scan_runner_cancel.py` | Touch | `.devices`→`.hosts` |
| Pi test | `hardware-agent/tests/unit/test_scan_progress_screen.py` | Touch | `DevicePayload`→`HostPayload` import/usage |
| Pi test | `hardware-agent/tests/integration/test_tui_flows.py` | Touch | `DevicePayload`→`HostPayload` import/usage |
| Pi test | `hardware-agent/tests/unit/test_workspace.py` | Touch | `ScanPayload(devices=[...])` keyword → `hosts=[...]` |
| Pi test | `hardware-agent/tests/unit/test_quick_mode_argv.py` | Touch | same keyword rename |
| Pi test | `hardware-agent/tests/integration/test_extensive_e2e.py` | Touch | same keyword rename |
| Test (existing) | `backend/tests/test_migrations.py` | Touch | its `DeviceRecord(...)` insert (line ~512) → `ScanHostRecord(...)`; nearby `ScanRecord(...)` insert (line ~507) uses `target_mode`/`scan_profile`→`scan_mode`/`status` |
| Test (existing) | `backend/tests/test_identity_migration.py` | Touch | its `ScanRecord(...)` insert (line ~205) uses `target_mode="subnet", scan_profile="lan"`; switch to `scan_mode`/`status` |
| Test (existing) | `backend/tests/test_ingest_scan.py` | Touch | imports/queries `DeviceRecord` (lines 8, 91) → `ScanHostRecord`; payload/assertions use the old ingest fields → `scan_mode`, `hosts`; assert persisted `status="completed"` |
| Test (existing) | `backend/tests/test_health.py` | Touch | update the route-surface / router-import assertions (below) |
| Test | `backend/tests/test_host_identity_migration.py` | New | mirror `test_identity_migration.py`; assert migration 1 (`scans` column swap) and migration 2 (rename) up/down, plus migration 3 (`hosts` table) |
| Test | `backend/tests/test_host_materialisation.py` | New | mirror `test_ingest_scan.py` (drives `persist_scan`) |
| Test | `backend/tests/test_read_endpoints.py` | New | mirror `test_health.py` (`TestClient` + `dependency_overrides`) |

**`main.py` mount + existing-test note (do not mark complete without this):**
`test_health.py` currently asserts the app exposes *only* `/api/v1/health` and that
`api.routers` is **not** importable (`test_route_surface_exposes_only_canonical_health`,
`test_routers_package_is_not_importable`). Adding the routers and the `routers` package breaks
both; they must be updated to assert the new route surface. Its `DISCARDED_BUSINESS_PATHS`
tuple (`/scans`, `/api/v1/scans`, `/findings`, `/api/v1/findings`) also needs review: this
feature mounts `GET /api/v1/scans/{scan_id}` and `GET /api/v1/findings`, so the bare
`/api/v1/scans` (no id) entry stays valid (that path is not mounted), but the
`/api/v1/findings` entries need re-checking against the actual new route table —
`/api/v1/findings` becomes a real, mounted path once `listFindings` lands, so it should no
longer be asserted as 404. `test_app_has_no_lifespan_hook_or_middleware` stays valid — this
feature adds no middleware (CORS/`OPTIONS` twins in the contract are a separate concern, not
built here).

## Auth boundary

The contract marks these routes `FrontendBearerAuth` (JWT). Auth is a separate epic (TRUTH
out-of-scope). **Recommendation: build the routes without JWT enforcement now** — no
login/JWT/role logic — but structure them so the auth epic can wrap them by adding a single
`Depends(...)` dependency (e.g. a future `require_bearer`) to each router without touching
query/response code. No `401/403` behaviour is implemented in this feature; the read logic and
shapes are what ship.

## Testing expectations

Gates: `uv run pytest` and `uv run ruff check` both pass — **in both `backend/` and
`hardware-agent/`** (this feature touches both). New code (incl. tests) carries no
comments/docstrings, matching each layer's style.

### Backend

- **Migration up/down** (`test_host_identity_migration.py`, mirror
  `test_identity_migration.py`'s `_simulate_upgrade` monkeypatch harness). Migration 1
  (`20260722_03`): `scans.target_mode` and `scans.scan_profile` dropped; `scans.scan_mode` +
  `scans.status` present (`status` server_default `completed`); downgrade restores the old
  columns. Migration 2 (`20260722_04`): `devices` table renamed to `scan_hosts`;
  `ports.device_id`/`findings.device_id` renamed to `scan_host_id`; downgrade reverses both
  renames. Migration 3 (`20260722_05`): `hosts` table created; `scan_hosts.host_id` added
  nullable with FK `hosts.id`; unique `(org_id, identity_key)` present; RLS enabled +
  `dmitri_runtime` granted `SELECT, INSERT, UPDATE` on `hosts`; no `SEQUENCE` grant; no
  `CREATE ROLE`; no `DELETE` grant.
- **Ingest `scan_mode`/`status`** (extend `test_ingest_scan.py`): a payload with `scan_mode`
  (and no `target_mode`/`scan_profile`) validates and persists; `ScanRecord.scan_mode` equals
  the sent value and `ScanRecord.status == "completed"`; a payload still carrying
  `target_mode`/`scan_profile` is rejected (the schema no longer accepts them). Payload uses
  `hosts`/`HostPayload` vocabulary (ADR-013); a payload still carrying `devices` is rejected
  (`additionalProperties: false`).
- **Host materialisation / identity** (`test_host_materialisation.py`, mirror
  `test_ingest_scan.py` driving `persist_scan` on `runtime_session`): same MAC across scan A
  (older) and scan B (newer) → one `HostRecord`, single `host_id`, `first_seen_at ==
  A.timestamp` and unchanged after B, `last_seen_at == B.timestamp`, mutable attrs reflect B;
  MAC-absent scan-host resolves by IP; a scan-host only in the latest scan has `first_seen_at
  == latest.timestamp` (new-device signal); each scan's `ScanHostRecord.host_id` is set.
- **Endpoints** (`test_read_endpoints.py`, mirror `test_health.py` `TestClient` +
  `app.dependency_overrides[get_session]`): happy path for each of the four endpoints (200 +
  shape); `GET /hosts/{host_id}` unknown id → 404; `GET /scans/{scan_id}` unknown id → 404;
  `GET /findings?host_id=<id>` returns exactly that host's findings and its
  `highest_severity` appears among them; scan detail host rows each carry `host_id`.
- **Contract-shape assertions**: assert the touched fields exist with correct types on
  responses — `HostSummary.first_seen_at`, `HostDetailResponse.first_seen_at`/`last_seen_at`,
  each scan-detail host's `host_id`, `FindingRead.host_id`. (Full `openapi.yaml` schema
  validation is optional but encouraged if a validator is already available.)

### Pi (`hardware-agent/`)

- **Contract rename** (extend `tests/test_contract_models.py`): `HostPayload` importable
  from `agent.normalize.contracts` and `agent.normalize`; `ScanPayload.hosts` accepts a list
  of `HostPayload`; constructing `ScanPayload` with a `devices=` keyword no longer works
  (renamed away — either a `TypeError` from the unexpected kwarg or, if extra kwargs are
  otherwise tolerated by the model config, an explicit assertion that `hosts` is the only
  accepted field name).
- **Every touched call site's existing test still passes** with the field renamed: the nine
  test files listed in the naming table are the mirror set — no new Pi test file is required,
  only the rename applied to existing assertions (`.devices` → `.hosts`,
  `DevicePayload(...)` → `HostPayload(...)`, `devices=[...]` keyword → `hosts=[...]`).
- Run `uv run pytest` and `uv run ruff check` inside `hardware-agent/` after the rename;
  both must pass alongside `backend/`'s gates.

## Constraints

- No new infrastructure, daemons, or external tooling → **no `HUMAN_INFRA_REQUIRED`**. Reuses
  the existing FastAPI app, `get_session`, Alembic, and the `persist_scan` transaction.
- Schema is Alembic-owned; no `SQLModel.metadata.create_all`. The new `HostRecord` (and
  renamed `ScanHostRecord`) register on the shared metadata via `models/__init__.py` (already
  imports `persistence`), so `alembic/env.py` autogenerate/target metadata sees them with no
  env change.
- The **scanner (Pi)**'s discovery, normalization, and scoring logic are untouched — only its
  contract *serialization* layer (`contracts.py`) and every site that reads the renamed field
  by name change. The enrichment/scoring engine is untouched. The backend **ingest schema** is
  corrected (`target_mode`/`scan_profile` → `scan_mode`, add `status`) to match the scanner
  and contract; host materialisation is additive inside `persist_scan`. No new ingest endpoint
  and no new field the scanner must produce.
- No `GET /api/v1/scans` list, no C10 failure-reason, no auth logic, no scan-lifecycle beyond
  `status="completed"`, no search/sort/pagination behaviour beyond returning correct rows in
  the contract envelope.

## Open questions / assumptions (approval gate) — status

All items below were resolved at the 2026-07-22 grilling session; listed for traceability,
not as open blockers.

1. **RESOLVED — identity key = MAC-else-IP**, per
   [`ADR-014`](../../docs/adr/ADR-014-host-identity-resolution.md). Accepted v1 limitations:
   DHCP IP churn fractures identity for MAC-less devices; MAC randomisation splits one machine
   into many; intermittent MAC splits one machine into two Hosts. Revisit only if the product
   targets routed subnets at scale (ADR-014's own "not a permanent ceiling" note).
2. **RESOLVED — ingest-time materialisation** (not read-time projection). `first_seen_at`
   durability and a fixed linkable `host_id` require write-time assignment; see decision 2(b).
3. **RESOLVED — fix at the source, no translation.** `target_mode`/`scan_profile` are
   vestigial and do not match the real scanner upload; replaced by `scan_mode` on the ingest
   schema + `ScanRecord`, plus a `status` column (default `completed`). Read layer reads both
   directly. Scanner is unchanged (it already emits `scan_mode`).
4. **RESOLVED — packaging: single PR (option B).** Folds the durable Host model, both ingest
   corrections (scan_mode/status, ADR-013 rename), and the four read endpoints into one PR
   spanning `backend/`, `contracts/`, and `hardware-agent/`.
5. **RESOLVED — C9 split read-only schema.** Adds a response-only `ScanHostView`
   (`HostPayload` fields + required `host_id`) and repoints `ScanDetailResponse.hosts` at it;
   the ingest `HostPayload` is left untouched. The shared-schema/required alternative was
   rejected because it forces the Pi to send a server-owned identity.
6. **RESOLVED — empty database, no backfill.** The ingest route was never mounted, so no
   pre-existing `scans`/`devices` rows exist; all three migrations assume an empty table and
   skip backfill logic.

### Residual items (not blockers, called out for implementers)

- **`org_id` currently NULL on ingest** — identity uniqueness relies on `NULLS NOT DISTINCT`
  until the auth epic populates `org_id`. Carried forward from the prior draft as an accepted
  transitional state, not re-litigated at the 2026-07-22 session.
- **`test_health.py`'s `DISCARDED_BUSINESS_PATHS`** needs a real look at implementation time
  (see the naming-table note above) — the new `/api/v1/findings` route changes which paths
  should 404 vs. 200.
- **Rename blast radius on the Pi side is bigger than ADR-013's text suggests** — see "Rename
  blast radius" under decision 1. Budget for touching TUI display code, not just the contract
  file.
