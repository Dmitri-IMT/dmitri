# TRUTH — Nmap enrichment deduplication

## Narrative

The scan modes currently repeat expensive enrichment work across successive pipeline
stages. This increases scan duration and resource use on the hardware agent without intentionally
adding coverage. Operators need the same complete security evidence and normalized results while
the agent performs each enrichment responsibility only where it is authoritative.

## Business rules

- Quick, Standard, Extensive, MAX, and industrial scans must preserve their current target and
  port coverage.
- Every current service, version, banner, platform identifier, operating-system fingerprint,
  host-level script result, port-level script result, vulnerability, and normalized finding remains
  available under the same conditions as before.
- The script catalog and vulnerability threshold of each scan mode remain unchanged.
- Expensive service and vulnerability enrichment must not be repeated when a prior execution adds
  no information to the finalized result.
- Host identity data collected during host discovery, including names and hardware vendor evidence,
  remains unchanged.
- Evidence collected before cancellation, timeout, or unit failure must be retained, and an
  incomplete enrichment must never be represented as a complete scan.
- Scan payload fields, persistence behavior, progress behavior, and user-facing mode selection
  remain compatible.
- The industrial scan must retain its established cautious pacing for OT-specific probes, its
  broad and OT-specific port coverage, its bounded behavior, and its complete service, script, and
  vulnerability evidence while removing repeated enrichment work.

## User stories

1. As a scan operator, I want regular scans to use fewer device resources and finish sooner, so
   that the scanner remains practical on constrained hardware.
2. As a security analyst, I want optimized scans to return the same security evidence as the
   current scans, so that performance improvements do not weaken an assessment.
3. As an operator reviewing a partial result, I want all evidence already obtained to remain
   visible and incompleteness to be explicit, so that I do not mistake missing enrichment for a
   clean host.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Successful result equivalence | A deterministic target set with known host, port, service, operating-system, script, and vulnerability evidence | Each regular mode is run before and after the optimization | The normalized results contain equivalent host identity, port coverage, service enrichment, operating-system evidence, script evidence, and findings, excluding run-specific metadata |
| Coverage preservation | The established coverage of each regular scan mode | The optimized scan enumerates targets | Quick, Standard, Extensive, and MAX examine the same target and port scopes as their current counterparts |
| Enrichment preservation | A host exposes services covered by every script assigned to its selected mode | The optimized scan completes | Every script assigned to that mode remains represented where it produces evidence, and service, version, banner, platform identifier, and vulnerability information remain available |
| No redundant enrichment | A host has one or more open ports and its scan completes | The scan execution trace is inspected | Service detection and vulnerability-script enrichment are each performed only by their authoritative pipeline stage, with no equivalent earlier execution whose result would be overwritten or discarded |
| Industrial enrichment deduplication | An industrial scan discovers a host through its broad or OT-specific port coverage | The scan completes | Service, operating-system, industrial-script, general vulnerability-script, and normalized finding evidence are collected once by the authoritative enrichment stage without repeating equivalent enrichment in either port-enumeration pass |
| Industrial safety preservation | An industrial scan examines OT-specific ports | Its port-enumeration and enrichment stages run | The established cautious pacing, bounded execution, target scope, port scope, and read-only behavior remain unchanged apart from removal of redundant enrichment work |
| Operating-system preservation | A target produces an operating-system fingerprint in the current pipeline | The optimized equivalent mode completes against the same target | The fingerprint fields and best available accuracy are preserved |
| Host identity preservation | Discovery resolves a host name, address, hardware address, or vendor | Later scan stages run | The finalized host retains the discovery identity evidence unchanged |
| Partial evidence retention | A scan is cancelled, times out, or a unit fails after producing evidence | The partial payload is finalized | All evidence already accepted by the pipeline is retained, the result is marked partial, and missing enrichment is not represented as a clean assessment |
| Contract compatibility | Existing consumers read scan payloads and progress events | They receive an optimized scan | No payload field, event contract, persistence behavior, or mode-selection behavior requires a consumer change |
| Regression gates | The implementation is complete | The hardware-agent test and lint gates run | All gates pass and tests explicitly enforce coverage, enrichment equivalence, partial-result semantics, and absence of redundant work |

## Out of scope (v1)

- Raspberry Pi 3 or Raspberry Pi 4 runtime profiles.
- Reducing port coverage, removing vulnerability scripts, lowering enrichment depth, or weakening
  operating-system detection.
- New scan modes, user settings, command-line options, payload fields, or UI changes.
- Changes to worker counts, batch sizes, timing policy, retry policy, or timeout policy.
- Changes to industrial protocol operations beyond scheduling existing Nmap enrichment once.
- Removal of unrelated unused discovery modules.

## Related specs

- Implementation: `ARCHITECTURE.md`
