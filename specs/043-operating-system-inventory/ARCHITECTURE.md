# ARCHITECTURE — Operating-system inventory

Status: planned. Read `TRUTH.md` before implementation. This feature is additive and
crosses the hardware agent, the published OpenAPI contract, backend ingestion,
persistence, and read APIs. The React frontend is explicitly outside this delivery.

## 1. End state

```text
Nmap -O XML
    |
    v
parse best osmatch + best osclass
    |
    v
PortScanResult.operating_system
    |
    v
HostInfo.operating_system
    |
    +--> HostPayload.operating_system --> workspace JSON --> TUI
    |
    +--> signed POST /api/v1/scans
              |
              +--> scan_hosts.operating_system_json   (scan snapshot)
              |
              +--> hosts.operating_system_json        (last supported inventory value)
                            |
                            +--> scan and host read APIs
```

OS detection remains part of the existing port stage because every current scan mode
already includes `-O` there. No new subprocess, Nmap flag, timeout, configuration value,
or `ScanRunner` constructor parameter is introduced.

## 2. Domain and contract model

Use `OperatingSystemInfo` for the mutable in-memory dataclass and
`OperatingSystemDetection` for every Pydantic/OpenAPI boundary.

```text
OperatingSystemInfo / OperatingSystemDetection
  name: string                         required, non-empty
  accuracy: integer                    required, 0..100 percentage
  vendor: string | null                optional
  family: string | null                optional
  generation: string | null            optional
  device_type: string | null           optional
  cpes: string[]                       zero or more non-empty platform identifiers

HostInfo
  operating_system: OperatingSystemInfo | None = None

HostPayload and host read models
  operating_system: OperatingSystemDetection | None = None
```

The JSON property is named `operating_system`; the database column is named
`operating_system_json`. Do not add aliases such as `os`, `confidence`, `os_name`, or
`platform_identifiers`. `accuracy` is the confidence percentage reported by Nmap, and
`cpes` carries Nmap's platform identifiers without treating service/application CPEs as
OS evidence.

Unavailable optional attributes are not replaced by `unknown`. Validators accept an omitted
optional property and explicit `null` for compatibility. An absent host-level detection is
represented by omitted `operating_system` on older input and by either omitted or `null` on
current input/output. Both forms validate to `None`.

## 3. Nmap XML parsing

Add `parse_operating_system(host_element) -> OperatingSystemInfo | None` beside the
existing Nmap XML helpers.

Selection is deterministic:

1. Inspect only `<host><os><osmatch>` elements. Raw `<osfingerprint>` content and service
   CPEs are not candidates.
2. Ignore a candidate whose `name` is empty or whose `accuracy` is missing, non-numeric,
   or outside `0..100`.
3. Select the `osmatch` with greatest integer `accuracy`; retain the first XML candidate
   on a tie.
4. Within the selected match, select the child `osclass` with greatest valid `accuracy`;
   retain the first on a tie. The class is optional.
5. Set `name` and contract `accuracy` from the selected `osmatch`. Set `vendor`, `family`
   (`osfamily`), `generation` (`osgen`), and `device_type` (`type`) from the selected
   class, stripping blank strings to `None`.
6. Collect non-empty `<cpe>` text from every `osclass` under the selected match, then
   deduplicate and sort it. Do not collect CPEs from lower-ranked matches.
7. Return `None` when no supported candidate remains.

This implements one best detection without retaining raw fingerprints or lower-ranked
candidates. Detection may legitimately be absent: Nmap OS fingerprinting depends on the
target and scan conditions and is never treated as a scan failure.

## 4. Port-stage result and merge

Introduce a small `PortScanResult` dataclass in `scanner/models.py`:

```text
PortScanResult
  ports: list[PortInfo]
  operating_system: OperatingSystemInfo | None
```

Change `scan_ports()` to return `PortScanResult` and `scan_ports_batch()` to return
`dict[str, PortScanResult]`. Each result is built from the same host XML element so the
IP, ports, and OS evidence cannot be associated with different hosts.

Keep `merge_ports()` and add
`merge_port_scan_results(existing, incoming) -> PortScanResult`. It merges ports with the
current rules and retains the OS detection with greatest `accuracy`; a non-`None`
detection beats `None`, and the existing detection wins a tie. The NSPi two-pass path
uses this helper. Today pass 1 supplies OS evidence because it has `-O`, while pass 2 has
no `-O`; pass 2 therefore enriches ports without erasing pass-1 OS evidence.

`run_port_stage()` assigns both `result.ports` and `result.operating_system` to the
matching `HostInfo`. The deep-inspection stage does not run `-O` and must not mutate the
field. Existing timeout, retry, circuit-breaker, cancellation, and partial-result rules
remain unchanged; any OS evidence already assigned to a host survives partial
normalisation.

## 5. Normalisation and local presentation

`build_host_payload()` performs a field-for-field conversion from
`HostInfo.operating_system` to `OperatingSystemDetection`. The existing workspace writer
then persists it automatically inside each host in the local scan JSON, and the existing
signed ingest client transmits the same `ScanPayload`; neither gets a second output path.

`ScanViewScreen` follows the exact copy and ordering in `DESIGN.md`, directly below each host
heading:

```text
  Operating system:
    Detected: Linux 5.4 - 5.10 (96% confidence)
    Vendor: Linux
    Family: Linux
    Generation: 5.X
    Device type: general purpose
    Platform IDs:
      - cpe:/o:linux:linux_kernel:5
```

Only available detail lines are rendered. With no detection it renders
`Operating system: Not detected`. The detected form always includes the percentage and does not
assert certainty.

## 6. Backend persistence and inventory semantics

Add nullable generic SQLAlchemy `JSON` columns named `operating_system_json` to both
`scan_hosts` and `hosts`.

- `ScanHostRecord.operating_system_json` is the immutable snapshot supplied for that
  scan host. It is `NULL` when that scan has no supported detection.
- `HostRecord.operating_system_json` is the latest supported inventory value. A new host
  copies the scan snapshot, including `NULL`.
- For an existing inventory host, update the value only when the incoming scan timestamp
  is at least the current `last_seen_at` and the incoming snapshot is non-null.
- A chronologically newer snapshot without OS evidence still updates the ordinary host
  facts and `last_seen_at`, but does not erase the stored OS object.
- A late-arriving older scan never replaces the inventory OS value.

JSON is deliberate: v1 reads and displays the object atomically, while filtering,
sorting, risk scoring, and vulnerability matching by OS are out of scope. Pydantic
validates the shape before write and when converting records back to responses. Do not
create an OS table or duplicate its fields into individual columns in v1.

The migration adds the two nullable columns without a backfill. Existing rows therefore
represent missing historical evidence and remain readable. Downgrade drops both columns.

## 7. Read API

Define the backend `OperatingSystemDetection` once in
`api/schemas/operating_system.py` and import it from ingest and read schemas. Add optional
`operating_system` to every host-bearing public shape:

- `HostPayload`: submitted scan evidence;
- `ScanHostView`: the scan-scoped snapshot in `GET /api/v1/scans/{scan_id}`;
- `HostSummary`: the retained inventory value in `GET /api/v1/hosts`;
- `HostDetailResponse`: the retained inventory value in
  `GET /api/v1/hosts/{host_id}`;
- `HostScanHistoryEntry`: the snapshot belonging to that historical scan.

Read mapping validates non-null JSON through the shared schema before returning it.
Inventory endpoints read from `HostRecord`; scan detail and scan history read from the
corresponding `ScanHostRecord`. No new endpoint or query parameter is added.

The authoritative OpenAPI document adds one reusable component named
`OperatingSystemDetection` and optional nullable references from the five schemas above.
It is not in their `required` arrays, preserving older clients and payloads.

## 8. Call paths that must remain connected

No new runner parameter exists, but implementation review must verify both scan entry
paths required by the repository integration rule:

```text
headless/daemon -> headless.run_headless_scan -> ScanRunner
                                              -> run_port_stage
                                              -> build_host_payload

TUI Home -> ScanProgressScreen -> ScanRunner -> run_port_stage
                                      |       -> build_host_payload
                                      v
                               ScanViewScreen

TUI PastScansScreen -> saved JSON -> ScanViewScreen
```

`ScanRunner` already owns normalisation for both headless and TUI scans. Therefore
`headless.py`, `ScanProgressScreen`, and their constructors require no modification.
`PastScansScreen` also requires no modification because it passes the selected JSON path
to `ScanViewScreen`, whose existing loader validates `ScanPayload`.

On the cloud path, verify:

```text
ingest route -> ScanIngestRequest -> persist_scan -> _persist_scan_host
                                           |      -> ScanHostRecord snapshot
                                           +----> upsert_hosts_for_scan -> HostRecord

GET scan detail -> ScanHostRecord -> ScanHostView
GET host list/detail/history -> HostRecord + ScanHostRecord -> read schemas
```

## 9. New files and naming (mandatory)

| Layer | Path | Action and exact responsibility |
|---|---|---|
| Agent model | `hardware-agent/src/agent/scanner/models.py` | Add `OperatingSystemInfo`, `PortScanResult`, and `HostInfo.operating_system`. |
| Agent XML | `hardware-agent/src/agent/utils/nmap_xml.py` | Add deterministic `parse_operating_system`. |
| Agent discovery | `hardware-agent/src/agent/discovery/port_discovery.py` | Return/merge `PortScanResult`; preserve NSPi pass-1 OS evidence. |
| Agent stage | `hardware-agent/src/agent/scanner/stages.py` | Attach the result to `HostInfo` and normalise it. |
| Agent contract | `hardware-agent/src/agent/normalize/contracts.py` | Add `OperatingSystemDetection` and optional `HostPayload.operating_system`. |
| Agent exports | `hardware-agent/src/agent/normalize/__init__.py` | Export `OperatingSystemDetection`. |
| Agent TUI | `hardware-agent/src/agent/tui/screens/scan_view.py` | Render detected and missing states; follow `DESIGN.md`. |
| Shared contract | `contracts/openapi/openapi.yaml` | Publish the reusable object and optional host properties. |
| Shared example | `contracts/examples/scan_result.example.json` | Add one detected host and one host without evidence. |
| Backend shared schema — new | `backend/src/api/schemas/operating_system.py` | Define the single backend `OperatingSystemDetection`. |
| Backend ingest schema | `backend/src/api/schemas/scan.py` | Add the optional object to `HostPayload`. |
| Backend read schema | `backend/src/api/schemas/read.py` | Add the object to all host-bearing read models. |
| Backend exports | `backend/src/api/schemas/__init__.py` | Export `OperatingSystemDetection`. |
| Backend ORM | `backend/src/api/models/persistence.py` | Add nullable JSON fields to scan and inventory host records. |
| Backend scan persistence | `backend/src/api/services/persistence.py` | Persist the scan-host snapshot. |
| Backend inventory | `backend/src/api/services/hosts.py` | Implement timestamp-aware retain/refresh semantics. |
| Backend reads | `backend/src/api/services/read.py` | Map snapshot/current JSON into every read shape. |
| Backend migration — new | `backend/alembic/versions/20260908_19_operating_system_inventory.py` | Add/drop the two nullable JSON columns; revision `20260908_19`, down revision `20260903_18`. |
| Agent parser tests — new | `hardware-agent/tests/unit/test_operating_system_parsing.py` | Cover selection, class fields, CPEs, malformed and missing evidence. |
| Agent stage tests — new | `hardware-agent/tests/unit/test_operating_system_stage.py` | Cover host association and normalisation. |
| Agent NSPi tests | `hardware-agent/tests/unit/test_nspi_two_pass_merge.py` | Cover OS retention and confidence merge between passes. |
| Agent contract tests | `hardware-agent/tests/test_contract_models.py` | Cover object validation and omitted host field. |
| Agent JSON tests | `hardware-agent/tests/unit/test_workspace.py` | Verify local JSON round-trip and missing evidence. |
| Agent TUI tests | `hardware-agent/tests/unit/test_tui_scan_view.py` | Cover detected, optional-detail, and not-detected rendering. |
| Backend migration tests — new | `backend/tests/test_operating_system_migration.py` | Verify revision chain, nullable JSON additions, and downgrade. |
| Backend ingest schema tests | `backend/tests/test_ingest_schema.py` | Cover omitted/null/valid/invalid detections. |
| Backend persistence tests | `backend/tests/test_ingest_scan.py` | Verify exact scan-host snapshot persistence. |
| Backend inventory tests | `backend/tests/test_host_materialisation.py` | Cover refresh, preservation, and older late arrival. |
| Backend read schema tests | `backend/tests/test_read_schema.py` | Cover all host-bearing schema shapes. |
| Backend scan read tests | `backend/tests/test_read_scans.py` | Verify scan snapshot response. |
| Backend host read tests | `backend/tests/test_read_hosts.py` | Verify inventory and historical responses. |
| Contract fidelity tests | `backend/tests/test_contract_fidelity.py` | Add the component to fidelity coverage. |

There are no planned changes under `frontend/`, no generated TypeScript update, and no
new files under agent configuration, `ScanRunner`, `ScanProgressScreen`, or transport.

## 10. Testing expectations and gates

### Hardware agent

- Parser fixtures cover multiple `osmatch` candidates, accuracy ties, multiple classes,
  blank optionals, duplicate CPEs, missing `<os>`, and malformed accuracy.
- NSPi tests prove that pass 2 cannot erase pass-1 detection and that a future stronger
  candidate wins.
- Stage tests use multiple hosts and reversed XML order to prove evidence stays with the
  matching IPv4 address.
- Contract and workspace tests prove valid round-trip, `0` and `100` bounds, omitted
  detection compatibility, and no fabricated values.
- TUI tests assert exact detected/not-detected language and every optional detail.
- Gate: from `hardware-agent/`, run `uv run pytest`. Formatting remains scoped to the
  existing hardware-agent pre-push hooks.

### Contract and backend

- Schema tests reject empty names, out-of-range/non-integer accuracy, empty CPE strings,
  and extra object properties.
- Ingestion tests prove older payloads still pass and current evidence is stored without
  transformation.
- Materialisation tests cover newer evidence, newer absence, older late evidence, and a
  first scan without evidence.
- Read tests distinguish scan snapshot from retained inventory value.
- Migration tests check both tables, nullable generic JSON type, revision chain, and
  downgrade operations.
- Contract fidelity includes `OperatingSystemDetection` and all five referencing schemas.
- Gates: from `backend/`, run `uv run ruff check src tests` and `uv run pytest`. Never run
  a backend formatter.

## 11. Constraints and non-goals

- Reuse the existing Nmap runner, batch execution, XML logs, partial-result handling, and
  signed scan payload. Do not add a second OS scan or fallback fingerprint engine.
- Preserve the current `-O` flags and timing policy from ADR-004. Performance remediation
  for NSPi timeouts is a separate change and must not silently remove OS detection.
- Do not infer an OS from port service names, banners, service CPEs, MAC vendor, Modbus
  fingerprints, or hostname.
- Do not persist raw `<osfingerprint>` XML or lower-ranked candidates.
- Do not add OS filtering, sorting, risk scoring, or vulnerability correlation.
- No infrastructure or hardware changes are required; `HUMAN_INFRA_REQUIRED` does not
  apply.
- Frontend display and generated frontend API types remain out of scope.
