# TASKS — Operating-system inventory

Execution is sequential. The approved sources are `TRUTH.md`, `ARCHITECTURE.md`,
`DESIGN.md`, and `INTEGRATION.md`. Frontend React is outside this delivery.

## Dependency graph

```text
Task 1 -> Task 2 -> Task 3
                -> Task 4
```

## Status table

| Task | Status | Review Rejections |
|------|--------|-------------------|
| 1. Capture OS evidence from Nmap | COMPLETED | 0 |
| 2. Normalize OS in the shared scan contract and local JSON | COMPLETED | 0 |
| 3. Render OS evidence in the TUI | COMPLETED | 0 |
| 4. Persist and expose OS through the backend | COMPLETED | 1 |

## Task 1: Capture OS evidence from Nmap
- **Description**: Add the in-memory operating-system and port-scan result models, parse the best supported Nmap `osmatch`/`osclass` deterministically, return ports and OS together for single and batch scans, merge NSPi passes without losing the best detection, and attach the result to the correct `HostInfo` in the port stage. Preserve all existing flags, timeouts, partial-result behavior, and host/IP association.
- **Dependencies**: —
- **Target Files**: [`hardware-agent/src/agent/scanner/models.py`, `hardware-agent/src/agent/utils/nmap_xml.py`, `hardware-agent/src/agent/discovery/port_discovery.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/tests/unit/test_operating_system_parsing.py`, `hardware-agent/tests/unit/test_operating_system_stage.py`, `hardware-agent/tests/unit/test_nspi_two_pass_merge.py`, `hardware-agent/tests/unit/test_quick_mode_argv.py`, `hardware-agent/tests/unit/test_discovery_timeout_forwarding.py`]
- **Success Criteria**: The best valid match and class are selected with deterministic tie handling; optional values are normalized without fabrication; CPEs come only from classes under the selected match and are deduplicated; malformed or absent evidence yields `None`; every scan mode returns a `PortScanResult`; multi-host results remain associated by IPv4; NSPi retains the strongest detection while merging ports; existing Nmap arguments and timeout forwarding are unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Normalize OS in the shared scan contract and local JSON
- **Description**: Add `OperatingSystemDetection` consistently to the hardware-agent model, published OpenAPI ingest contract, and backend ingest schema; map `HostInfo.operating_system` into `HostPayload.operating_system`; export the contracts; and verify current and legacy workspace JSON round trips. Do not add persistence, read API fields, a second serialization path, generated frontend types, or frontend changes.
- **Dependencies**: 1
- **Target Files**: [`hardware-agent/src/agent/normalize/contracts.py`, `hardware-agent/src/agent/normalize/__init__.py`, `hardware-agent/src/agent/scanner/stages.py`, `hardware-agent/tests/test_contract_models.py`, `hardware-agent/tests/unit/test_workspace.py`, `contracts/openapi/openapi.yaml`, `contracts/examples/scan_result.example.json`, `backend/src/api/schemas/operating_system.py`, `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/__init__.py`, `backend/tests/test_ingest_schema.py`, `backend/tests/test_contract_fidelity.py`]
- **Success Criteria**: Valid detections enforce non-empty names, integer accuracy from 0 through 100, non-empty CPEs, optional structured attributes, and forbidden extras consistently across agent, OpenAPI, and backend ingest; `HostPayload.operating_system` is optional/nullable and defaults to `None`; `build_host_payload()` performs a lossless field mapping; saved JSON contains host OS evidence; JSON and ingest payloads that omit the field remain valid and load as no detection; the shared contract and both Pydantic implementations remain faithful without modifying frontend artifacts.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Render OS evidence in the TUI
- **Description**: Render the normalized operating-system block in the existing scan result screen exactly as specified in `DESIGN.md`, for both current payloads and saved results. Keep navigation, summaries, widgets, and styles unchanged.
- **Dependencies**: 2
- **Target Files**: [`hardware-agent/src/agent/tui/screens/scan_view.py`, `hardware-agent/tests/unit/test_tui_scan_view.py`, `hardware-agent/tests/integration/test_tui_flows.py`]
- **Success Criteria**: Each host renders its own detected name and confidence; supplied vendor, family, generation, device type, and CPEs appear in the specified order; absent optional details leave no empty labels; absent or legacy evidence renders `Operating system: Not detected`; mixed and partial payloads do not cross-associate evidence; fresh and past-scan entry paths show identical content; no new widget, stylesheet, or frontend file is introduced.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Persist and expose OS through the backend
- **Description**: Extend the shared contract and backend read schemas created in Task 2 to every host-bearing read model, migrate nullable JSON snapshots onto scan hosts and inventory hosts, persist exact scan evidence, retain the last supported chronologically current inventory detection, and expose the correct snapshot/current value through every host-bearing read API. Keep older payloads and rows valid, include upgrade/downgrade coverage, and do not touch the frontend or generated TypeScript.
- **Dependencies**: 2
- **Target Files**: [`contracts/openapi/openapi.yaml`, `backend/src/api/schemas/read.py`, `backend/src/api/models/persistence.py`, `backend/src/api/services/persistence.py`, `backend/src/api/services/hosts.py`, `backend/src/api/services/read.py`, `backend/alembic/versions/20260908_19_operating_system_inventory.py`, `backend/tests/test_operating_system_migration.py`, `backend/tests/test_ingest_scan.py`, `backend/tests/test_host_materialisation.py`, `backend/tests/test_read_schema.py`, `backend/tests/test_read_scans.py`, `backend/tests/test_read_hosts.py`, `backend/tests/test_contract_fidelity.py`]
- **Success Criteria**: OpenAPI and Pydantic expose one consistent optional/nullable object on ingest, scan detail, host list/detail, and scan history; extra or malformed fields are rejected; old payloads remain accepted; scan snapshots store exact validated evidence or SQL `NULL`; inventory updates only from a non-null detection on a chronologically current scan and is not erased by a newer absence or replaced by an older arrival; reads validate stored JSON and distinguish scan snapshot from retained inventory; migration adds and downgrades both nullable generic JSON columns on the correct revision chain; backend lint and tests pass; no frontend file changes.
- **Status**: COMPLETED
- **Review Rejections**: 1
