# INTEGRATION — Operating-system inventory

This document defines the cross-process handoff between the Raspberry Pi agent, the
published OpenAPI contract, backend ingestion, PostgreSQL persistence, and read APIs.
The data object and naming in `ARCHITECTURE.md` are authoritative.

## 1. Sequence

1. The port-stage Nmap process writes `<os><osmatch><osclass>` under the XML `<host>`.
2. The agent selects one `OperatingSystemInfo` while parsing that same host element and
   merges it with the host's port result.
3. `run_port_stage()` attaches it to the `HostInfo` selected by IPv4 address.
4. `build_host_payload()` creates optional `HostPayload.operating_system`.
5. The local workspace writer saves the complete `ScanPayload`; `ScanViewScreen` reads the
   same model for current and past scans.
6. The ingest client signs and submits that same JSON to `POST /api/v1/scans`.
7. The backend validates `OperatingSystemDetection`, stores the exact scan snapshot on
   `ScanHostRecord`, and conditionally refreshes the corresponding `HostRecord` inventory.
8. Scan reads return the snapshot; host reads return the retained inventory value, while
   host history returns each associated snapshot.

At no point is service/application CPE evidence promoted into the OS object.

## 2. Wire contract

Example with supported evidence:

```json
{
  "ip": "192.168.1.10",
  "mac": "B8:27:EB:44:55:66",
  "hostname": "controller.local",
  "vendor": "Vendor",
  "operating_system": {
    "name": "Linux 5.4 - 5.10",
    "accuracy": 96,
    "vendor": "Linux",
    "family": "Linux",
    "generation": "5.X",
    "device_type": "general purpose",
    "cpes": ["cpe:/o:linux:linux_kernel:5"]
  },
  "ports": []
}
```

An old host object with no `operating_system` remains valid. A current producer may send
`"operating_system": null`; this also means no supported detection. Missing nested
attributes may be omitted or `null`, never populated with placeholders.

The OpenAPI component is `OperatingSystemDetection`. Its `name` and `accuracy` are
required; all descriptive fields are nullable/optional; `cpes` defaults to an empty list.
The host-level property is optional and nullable in ingest and read schemas.

## 3. Persistence mapping

| Wire/source | Persistence target | Read destination |
|---|---|---|
| `HostPayload.operating_system` | `ScanHostRecord.operating_system_json` | `ScanHostView.operating_system`; `HostScanHistoryEntry.operating_system` |
| Supported, chronologically current scan-host detection | `HostRecord.operating_system_json` | `HostSummary.operating_system`; `HostDetailResponse.operating_system` |
| Missing scan-host detection | SQL `NULL` on `scan_hosts`; no overwrite on an existing `hosts` row | Scan reads return no detection; inventory reads retain the previous supported value |

Persistence uses `OperatingSystemDetection.model_dump(mode="json", exclude_none=True)`.
Reads validate non-null JSON with `OperatingSystemDetection.model_validate(...)`; they do
not silently repair malformed database values.

## 4. Compatibility and rollout

This is an additive contract change, but backend ingest uses `extra="forbid"`. Deployment
order is therefore mandatory:

1. Publish the updated OpenAPI contract.
2. Deploy the migration and updated backend. It accepts both old payloads without the
   field and new payloads with the field.
3. Deploy the updated hardware agent.

No API version bump or historical backfill is needed. Existing database rows have `NULL`,
existing local JSON loads with `operating_system=None`, and the TUI renders the explicit
not-detected state.

After updated agents are producing the field, rolling only the backend back to a version
whose `HostPayload` forbids it will reject ingestion. Roll back the agent first (or
together), then the backend. The database columns may remain during an application
rollback; run the migration downgrade only after no deployed code reads or writes them.

No frontend deploy or TypeScript generation belongs to this rollout.

## 5. Failure and partial-result mapping

| Condition | Agent/local behavior | Backend/read behavior |
|---|---|---|
| No `<os>` or no valid candidate | Set detection to `None`; scan continues; TUI says `Operating system: Not detected`. | Ingest succeeds; scan snapshot is absent; existing inventory OS is retained. |
| Malformed candidate accuracy | Ignore that candidate; use the best remaining valid candidate or `None`. | Not applicable because malformed evidence is not emitted. |
| Multiple equal best matches/classes | Retain the first in Nmap XML order for deterministic output. | Persist and return the selected object unchanged. |
| NSPi pass 2 has no OS evidence | Merge ports and retain pass-1 OS evidence. | Receives one final object only. |
| Port batch timeout/failure | Preserve the current stage's existing partial/failure semantics; never invent OS evidence. | If a partial payload is produced, ingest the host object exactly as supplied. |
| Deep inspection timeout | Already captured port-stage OS evidence remains on `HostInfo`. | Persist the surviving partial snapshot normally. |
| Older payload omits field | Local model loads with `None`. | Ingest succeeds and does not erase inventory evidence. |
| Invalid wire object | Local/backend Pydantic validation fails with the existing validation error path. | No partial OS write occurs. |
| Malformed persisted JSON | Not applicable. | Read conversion fails visibly; do not fabricate or downgrade it to `None`. |

OS absence does not change scan status, exit codes, timeout budgets, circuit-breaker
counts, or partial-result metadata.

## 6. Cross-layer verification matrix

| Requirement | Verification |
|---|---|
| Exact host association | Multi-host agent stage test with XML order different from input order. |
| Best candidate | Parser tests for match/class confidence and deterministic ties. |
| NSPi merge | Two-pass test where pass 1 detects OS and pass 2 does not, plus stronger incoming candidate. |
| Local lifecycle | `ScanPayload` workspace write/read test and current/past `ScanViewScreen` rendering tests. |
| Ingest compatibility | Backend schema tests for omitted, null, valid, and invalid values. |
| Scan snapshot | Persistence plus `GET /api/v1/scans/{scan_id}` test. |
| Inventory retention | Chronological materialisation tests for supported -> missing and supported -> supported. |
| Late arrival | Older scan with a detection cannot replace a newer inventory value. |
| Read contract | Host list, host detail, scan detail, and history response tests plus OpenAPI fidelity. |
| Migration | Upgrade/downgrade operation test and normal migration-chain test. |

The implementation is complete only when both direct scan entry paths have been checked:
headless/daemon `ScanRunner` and TUI `ScanProgressScreen -> ScanRunner`. No parameter is
threaded through them, but both must produce identical `HostPayload` objects.
