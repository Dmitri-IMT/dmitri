# DESIGN — NSPi OT inventory and Modbus assessment

Status: proposal for implementation review.

## 1. Scan algorithm

For every `nspi` scan:

1. Run existing host discovery.
2. Run the existing NSPi two-pass port stage.
3. Run the existing deep stage with every current NSE script.
4. Select a Modbus candidate when TCP/502 or another explicitly selected port is
   open and service/NSE evidence supports Modbus.
5. Parse all `modbus-discover` `ScriptResult.data` first, with its text output as
   a compatibility fallback. Preserve Unit IDs, identification, exceptions and
   evidence source.
6. Under `inventory`, send FC43/MEI 14 only when identification is still missing
   and there is an allowed Unit ID. Do not enumerate 1..247 a second time.
7. Under `read_only_mapping`, validate and execute only the exact target rules.
8. Under `active_validation`, revalidate both permission gates and execute only
   the exact single-point FC05/FC06 operations after inventory. Mapping results
   never become write targets automatically.
9. Derive contextual findings and high-confidence fingerprint candidates.
10. Normalise once, then write local JSON and/or ingest it as today.

Nmap documents `modbus-discover` as both `discovery` and `intrusive`. Its default
behaviour finds the first legal Unit ID; `aggressive=true` continues searching.
The current command is retained. An exhaustive Unit-ID search is not silently
enabled by this feature.

### Plug-and-scan automation

The scan-start surface asks an ordinary operator only for the top-level mode and
NSPi submode. Network detection, candidate selection, Unit-ID selection,
mapping-plan selection, fingerprint normalisation, CVE enrichment and report
generation are automatic.

The resolution rules are deterministic:

1. Reuse Unit IDs returned by `modbus-discover`.
2. If an identified endpoint has no Unit ID, use only the bounded fallback
   defined by the product policy; never turn on exhaustive NSE enumeration
   implicitly.
3. Prefer a locally installed site mapping profile.
4. Otherwise use a matching reviewed vendor/product profile.
5. Otherwise use the conservative built-in baseline and label it as an
   incomplete sample.
6. For active validation, use only a locally installed operation whose device
   selector matches the discovered IP/network and fingerprint. With no match,
   skip writes and explain why.

The report translates protocol evidence into plain language. Technical details
remain available for an experienced reviewer, but the primary result must not
require the operator to interpret an NSE blob, Modbus exception number or CPE.

## 2. Address mapping

### Address notation

The wire address is always stored as the zero-based PDU address from 0 through
65535. The UI may display a conventional reference such as `40001`, but must
label that value as a presentation convention because modern vendor maps do not
all use the classic 0xxxx/1xxxx/3xxxx/4xxxx notation.

### Range execution

For each automatically selected target, discovered/approved Unit ID and resolved
range:

1. Split the range into `block_size` chunks within Modbus protocol limits and
   the project's lower safety ceiling.
2. Check cancellation, deadline and the per-host request budget.
3. Wait the configured inter-request delay.
4. Call the one typed PyModbus read method selected by `address_space`.
5. Record a valid response, Modbus exception code, timeout or local error.
6. On `illegal data address`, optionally bisect the failed chunk until the
   configured minimum block size or request budget is reached. Do not bisect a
   timeout because that would multiply traffic against an unhealthy device.
7. Merge adjacent results only when status, Unit ID, address space and capture
   policy match.

The bisection option is off in the generic baseline and may be enabled only by a
reviewed site/vendor mapping profile. It finds readable islands without an
unconditional address-by-address sweep.

### Learning what an address does

Readability is directly observed; meaning is not. Meaning is attached by one of
these evidence levels:

1. `documented`: operator imports a vendor/engineering address map.
2. `observed_correlation`: repeated read-only snapshots correlate with a known,
   manually performed lab action.
3. `unknown`: no semantic claim.

The scanner never changes a coil/register to discover its effect. Comparing two
or more authorised snapshots can be a later analysis function; it must report
correlation, timestamp and changed addresses rather than claiming causality.

## 3. PyModbus adapters

The read-only adapter used by `inventory` and `read_only_mapping` may call only:

- `read_device_information` (FC43/MEI 14);
- `read_coils` (FC01);
- `read_discrete_inputs` (FC02);
- `read_holding_registers` (FC03);
- `read_input_registers` (FC04);
- connection open/close.

The adapter normalises PyModbus exceptions and API-version differences behind
tests. It has no write method and accepts no raw PDU. Pin the tested PyModbus 3.x
line in `pyproject.toml` and `uv.lock`; do not use an unbounded
`pymodbus>=3.0.0` declaration like MATRIX.

The separate active-validation adapter may additionally call only:

- `write_coil` (FC05);
- `write_register` (FC06).

It is constructed only after the local `OtAutomationPolicy`, scan submode, target
allowlist and acknowledgement all pass. The mapper cannot import or receive
this adapter. Neither adapter exposes multiple writes, mask writes,
read/write-combined operations, diagnostics or arbitrary PDUs.

Unit ID 0 is not part of the normal active-policy range because it is the
standard broadcast identifier. Observed Nmap data may still retain any byte
value; an explicitly justified lab fixture may test unusual gateway behaviour.

## 4. Active validation state machine

An active-validation operation is a controlled verification, not address
discovery. It requires a disposable test point whose meaning and safe values are
known in advance and stored by the installer in the local automation policy.
The scan operator chooses the submode and confirms its risk but does not enter
the write address or value.

```text
validate both permission gates
        v
read original value
        |
        +-- differs from expected --> skipped_expected_value_mismatch
        v
send one FC05/FC06 test write (never retry)
        v
read back
        v
enter restoration-critical section
        v
write captured original value once
        v
read and verify final value
        |
        +-- equal --> restoration verified
        +-- different/unreadable --> restoration unverified; stop all validation
```

Rules:

1. The test value must differ from the expected original value and fit the
   address-space type (`bool` for a coil, `0..65535` for a register).
2. If the first read fails or differs from `expected_current_value`, no write is
   sent.
3. A test write is sent exactly once. A timeout means its effect is unknown and
   is followed by read-back/restoration handling, not a repeated test write.
4. Once a test write has been attempted, one best-effort restoration of the
   captured original value is mandatory, even when read-back is inconclusive.
5. Cancellation requested after the test write is deferred until restoration
   has been attempted. Power loss and process termination still cannot provide
   a rollback guarantee.
6. Failure to verify restoration terminates all remaining validations and
   creates a prominent incident result. It must never be hidden by a partial
   scan status.
7. V1 allows at most one operation per target and a hard maximum of five per
   scan; the local agent policy defaults to one and may lower the limit.

Restoration status has precise semantics:

- `not_required`: the test write was never sent;
- `verified`: the final read equals the captured original value;
- `failed`: the restoration write was explicitly rejected or failed locally;
- `unverified`: restoration may have been sent, but the final value could not be
  read or did not equal the original value.

## 5. Findings model

| Observation | Result type | Default interpretation |
|---|---|---|
| TCP/502 open, no protocol response | Inventory | Suspected Modbus endpoint; no vulnerability. |
| Valid Modbus identification | Inventory | Confirmed endpoint and fingerprint evidence. |
| Valid unauthenticated FC01-04 response | Inventory + contextual finding | Legacy protocol exposure confirmed; no CVE implied. |
| Modbus exception | Inventory | Device responded and rejected the request; preserve code. |
| Timeout | Inventory | Inconclusive; never “address absent”. |
| High-confidence product/version CPE | Enrichment input | Reuse current NVD query path. |
| NSE/vulners CVE | Finding | Existing behaviour unchanged. |
| Operator did not request writes | Audit fact | `write_tested=false`, never “writes protected”. |
| FC05/FC06 accepted and read-back matches | Inventory + finding | Unauthenticated single-point write confirmed; no CVE implied. |
| Write rejected with a Modbus exception | Validation result | Preserve the exception; do not claim all writes are protected. |
| Test write timeout | Validation result | Effect is unknown; restoration path is still required. |
| Restoration not verified | Incident + halted validation | Do not report validation success or continue writing. |

Recommended contextual finding identifier/title:

- source: `modbus-read-only-assessment`
- title: `Unauthenticated Modbus data read is reachable`
- severity: `medium` only when a configured read succeeds; policy may later
  lower it based on zone/context.
- confidence: confirmed through the backend's existing direct-evidence rule.

Recommended active-validation finding:

- source: `modbus-active-validation`
- title: `Unauthenticated Modbus write was accepted`
- severity: `high` by default; environmental risk may raise it outside an
  isolated lab.
- confidence: confirmed only when the test value is observed on read-back.
- evidence: exact function, Unit ID, address, original/test/read-back/final
  values and restoration status.

Do not create a finding solely because Modbus is present. The inventory may
still recommend segmentation, allowlisting, monitoring and migration to an
authenticated security layer where supported.

## 6. Expected JSON

The exact field names are fixed during the contract task, but the intended
shape is:

```json
{
  "scan_id": "23833c90-94e1-4a97-8a99-0521ee05a44d",
  "timestamp": "2026-09-02T15:20:12Z",
  "subnet": "192.168.10.0/24",
  "scan_mode": "nspi",
  "hosts": [
    {
      "ip": "192.168.10.30",
      "mac": "00:80:F4:12:34:56",
      "hostname": "plc-cell-1",
      "vendor": "Schneider Electric",
      "ports": [
        {
          "port": 502,
          "protocol": "tcp",
          "state": "open",
          "service": "modbus",
          "version": null
        }
      ],
      "industrial_services": [
        {
          "protocol": "modbus_tcp",
          "port": 502,
          "confidence": "confirmed",
          "evidence_sources": ["nmap-service", "modbus-discover", "pymodbus"],
          "units": [
            {
              "unit_id": 1,
              "status": "responding",
              "device_identification": {
                "vendor_name": "Schneider Electric",
                "product_code": "BMX P34",
                "major_minor_revision": "2.60",
                "model_name": null,
                "user_application_name": null,
                "objects": {}
              },
              "address_ranges": [
                {
                  "address_space": "holding_register",
                  "start_address": 0,
                  "count": 16,
                  "status": "readable",
                  "exception_code": null,
                  "label": "range supplied by lab operator",
                  "nonzero_count": 3,
                  "value_min": 0,
                  "value_max": 1450,
                  "values": null,
                  "value_sha256": "sha256:example",
                  "observed_at": "2026-09-02T15:20:10Z"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "findings": [
    {
      "ip": "192.168.10.30",
      "port": 502,
      "protocol": "tcp",
      "service": "modbus",
      "source": "modbus-read-only-assessment",
      "source_script": null,
      "cve_id": null,
      "cvss_score": null,
      "severity": "medium",
      "title": "Unauthenticated Modbus data read is reachable",
      "description": "An authorised read-only probe received process data without application-layer authentication.",
      "recommendation": "Restrict TCP/502 to required peers and maintenance paths; monitor requests and use an authenticated security layer where supported.",
      "evidence": "Unit 1 answered FC03 for zero-based addresses 0-15. No write function was sent.",
      "references": []
    }
  ],
  "metadata": {
    "nspi_policy_version": 1,
    "nspi_submode": "read_only_mapping",
    "modbus_requests_sent": 3,
    "modbus_timeouts": 0,
    "modbus_write_requests_sent": 0,
    "partial_result": false
  }
}
```

An active-validation unit adds a bounded record such as:

```json
{
  "validations": [
    {
      "address_space": "holding_register",
      "address": 100,
      "label": "disposable laboratory test register",
      "function_code": 6,
      "original_value": 0,
      "expected_current_value": 0,
      "test_value": 1,
      "write_status": "accepted",
      "read_back_value": 1,
      "restoration_status": "verified",
      "final_value": 0,
      "change_ticket": "TCC-LAB-2026-09-02",
      "started_at": "2026-09-02T15:21:00Z",
      "completed_at": "2026-09-02T15:21:02Z"
    }
  ]
}
```

## 7. Redpoint and MATRIX boundary

Redpoint's `modicon-info.nse` first requests standard FC43 identification, then
uses Schneider FC90 and multiple engineering-style messages to retrieve CPU,
memory-card and project information. It is useful to enrich an already
identified Schneider lab asset. It is too vendor-specific and intrusive for the
generic default.

MATRIX's unauthorised-read module demonstrates the four PyModbus read calls and
a 0.5-second interval. Its production shortcomings are fixed by this design:
explicit Unit IDs and ranges, bounded requests, typed output, cancellation,
timeouts, no global logging configuration and no raw-packet dependency. Its
single-value write scenarios inform the isolated fixture, but the product uses
its own two-gate state machine and restoration evidence. The MIT source need
not be copied because PyModbus supplies the valuable protocol code.

## 8. Test design

### Unit

- Structured and text-only `modbus-discover` fixtures, multiple Unit IDs,
  exception output and malformed output.
- Local automation-policy validation: target outside subnet, unmatched device,
  closed port, Unit ID 0/248+, overflowed range and excessive
  block/request/validation limits.
- Automatic plan resolution: site profile, vendor profile, generic baseline,
  discovered Unit-ID reuse and bounded fallback.
- Every address-space-to-function mapping and PyModbus response/exception.
- Chunking, request budget, delay, optional bisection, cancellation and hashing.
- Explicit assertion that the read-only adapter has no write/raw-PDU method and
  that the validation adapter exposes only FC05/FC06.
- Active-validation state transitions: disabled local policy, target outside
  allowlist, missing acknowledgement, expected-value mismatch, accepted,
  rejected, timeout, restore verified/unverified and cancellation before/after
  test write.
- Exact current NSPi script tuple and generated Nmap argv.

### Agent integration

- A deterministic pinned PyModbus server with four data spaces, device info and
  isolated writable test points.
- Current NSE output plus fallback: prove the fallback does not duplicate a
  complete NSE identification.
- CLI, TUI and daemon produce equivalent submode requests and resolve the same
  locally installed automation policy.
- Cancellation during a Modbus request closes the active client and returns a
  valid partial payload.
- Cancellation after a validation write waits for the restoration-critical
  section; an unverified restore stops subsequent operations.
- Packet assertions prove that inventory/mapping emit no writes and validation
  emits only the configured FC05/FC06 plus one restoration.
- Workspace JSON round-trips through `ScanPayload`.

### Backend/contract

- Agent/backend model fidelity and generated OpenAPI types.
- Migration upgrade/downgrade, idempotent ingest, tenant isolation, bounded
  raw-value validation and complete validation/restoration persistence.
- Scan/host detail reads include OT inventory; lists remain compact.
- High-confidence CPE enters existing enrichment; ambiguous data does not.

### Frontend/TUI

- Inventory, no-Modbus, partial, timeout, exception, large-range and active
  validation summaries.
- Advanced mapping runs automatically from site/vendor/default profiles after
  submode selection. Active validation requires a separate confirmation and
  reports local-policy refusal or absence of an approved point.
- Only administrators can send a remote active-validation command.
- The ordinary flow never asks for IP, Unit ID, range, function code or value.
- Plain-language summaries remain useful when all technical detail panels are
  collapsed.
- Existing non-NSPi scans render unchanged.

### Hardware acceptance

- Same fixture and request policy on Pi 3 B+ and Pi 4 4 GB.
- Record elapsed time, peak RSS, CPU, request count, timeout count, payload size
  and Nmap/agent versions.
- No loss of NSE findings and no OT concurrency above one.
- Inventory/mapping PCAP contains no writes; active-validation PCAP contains
  only the exact configured write and restoration, never a range sweep.
- A plug-to-report usability run verifies that a participant without Modbus
  experience can start inventory and identify the main risks and recommended
  actions without assistance.
