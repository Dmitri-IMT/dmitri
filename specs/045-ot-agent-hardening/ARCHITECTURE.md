# ARCHITECTURE — OT agent hardening

Implementation design for [`TRUTH.md`](TRUTH.md). The evidence for every change is
[`AUDIT.md`](AUDIT.md). This document **supersedes
[`specs/042-nspi-modbus-ot/ARCHITECTURE.md`](../042-nspi-modbus-ot/ARCHITECTURE.md) §7** (OT
persistence and reads) and leaves the rest of 042 standing.

Decisions this design is bound by and does not re-open:
[`ADR-019`](../../docs/adr/ADR-019-v2-active-scanning-and-agent-hardening.md) (egress-only,
untrusted device data, identity may not widen scope, least privilege, bounds reachable, read-only
proven), [`ADR-018`](../../docs/adr/ADR-018-nspi-active-modbus-safety.md) (the Modbus safety
boundary), [`ADR-010`](../../docs/adr/ADR-010-scan-contingency-policy.md) §1 and §3 (partial versus
stopped; no new terminal state), [`ADR-012`](../../docs/adr/ADR-012-headless-exit-code-contract.md)
(exit codes).

## 0. Base state — read this before writing code

The worktree branch `audit/nspi-137` is **not** the base for this work. Two audited commits
(`6e19062`, `79c559d`) live only on `main` (`f68397c`):

| Fact | Where it is true |
|---|---|
| `runner.py` success path uses `terminated_by="error" if partial_result else "completed"` and `interrupted_stage=partial_stage` (finding 16) | `main` only — `git show main:hardware-agent/src/agent/scanner/runner.py` lines 296-311 |
| `-sV` removed from `discovery_arguments()` and `NSPI_PASS2_ARGS`; `port_stage_scripts()` deleted; `effective_version_intensity()` added (finding 17) | `main` only |
| Several `.claude/docs/` findings already repaired | `main` only |

**Branch this feature from `main`.** On `audit/nspi-137` findings 16 and 17 appear already
correct, and a fix written there will be a no-op that regresses on merge.

`main` cannot migrate (blocker 1). The Alembic merge revision (§8) therefore lands first, before
any other task. The no-database failure (§7.2) lands second and never before it.

## 1. System context

The feature touches four points in the existing pipeline and one new backend read surface. Nothing
about stage ordering changes.

```text
                      discovery  (network_discovery)
                          |
                      port scan  (port_discovery / stages.run_port_stage)
                          |
              deep inspection  (vulnerability_detection / stages.run_deep_inspection_stage)
                          |     [C] one bounded -sV recovery pass when a host with open
                          |         ports produced no deep-stage element
                          v
              OT inspection  (stages.run_ot_inspection_stage)
                 [A] untrusted device data bounded at parse, escaped at render
                 [B] device-claimed identity may only narrow the mapping profile
                 [D] every active path paced, counted and time-bounded
                          |
                   normalisation  (normalize/contracts.ScanPayload)
                 [E] raw values and their aggregates stay in memory; only a
                     keyed digest crosses the payload boundary
                          |
            +-------------+--------------------+
            |                                  |
     workspace JSON                     signed ingest
     TUI scan_view (escaped)         POST /api/v1/scans
                                            |
                                  persistence  (services/persistence
                                   + services/industrial)
                                   industrial_services / modbus_units
                                   findings.modbus_unit_id
                                            |
                                     read  (services/read)
                                   GET /hosts, /hosts/{id}, /scans/{id},
                                   /findings   [F] one bad row degrades,
                                               never 500s the list
```

Scan outcome ([G], §6) is decided in `ScanRunner._run()` and consumed by `headless.py` (exit code),
`scanner/workspace.prune_logs` (retention classification) and the TUI partial badge. Schema history
and the test harness ([H], §7-8) are backend-only.

## 2. Data model and contracts

### 2.1 Four shapes, deliberately different

| Shape | Where | Carries raw process values? | Carries value aggregates? |
|---|---|---|---|
| In-memory dataclass `ModbusAddressRange` | `agent/ot/modbus/models.py` | yes, transiently, to compute the digest | yes, `None` when absent |
| Wire/workspace payload `ModbusAddressRangePayload` | `agent/normalize/contracts.py`, `backend/.../schemas/industrial.py`, OpenAPI | **no** | **no** |
| Persisted row JSON `modbus_units.address_ranges_json` | Postgres | **no** | **no** |
| Read view `ModbusAddressRangeView` | `backend/.../schemas/read.py`, OpenAPI | **no** | **no** |

Raw values and their aggregates exist only inside the agent process, for the lifetime of one host's
mapping. They are not written to the workspace JSON, the wire, the database, the logs, or any
operator-facing surface. This satisfies "raw process values are not persisted by default" and
"never written to logs or operator-facing output" with no runtime switch, and it means the read
path needs no value filter to get wrong.

### 2.2 Contract changes — agent payload and ingest

Removed from `ModbusUnitPayload` (both sides) and from OpenAPI:

- `validations: list[ModbusValidationPayload]` — and the whole `ModbusValidationPayload`
  component. The write-validation depth does not exist (out of scope, TRUTH.md); the contract
  carries no field for it.

Removed from `ModbusAddressRangePayload` (both sides) and from OpenAPI:

- `values`, `nonzero_count`, `value_min`, `value_max` — process data, see §2.1.
- `value_sha256` — reversible over a 16-possibility value space (four coils).

Added to `ModbusAddressRangePayload`:

- `value_digest: str | None` — `"hmac-sha256:<64 hex>"`, or `null` when no value was read or no
  digest key is installed. Pattern-validated on both sides.

Added to `ModbusDeviceIdentificationPayload`:

- `truncated: bool = False` — set when any string was cut to `MAX_DEVICE_STRING_CHARS` or any
  object was dropped at `MAX_IDENTIFICATION_OBJECTS`. This is how "the limit applied is evident"
  reaches the operator and the API.

Added to `ModbusTcpServicePayload`:

- `write_requests_sent: int = 0` — measured, see §5.4.

Symmetry: `agent/normalize/contracts.py` gains `model_config = ConfigDict(extra="forbid")` on the
four remaining Modbus payload models (`ModbusTcpServicePayload`, `ModbusUnitPayload`,
`ModbusDeviceIdentificationPayload`, `ModbusAddressRangePayload`) plus `max_length` on every
list and `constr(max_length=...)` on every device-supplied string, so agent-side validation is
at least as strict as the backend's.

### 2.3 Constants

| Constant | Value | Module |
|---|---|---|
| `MAX_DEVICE_STRING_CHARS` | 128 | `agent/ot/untrusted.py` |
| `MAX_IDENTIFICATION_OBJECTS` | 16 | `agent/ot/untrusted.py` |
| `MAX_IDENTIFICATION_SOURCES` | 8 | `agent/ot/untrusted.py` |
| `MAX_ADDRESS_RANGES_PER_UNIT` | 32 | `agent/ot/untrusted.py` |
| `MAX_OT_STAGE_SECONDS` | 600 | `agent/ot/policy.py` |
| `MAX_OT_HOST_SECONDS` | 90 | `agent/ot/policy.py` |
| `DIGEST_PREFIX` | `"hmac-sha256:"` | `agent/ot/digest.py` |
| `DIGEST_KEY_BYTES` | 32 | `agent/ot/digest.py` |
| `INDUSTRIAL_OBSERVATION_RETENTION_DAYS` | 180 | `backend/src/api/core/config.py` |

Existing `ot/policy.py` ceilings (`MAX_MAPPING_*`, `inter_request_delay_ms`) are unchanged.

### 2.4 Persistence — two tables, JSON beneath

Supersedes 042 §7's four tables. `modbus_ranges` and `modbus_validations` are **not** built.

```text
scan_hosts ──┬── industrial_services ── modbus_units ──┬── (address_ranges_json)
             │        │                                └── (identification_json)
ports ───────┘        └── (evidence_sources_json)
findings.modbus_unit_id ─────────────────────────────────┘  (nullable FK)
```

`industrial_services`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `scan_host_id` | int FK `scan_hosts.id`, indexed | owning scan host |
| `port_id` | int FK `ports.id`, nullable, indexed | the TCP port row, when one exists |
| `protocol` | text | `'modbus_tcp'`, CHECK-constrained |
| `port` | int | denormalised so a read needs no join when `port_id` is null |
| `confidence` | text | `'suspected'` / `'confirmed'`, CHECK-constrained |
| `mapping_source` | text nullable | e.g. `generic_baseline`, `site:<name>` |
| `evidence_sources_json` | JSONB | bounded `list[str]` |
| `write_requests_sent` | int | measured counter, default 0 |
| `created_at` | timestamptz | |

Unique: `(scan_host_id, protocol, port)`.

`modbus_units`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | the identity a finding points at |
| `industrial_service_id` | int FK `industrial_services.id`, indexed | |
| `unit_id` | int | 0-255 |
| `status` | text | `responding`/`exception`/`timeout`/`error`/`skipped`, CHECK-constrained |
| `exception_code` | int nullable | |
| `error` | text nullable | bounded device text |
| `identification_json` | JSONB nullable | the whole `ModbusDeviceIdentification`, `objects` and `truncated` included |
| `identification_sources_json` | JSONB | bounded `list[str]` |
| `address_ranges_json` | JSONB | bounded list of `{address_space, start_address, count, status, exception_code, label, observed_at, value_digest}` |
| `created_at` | timestamptz | |

Unique: `(industrial_service_id, unit_id)`.

Address ranges, identification extras and evidence sources are JSON **on the row that owns them**
because they are only ever read as part of that row. They are bounded at ingest by the payload
models (§2.3), so the JSON cannot grow without a contract change.

`findings.modbus_unit_id`: nullable `int` FK `modbus_units.id`, indexed. This is the risk
attribution point. `cpes` is keyed on `(port_id, cpe)` and cannot say which of several units
behind one serial gateway a CPE came from; unit-level attribution is the reason units become a
table. Existing findings keep `NULL`, which reads as "attributed to the port, not to a unit".

Both tables get `ENABLE ROW LEVEL SECURITY`, the Supabase-role revoke, and
`GRANT SELECT, INSERT, UPDATE` plus sequence usage to `dmitri_runtime`, exactly as
`20260905_19_home_activity_feed.py` does. Organisation isolation is inherited: every read reaches
these rows through `scan_hosts -> scans.org_id`, the same path as ports and CPEs.

**Retention.** Industrial observation rows are scan-scoped and die with their scan. The stated
retention period is `INDUSTRIAL_OBSERVATION_RETENTION_DAYS = 180` days from scan ingestion,
recorded in `backend/src/api/core/config.py`, in the OpenAPI description of
`IndustrialServiceView`, and in `docs/DEV-SETUP.md`. No pruning job exists in the backend today and
this feature does not build one — see §10 for that limitation.

### 2.5 Read surface

New views in `backend/src/api/schemas/read.py`, attached to `ScanHostView.industrial_services` and
`HostDetailResponse.industrial_services`:

- `IndustrialServiceView` — `protocol`, `port`, `confidence`, `mapping_source`,
  `evidence_sources`, `units`.
- `ModbusUnitView` — `id`, `unit_id`, `status`, `exception_code`, `error`, `identification`
  (`ModbusDeviceIdentificationView`, `truncated` included), `identification_sources`,
  `address_ranges`.
- `ModbusAddressRangeView` — `address_space`, `start_address`, `count`, `status`,
  `exception_code`, `label`, `observed_at`, `value_digest`.

Nothing else. No `values`, no `nonzero_count`, no `value_min`, no `value_max` — the fields do not
exist anywhere behind the read path, so there is nothing to leak.

`FindingRead` gains `modbus_unit: FindingModbusUnitRef | None` (`{id, unit_id, port}`), so a
vulnerable firmware names the device an engineer must walk to.

`ScanHostView`, `HostSummary` and `HostDetailResponse` each gain
`unreadable_fields: list[str] = []` — the degradation signal for finding 7, see §7.1.

### 2.6 Keyed digest — where the secret lives

The digest is computed **on the Pi**, because the backend must never see the values it is derived
from.

- **Material**: 32 random bytes, hex-encoded.
- **Scope**: one per organisation. Generated on demand by `backend-provision-agent` and stored in
  `orgs.ot_digest_key` (text, nullable, added by the same migration). The CLI prints it to stdout
  once per provisioning, alongside the device key it already prints, so every appliance in an org
  shares one key and digests stay comparable across appliances and across scans.
- **On the Pi**: `DMITRI_OT_DIGEST_KEY` (64 hex characters) or, when unset,
  `~/.config/dmitri/ot-digest-key` (mode 0600), resolved by
  `agent/ot/digest.default_digest_key_path()` with the same `XDG_CONFIG_HOME` / `LOCALAPPDATA`
  convention `ot/policy.default_ot_policy_path()` already uses.
- **Computation**: `HMAC-SHA256(key, canonical)` where `canonical` is
  `json.dumps([address_space, start_address, count, values], separators=(",", ":"), ensure_ascii=True)`.
  Address and space are inside the MAC so the same value pattern at two addresses gives two
  digests.
- **Absence**: no key installed means `value_digest=None`, the range is still recorded with its
  status, and `build_metadata` stamps `modbus_digest_key_present: false`. Scanning never fails for
  a missing key.
- **The backend never uses the key.** It stores the digest string and compares digests for
  equality. No API returns the key, and no read path loads `orgs.ot_digest_key`.

Residual risk, stated deliberately: a backend compromise that reads `orgs.ot_digest_key` could
brute-force digests over a small value space. The alternative — a per-appliance key generated on
the Pi and never sent to the server — removes that risk but makes digests incomparable between two
appliances in one organisation, which TRUTH's "organisation-scoped secret" wording rules out. See
§10.

## 3. [A] Untrusted device data

### 3.1 Bounded at parse

New `agent/ot/untrusted.py`:

- `bound_text(value: str | None) -> tuple[str | None, bool]` — truncates to
  `MAX_DEVICE_STRING_CHARS`, strips control characters, returns whether it cut.
- `bound_objects(objects: Mapping[str, Any]) -> tuple[dict[str, str], bool]` — keeps the first
  `MAX_IDENTIFICATION_OBJECTS` by numeric object id, bounds each value, returns whether it
  dropped.
- `bound_sources(values: Iterable[str]) -> list[str]` — dedupes and caps at
  `MAX_IDENTIFICATION_SOURCES`.

Applied in `ot/modbus/client._decode_device_information` (FC43/MEI-14) and
`ot/modbus/nse._parse_identification` (script output). `ModbusDeviceIdentification.truncated` is
the OR of every bound applied. `ModbusUnit.error` is bounded the same way. This closes the
`_decode_device_information` bound gap without relying on the PDU frame size.

### 3.2 One bad response affects one response

- `client.probe_device_identification` and `client.ModbusReadSession.read` catch `Exception` around
  decoding, after the cancellation checks, and map it to `status="error"` with the exception type in
  `error`. pymodbus decode failures raise `KeyError`, `IndexError`, `AttributeError` and
  `struct.error`, none of which is in the present tuple.
- `inventory._inventory_port` wraps **each** probe in its own `try/except`, so unit 3 failing
  cannot end the loop over units 1, 2, 4.
- `inventory.inventory_modbus_host`'s outer `except Exception` no longer replaces the service. It
  keeps the `ModbusService` built so far — the units already merged from `modbus-discover` included
  — sets `confidence` to what the evidence supports, and appends `"inventory-error"` to
  `evidence_sources`. The exception is logged with `LOGGER.exception`; nothing is swallowed.

### 3.3 Parse failures are recorded

`nse._parse_unit_id` stops using `int(value, 0)` — base 0 rejects `"08"`. It becomes explicit:
try base 10, then `0x`/`0b`/`0o` prefixes, else return `None`. `nse.parse_modbus_discover` keeps
every unit it could read, counts what it could not into
`ModbusService.parse_failures: int` (new field), and logs each at `WARNING` with the offending key.
One unreadable sid no longer discards a whole script's units. `build_metadata` stamps
`modbus_parse_failures`.

### 3.4 Classification by meaning, not by substring

`nse._is_error_entry` drops the `or "exception" in value.lower()` clause. Only the key decides:
`key.rsplit(".", 1)[-1].lower() in {"error", "exception"}`. A product named
`"ExceptionLogger 3000"` is a product name.

### 3.5 Absent data summarises as absent

`mapper._materialise` HMACs readable values then drops the list. `ModbusAddressRange` keeps
status, bounds, label, and `value_digest`. Empty reads and `capture_values="none"` leave
`value_digest` unset. Process fields never exist on the in-memory range.

### 3.6 A missing lookup fails visibly

`stages.run_port_stage` restores the defensive read it replaced: `results.get(ip)` with an explicit
`raise UnitScanError` (or `KeyError` with the ip in the message) when a caller did not pre-seed the
ip, instead of `results[ip]` depending on every caller having done so.

### 3.7 Escaped at render

New `agent/tui/markup.py` with `safe(value: object) -> str` wrapping `rich.markup.escape`. Every
device-supplied string rendered by `tui/screens/scan_view.py` — vendor name, product name, model
name, user application name, unit error, port banner and version — goes through it. `DESIGN.md`
owns the layout and copy; this module is the mechanism.

## 4. [B] Scope and consent

### 4.1 Identity may narrow, never widen

`mapper.resolve_mapping_plan` keeps its site-profile precedence and adds one gate. New predicate in
`ot/policy.py`:

```
def profile_is_conservative(profile: MappingProfile) -> bool
```

True when the profile is no broader than `GENERIC_BASELINE_RANGES` on every axis: total addresses
per space, `block_size`, `capture_values` (`none` < `summary` < `raw`), range count, and configured
unit-id count. A profile matched **only** on `vendors`/`products` is applied only when this
predicate holds; otherwise the generic baseline applies and `mapping_source` records
`generic_baseline` with `"identity-not-corroborated"` appended to `service.evidence_sources`.
Profiles matched on `cidrs` or `macs` are unaffected, in either direction — that is the
corroboration ADR-019 §4 requires.

### 4.2 Depth validated where it acts

New `agent/config.validate_nspi_depth(scan_mode, nspi_submode) -> None`, raising
`UnsupportedScanDepth` (new `FatalScanError` subclass in `scanner/errors.py`). It refuses
`active_validation` and rejects a submode with a non-`nspi` mode — the logic `headless.py:56-69`
holds today.

`ScanRunner.__init__` calls it before any state is built, so the refusal happens before any active
request and no result can stamp `nspi_submode: "active_validation"` into metadata.
`headless.validate_inputs` delegates to the same function and keeps raising `InvalidScanInput` for
its CLI-shaped message, so the CLI still fails early with good wording. The safety decision now
lives in the object that acts on it.

**CLAUDE.md integration rule.** This is a validation added to `ScanRunner`'s constructor, so every
construction site is accounted for in §9:

| Call site | File | Responsibility |
|---|---|---|
| `run_headless_scan` | `hardware-agent/src/agent/headless.py:111` | already validates; delegates to the shared function |
| `ScanProgressScreen._start_scan` | `hardware-agent/src/agent/tui/screens/scan_progress.py:147` | must catch `UnsupportedScanDepth` and surface a failure state rather than crash the screen |
| `HomeScreen` -> `ScanProgressScreen` | `hardware-agent/src/agent/tui/screens/home.py:74` | passes `nspi_submode`; no new parameter, but the refusal path must be reachable from here |

No new `ScanRunner` constructor parameter is introduced. The OT wall-clock ceiling (§5.3) is a
module constant resolved inside `stages.run_ot_inspection_stage`, deliberately, so the runner
signature and both TUI call sites stay unchanged.

## 5. [D] Bounds on active scanning

### 5.1 Identification pacing

`inventory.inventory_modbus_host` and `_inventory_port` take
`policy: OtAutomationPolicy` and `sleep: Callable[[float], None] = time.sleep`, and sleep
`policy.inter_request_delay_ms / 1000` before **every** FC43 probe, not only before mapper reads.
`stages.run_ot_inspection_stage` passes the `effective_policy` it already computes. The four-probe
count bound stays; the rate bound now exists. Connection-reuse policy stays as it is — one
connection per probe, closed in `finally` — and is stated in the code map.

### 5.2 Requests counted in one budget

`MappingBudget` already seeds `used` from `service.requests_sent`. Unchanged.

### 5.3 A reachable wall-clock ceiling

`AgentSettings.scan_deadline_s` defaults to `0` and nothing sets it, so `mapper._must_stop()`'s
deadline arm is dead (finding 9). Rather than give every mode a global deadline — a much broader
change — the OT stage declares its own ceiling, which is what ADR-019 §6 asks each active stage to
do:

`stages.run_ot_inspection_stage` computes

```
stage_deadline = min_not_none(caller_deadline, perf_counter() + MAX_OT_STAGE_SECONDS)
host_deadline  = min_not_none(stage_deadline, perf_counter() + MAX_OT_HOST_SECONDS)
```

and passes `host_deadline` to both `inventory_modbus_host` (new `deadline` parameter, checked
before each probe) and `map_modbus_service` (existing parameter). `caller_deadline` remains the
`scan_deadline_s` deadline when an operator sets one, so the two bounds compose and the tighter
wins.

On expiry the stage stops launching work, marks the remaining units/ranges `skipped`, keeps
everything already gathered, emits `ScanEvent(kind="ot_stage_deadline")` with the reason and the
limit that fired, and stamps `modbus_stage_deadline_reached: true` plus
`modbus_stage_deadline_seconds: <int>` in metadata. That flag does **not** set `partial_result`.
The run is still `terminated_by="completed"` with `interrupted_stage=None` unless port or deep
hosts were skipped. Both OT bounds are in force in the shipped default configuration.

### 5.4 Read-only proven, writes counted

New `agent/ot/modbus/readonly.py`:

- `READ_ONLY_METHODS: frozenset[str]` — `connect`, `close`, `is_socket_open`, `read_coils`,
  `read_discrete_inputs`, `read_holding_registers`, `read_input_registers`,
  `read_device_information`.
- `ReadOnlyModbusClient` — wraps a `ModbusTcpClient`, forwards only those names, and raises
  `WriteAttemptError` (an `AttributeError` subclass) for anything else, incrementing a counter.

`client.ModbusReadSession` and `client.probe_device_identification` hold a
`ReadOnlyModbusClient`, never the bare client. The read-only boundary stops being a naming
convention: `session._client.write_register(...)` now raises, and the test asserts reachability
rather than namespace absence.

`ModbusService.write_requests_sent` is a real field, incremented only by a write path (none
exists). `stages.build_metadata` replaces the literal `"modbus_write_requests_sent": 0` with
`sum(service.write_requests_sent for service in modbus_services)`. It reads `0` today by
measurement, and will read the truth the day `active_validation` ships.

### 5.5 Egress-only

`hardware-agent/tests/unit/test_egress_only.py` walks every module under
`hardware-agent/src/agent/` with `ast` and fails on `socket.bind`, `socket.listen`,
`socket.create_server`, `socketserver`, `asyncio.start_server`, `http.server`, `uvicorn` or
`ModbusTcpServer`. Test servers used by `hardware-agent/tests/integration/` bind `127.0.0.1` on an
ephemeral port and live under `tests/`, which the walk does not cover. This is an invariant test,
not a review note, as ADR-019 §2 requires.

## 6. [G] Scan outcome — restore ADR-010

`ScanRunner._run()`'s success path on `main` must return to ADR-010 §3's prescription:

```python
partial_result=port_units_skipped > 0 or deep_units_skipped > 0,
interrupted_stage=None,
terminated_by="completed",
```

No new terminal state, no ADR amendment — ADR-010 already decided this. `terminated_by="error"`
stays reserved for `CircuitBreakerError` (§1 of that ADR), so the two cases remain
distinguishable. `interrupted_stage` names a stage only on the cancel, timeout and fatal paths,
which already set it.

Consequences that follow for free and must be asserted, not re-implemented:
`workspace._FAILED_TERMINATED_BY` classifies the completed-with-partial run as a success again, and
`headless.py` still derives exit code 10 from `partial_result` (ADR-012 unchanged).

One consequence does **not** follow for free. `scan_progress.py:450-451` looks
`interrupted_stage` up in `_INTERRUPTED_STAGE_LABELS` and falls through to `"an earlier stage"` on
a miss — and `None`, the value ADR-010 requires for a finished scan, is exactly that miss
(AUDIT finding 19, pre-existing). Restoring §6 without fixing the label tells the operator a
completed scan was interrupted at an unnamed stage. The screen must therefore distinguish
"finished, some evidence incomplete" (`terminated_by="completed"`, `partial_result=True`,
`interrupted_stage is None`) from "stopped early" (`timeout` / `error` / `user_cancel`, with a
stage), and name a stage only in the second case. `DESIGN.md` owns the copy and the two states;
the mechanism is that `interrupted_stage is None` selects the first branch rather than a default
label.

### 6.1 Service evidence survives one lost step

`6e19062` made the deep stage the only source of real service and version evidence. When a host
with open ports produces no deep-stage host element, it now reports Nmap's port-number guesses and
no version at all.

`stages.run_deep_inspection_stage` gains one bounded recovery pass. When a host with open ports
yields `result is None`, `UnitScanError` or `BudgetExceeded`, the stage calls the existing and
currently unused `discovery.service_detection.detect_services(runner, host.ip, host.ports,
version_intensity=effective_version_intensity(settings.version_intensity), timeout=...)` once, and
merges the outcome with `merge_ports`. `detect_services` gains a `timeout: float | None = None`
parameter forwarded to `runner.run_xml`. If the recovery pass also returns nothing the host keeps
its port-stage evidence untouched and is still counted in `hosts_skipped`.

This keeps the deduplication `6e19062` bought — one `-sV` pass in the happy path — and restores
independence only where the happy path failed. Nothing is erased: `merge_ports` is still only
called with real results.

## 7. [F] [H] Stored records, schema history, test harness

### 7.1 One bad row does not fail a list

`read.py::_to_operating_system` currently lets a `ValidationError` escape into the `GET /hosts`
handler, so one unreadable `operating_system_json` fails the list for the whole organisation.

New private helper in `backend/src/api/services/read.py`:

```
def _validate_or_degrade(model, value, *, field, unreadable, context) -> Model | None
```

It validates, and on `ValidationError` logs a warning with the row identity, appends `field` to the
caller's `unreadable` list, and returns `None`. `_to_host_summary`, `_to_scan_host_view` and
`get_host_detail` collect that list into the new `unreadable_fields` response field. The same
helper guards `identification_json` and `address_ranges_json`. A malformed row is reported as
unavailable; the other hosts are returned; the request succeeds.

The row is never silently repaired or rewritten.

### 7.2 A test run without a database fails

`backend/tests/conftest.py:121-124` currently calls `pytest.skip("DATABASE_URL_TEST not set")` in
the `postgres_engine` fixture, so a bare run prints ~568 passed / 599 skipped and proves almost
nothing. That is how the two-head fork reached `main`.

Replace it with a `pytest_configure` hook in the same file:

```python
def pytest_configure(config):
    if DATABASE_URL_TEST is None:
        raise pytest.UsageError(
            "DATABASE_URL_TEST must point at the dmitri_test database. "
            "Run ./database.sh --test."
        )
```

`UsageError` aborts collection with exit code 4 before any test runs, names the reason, and cannot
be silenced by a marker, an environment variable, a `-p no:` plugin flag or a CLI option. The
`pytest.skip` call is deleted; the fixture keeps its `assert DATABASE_URL_TEST is not None`
narrowing. **No opt-out is added, and none may be added later.**

Ordering: this lands **after** the merge revision (§8). Before that, the suite cannot migrate, so
landing the failure first would break the suite for the whole team with no escape hatch.

### 7.3 Exactly one head

Blocker 1: `20260903_18` (this work) and `20260904_18` (`main`, PR #135) both claim
`20260811_17`; the chain forks into `20260905_19` and `20260908_19` and never rejoins.

```
20260811_17 ─┬─ 20260903_18 ── 20260908_19 ─┐
             └─ 20260904_18 ── 20260905_19 ─┴─ 20260912_20 (merge) ── 20260912_21
```

A **merge revision** resolves it. `20260903_18` is **not** repointed: it has been applied to
databases, and rewriting a released revision makes those databases diverge — TRUTH.md forbids it
("a schema change that has already been released is never rewritten").

## 8. Migrations

`backend/alembic/versions/20260912_20_merge_ot_and_activity_heads.py`

```python
revision = "20260912_20"
down_revision = ("20260905_19", "20260908_19")
```

Empty `upgrade()` / `downgrade()`. Its only job is to make `alembic heads` report one revision so
`alembic upgrade head` works from any earlier state. Lands first, alone, before every other task.

`backend/alembic/versions/20260912_21_industrial_observations.py`

`down_revision = "20260912_20"`. Creates `industrial_services` and `modbus_units` with the columns,
CHECK and UNIQUE constraints of §2.4; adds `findings.modbus_unit_id` with its FK and index; adds
`orgs.ot_digest_key`; enables RLS on both new tables; revokes the Supabase roles; grants
`SELECT, INSERT, UPDATE` plus sequence usage to `dmitri_runtime`. `downgrade()` reverses all of it
in order, so a database at head returns to a consistent earlier state.

## 9. New files and naming (mandatory)

`N` = new, `T` = touched.

### 9.1 `hardware-agent/`

| | Path | Change |
|---|---|---|
| N | `hardware-agent/src/agent/ot/untrusted.py` | `MAX_DEVICE_STRING_CHARS`, `MAX_IDENTIFICATION_OBJECTS`, `MAX_IDENTIFICATION_SOURCES`, `MAX_ADDRESS_RANGES_PER_UNIT`, `bound_text`, `bound_objects`, `bound_sources` |
| N | `hardware-agent/src/agent/ot/digest.py` | `DIGEST_PREFIX`, `DIGEST_KEY_BYTES`, `default_digest_key_path`, `load_digest_key`, `value_digest` |
| N | `hardware-agent/src/agent/ot/modbus/readonly.py` | `READ_ONLY_METHODS`, `ReadOnlyModbusClient`, `WriteAttemptError` |
| N | `hardware-agent/src/agent/tui/markup.py` | `safe()` — `rich.markup.escape` wrapper |
| T | `hardware-agent/src/agent/ot/policy.py` | `MAX_OT_STAGE_SECONDS`, `MAX_OT_HOST_SECONDS`, `profile_is_conservative()` |
| T | `hardware-agent/src/agent/ot/modbus/models.py` | `ModbusDeviceIdentification.truncated`; `ModbusAddressRange.value_digest` replaces `value_sha256`; `ModbusService.write_requests_sent`, `ModbusService.parse_failures`; `ModbusValidation` and `ModbusUnit.validations` deleted |
| T | `hardware-agent/src/agent/ot/modbus/client.py` | `ReadOnlyModbusClient` in `ModbusReadSession` and `probe_device_identification`; broadened decode `except`; bounded `_decode_device_information` |
| T | `hardware-agent/src/agent/ot/modbus/inventory.py` | `policy`, `sleep`, `deadline` parameters; per-probe isolation; non-destructive outer handler |
| T | `hardware-agent/src/agent/ot/modbus/mapper.py` | `profile_is_conservative` gate in `resolve_mapping_plan`; `_hash_values` -> keyed `value_digest`; `_materialise` absent-summary fix |
| T | `hardware-agent/src/agent/ot/modbus/nse.py` | `_parse_unit_id` base handling; recorded parse failures; `_is_error_entry` key-only; bounded identification |
| T | `hardware-agent/src/agent/scanner/stages.py` | OT stage/host deadlines; pacing policy passed to inventory; measured `modbus_write_requests_sent`; `modbus_parse_failures`, `modbus_stage_deadline_reached`, `modbus_stage_deadline_seconds`, `modbus_digest_key_present`; `results.get(ip)` guard; deep-stage `detect_services` recovery pass |
| T | `hardware-agent/src/agent/scanner/progress.py` | `ScanEventKind` gains `ot_stage_deadline` |
| T | `hardware-agent/src/agent/scanner/runner.py` | `validate_nspi_depth` in `__init__`; ADR-010 success path (`terminated_by="completed"`, `interrupted_stage=None`) |
| T | `hardware-agent/src/agent/scanner/errors.py` | `UnsupportedScanDepth(FatalScanError)` |
| T | `hardware-agent/src/agent/config.py` | `validate_nspi_depth()` |
| T | `hardware-agent/src/agent/headless.py` | `validate_inputs` delegates to `validate_nspi_depth` |
| T | `hardware-agent/src/agent/discovery/service_detection.py` | `timeout` parameter forwarded to `run_xml` |
| T | `hardware-agent/src/agent/normalize/contracts.py` | `extra="forbid"` + list/string caps on the Modbus models; `validations` and `ModbusValidationPayload` removed; `values`/`nonzero_count`/`value_min`/`value_max`/`value_sha256` removed; `value_digest`, `truncated`, `write_requests_sent` added |
| T | `hardware-agent/src/agent/tui/screens/scan_view.py` | every device string through `markup.safe` |
| T | `hardware-agent/src/agent/tui/screens/scan_progress.py` | **CLAUDE.md call site** — handles `UnsupportedScanDepth` from the `ScanRunner` constructor; `_handle_partial` names a stage only when one was interrupted (finding 19) |
| T | `hardware-agent/src/agent/tui/screens/home.py` | **CLAUDE.md call site** — constructs `ScanProgressScreen`; refusal path reachable |

### 9.2 `backend/`

| | Path | Change |
|---|---|---|
| N | `backend/alembic/versions/20260912_20_merge_ot_and_activity_heads.py` | merge revision, `down_revision = ("20260905_19", "20260908_19")` |
| N | `backend/alembic/versions/20260912_21_industrial_observations.py` | two tables, `findings.modbus_unit_id`, `orgs.ot_digest_key`, RLS + grants |
| N | `backend/src/api/schemas/industrial.py` | ingest models `ModbusDeviceIdentification`, `ModbusAddressRange`, `ModbusUnit`, `IndustrialService` |
| N | `backend/src/api/services/industrial.py` | `persist_industrial_services()`, `industrial_services_for_scan_host()` |
| T | `backend/src/api/models/persistence.py` | `IndustrialServiceRecord`, `ModbusUnitRecord`, `FindingRecord.modbus_unit_id` |
| T | `backend/src/api/models/identity.py` | `Org.ot_digest_key` |
| T | `backend/src/api/schemas/scan.py` | re-exports from `schemas/industrial.py`; `ModbusValidationPayload` deleted; value and aggregate fields deleted; `value_digest`, `truncated`, `write_requests_sent` added |
| T | `backend/src/api/schemas/read.py` | `IndustrialServiceView`, `ModbusUnitView`, `ModbusDeviceIdentificationView`, `ModbusAddressRangeView`, `FindingModbusUnitRef`; `industrial_services` on `ScanHostView` and `HostDetailResponse`; `unreadable_fields` on `ScanHostView`, `HostSummary`, `HostDetailResponse`; `FindingRead.modbus_unit` |
| T | `backend/src/api/services/persistence.py` | `_persist_scan_host` calls `persist_industrial_services`; `upsert_finding` carries `modbus_unit_id` |
| T | `backend/src/api/services/read.py` | `_validate_or_degrade`; industrial views on host/scan reads; `modbus_unit` on findings |
| T | `backend/src/api/core/config.py` | `INDUSTRIAL_OBSERVATION_RETENTION_DAYS = 180` |
| T | `backend/src/api/management/provision_agent.py` | generates/reuses `orgs.ot_digest_key`, prints `ot_digest_key=<hex>` |
| T | `backend/tests/conftest.py` | `pytest_configure` `UsageError`; `pytest.skip` at 121-124 deleted |

### 9.3 `contracts/` and `frontend/`

| | Path | Change |
|---|---|---|
| T | `contracts/openapi/openapi.yaml` | delete `ModbusValidationPayload` (2427) and `ModbusUnitPayload.validations` (2532); delete value/aggregate properties from `ModbusAddressRangePayload` (2377); add `value_digest`, `truncated`, `write_requests_sent`; add the four read views and `FindingModbusUnitRef`; add `industrial_services` and `unreadable_fields` to the read schemas |
| T | `contracts/examples/scan_result.example.json` | matches the new payload shape |
| T | `frontend/src/types/openapi.d.ts` | **generated only** — `npm run gen:types`. No hand edits, no component or screen work; the OT web screen is out of scope |

### 9.4 Tests

| | Path | Mirrors |
|---|---|---|
| N | `hardware-agent/tests/unit/test_ot_untrusted.py` | `test_ot_policy.py` |
| N | `hardware-agent/tests/unit/test_ot_digest.py` | `test_ot_policy.py` |
| N | `hardware-agent/tests/unit/test_modbus_readonly.py` | `test_modbus_client.py` |
| N | `hardware-agent/tests/unit/test_egress_only.py` | `test_nspi_constants.py` |
| N | `hardware-agent/tests/unit/test_scan_depth_validation.py` | `test_nspi_submode_selection.py` |
| N | `hardware-agent/tests/unit/test_modbus_profile_corroboration.py` | `test_modbus_mapper.py` |
| N | `hardware-agent/tests/unit/test_deep_stage_service_recovery.py` | `test_stage_isolation.py` |
| T | `hardware-agent/tests/unit/test_modbus_client.py` | replace the namespace test (137-148) with the reachability test |
| T | `hardware-agent/tests/unit/test_modbus_nse.py` | zero-padded sid, recorded parse failure, `"ExceptionLogger 3000"` |
| T | `hardware-agent/tests/unit/test_modbus_inventory.py` | per-unit isolation, pacing, preserved evidence |
| T | `hardware-agent/tests/unit/test_modbus_mapper.py` | keyed digest, absent summary, no raw values on the payload |
| T | `hardware-agent/tests/unit/test_modbus_stage.py` | measured write counter (drop the `== 0` literal assertion at 131), stage deadline |
| T | `hardware-agent/tests/unit/test_scan_runner_partial.py` | ADR-010 completed-with-partial |
| T | `hardware-agent/tests/unit/test_workspace.py` | completed-with-partial is not in `_FAILED_TERMINATED_BY` |
| T | `hardware-agent/tests/unit/test_tui_scan_view.py` | markup-bearing vendor string renders literally |
| T | `hardware-agent/tests/unit/test_scan_progress_screen.py` | refused depth surfaces a failure state; `interrupted_stage=None` does not read as interrupted |
| T | `hardware-agent/tests/test_contract_models.py` | payload strictness and removed fields |
| N | `backend/tests/test_alembic_single_head.py` | `test_migrations.py` |
| N | `backend/tests/test_industrial_observations_migration.py` | `test_operating_system_migration.py` |
| N | `backend/tests/test_industrial_persistence.py` | `test_host_materialisation.py` |
| N | `backend/tests/test_industrial_read_routes.py` | `test_read_hosts.py` |
| N | `backend/tests/test_unreadable_row_degradation.py` | `test_read_service.py` |
| N | `backend/tests/test_database_required.py` | subprocess `pytest` run with `DATABASE_URL_TEST` unset |
| T | `backend/tests/test_ingest_schema.py` | removed and added ingest fields |
| T | `backend/tests/test_contract_fidelity.py` | OpenAPI matches the routes |
| T | `backend/tests/test_read_schema.py` | new read views |
| T | `backend/tests/test_provision_agent.py` | digest key emitted once per org |

### 9.5 Documentation

TRUTH.md's `Docs drift` section is in scope for this feature. Re-scope against `main` first —
`79c559d` already repaired `cli.md`, `overview.md`, `scanner/runner.md`, `scanner/stages.md` and
`discovery.md`.

| | Path | Change |
|---|---|---|
| T | `docs/adr/ADR-019-v2-active-scanning-and-agent-hardening.md` | Status Accepted (2026-09-12); process-data clause (done in spec refine) |
| T | `specs/042-nspi-modbus-ot/TRUTH.md` | item 14 points at 045; summaries do not leave the Pi |
| T | `specs/042-nspi-modbus-ot/ARCHITECTURE.md` | superseded-by banner on §7 |
| T | `docs/CLI.md` | the `nspi-submode` argument exists |
| T | `docs/README.md` | index ADR-018, ADR-019, `docs/tests/`, `docs/examples/` |
| T | `docs/DEV-SETUP.md` | `DMITRI_OT_POLICY_PATH`, `DMITRI_OT_DIGEST_KEY`, the live-database requirement, the retention period |
| T | `docs/tests/nspi-modbus-inventory.md` | correct branch; `industrial_services` is readable |
| T | `docs/tests/nspi-modbus-read-only-mapping.md` | active validation is absent in the web, disabled in the TUI |
| T | `docs/roadmap/TASKS.md`, `docs/roadmap/README.md` | close T4.1; record the OT work |
| N | `.claude/docs/hardware-agent/ot.md` | the OT package, its stage, `pymodbus`, the policy and the digest |
| T | `.claude/docs/hardware-agent/index.md`, `overview.md` | list `ot/`, the Modbus stage, `pymodbus`, the current `AGENT_VERSION` |
| T | `.claude/docs/hardware-agent/daemon.md` | the `invalid_command` branch is the live write-depth guard, not dead code |
| T | `.claude/docs/hardware-agent/tui.md` | three submodes and the submode label |
| T | `.claude/docs/backend/migrations.md` | the merge revision, the single-head convention, both new rows |
| T | `.claude/docs/backend/models.md`, `schemas.md`, `services.md` | the two OT tables, `schemas/industrial.py`, `services/industrial.py` |
| T | `.claude/docs/contracts.md`, `.claude/docs/index.md` | the OT contract schemas and the new map entry |
| T | `.claude/CLAUDE.md` | the false-green warning describes something that can no longer happen |

## 10. Testing expectations

### 10.1 `hardware-agent/`

Gate: `cd hardware-agent && uv run pytest` (785 passing today; every new test adds to it). `ruff`
and `black` run from the pre-push hooks, scoped to `hardware-agent/`.

| Behaviour | Test |
|---|---|
| Markup in identification renders literally | `test_tui_scan_view.py` — vendor `"[/nope]"`, assert no `MarkupError` and the literal text |
| Oversized identification truncates at the boundary, unit retained, `truncated=True` | `test_ot_untrusted.py` + `test_modbus_client.py` |
| Zero-padded sid keeps the valid units, records the failure | `test_modbus_nse.py` — `"08"`, `"007"`, `"1"` |
| One malformed FC43 mid-host preserves the other units | `test_modbus_inventory.py` — probe raising `struct.error` for unit 3 |
| `"ExceptionLogger 3000"` is not an error | `test_modbus_nse.py` |
| Absent data summarises as `None` | `test_modbus_mapper.py` |
| Identity alone cannot widen; CIDR/MAC can; narrower always applies | `test_modbus_profile_corroboration.py` — three cases |
| Refused depth stops before any request, from both entry points | `test_scan_depth_validation.py` + `test_scan_progress_screen.py` |
| FC43 probes paced | `test_modbus_inventory.py` with an injected `sleep` recorder |
| Stage deadline stops, reports, retains | `test_modbus_stage.py` with a slow probe and a patched `MAX_OT_HOST_SECONDS`; metadata has `modbus_stage_deadline_reached` and `modbus_stage_deadline_seconds`; `partial_result` unchanged |
| Every bound in force by default | `test_nspi_constants.py` — assert the defaults produce a non-`None` deadline |
| No listening socket | `test_egress_only.py` |
| A reachable write fails the suite | `test_modbus_readonly.py` — `session._client.write_register` raises `WriteAttemptError` |
| Write counter measured | `test_modbus_stage.py` — the metadata value comes from the field, not a literal |
| Completed with partial evidence | `test_scan_runner_partial.py` — one skipped host, assert `terminated_by="completed"`, `partial_result=True`, `interrupted_stage is None` |
| Genuine failure still names its cause and stage | `test_scan_runner_partial.py` / `test_circuit_breaker.py` |
| Retention classifies correctly | `test_workspace.py` — completed-with-partial is not in `_FAILED_TERMINATED_BY` |
| A finished scan is not labelled interrupted | `test_scan_progress_screen.py` — `interrupted_stage=None` with `partial_result=True` never renders `"an earlier stage"` |
| Service evidence survives a lost deep step | `test_deep_stage_service_recovery.py` |
| No raw value or aggregate on the payload | `test_contract_models.py` — assert the field names are absent |
| Digest keyed, stable, and different per address | `test_ot_digest.py`; no key -> `None`, no failure |
| No process value in logs | `test_modbus_mapper.py` with `caplog` over a mapping run |

`hardware-agent/tests/integration/` keeps running against the real local `pymodbus` server on
`127.0.0.1`, which the egress-only test does not cover.

### 10.2 `backend/`

Gate: `./database.sh --test`, then `cd backend && uv run ruff check src tests && uv run pytest`.
**`ruff check` is the only Python gate here — never `ruff format`, never a repo-wide formatter.** A
run with a non-zero skip count is not a pass; after §7.2 there is no skip to report.

| Behaviour | Test |
|---|---|
| Exactly one head | `test_alembic_single_head.py` — `ScriptDirectory.get_heads()` has length 1 |
| Upgrade from empty reaches head | `test_industrial_observations_migration.py` |
| Upgrade from the last released state, nothing reapplied or altered | `test_industrial_observations_migration.py` — upgrade to `20260905_19`, then to head |
| Reversible | `test_industrial_observations_migration.py` — downgrade the repair revisions |
| Observation survives the lifecycle | `test_industrial_persistence.py` + `test_industrial_read_routes.py` — ingest a payload, read the host back, compare every field |
| Idempotent ingestion | `test_industrial_persistence.py` — ingest twice, assert one row per unit |
| Organisation isolation | `test_industrial_read_routes.py` — two orgs |
| Risk attributed to a unit | `test_industrial_persistence.py` — two units, different firmware, assert `FindingRead.modbus_unit` |
| Process values withheld | `test_read_schema.py` + `test_contract_fidelity.py` — the view has no value or aggregate field |
| Contract carries no unbuilt behaviour | `test_contract_fidelity.py` — `ModbusValidationPayload` absent from the schema |
| Unreadable stored record degrades | `test_unreadable_row_degradation.py` — write junk `operating_system_json` and junk `identification_json`, assert 200, the other hosts present, `unreadable_fields` populated |
| No database is a failure | `test_database_required.py` — `subprocess` `pytest` with `DATABASE_URL_TEST` unset, assert non-zero exit and the message; assert no flag makes it pass |
| Digest key issued per org, never returned by an API | `test_provision_agent.py` + `test_read_schema.py` |

### 10.3 `frontend/`

Gate: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`. The only
change is `src/types/openapi.d.ts` from `npm run gen:types`; the gate exists to prove the
regenerated types still compile against the current components. No new frontend test, and no OT
screen — that belongs to the feature that owns it.

## 11. Judgement calls and limitations

Stated because TRUTH.md left room and a reader should see the reasoning, not guess it.

1. **Aggregates are removed from the wire, not filtered at read.** TRUTH says aggregates are "not
   returned"; user story 12 says process data stays in the plant. Keeping them on the wire and
   filtering at read leaves a leak one refactor away. They now stop at the agent's payload boundary
   (§2.1). The three fields survive on the in-memory dataclass, with the lying empty-list branch
   removed, because the acceptance criterion "Absent data summarised" describes a summary that is
   still computed.
2. **The wall-clock ceiling is per-stage, not a global `scan_deadline_s` default.** Giving every
   mode a global deadline changes behaviour well outside this feature. ADR-019 §6 asks each active
   stage to declare its own ceiling; `MAX_OT_STAGE_SECONDS` / `MAX_OT_HOST_SECONDS` do that, and
   compose with an operator-set `scan_deadline_s`. Consequence: the non-OT stages still have no
   reachable wall-clock bound. That is out of this feature's scope and is not claimed as fixed.
3. **The org digest key is stored server-side.** Needed so a second appliance in one organisation
   produces comparable digests, which "organisation-scoped secret" implies. The cost is a
   server-side secret whose compromise would allow brute-forcing digests. The alternative
   (per-appliance key, never sent to the server) is safer but breaks cross-appliance comparison.
   Decide before implementation if you disagree.
4. **Retention is stated, not enforced.** TRUTH requires "a stated retention period"; 180 days is
   now stated in code, contract and docs. No backend pruning job exists to enforce it, and building
   one is a separate feature. Per CLAUDE.md, this limitation is declared rather than papered over
   with a stopgap pruner.
5. **`unreadable_fields` is the degradation signal.** TRUTH says an unreadable row is "reported as
   unavailable"; it does not name a mechanism. A per-row list of field names is the smallest thing
   that carries the report to the client without a second request.
6. **The deep-stage recovery pass reuses `detect_services`.** Finding 17 was left as a design
   decision. Restoring `-sV` to the port stage would undo `6e19062`'s deduplication; a bounded
   recovery pass restores independence only on the failure path, and turns an already-present unused
   function into the mechanism rather than adding new Nmap code.
7. **Finding 10 is not addressed.** The partial signal is still inferred from absent Nmap host
   elements. TRUTH lists it under `Known items, deliberately not fixed here`, so §6 restores the
   correct terminal state over an input that remains imprecise.

No `HUMAN_INFRA_REQUIRED` item arises from this feature. `setcap` provisioning and running the
agent unprivileged are the deployment change ADR-019 §5 calls for, and TRUTH.md puts them out of
scope.

## 12. Related

- [`TRUTH.md`](TRUTH.md) — binding behaviour
- [`INTEGRATION.md`](INTEGRATION.md) — the cross-layer contract this design implies
- [`AUDIT.md`](AUDIT.md) — evidence, blockers 1-2, findings 4-9, 11-17, 19
- [`REMEDIATION-PLAN.md`](REMEDIATION-PLAN.md) — order of operations
- `DESIGN.md` — TUI changes (escaped rendering, the refused-depth state, the OT summary)
