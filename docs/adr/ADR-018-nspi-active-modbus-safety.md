# ADR-018: NSPi Modbus submodes and active-scan safety boundary

> **Status:** Accepted (2026-09-03).

## Context

NSPi must remain usable by an operator without Modbus expertise while serving
authorised OT assessments with different depths. Modbus TCP has no native
application-layer authentication in its traditional form, and even read-only
active traffic can affect fragile controllers. A future write test has greater
process risk and cannot inherit permission merely because the operator selected
NSPi or because TCP/502 is open.

The existing NSPi Nmap path, including its 14 NSE scripts, already supplies
useful network and vulnerability evidence and must not be replaced.

## Decision

`nspi` remains the top-level mode and has three versioned submodes:

| Submode | Modbus operations | Operator intent |
|---|---|---|
| `inventory` | NSE plus bounded FC43 identification fallback | Default |
| `read_only_mapping` | Inventory plus bounded typed FC01-FC04 reads | Explicit |
| `active_validation` | Identification/read stages plus exact FC05/FC06 validation | Explicit and acknowledged |

Omitting `nspi_options` selects `inventory`. Non-NSPi commands reject those
options. The ordinary command carries only the submode and, for active
validation, an acknowledgement and change-ticket reference. It never carries
arbitrary targets, Unit IDs, ranges, addresses or values.

Read-only code exposes only FC01-FC04 and FC43 through typed methods and has no
write or raw-PDU escape hatch. Mapping is sequential, delayed and bounded by
hard caps. It uses discovered targets and Unit IDs, a locally installed profile
when one matches, or a fixed conservative baseline.

`active_validation` requires two independent gates:

1. the scan request explicitly selects and acknowledges the submode; and
2. an installation-scoped policy on the Raspberry Pi enables an exact
   preapproved disposable point for the discovered device.

Neither gate can replace or expand the other. Validation must read the original
value, check it against the approved expectation, write once, read back, restore
once and verify restoration. Once a test write is sent, cancellation waits for
the restoration attempt. An unverified restoration stops later validations and
is reported prominently.

FC15, FC16, FC22, FC23, arbitrary PDUs, writable-address discovery, replay,
spoofing, flooding and denial-of-service tests are excluded from the normal
product pipeline. They may exist only as separately authorised laboratory
experiments.

## Consequences

- Selecting `read_only_mapping` is sufficient for automatic target, Unit-ID and
  mapping-plan resolution; routine operators do not answer protocol questions.
- “Read-only” means no Modbus write function, not passive monitoring.
- Remote commands cannot turn a missing local write policy into permission.
- The TUI and web may expose inventory and mapping before active validation is
  implemented; the active choice remains visibly unavailable meanwhile.
- Existing Nmap/NSE findings continue unchanged and fingerprint-based CPEs reuse
  the backend's existing NVD/KEV/EPSS enrichment.
- A timeout or open TCP/502 port alone is not reported as a vulnerability.

## Rejected alternatives

- One NSPi mode with implicit escalating probes: it hides risk from the
  operator and cannot express consent.
- Arbitrary Modbus function/address inputs in the routine UI or remote command:
  they turn a plug-and-scan workflow into a generic write interface.
- Treating a mapping result as a write target: readability does not establish a
  point's meaning or safety.
- Importing MATRIX attack modules into production: their intrusive scenarios do
  not meet the bounded and restorable product contract.

## References

- [`specs/042-nspi-modbus-ot/TRUTH.md`](../../specs/042-nspi-modbus-ot/TRUTH.md)
- [`specs/042-nspi-modbus-ot/ARCHITECTURE.md`](../../specs/042-nspi-modbus-ot/ARCHITECTURE.md)
- NIST SP 800-82 Rev. 3: https://csrc.nist.gov/pubs/sp/800/82/r3/final
- Modbus Application Protocol V1.1b3:
  https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf
