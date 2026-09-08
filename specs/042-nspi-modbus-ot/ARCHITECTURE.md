# ARCHITECTURE — NSPi OT inventory and Modbus assessment

Status: implementation in progress. `inventory`, `read_only_mapping`, submode
selection and the initial FC43 fingerprint catalogue are implemented;
`active_validation` and relational OT persistence remain planned.

This is a cross-layer feature: `hardware-agent/`, `backend/`, the shared OpenAPI
contract and `frontend/` all change. The existing NSPi Nmap/NSE path remains the
base scanner. The new implementation adds a typed OT observation stage and
three explicit NSPi submodes: inventory, read-only mapping and guarded active
validation.

Read `TRUTH.md` before implementing. Its safety boundaries are product rules,
not suggestions.

## 1. End state

```text
operator / command
        |
        | scan_mode=nspi + optional nspi_options.submode
        v
host discovery
        v
NSPi port scan: current pass 1 + current OT-port pass 2
        v
current deep NSE scan: all 14 NSPI_NSE_SCRIPTS
        |
        +---- generic NSE/CVE findings (unchanged)
        |
        v
OT interpretation
  - consume port/service and modbus-discover ScriptResult
  - select only confirmed/candidate TCP endpoints
        v
bounded Modbus inspection
  - inventory: FC43/14 fallback where useful
  - read-only mapping: profile or baseline FC01/02/03/04 ranges
  - active validation: exact FC05/FC06 point + mandatory restoration
        v
normalise one typed payload
        +---- local workspace JSON
        +---- signed backend ingest
                         v
             persistence + current enrichment
                         v
                 scan/host UI
```

The OT stage is after deep inspection so that it reuses the parsed
`modbus-discover` evidence and does not repeat work blindly. It runs before
normalisation so partial-result handling remains centralised in `ScanRunner`.

### Product roles

- **Operator**: connects the appliance, selects `nspi` and one submode, confirms
  the displayed risk when needed, starts the scan and reads a plain-language
  report. No IP, Unit ID, function code or register knowledge is required.
- **Installer/OT owner**: optionally prepares site/vendor mapping profiles and
  the locally stored active-validation allowlist once. This role knows which
  test points are disposable and safe.
- **Agent**: detects the network, hosts, services, Modbus candidates and Unit
  IDs; selects the applicable profile; performs bounded requests; correlates
  fingerprints and produces the result automatically.

An unconfigured appliance still provides complete `inventory` and conservative
`read_only_mapping`. It never invents a writable point for
`active_validation`.

## 2. Existing code that remains authoritative

| Existing component | Decision | Reason |
|---|---|---|
| `NSPI_PORTS` and the two NSPi port passes | Reuse unchanged | Already finds general and well-known OT services. |
| `NSPI_NSE_SCRIPTS` | Reuse all scripts | Preserves today's coverage, including `modbus-discover`, `enip-info`, SMB, RDP, SSH, TLS, HTTP and `vulners`. |
| `NmapRunner` and XML logging | Reuse | Already provides subprocess timeout, evidence files and termination. |
| `parse_nse_node` / `ScriptResult` | Reuse | NSE structured XML already survives in memory; only a Modbus interpreter is missing. |
| stage retry, circuit breaker, deadline and partial payload | Extend | OT requests need the same failure semantics. |
| `extract_findings` | Extend with OT rules | NSE/CVE extraction stays intact. |
| workspace JSON and signed ingest | Extend typed payload | There must remain one result contract. |
| backend NVD/KEV/EPSS/risk services | Reuse | The Pi should fingerprint; the backend should enrich. |
| PyModbus | Add as the only Modbus runtime library | Mature typed operations avoid a home-grown protocol stack. Pin and lock one tested 3.x release because its API is not SemVer-stable. |
| Redpoint `modicon-info.nse` | Optional separate laboratory stage | Reuses a ready Schneider enumerator, but it is intrusive, vendor-specific and sends proprietary FC90 traffic. |
| MATRIX | Do not import | Its useful protocol primitive is already PyModbus. Its attack scenarios belong in isolated TCC tests, not the normal scan pipeline. |

The regression guard for Nmap is a test that checks both the exact current
`NSPI_NSE_SCRIPTS` membership and the final deep-inspection argv. An optional
vendor script is a second command and cannot mutate that tuple.

## 3. NSPi submodes

`nspi_options` is optional and versioned. Omission is equivalent to:

```json
{
  "version": 1,
  "submode": "inventory"
}
```

### `inventory` — default, least intrusive

- Runs the current Nmap/NSE pipeline.
- Produces typed Modbus observations from `modbus-discover` and service data.
- Uses a minimal FC43/MEI 14 PyModbus fallback only for a candidate TCP endpoint
  whose NSE output did not provide device identification.
- Does not read coils or process registers.

### `read_only_mapping` — explicit, more intrusive

- Includes everything in `inventory`.
- Automatically selects confirmed Modbus endpoints and Unit IDs discovered by
  the current NSE/inventory results.
- Resolves bounded ranges in this order: installed site profile, recognised
  vendor/product profile, then conservative generic baseline.
- A range names an address space, not an arbitrary function code. The agent maps
  `coil -> 01`, `discrete_input -> 02`, `holding_register -> 03`, and
  `input_register -> 04` internally.
- Supports `capture_values = none | summary | raw`; the default is `summary`.

### `active_validation` — explicit, most intrusive

- Includes the current Nmap/NSE pipeline and normal Modbus identification.
- May include explicitly configured read-only mapping, but never discovers a
  write target from mapping results.
- Accepts only preapproved FC05/FC06 validation operations for one coil or
  holding register at a time. The operator does not enter those addresses when
  starting a scan.
- Requires both an acknowledged scan request and a local Raspberry Pi safety
  policy that enables the target network. Neither authority replaces the other.
- Performs read-before-write, one test write, read-back, one best-effort restore
  of the captured original value and restoration verification.
- Defers cancellation during the restoration-critical section. An unverified
  restore stops all remaining validations and is surfaced as an incident.

All three submodes are active network scans. “Read-only” distinguishes protocol
operations from writes; it does not mean passive monitoring. “Sequential” means
one OT protocol request at a time and does not mean Modbus RTU or a physical
serial port.

| NSPi submode | Current 14 NSE scripts | Identification | Address reads | Single-point write validation |
|---|---:|---:|---:|---:|
| `inventory` | Yes | Yes | No | No |
| `read_only_mapping` | Yes | Yes | Explicit ranges | No |
| `active_validation` | Yes | Yes | Optional explicit ranges | Exact FC05/FC06 operations only |

This hierarchy is analogous to the existing general scan modes while retaining
`scan_mode = nspi` as the stable top-level contract. The submode changes OT
depth and risk; it does not remove today's NSE coverage.

### Schneider vendor laboratory probe — separate opt-in

This is not a general NSPi submode. A local, explicitly authorised lab
configuration may run an operator-installed, checksum-pinned
`modicon-info.nse` only after standard identification indicates
Schneider/Modicon. The result is parsed through the same `ScriptResult` path.
Redistribution and Nmap-license compatibility must be approved before vendoring
the script. Once installed and enabled, selection is automatic when the
fingerprint and chosen submode satisfy its policy; the ordinary operator does
not choose scripts.

## 4. Input contract

The intended wire model is:

```text
NspiOptions
  version: 1
  submode: inventory | read_only_mapping | active_validation
  active_risk_acknowledged          # active_validation only
  change_ticket?                    # active_validation audit reference
```

The ordinary command intentionally does not carry targets, Unit IDs, ranges or
write values. This keeps plug-and-scan simple and prevents a remote caller from
constructing arbitrary write operations. Hard server- and agent-side limits cap
targets, Unit IDs, ranges, addresses per range, block size, requests per host
and validation operations.

An installation-scoped `OtAutomationPolicy`, loaded locally on the agent and
never accepted from a remote command, contains optional expert configuration:

```text
mapping_profiles[]
  selector                         # CIDR/MAC/vendor/product constraints
  unit_ids?                        # otherwise reuse discovered IDs
  ranges[]                         # address space/start/count/block/capture

vendor_probes[]                    # e.g. checksum-pinned Redpoint script

active_validation_enabled: false   # secure default
allowed_cidrs[]
max_validation_operations_per_scan # default 1; hard product ceiling 5
validation_operations[]
  selector                         # must resolve to one discovered device
  port
  unit_id
  address_space                    # coil or holding_register
  address
  expected_current_value
  test_value
  label
```

The effective permission is the intersection of hard product limits, local
policy and the per-scan request. The backend cannot enable a locally disabled
validation. In v1 there is at most one operation per target and no more than
five operations in a scan; an installation may lower both limits.

When no mapping profile matches, the built-in generic baseline reads four
zero-based samples: addresses `0-3` in coils, discrete inputs, holding registers
and input registers. Each sample is one block of four values, uses summary
capture and is labelled `generic baseline sample`. Mapping reuses at most four
discovered Unit IDs, waits 100 ms between requests and shares a hard ceiling of
32 Modbus requests per host with identification. A local policy may lower that
request ceiling and alter the delay within `25-2000 ms`, but cannot raise the
hard ceiling. The runtime never expands ranges based on time remaining and the
report describes the result as a baseline sample, not a complete address map.

The model is added consistently to:

- backend create-command schema and persisted command data;
- backend-to-agent WebSocket frame;
- agent `AgentCommand`;
- headless/CLI/TUI construction of `ScanRunner`;
- scan metadata/output policy summary.

Old commands without `nspi_options` remain valid. Non-NSPi modes reject the
field instead of silently ignoring it.

## 5. Output contract

`HostPayload` gains `industrial_services`, a discriminated list. The first
member is `ModbusTcpServicePayload`; no generic plugin registry is built yet.

```text
ModbusTcpServicePayload
  protocol: modbus_tcp
  port
  confidence: suspected | confirmed
  evidence_sources[]               # service fingerprint, NSE, PyModbus
  mapping_source?                  # generic_baseline, site:name or vendor:name
  units[]

ModbusUnitPayload
  unit_id                           # observed byte; active policy only uses 1..247
  status: responding | exception | timeout | skipped
  identification_sources[]         # e.g. modbus-discover, pymodbus-fc43
  device_identification?
    vendor_name?
    product_code?
    major_minor_revision?
    model_name?
    user_application_name?
    objects{}                       # other returned MEI objects
  address_ranges[]
  validations[]

ModbusAddressRangePayload
  address_space
  start_address                    # always zero-based PDU notation
  count
  status: readable | illegal_address | illegal_function | timeout | error | skipped
  exception_code?
  label?                            # copied from approved input map
  nonzero_count?
  value_min?
  value_max?
  values?                           # only capture_values=raw
  value_sha256?                     # comparison without retaining raw values
  observed_at

ModbusValidationPayload
  address_space                    # coil or holding_register
  address                          # zero-based PDU address
  label
  function_code                    # 5 or 6
  original_value?
  expected_current_value
  test_value
  write_status: accepted | rejected | timeout | error | skipped
  read_back_value?
  restoration_status: not_required | verified | unverified | failed
  final_value?
  change_ticket
  started_at
  completed_at
```

Inventory stays separate from `FindingPayload`. A finding references host,
port, protocol, evidence source and, where relevant, Unit ID/range/validation in
its evidence text. This avoids representing ordinary OT assets as
vulnerabilities.

## 6. Agent components

Add a focused `agent/ot/modbus/` package:

- `models.py`: policy-independent internal observations and status enums.
- `nse.py`: converts `modbus-discover` structured/text output into observations.
- `client.py`: narrow read-only PyModbus adapter exposing identification and the
  four read functions.
- `mapper.py`: validates target rules, chunks ranges, applies budgets/delays and
  records response/exception status.
- `fingerprints.py`: maps reviewed exact FC43 vendor/product/version tuples to
  high-confidence CPE candidates without guessing ambiguous products.
- `validation.py`: separately guarded FC05/FC06 adapter and the
  read/write/read/restore/verify state machine. Read-only components never
  import its write adapter.
- `findings.py`: contextual exposure and fingerprint-to-enrichment candidates.

Do not create a generic protocol plugin framework for one protocol. The
discriminated payload and isolated package are sufficient seams for the next
protocol.

`HostInfo` receives an `industrial_services` collection so information survives
stage merging. `build_host_payload` serialises it. `ScanRunner` adds the
`ot_inspection` stage only for `nspi`; it selects behaviour from the validated
submode.

### Cancellation

Introduce the smallest shared active-operation interface needed by
`ScanRunner.request_cancel()`: `request_cancel()`. Its Nmap implementation
terminates the subprocess and its read-only Modbus implementation closes the
current client/socket. Cancellation is also checked between every request and
mapping block. A low response timeout bounds an uncooperative close.

Active validation has different cancellation semantics. Before the test write,
cancellation stops normally. After the test write is sent, `request_cancel()`
sets a pending flag but does not close the socket until one restoration attempt
and verification finish. This critical section cannot guarantee recovery after
power loss or process termination, which is why disposable points and an
isolated/maintenance state remain mandatory.

### Resource behaviour on Raspberry Pi

- A synchronous client is sufficient because OT concurrency is one.
- Reuse one connection per host/port while its rules run, then close it.
- Send every OT protocol request sequentially; this is independent of physical
  Modbus RTU/serial support, which remains out of scope.
- Stream range summaries into the in-memory observation; do not construct a
  65,536-address probe list.
- Keep raw value capture bounded and disabled by default.
- Benchmark gates record peak RSS, elapsed time, request count, timeout count and
  JSON size on Pi 3 B+ and Pi 4 4 GB.

## 7. Backend persistence and reads

The complete product will add scan-scoped relational records:

```text
industrial_services  -> scan_hosts, ports
modbus_units         -> industrial_services
modbus_ranges        -> modbus_units
modbus_validations   -> modbus_units
```

The range table stores summary fields and a nullable bounded JSON value list.
The validation table stores every step and restoration outcome; it does not
store a reusable authorisation token. Device-identification extras and evidence
sources may be bounded JSON because their vendor keys vary. Unique constraints
make ingest idempotent within a scan. All reads remain organisation-scoped
through the owning scan.

The first catalogue accepts only FC43-backed Schneider Electric/Schneider
Automation Modicon M340 and M580 identifications with an unambiguous numeric
firmware revision. It attaches the versioned firmware CPE to the same TCP port,
which reuses the current CPE-to-NVD/KEV/EPSS enrichment pipeline. Missing,
ambiguous or unsupported fingerprints remain inventory and are not guessed
into a CPE. Relational persistence and OT-specific read APIs remain Task 10.

## 8. Presentation

- CLI/workspace JSON needs no second output path; the extended `ScanPayload` is
  written by the existing workspace writer.
- TUI progress gains an OT stage and renders a concise inventory summary. It
  never prints thousands of values.
- Web scan detail shows protocol, port, confidence, Unit IDs, identification and
  range/validation status. Raw values, when present, are
  collapsed/download-oriented.
- The main interaction is one choice and one start action. Technical target,
  Unit-ID, range and function-code controls do not appear in the ordinary scan
  flow.
- Choosing `active_validation` requires an administrator and explicit
  confirmation on the web and equivalent acknowledgement in CLI/TUI. The UI
  reports when the local Pi policy refuses or has no matching approved point.
- The report leads with “what was found”, “why it matters”, confidence and
  recommended action; raw protocol evidence is an expandable detail.
- Findings continue through the existing findings surfaces.

## 9. Safety and evidence

NIST SP 800-82 Rev. 3 warns that active scanning can destabilise sensitive OT
devices. Therefore each result records precisely what was sent and what was not
sent. Read-only paths make write functions structurally impossible, while the
active-validation path exposes only the two single-point functions behind both
permission gates.

Required audit fields include submode/version, effective limits, target/range
count, read/write/restore requests sent, retries, timeouts, skipped work,
change-ticket reference, evidence sources, elapsed time, partial-result flag and
termination reason. Secrets and complete raw packet bodies do not enter
application logs.

## 10. Call paths that must be verified

Before an integration task is complete, grep and test every constructor/call
site for:

- `ScanRunner` — headless/CLI and `ScanProgressScreen`;
- `ScanProgressScreen` — TUI home/category/mode flows;
- backend command creation, persistence, delivery and recovery;
- `AgentCommand` parsing and daemon `run_headless_scan` call;
- `HostPayload`, `ScanIngestRequest`, scan detail and host detail;
- generated frontend OpenAPI types and their consuming components.

This list is mandatory because the TUI calls the scan runner directly and does
not pass through a separate orchestrator.
