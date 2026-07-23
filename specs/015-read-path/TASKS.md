# Tasks — Read path: hosts, scan detail, and findings (`015-read-path`)

12 tasks. **Unblocked now: #1, #8, #9.**

Cross-layer (`backend/` + `contracts/` + `hardware-agent/`). Two independent fronts run in
parallel: **Backend read path** (#1–#7) and **ADR-013 device→host rename** (#8–#12). The
CLAUDE.md TUI-threading rule is N/A — this feature adds no new `ScanOrchestrator`/`ScanRunner`
parameter (per ARCHITECTURE §"CLAUDE.md TUI rule … N/A"); the Pi runner/TUI screens are touched
only for the mechanical field rename. Gates run in **both** `backend/` and `hardware-agent/`:
`uv run pytest` and `uv run ruff check` must pass in each.

---

## Task 1: Schema foundation — model rename + durable host + 3 migrations
- **Status**: COMPLETED
- **Description**: Land the whole schema change as one coherent unit per ARCHITECTURE decisions 2 & 3 and the "Data model / contracts" migrations. In `models/persistence.py`: rename `DeviceRecord`→`ScanHostRecord` (table `devices`→`scan_hosts`), `PortRecord.device_id`→`scan_host_id` (FK `scan_hosts.id`), `FindingRecord.device_id`→`scan_host_id` (FK `scan_hosts.id`); add `HostRecord` (table `hosts`) with the exact columns and `UniqueConstraint("org_id","identity_key", postgresql_nulls_not_distinct=True)`; add `ScanHostRecord.host_id: UUID | None` FK `hosts.id`; on `ScanRecord` drop `target_mode`/`scan_profile`, add `scan_mode: str` and `status: str` (default `"completed"`). Write the three chained migrations exactly as specced (`20260722_03_scan_mode_status` down_rev `20260716_02`; `20260722_04_scan_host_rename` down_rev `20260722_03`; `20260722_05_host_identity` down_rev `20260722_04`) including RLS/grants (`SELECT,INSERT,UPDATE` on `hosts` to `dmitri_runtime`, no SEQUENCE/DELETE grant, no CREATE ROLE) and the cosmetic sequence rename. Update the two existing migration tests so they stay green under the renamed model/columns.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/models/persistence.py`, `backend/alembic/versions/20260722_03_scan_mode_status.py`, `backend/alembic/versions/20260722_04_scan_host_rename.py`, `backend/alembic/versions/20260722_05_host_identity.py`, `backend/tests/test_migrations.py`, `backend/tests/test_identity_migration.py`, `backend/tests/test_host_identity_migration.py`]
- **Success Criteria**: `ScanHostRecord`/`HostRecord` importable and registered on the shared metadata; `ScanRecord` has `scan_mode`+`status` and no `target_mode`/`scan_profile`. `test_host_identity_migration.py` (mirroring `test_identity_migration.py`'s upgrade harness) asserts: migration 03 drops `scans.target_mode`/`scan_profile`, adds `scan_mode`+`status` (server_default `completed`), and downgrade restores; migration 04 renames `devices`→`scan_hosts` and `ports.device_id`/`findings.device_id`→`scan_host_id`, downgrade reverses; migration 05 creates `hosts`, adds nullable `scan_hosts.host_id`+FK+`ix_scan_hosts_host_id`, unique `(org_id, identity_key)` NULLS NOT DISTINCT, RLS enabled + correct grant, no SEQUENCE/DELETE grant, no CREATE ROLE. `uv run pytest` + `uv run ruff check` pass in `backend/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 2: Ingest schema — scan_mode + Device→Host rename
- **Description**: Per ARCHITECTURE decisions 1 & 4. In `schemas/scan.py`: remove `TargetMode`/`ScanProfile` literals and the `target_mode`/`scan_profile` fields; add `scan_mode: Literal["quick","standard","extensive","nspi","max"]`; rename `Device`→`Host` and `ScanResult.devices`→`hosts`; rename `ScanIngestResponse.devices_received`→`hosts_received`. Update `schemas/__init__.py` to export `Host` in place of `Device` (and optionally the new `read.py` models per existing pattern). In `schemas/persistence.py` update `PersistedScanSummary`/`PersistedScanDetail` to use `scan_mode` (+`status` on the detail view) so they no longer reference dropped columns; leave `PersistedDevice` naming as-is (dead code, flagged).
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/schemas/scan.py`, `backend/src/api/schemas/__init__.py`, `backend/src/api/schemas/persistence.py`]
- **Success Criteria**: `ScanResult` validates a payload carrying `scan_mode` + `hosts` and rejects one carrying `target_mode`/`scan_profile` or `devices` (schema no longer accepts them); `Host` importable from `api.schemas`; internal `Persisted*` views reference `scan_mode`/`status`, not the dropped columns. `uv run pytest` + `uv run ruff check` pass in `backend/`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Host materialisation service
- **Status**: COMPLETED
- **Description**: New `services/hosts.py` implementing ADR-014 identity per ARCHITECTURE decision 2(b). `identity_key(mac, ip)` returns `f"mac:{mac.upper()}"` when a MAC is present else `f"ip:{ip}"`. `upsert_hosts_for_scan(session, scan_record, scan)` runs the specced algorithm: for each `ScanHostRecord` resolve/create a `HostRecord` scoped by `org_id IS NOT DISTINCT FROM scan.org_id` + `identity_key`; set `first_seen_at=min(...)`; when this scan is the most recent (`scan.timestamp >= host.last_seen_at`) advance `last_seen_at` and refresh mutable attrs (ip, mac, hostname, vendor, `open_ports_count`=count of open ports, `highest_severity`=max finding severity for that scan-host); assign `scan_host.host_id = host.id`.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/services/hosts.py`]
- **Success Criteria**: `identity_key` prefixes/upper-cases correctly and prefers MAC; `upsert_hosts_for_scan` creates one host per identity, never moves `first_seen_at` backward-wrongly (keeps the min), only refreshes mutable attrs when the scan is most recent, and sets each `scan_host.host_id`. Exercised by Task 4's materialisation test. `uv run ruff check` passes in `backend/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 4: Ingest persist_scan rewire + materialisation call
- **Status**: COMPLETED
- **Description**: Per ARCHITECTURE naming table (ingest service row). In `services/persistence.py` `persist_scan`: write `scan_mode=scan.scan_mode` and drop `target_mode`/`scan_profile` (rely on `status` default `completed`); rename `_persist_device`→`_persist_scan_host`, `device_index`→`scan_host_index`, `device_record`→`scan_host_record`; iterate `scan.hosts`; after scan-hosts/ports are flushed and have ids, call `upsert_hosts_for_scan(...)` so each scan-host's `host_id` is assigned inside the same transaction. Add `test_host_materialisation.py` (mirror `test_ingest_scan.py`, drives `persist_scan` on `runtime_session`) and update `test_ingest_scan.py` for the new vocabulary.
- **Dependencies**: Task 2, Task 3
- **Target Files**: [`backend/src/api/services/persistence.py`, `backend/src/api/services/enrichment.py`, `backend/tests/test_host_materialisation.py`, `backend/tests/test_ingest_scan.py`]

  > Scope note (orchestrator, 2026-07-22): `enrichment.py` added to Task 4 — it sits on the `worker.py → enrichment.py` ingest call path and still referenced the pre-Task-1 `DeviceRecord`/`device_id`/`device_record` names, breaking collection of `test_ingest_scan.py`/`test_worker_startup.py`. Mechanical rename only (CLAUDE.md integration rule).
- **Success Criteria**: A `scan_mode`/`hosts` payload persists; `ScanRecord.scan_mode` equals the sent value and `ScanRecord.status == "completed"`. Materialisation test: same MAC across scan A (older) and B (newer) → one `HostRecord`, single `host_id`, `first_seen_at == A.timestamp` (unchanged after B), `last_seen_at == B.timestamp`, mutable attrs reflect B; MAC-absent scan-host resolves by IP; a scan-host only in the latest scan has `first_seen_at == latest.timestamp`; each `ScanHostRecord.host_id` is set. `test_ingest_scan.py` uses `ScanHostRecord`/`hosts`/`scan_mode` and asserts `status="completed"`. `uv run pytest` + `uv run ruff check` pass in `backend/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 5: Read response schemas
- **Status**: COMPLETED
- **Description**: New `schemas/read.py` with the contract-shaped pydantic models per ARCHITECTURE "API response schemas": `Port`, `ScanHostView` (`HostPayload` fields + required `host_id: UUID`, C9 — do not reuse ingest `Host`), `FindingRead` (with the specced DB→wire field mapping), `HostSummary` (contract fields + `first_seen_at`, C6), `HostScanHistoryEntry`, `HostDetailResponse`, `ScanDetailResponse` (hosts=`ScanHostView[]`, findings=`FindingRead[]`, plus `scan_mode`/`status`/counts), and envelopes `HostListResponse`/`FindingListResponse` (`{data, total, page}`).
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/schemas/read.py`]
- **Success Criteria**: All nine models exist with fields/types matching `contracts/openapi/openapi.yaml` for the touched schemas; `HostSummary.first_seen_at` and `ScanHostView.host_id` are present and required; `ScanHostView` is distinct from the ingest `Host`/`HostPayload`. `uv run ruff check` passes in `backend/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 6: Read service — queries
- **Status**: COMPLETED
- **Description**: New `services/read.py` implementing `list_hosts()`, `get_host_detail()`, `get_scan_detail()`, `list_findings()` as read-only queries over the sync session (per ARCHITECTURE "System context"). `list_findings(host_id=...)` joins `FindingRecord.scan_host_id → ScanHostRecord.id → ScanHostRecord.host_id == host_id` (excluding `scan_host_id IS NULL`). `get_host_detail` returns ports from the latest observation's scan-host and `scan_history` from `scan_hosts`⋈`scans` where `host_id == id`. `get_scan_detail` maps each host row's `host_id` from `ScanHostRecord.host_id` and reads `scan_mode`/`status` directly from the stored scan.
- **Dependencies**: Task 1, Task 5
- **Target Files**: [`backend/src/api/services/read.py`]
- **Success Criteria**: Each function returns the corresponding `schemas/read.py` model(s); `list_findings` returns exactly the host's findings via the scan-host join; `get_host_detail`/`get_scan_detail` return `first_seen_at`/`last_seen_at`/`host_id`/`scan_mode`/`status` from stored data with no vocabulary translation. Covered by Task 7's endpoint tests. `uv run ruff check` passes in `backend/`.
- **Review Rejections**: 1

## Task 7: Routers + app mount + endpoint tests
- **Status**: COMPLETED
- **Description**: Per ARCHITECTURE naming table (router rows) and the "main.py mount + existing-test note". Add `routers/__init__.py` (package marker) and routers `hosts.py` (`GET /api/v1/hosts`, `GET /api/v1/hosts/{host_id}`), `scans.py` (`GET /api/v1/scans/{scan_id}`), `findings.py` (`GET /api/v1/findings`), each obtaining `session: Session = Depends(get_session)` and structured so an auth `Depends(...)` can wrap later (no JWT built now). Mount all three in `main.py`. Add `test_read_endpoints.py` (mirror `test_health.py`, `TestClient` + `dependency_overrides[get_session]`). Update `test_health.py`: the app no longer exposes only `/health`, `api.routers` is now importable, and re-check `DISCARDED_BUSINESS_PATHS` (`/api/v1/findings` and `/api/v1/scans/{scan_id}` are now mounted; bare `/api/v1/scans` list stays 404).
- **Dependencies**: Task 5, Task 6
- **Target Files**: [`backend/src/api/routers/__init__.py`, `backend/src/api/routers/hosts.py`, `backend/src/api/routers/scans.py`, `backend/src/api/routers/findings.py`, `backend/src/api/main.py`, `backend/tests/test_read_endpoints.py`, `backend/tests/test_health.py`]
- **Success Criteria**: Happy path for each of the four endpoints (200 + correct shape); `GET /hosts/{host_id}` and `GET /scans/{scan_id}` unknown id → 404; `GET /findings?host_id=<id>` returns exactly that host's findings and its `highest_severity` appears among them; scan-detail host rows each carry `host_id`. Contract-shape assertions on `HostSummary.first_seen_at`, `HostDetailResponse.first_seen_at`/`last_seen_at`, scan-detail `host_id`, `FindingRead.host_id`. `test_health.py` reflects the new route surface. `uv run pytest` + `uv run ruff check` pass in `backend/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 8: Contract deltas — openapi.yaml + example
- **Status**: COMPLETED
- **Description**: Per ARCHITECTURE "Contract deltas". In `contracts/openapi/openapi.yaml`: ADR-013 renames (`ScanIngestRequest.devices`→`hosts` incl. `required`; component `DevicePayload`→`HostPayload` and every `$ref`; `ScanIngestAcceptedResponse.devices_received`→`hosts_received` incl. `required` + the 202 example); C6 add `first_seen_at` (date-time) to `HostSummary` properties + `required`; C9 add response-only `ScanHostView` (HostPayload fields + required `host_id` uuid, `additionalProperties: false`) and repoint `ScanDetailResponse.hosts.items` to it, leaving `HostPayload` otherwise unchanged. In `contracts/examples/scan_result.example.json`: replace `target_mode`/`scan_profile` with `scan_mode` (e.g. `"standard"`) and `devices`→`hosts`.
- **Dependencies**: —
- **Target Files**: [`contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`]
- **Success Criteria**: openapi.yaml has no remaining `DevicePayload`/`devices_received`/`ScanIngestRequest.devices` references; `HostSummary.required` includes `first_seen_at`; `ScanHostView` exists with required `host_id` and `ScanDetailResponse.hosts.items` `$ref`s it; `HostPayload` unchanged apart from the rename. The example validates against the corrected/renamed schema. YAML parses.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 9: Pi contract rename — contracts.py + exports
- **Status**: COMPLETED
- **Description**: ADR-013 serialization rename per ARCHITECTURE naming table (Pi contract/exports rows). In `hardware-agent/src/agent/normalize/contracts.py`: rename `DevicePayload`→`HostPayload` and `ScanPayload.devices: list[DevicePayload]`→`ScanPayload.hosts: list[HostPayload]`. In `hardware-agent/src/agent/normalize/__init__.py`: re-export `HostPayload` in place of `DevicePayload`.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/normalize/contracts.py`, `hardware-agent/src/agent/normalize/__init__.py`]
- **Success Criteria**: `HostPayload` importable from `agent.normalize.contracts` and `agent.normalize`; `ScanPayload` exposes `hosts` (not `devices`); `DevicePayload` name gone. `uv run ruff check` passes in `hardware-agent/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 10: Pi producers — stages + runner
- **Status**: COMPLETED
- **Description**: Per ARCHITECTURE "Rename blast radius" (Pi stages/runner rows). In `scanner/stages.py`: rename `build_device_payload(host) -> DevicePayload` to `build_host_payload(host) -> HostPayload`. In `scanner/runner.py`: local `devices = [stages.build_device_payload(h) ...]` → `hosts = [stages.build_host_payload(h) ...]` and `ScanPayload(devices=devices, ...)` → `ScanPayload(hosts=hosts, ...)`.
- **Dependencies**: Task 9
- **Target Files**: [`hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/src/agent/scanner/runner.py`]
- **Success Criteria**: `build_host_payload` is the only producer name; `runner.py` constructs `ScanPayload(hosts=...)`; no `build_device_payload`/`devices=` remain in these files. `uv run ruff check` passes in `hardware-agent/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 11: Pi TUI screens — read-site rename
- **Status**: COMPLETED
- **Description**: Per ARCHITECTURE "Rename blast radius" (Pi TUI rows). Update every `payload.devices` read to `payload.hosts` in `tui/screens/scan_view.py` (3), `tui/screens/scan_progress.py` (3), and `tui/screens/home.py` (2). Display logic unchanged — field name only.
- **Dependencies**: Task 9
- **Target Files**: [`hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/src/agent/tui/screens/scan_progress.py`, `hardware-agent/src/agent/tui/screens/home.py`]
- **Success Criteria**: No `payload.devices` reads remain in the three screens; counts/rows/port sums read `payload.hosts`. `uv run ruff check` passes in `hardware-agent/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 12: Pi tests — rename mirror set
- **Status**: COMPLETED
- **Description**: Apply the field/keyword rename across the nine Pi test files per ARCHITECTURE naming table (Pi test rows): `DevicePayload`→`HostPayload` imports/usage, `.devices`→`.hosts` assertions, and `ScanPayload(devices=[...])` keyword → `hosts=[...]`. Extend `test_contract_models.py` to assert `HostPayload` is importable from both `agent.normalize.contracts` and `agent.normalize`, that `ScanPayload.hosts` accepts a `HostPayload` list, and that a `devices=` keyword no longer constructs a `ScanPayload`.
- **Dependencies**: Task 9, Task 10, Task 11
- **Target Files**: [`hardware-agent/tests/test_contract_models.py`, `hardware-agent/tests/unit/test_tui_scan_view.py`, `hardware-agent/tests/unit/test_headless.py`, `hardware-agent/tests/unit/test_scan_runner_partial.py`, `hardware-agent/tests/unit/test_scan_runner_cancel.py`, `hardware-agent/tests/unit/test_scan_progress_screen.py`, `hardware-agent/tests/integration/test_tui_flows.py`, `hardware-agent/tests/unit/test_workspace.py`, `hardware-agent/tests/unit/test_quick_mode_argv.py`, `hardware-agent/tests/integration/test_extensive_e2e.py`]
- **Success Criteria**: All nine files reference `hosts`/`HostPayload` only; `test_contract_models.py` asserts the import + `hosts` field + rejection of the `devices=` keyword. `uv run pytest` + `uv run ruff check` pass in `hardware-agent/`.
- **Status**: PENDING
- **Review Rejections**: 0

## Task 13: FindingRecord durable `finding_id` UUID + migration
- **Status**: COMPLETED
- **Description**: Foundation gap discovered during Task 6 (operator decision 2026-07-22 "Add UUID column + migration"). The read contract (`contracts/openapi/openapi.yaml` `FindingRecord.finding_id`, required, `format: uuid`) exposes a UUID finding identity, but the durable `FindingRecord` model from Task 1 has only an int autoincrement PK. Add `finding_id: UUID = Field(default_factory=uuid4, unique=True, index=True)` to `FindingRecord` in `models/persistence.py` (keep the existing int `id` PK), and write a new chained alembic migration `20260722_06_finding_uuid` (down_rev `20260722_05`) that: adds the `finding_id` column nullable, backfills existing rows with `gen_random_uuid()`, sets NOT NULL, adds the unique constraint + index; downgrade reverses. `default_factory=uuid4` means ingest (`persist_scan`) auto-populates it with no persistence.py change. Update `test_host_identity_migration.py` (or the appropriate migration test) to cover migration 06.
- **Dependencies**: Task 1
- **Target Files**: [`backend/src/api/models/persistence.py`, `backend/alembic/versions/20260722_06_finding_uuid.py`, `backend/tests/test_host_identity_migration.py`]
- **Success Criteria**: `FindingRecord.finding_id` is a UUID with a uuid4 default, unique+indexed; new rows get a UUID automatically; migration 06 chains off 05, adds the column with backfill + NOT NULL + unique + index, downgrade reverses; migration test covers it. `uv run pytest --ignore=tests/test_worker_startup.py` + `uv run ruff check` pass in `backend/`.
- **Review Rejections**: 1

---

## Dependency graph

```
Backend read path:
  #1 ─┬─► #2 ─┐
      │       ├─► #4
      ├─► #3 ─┘
      ├─► #5 ─┬─► #6 ─► #7
      │       └────────►┘
      └────────────────►#6, #7 (need #1's model)

ADR-013 rename (independent front):
  #8 (contract) — standalone
  #9 ─┬─► #10 ─┐
      ├─► #11 ─┼─► #12
      └────────┘
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Schema foundation — model rename + durable host + 3 migrations | COMPLETED |
| 2 | Ingest schema — scan_mode + Device→Host rename | COMPLETED |
| 3 | Host materialisation service | COMPLETED |
| 4 | Ingest persist_scan rewire + materialisation call | COMPLETED |
| 5 | Read response schemas | COMPLETED |
| 6 | Read service — queries | COMPLETED |
| 13 | FindingRecord durable finding_id UUID + migration | COMPLETED |
| 7 | Routers + app mount + endpoint tests | COMPLETED |
| 8 | Contract deltas — openapi.yaml + example | COMPLETED |
| 9 | Pi contract rename — contracts.py + exports | COMPLETED |
| 10 | Pi producers — stages + runner | COMPLETED |
| 11 | Pi TUI screens — read-site rename | COMPLETED |
| 12 | Pi tests — rename mirror set | COMPLETED |
