# TASKS — NSPi OT inventory and Modbus assessment

Statuses below track the implementation. Execute tasks in dependency order. A
task is complete only after its focused tests and the relevant layer gate pass.
Never run a repository-wide formatter.

## Milestones

- **M1 — contract, safety policy and laboratory:** Tasks 1-2.
- **M2 — useful local/Pi scan with three submodes:** Tasks 3-8.
- **M3 — persisted product result and controls:** Tasks 9-12.
- **M4 — optional vendor depth and TCC evaluation:** Tasks 13-14.

## Task 1: Freeze the submode contract and safety ADR

- **Description**: Finalise `NspiOptions`, `NspiSubmode`, Modbus mapping,
  single-point validation and industrial-observation schemas. Add an ADR
  recording why NSPi has three active submodes, why write validation needs two
  independent permission gates, and why DoS/replay/spoofing stay outside the
  normal pipeline. Omitted options mean `inventory`; non-NSPi commands reject
  them. Keep the ordinary wire request limited to submode, acknowledgement and
  audit reference; expert target/range/write details belong to the local
  installation policy.
- **Dependencies**: —
- **Target Files**: `contracts/openapi/openapi.yaml`,
  `hardware-agent/src/agent/normalize/contracts.py`,
  `hardware-agent/src/agent/transport/command_channel.py`,
  `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/commands.py`,
  `backend/src/api/schemas/agent_frames.py`, `frontend/src/types/openapi.d.ts`,
  `docs/adr/ADR-012-nspi-active-modbus-safety.md`, contract-fidelity tests.
- **Success Criteria**: One versioned wire shape represents `inventory`,
  `read_only_mapping` and `active_validation`; all bounds validate on both trust
  boundaries; old commands/payloads remain valid; non-NSPi misuse fails;
  read-only paths cannot receive validation operations; agent/backend/OpenAPI
  fidelity tests pass.
- **Status**: IN PROGRESS — result contracts are frozen; command-side
  `NspiOptions` and the ADR remain.

## Task 2: Pin PyModbus and build the deterministic Modbus laboratory target

- **Description**: Add one tested PyModbus 3.x dependency and lock it. Build a
  test-only server fixture with device identification, all four read spaces,
  legal/illegal ranges, exception/delay behaviour and explicitly disposable
  writable coil/register points. Do not add Scapy or MATRIX as production
  dependencies.
- **Dependencies**: 1
- **Target Files**: `hardware-agent/pyproject.toml`, `hardware-agent/uv.lock`,
  `hardware-agent/tests/fixtures/`, `hardware-agent/tests/integration/`.
- **Success Criteria**: The fixture starts/stops deterministically without root,
  exercises the pinned client API, produces no external network traffic and can
  simulate reads, writes, exceptions, timeouts and restoration; tests reset
  writable state between cases; hardware-agent tests pass.
- **Status**: IN PROGRESS — PyModbus is pinned and the local target covers FC43,
  four data spaces, invalid ranges and resettable write points; the remaining
  timeout/restoration assertions belong to the mapping/validation increments.

## Task 3: Interpret existing NSE Modbus evidence

- **Description**: Add Modbus internal models and a tolerant interpreter for
  the existing `modbus-discover` `ScriptResult`. Prefer structured NSE data and
  support text-only fixtures for Nmap-version compatibility. Preserve Unit IDs,
  identification, exceptions and evidence provenance.
- **Dependencies**: 1
- **Target Files**: `hardware-agent/src/agent/ot/modbus/models.py`,
  `hardware-agent/src/agent/ot/modbus/nse.py`,
  `hardware-agent/src/agent/scanner/models.py`, focused unit tests and XML
  fixtures.
- **Success Criteria**: Realistic single/multiple Unit-ID and error fixtures
  normalise deterministically; malformed output cannot fail the scan; no new
  packet is sent by this task.
- **Status**: COMPLETE

## Task 4: Implement the narrow read-only Modbus client

- **Description**: Wrap PyModbus connection, FC43/MEI 14 and FC01-04 in a small
  read-only adapter. Normalise protocol exceptions, local errors and timeouts.
  Support cancellation by closing the active client. Expose no write or raw PDU
  API.
- **Dependencies**: 2, 3
- **Target Files**: `hardware-agent/src/agent/ot/modbus/client.py`, focused unit
  and integration tests.
- **Success Criteria**: Identification and every allowed read work against the
  fixture; timeout/cancel close the connection; API-surface and request-spy
  tests prove that no write function is reachable.
- **Status**: IN PROGRESS — FC43 and cancellation are complete; FC01-FC04 are
  deferred to `read_only_mapping`.

## Task 5: Build the bounded address mapper

- **Description**: Implement validated target selection, range chunking,
  request budgets, sequential execution, delays, capture modes, hashing and
  optional illegal-address bisection. Never bisect timeouts. Stream bounded
  summaries instead of allocating a full address-space scan. Resolve plans
  automatically in site-profile, vendor-profile, built-in-baseline order and
  freeze the conservative baseline constants with the laboratory tests.
- **Dependencies**: 4
- **Target Files**: `hardware-agent/src/agent/ot/modbus/mapper.py`, policy and
  mapping unit/integration tests.
- **Success Criteria**: Only discovered/open/authorised targets run; exact
  ranges and Unit IDs are respected; an unconfigured installation still gets a
  clearly labelled baseline sample; caps cannot be raised by input; request
  count is deterministic; partial observations survive error/cancel/deadline;
  raw values appear only when enabled by installed policy.
- **Status**: PENDING

## Task 6: Implement guarded active validation and restoration

- **Description**: Add a separate adapter/state machine exposing only FC05 and
  FC06. Enforce the intersection of hard limits, local `OtAutomationPolicy` and the
  acknowledged scan request. Implement read-before-write, expected-value guard,
  one test write, read-back, one mandatory best-effort restoration and final
  verification. Resolve write points only from installer-prepared local policy;
  never ask the ordinary operator for addresses, derive write targets from a
  mapping result or retry a test write.
- **Dependencies**: 2, 4
- **Target Files**: `hardware-agent/src/agent/ot/policy.py`,
  `hardware-agent/src/agent/ot/modbus/validation.py`, configuration loading and
  focused unit/integration tests.
- **Success Criteria**: Secure default disables validation; a remote request
  cannot override local refusal; wrong expected value sends no write; only the
  exact configured FC05/FC06 is sent; cancellation after a write waits for the
  restoration-critical section; unverified restoration stops all later
  validations and remains visible in the result; read-only code cannot import
  or receive the validation adapter.
- **Status**: PENDING

## Task 7: Integrate all NSPi submodes without changing NSE coverage

- **Description**: Add the `ot_inspection` stage after deep inspection and
  before normalisation. Consume Task 3 output first, use Task 4 only as a useful
  fallback, invoke Task 5 only for configured mapping and invoke Task 6 only for
  `active_validation`. Thread submode, local policy and cancellation through
  `ScanRunner`; extend progress weights/events and partial metadata.
- **Dependencies**: 3, 4, 5, 6
- **Target Files**: `hardware-agent/src/agent/scanner/stages.py`,
  `hardware-agent/src/agent/scanner/runner.py`,
  `hardware-agent/src/agent/scanner/progress.py`,
  `hardware-agent/src/agent/config.py`, scanner tests.
- **Success Criteria**: The exact 14 current NSPi NSE scripts still run in all
  submodes; their findings remain; complete NSE identification prevents a
  duplicate fallback; OT concurrency is one; zero Modbus hosts succeeds;
  cancellation has the correct normal/restoration-critical semantics.
- **Status**: IN PROGRESS — `inventory` is integrated; mapping and validation
  dispatch remain.

## Task 8: Normalise findings and write the complete local JSON

- **Description**: Serialise industrial services, ranges and validation steps
  into `HostPayload`; add evidence-backed read/write findings and policy/audit
  counters; reuse the existing workspace writer. Keep ordinary inventory
  separate from findings and raw values off by default.
- **Dependencies**: 7
- **Target Files**: `hardware-agent/src/agent/normalize/contracts.py`,
  `hardware-agent/src/agent/normalize/findings.py`,
  `hardware-agent/src/agent/normalize/ot.py`,
  `hardware-agent/src/agent/scanner/stages.py`, workspace/contract/finding tests.
- **Success Criteria**: Local JSON validates and round-trips; evidence identifies
  Unit/range/operation and restoration; port 502 alone creates no finding;
  confirmed FC05/FC06 read-back creates the intended finding; unverified restore
  is prominent; legacy non-NSPi payloads are unchanged.
- **Status**: IN PROGRESS — inventory observations and audit counters are in the
  local JSON; range/validation findings remain.

## Task 9: Thread submode and local automation policy through CLI, TUI and daemon

- **Description**: Give CLI/TUI a safe default and a simple submode choice,
  persist the choice/acknowledgement on backend commands, deliver it over
  WebSocket and pass it through headless execution. Load mapping, vendor and
  validation details from the independent installation-scoped
  `OtAutomationPolicy` on the Pi. Trace every `ScanRunner` and
  `ScanProgressScreen` call site.
- **Dependencies**: 1, 7
- **Target Files**: `hardware-agent/src/agent/cli.py`,
  `hardware-agent/src/agent/headless.py`, `hardware-agent/src/agent/daemon.py`,
  `hardware-agent/src/agent/tui/screens/scan_mode.py`,
  `hardware-agent/src/agent/tui/screens/scan_progress.py`, relevant TUI screens,
  `backend/src/api/models/command.py`, command services/schemas/routers and a
  migration.
- **Success Criteria**: CLI, direct TUI and remote daemon deliver identical
  effective submodes; omission selects inventory; active validation cannot
  start without matched local operations, risk acknowledgement and local
  enablement; the ordinary scan command contains no arbitrary target/range/write
  values; command redelivery/recovery preserves options; constructor/call-site
  grep is recorded in review.
- **Status**: IN PROGRESS — all existing NSPi entry points use the automatic
  inventory default; explicit submode selection and local policy remain.

## Task 10: Persist OT observations and expose tenant-safe reads

- **Description**: Add industrial-service, Modbus-unit, Modbus-range and
  Modbus-validation tables, idempotent ingest, bounded JSON fields and scan/host
  detail schemas. Link services to scan hosts and ports. Persist every
  validation step and restoration outcome without persisting an authorisation
  token.
- **Dependencies**: 1, 8
- **Target Files**: `backend/src/api/models/persistence.py`,
  `backend/src/api/services/persistence.py`, `backend/src/api/services/read.py`,
  `backend/src/api/schemas/scan.py`, `backend/src/api/schemas/read.py`, Alembic
  migration and backend tests.
- **Success Criteria**: Upgrade/downgrade works; repeated ingest is idempotent;
  data cannot cross organisations; scan and latest-host detail reproduce the
  payload; limits reject oversized value lists; restoration failures survive
  reads; backend lint and tests pass.
- **Status**: PENDING

## Task 11: Reuse current vulnerability enrichment for reliable OT fingerprints

- **Description**: Create a small deterministic mapping catalogue from supported
  vendor/product/version fingerprints to CPE candidates with explicit
  confidence. Send only high-confidence candidates through the existing
  NVD/KEV/EPSS path; preserve ambiguous inventory without guessing. Add the
  confirmed unauthenticated-write finding without assigning a fabricated CVE.
- **Dependencies**: 8, 10
- **Target Files**: Modbus fingerprint normaliser, backend enrichment job
  creation, finding confidence/risk integration, catalogue fixtures and tests.
- **Success Criteria**: Supported exact fingerprints enqueue the existing job;
  ambiguous/missing versions do not; NSE CVE enrichment behaves as before;
  read/write findings show their direct evidence and source provenance.
- **Status**: PENDING

## Task 12: Present NSPi submodes and OT results in TUI and web

- **Description**: Add the three NSPi submodes to the TUI and authorised web
  command flow. Present protocol/Unit/range/validation summaries in TUI and web
  scan/host detail. Active validation requires a separate, explicit confirmation
  explaining that only installer-approved points will be used and showing the
  change-ticket reference. Keep IP/Unit/range/function/value inputs out of the
  ordinary operator flow. Use generated OpenAPI types and keep large/raw values
  collapsed.
- **Dependencies**: 9, 10
- **Target Files**: `hardware-agent/src/agent/tui/screens/scan_mode.py`,
  `hardware-agent/src/agent/tui/screens/scan_progress.py`,
  `hardware-agent/src/agent/tui/screens/scan_view.py`, frontend scan/host
  components, agent command hook/control, generated types and focused tests.
- **Success Criteria**: No-Modbus, confirmed, partial, timeout, exception,
  mapping and validation states are distinguishable; only administrators can
  remotely request validation; local-policy refusal and restoration failure are
  clear; primary results explain risk/evidence/action without requiring NSE,
  CPE or exception-code knowledge; no generic write/exploit button appears;
  non-NSPi scans are unchanged; frontend lint, typecheck, tests and build pass.
- **Status**: PENDING

## Task 13: Add the optional Redpoint Schneider laboratory adapter

- **Description**: Complete license review, document operator installation and
  checksum pinning, and add a separate Nmap stage for `modicon-info.nse`. Gate
  it on explicit authorisation and a prior Schneider fingerprint. Parse output
  using the existing NSE/XML path. Do not modify the default NSPi script tuple.
- **Dependencies**: 3, 7, legal/license decision
- **Target Files**: optional vendor-probe configuration, scanner stage/parser,
  installation documentation and fixture-based tests.
- **Success Criteria**: Default scans never execute it; a configured Schneider
  lab fixture selects it automatically from the fingerprint/submode policy;
  the ordinary operator never chooses a script; missing scripts become a
  skipped optional probe; FC90 evidence is labelled; current 14-script
  regression remains green.
- **Status**: PENDING

## Task 14: Build the TCC evaluation matrix and Raspberry benchmarks

- **Description**: Turn the article and MATRIX threat categories into a
  repeatable isolated-lab evaluation. Validate the three product submodes;
  separate disposable experiments demonstrate why multiple writes, overflow,
  DoS, replay and spoofing do not belong to the normal pipeline. Benchmark
  identical policies on Pi 3 B+ and Pi 4 4 GB and document placement and
  maintenance-window rules for the supplied topology and generic OT networks.
  Include a plug-to-report usability test with a participant who has no Modbus
  expertise.
- **Dependencies**: 8, 11, 12; Task 13 optional
- **Target Files**: `docs/lab/`, benchmark scripts/configuration, TCC result
  templates and PCAP assertion documentation.
- **Success Criteria**: Another researcher can reproduce inputs and results;
  inventory/mapping PCAPs contain no writes; validation PCAP contains only the
  exact test write and restoration; Pi comparison includes elapsed time, CPU,
  peak RSS, request/timeouts and JSON size; limitations and ethical boundary
  are explicit; the participant can start inventory and identify the principal
  risks and recommended actions without entering protocol parameters.
- **Status**: PENDING

## Required gates

- `hardware-agent/`: `uv run pytest` (format/lint remain in its existing hooks).
- `backend/`: `uv run ruff check src tests` and `uv run pytest`; never run
  `ruff format`.
- `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
- Contract generation/fidelity commands already used by the repository.

Every task must run its focused tests first. Run full layer gates at milestone
boundaries and again before declaring the feature complete.
