# INTEGRATION — industrial observations across the layers

This document defines the cross-process handoff for OT/Modbus observations: Raspberry Pi agent ->
published OpenAPI contract -> backend ingestion -> PostgreSQL persistence -> read APIs ->
generated frontend types. The data model and naming in [`ARCHITECTURE.md`](ARCHITECTURE.md) are
authoritative; this file defines the seam.

It supersedes the persistence and read half of
[`specs/042-nspi-modbus-ot/ARCHITECTURE.md`](../042-nspi-modbus-ot/ARCHITECTURE.md) §7. Shape
follows the in-repo precedent,
[`specs/043-operating-system-inventory/INTEGRATION.md`](../043-operating-system-inventory/INTEGRATION.md).

The one property this whole seam exists to guarantee: **raw process values and every statistic
derived from them stop inside the agent process.** Everything downstream of
`build_host_payload()` sees status, identity and a keyed digest, and nothing else.

## 1. Sequence

1. `ot/modbus/nse.py` parses `modbus-discover` script output into `ModbusUnit` objects,
   bounding every device string and recording — never swallowing — each unreadable entry.
   After `6e19062` that script is not a port-stage NSE; the OT inspection stage consumes
   the output.
2. `stages.run_ot_inspection_stage()` resolves the effective `OtAutomationPolicy`, computes the
   stage and per-host wall-clock deadlines, and calls `inventory_modbus_host()` per candidate host.
   Each FC43 probe is preceded by the policy's `inter_request_delay_ms`.
3. For `read_only_mapping`, `mapper.resolve_mapping_plan()` chooses a profile. A profile matched
   only on device-claimed vendor/product is applied only when `profile_is_conservative()` holds;
   otherwise the generic baseline applies and `map_modbus_service()` appends
   `identity-not-corroborated` to `evidence_sources` once.
4. `mapper.map_modbus_service()` reads bounded ranges through `ReadOnlyModbusClient`. Values live
   in memory only long enough for `ot/digest.value_digest()` to produce
   `"hmac-sha256:<hex>"` from the org-scoped key on the Pi. No key installed means
   `value_digest=None`.
5. `stages.build_host_payload()` creates `HostPayload.industrial_services` — a list of
   `ModbusTcpServicePayload`. Raw values, `nonzero_count`, `value_min` and `value_max` are **not**
   copied into it, so they never exist outside step 4.
6. `stages.build_metadata()` stamps the measured counters, including
   `modbus_write_requests_sent` summed from `ModbusService.write_requests_sent`.
7. The workspace writer saves the complete `ScanPayload`; `ScanViewScreen` reads the same model
   and renders every device string through `tui/markup.safe()`.
8. The ingest client signs and submits that same JSON to `POST /api/v1/scans`.
9. The backend validates `IndustrialService` (`schemas/industrial.py`), then
   `services/industrial.persist_industrial_services()` writes `industrial_services` and
   `modbus_units` rows under the `ScanHostRecord` created by `_persist_scan_host()`.
10. `services/persistence.upsert_finding()` attaches `findings.modbus_unit_id` when a finding's
    evidence came from a specific unit.
    The agent emits `FindingPayload.unit_id` on each per-unit read-only Modbus finding
    (`modbus-read-only-assessment`); ingest maps that Modbus 0–255 id on the finding's `port`
    to the persisted `modbus_units` row for that scan host. NSE findings omit `unit_id` and
    stay port-attributed (`modbus_unit_id` null).
11. Host, scan and finding reads return the views of §3; `frontend/src/types/openapi.d.ts` is
    regenerated from the contract and nothing else in `frontend/` changes.

At no point does the backend hold, request or use the digest key. It stores the digest string and
compares digests for equality.

## 2. Wire contract

### 2.1 Example host object

```json
{
  "ip": "192.168.1.50",
  "mac": "00:80:F4:11:22:33",
  "hostname": "plc-line-2.plant.local",
  "vendor": "Schneider Electric",
  "operating_system": null,
  "ports": [
    { "port": 502, "protocol": "tcp", "state": "open", "service": "mbap", "version": null, "cpes": [] }
  ],
  "industrial_services": [
    {
      "protocol": "modbus_tcp",
      "port": 502,
      "confidence": "confirmed",
      "evidence_sources": ["tcp-port", "nmap-service", "modbus-discover", "pymodbus"],
      "mapping_source": "generic_baseline",
      "write_requests_sent": 0,
      "units": [
        {
          "unit_id": 1,
          "status": "responding",
          "exception_code": null,
          "error": null,
          "device_identification": {
            "vendor_name": "Schneider Electric",
            "product_code": "BMEP582040",
            "major_minor_revision": "2.70",
            "vendor_url": null,
            "product_name": "Modicon M580",
            "model_name": null,
            "user_application_name": null,
            "objects": { "0": "Schneider Electric", "1": "BMEP582040", "2": "2.70" },
            "truncated": false
          },
          "identification_sources": ["modbus-discover", "fc43"],
          "address_ranges": [
            {
              "address_space": "coil",
              "start_address": 0,
              "count": 4,
              "status": "readable",
              "exception_code": null,
              "label": "generic baseline sample",
              "observed_at": "2026-09-12T14:03:11Z",
              "value_digest": "hmac-sha256:3f1c...c9"
            },
            {
              "address_space": "holding_register",
              "start_address": 0,
              "count": 4,
              "status": "illegal_address",
              "exception_code": 2,
              "label": "generic baseline sample",
              "observed_at": "2026-09-12T14:03:12Z",
              "value_digest": null
            }
          ]
        }
      ]
    }
  ]
}
```

### 2.2 Fields removed from the published contract

| Removed | Component | Reason |
|---|---|---|
| `validations` | `ModbusUnitPayload` | the write-validation depth is not built (TRUTH.md, out of scope) |
| the whole `ModbusValidationPayload` component | — | same |
| `values` | `ModbusAddressRangePayload` | raw process data stays in the plant |
| `nonzero_count`, `value_min`, `value_max` | `ModbusAddressRangePayload` | statistics over process data are process data |
| `value_sha256` | `ModbusAddressRangePayload` | a plain SHA-256 over four coils is 16 guesses |

### 2.3 Fields added

| Added | Component | Shape |
|---|---|---|
| `value_digest` | `ModbusAddressRangePayload` | `string \| null`, pattern `^hmac-sha256:[0-9a-f]{64}$` |
| `truncated` | `ModbusDeviceIdentificationPayload` | `boolean`, default `false` |
| `write_requests_sent` | `ModbusTcpServicePayload` | `integer >= 0`, default `0` |

### 2.4 Strictness, both sides

`extra="forbid"` on all four remaining Modbus payload models in **both**
`hardware-agent/src/agent/normalize/contracts.py` and `backend/src/api/schemas/industrial.py`, plus
matching `max_length` on every list and `constr(max_length=MAX_DEVICE_STRING_CHARS)` on every
device-supplied string. Agent-side validation is at least as strict as the backend's, so a payload
the backend would reject never reaches the wire and never lands in the workspace JSON either.

`industrial_services` remains optional with an empty-list default: a non-NSPi scan, or an older
agent, sends nothing and ingest succeeds.

## 3. Persistence and read mapping

| Wire source | Persistence target | Read destination |
|---|---|---|
| `HostPayload.industrial_services[]` | `industrial_services` row per `(scan_host_id, protocol, port)` | `ScanHostView.industrial_services[]`, `HostDetailResponse.industrial_services[]` |
| `.port` | `industrial_services.port`, plus `port_id` resolved from the `ports` row when one exists | `IndustrialServiceView.port` |
| `.confidence`, `.mapping_source`, `.write_requests_sent` | same-named columns | `IndustrialServiceView` |
| `.evidence_sources[]` | `evidence_sources_json` | `IndustrialServiceView.evidence_sources` |
| `.units[]` | `modbus_units` row per `(industrial_service_id, unit_id)` | `IndustrialServiceView.units[]` |
| `.units[].status`, `.exception_code`, `.error` | same-named columns | `ModbusUnitView` |
| `.units[].device_identification` | `identification_json` | `ModbusUnitView.identification` |
| `.units[].identification_sources[]` | `identification_sources_json` | `ModbusUnitView.identification_sources` |
| `.units[].address_ranges[]` | `address_ranges_json` on the unit row | `ModbusUnitView.address_ranges[]` |
| unit-attributed finding | `findings.modbus_unit_id` | `FindingRead.modbus_unit` = `{id, unit_id, port}` |
| — | `modbus_units.id` | `ModbusUnitView.id` — the stable handle a finding points at |

Persistence writes `model_dump(mode="json", exclude_none=True)` for the JSON columns, as
`operating_system_json` does. Reads validate non-null JSON through `_validate_or_degrade` (§5) and
never silently repair a stored value.

**Idempotency.** Re-ingesting the same scan re-enters `_persist_scan_host` for the same
`(scan_id, ip)`. `persist_industrial_services` selects on the unique keys and updates in place
rather than inserting, so the unique constraints `(scan_host_id, protocol, port)` and
`(industrial_service_id, unit_id)` make double ingestion produce one row per observation — the
same shape `_persist_port` and its `(port_id, cpe)` constraint already rely on.

**Organisation isolation.** No new org column. Every read reaches these rows through
`modbus_units -> industrial_services -> scan_hosts -> scans.org_id`, the path ports and CPEs
already use, and both new tables carry `ENABLE ROW LEVEL SECURITY` with `dmitri_runtime` grants.

**Retention.** Rows are scan-scoped and die with their scan. The stated period is
`INDUSTRIAL_OBSERVATION_RETENTION_DAYS = 180` days from ingestion, published in the
`IndustrialServiceView` description. No pruning job enforces it yet
(`ARCHITECTURE.md` §11.4).

## 4. The digest key — a second, out-of-band channel

The digest crosses the wire; the key never does.

| Step | Where | What moves |
|---|---|---|
| Generate | `backend-provision-agent` | 32 random bytes, stored once in `orgs.ot_digest_key` |
| Hand over | that CLI's stdout | `ot_digest_key=<64 hex>`, printed at every provisioning of an agent in that org |
| Install | the Pi | `DMITRI_OT_DIGEST_KEY`, or `~/.config/dmitri/ot-digest-key` at mode 0600 |
| Use | `agent/ot/digest.value_digest()` | HMAC-SHA256 over `[address_space, start_address, count, values]` |
| Store | `modbus_units.address_ranges_json[].value_digest` | the digest string only |
| Compare | any consumer | equality between two scans' digests for the same range |

No API accepts, returns or logs the key. No read path loads `orgs.ot_digest_key`. Rotating the key
makes digests from before the rotation incomparable with digests after it, which is the intended
and only consequence.

## 5. Failure and degradation mapping

| Condition | Agent / local behaviour | Backend / read behaviour |
|---|---|---|
| No Modbus candidate port | `industrial_services` is `[]`; the OT stage emits "No Modbus candidates found" | ingest succeeds; reads return an empty list |
| One unit's FC43 response undecodable | that unit gets `status="error"` with a bounded message; every other unit on the port keeps its evidence | persisted as sent; the failing unit is visible as failed |
| Device string over the limit | truncated at `MAX_DEVICE_STRING_CHARS`, `truncated=true` | persisted and returned with the flag; the limit applied is evident to the client |
| Unreadable unit id in script output | the valid units are kept; the failure is logged and counted into `modbus_parse_failures` | not applicable — malformed evidence is never emitted |
| Device claims a broader profile with no CIDR/MAC match | the generic baseline applies; `evidence_sources` gains `identity-not-corroborated` | persisted as sent; `mapping_source` shows `generic_baseline` |
| `active_validation` requested through any entry point | `UnsupportedScanDepth` before any active request; no payload, no metadata claiming that depth | never reaches ingest |
| OT stage wall-clock ceiling reached | remaining units and ranges marked `skipped`; gathered evidence retained; `modbus_stage_deadline_reached=true` and `modbus_stage_deadline_seconds` set; `partial_result` unchanged | persisted as sent; skipped statuses are readable |
| No digest key installed | `value_digest=null`; the range and its status are still recorded; `modbus_digest_key_present=false` | persisted as `null`; change detection is unavailable for that scan and the client can see why |
| Scan finishes with one host skipped | `terminated_by="completed"`, `partial_result=true`, `interrupted_stage=null`; headless exit 10 | `partial_result` and `interrupted_stage` are agent-local; neither appears in `backend/src` or the OpenAPI contract, so ingest is unchanged |
| Scan stops early | `terminated_by` names `timeout` / `error` / `user_cancel` with the stage that was interrupted | unchanged |
| Malformed persisted `identification_json` or `address_ranges_json` | not applicable | `_validate_or_degrade` logs it, omits the object, appends the field name to `unreadable_fields`, and returns 200 with the other hosts intact |
| Malformed persisted `operating_system_json` | not applicable | same path — this is the finding-7 fix, applied to all three JSON columns at once |
| Older agent omits `industrial_services` | model loads with `[]` | ingest succeeds; reads return `[]` |

An absent or degraded industrial observation changes no scan status, no exit code, no timeout
budget, no circuit-breaker count and no partial-result metadata.

## 6. Compatibility and rollout

Ingest uses `extra="forbid"` on both sides, and this change **removes** wire fields as well as
adding them. Deployment order is therefore mandatory and tighter than 043's:

1. **Alembic merge revision alone** (`20260912_20`). Until it lands, `alembic upgrade head` fails
   and nothing else can deploy or be tested. Tell the team: `main` cannot migrate until this ships.
2. **The observations migration** (`20260912_22`) and the updated backend. It accepts old payloads
   without `industrial_services` and new payloads with the new shape, and it **rejects** a payload
   still carrying `validations` or `values` — so the backend must not go out before the agent stops
   sending them, which is why step 3 pairs with it.
3. **The updated contract and the hardware agent, together.** Publish
   `contracts/openapi/openapi.yaml`, then roll the agent. A new agent against an old backend is
   rejected on the added fields; an old agent against a new backend is rejected on the removed
   ones. Both directions fail closed with a validation error, never with a silent drop — which is
   the specific failure (blocker 2) this feature exists to end.
4. **Regenerate the frontend types** (`npm run gen:types`) and run the frontend gate. No component,
   screen or test work: the OT web screen is out of scope.

No API version bump. No historical backfill — scans ingested before this feature never carried
retrievable industrial evidence, and inventing rows for them would fabricate observations.

Rolling back: roll the agent back first (or together with the backend), then the backend. The new
tables and `findings.modbus_unit_id` may remain during an application rollback; run the migration
downgrade only after no deployed code reads or writes them, and never downgrade past
`20260912_20` while any environment depends on a single head.

## 7. Cross-layer verification matrix

| Requirement | Verification |
|---|---|
| Exactly one schema head | `backend/tests/test_alembic_single_head.py` |
| Upgrade from empty and from the last released state; reversible | `backend/tests/test_industrial_observations_migration.py` |
| Observation survives the lifecycle | ingest a fixture payload, read the host back, compare service, units, identification and range statuses field by field — `backend/tests/test_industrial_read_routes.py` |
| Idempotent ingestion | ingest the same scan twice, assert one row per unit — `backend/tests/test_industrial_persistence.py` |
| Risk attributed to a unit | two units behind one port, different firmware, assert `FindingRead.modbus_unit` names the vulnerable one — `backend/tests/test_industrial_persistence.py` |
| Organisation isolation | two orgs with observations, each reads only its own — `backend/tests/test_industrial_read_routes.py` |
| Process values withheld | assert no `values`, `nonzero_count`, `value_min` or `value_max` in the read schema or the OpenAPI document — `backend/tests/test_read_schema.py`, `test_contract_fidelity.py` |
| Contract carries no unbuilt behaviour | assert `ModbusValidationPayload` is absent from the contract and both schema modules — `backend/tests/test_contract_fidelity.py`, `hardware-agent/tests/test_contract_models.py` |
| Change detection without retention | same range, two different values, two different digests; unkeyed reconstruction impossible — `hardware-agent/tests/unit/test_ot_digest.py` |
| Values never logged | `caplog` over a mapping run asserts no value appears — `hardware-agent/tests/unit/test_modbus_mapper.py` |
| Unreadable stored record degrades | junk in each of the three JSON columns; 200, other hosts present, `unreadable_fields` populated — `backend/tests/test_unreadable_row_degradation.py` |
| Agent strictness >= backend strictness | the same invalid object rejected by both models — `hardware-agent/tests/test_contract_models.py` |
| Generated types compile | `npm run gen:types && npm run typecheck && npm run build` |
| Gates | `hardware-agent`: `uv run pytest`. `backend`: `./database.sh --test` then `uv run ruff check src tests` and `uv run pytest` — **never `ruff format`**, and a non-zero skip count is not a pass. `frontend`: `npm run lint / typecheck / test / build`. |

The implementation is complete only when both agent entry paths have been checked — headless/daemon
`ScanRunner` and TUI `ScanProgressScreen -> ScanRunner` — and both produce identical
`HostPayload.industrial_services` objects and both refuse an unpermitted scan depth before any
active request. That is the CLAUDE.md integration rule applied to this seam; see
[`ARCHITECTURE.md`](ARCHITECTURE.md) §4.2 for the call-site table.
