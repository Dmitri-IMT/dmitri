# ARCHITECTURE — Nmap enrichment deduplication

Implements `TRUTH.md` on the synchronized `main` baseline (`eda7ca2`). Hardware agent only. No
screen, API, persistence, command-channel, or deployment contract changes.

## Current-main constraints

The synchronized baseline already contains two decisions that this change must preserve:

- structured operating-system inventory is parsed and serialized;
- NSPi has bounded Nmap calls followed by a separate, serial Modbus inventory/mapping stage.

Regular modes currently repeat `-sV`, and Quick/Standard also repeat NSE scripts, between port
enumeration and deep inspection. NSPi already removed enrichment from its broad pass, but its
OT-port pass still repeats `-sV` before the deep call. The optimization removes only those duplicate
service/script probes.

The removed port-stage `-sV` used Nmap's implicit version intensity 7, while deep inspection used
the configured default 5. The authoritative deep call therefore uses `max(configured, 7)` so its
fingerprint depth is not reduced. Quick/Standard deep inspection continues to honor the declared
`vulners.mincvss` threshold; accidental below-threshold evidence from their former unthresholded
early scripts is not part of the supported mode contract.

## Pipeline after the change

```text
discover_hosts()
  -> run_port_stage()
       -> regular: one batched port + OS call
       -> NSPi: T4 broad pass + T2 OT-port pass, merged
  -> run_deep_inspection_stage()
       -> one -sV + complete NSE catalog per host with open ports
       -> NSPi keeps -O and its internal host/script timeouts here
  -> run_ot_inspection_stage()        # NSPi only; unchanged
  -> normalize retained evidence
```

Both TUI and headless/daemon entry paths already converge on `ScanRunner`; no constructor or
external call signature changes.

## Nmap responsibility matrix

Common regular port prefix: `-Pn -n -T4`. Common deep prefix:
`-Pn -n -T4 -sV --version-intensity <effective>`.

| Mode | Port enumeration | Authoritative deep enrichment |
|------|------------------|-------------------------------|
| Quick | default top-1000 + `-O` | one-script catalog, min CVSS 5 |
| Standard | default top-1000 + `-O` | six-script catalog, min CVSS 5 |
| Extensive | `-O --top-ports 10000` | eleven-script catalog, min CVSS 3 |
| MAX | `-O -p- --min-rate 1000` | eleven-script catalog, min CVSS 1 |
| NSPi | pass 1: `-Pn -T4 -n --host-timeout 300s`; pass 2: `-Pn -T2 -n -p <seven OT ports> --host-timeout 300s` | fourteen-script catalog, min CVSS 5, `-O --script-timeout 60s --host-timeout 300s` |

Neither port pass contains `-sV`, `--script`, or `--script-args`. NSPi retains its exact two-pass
scope, T4/T2 pacing, per-host bounds, merge by `(port, protocol)`, best available OS evidence, and
the later Modbus stage. Its deep `-p` value is the sorted union of open ports from both passes.

## Evidence and partial-result semantics

Successful deep results merge additively into the existing `HostInfo`; discovery identity,
filtered ports, OS evidence, service fields, CPEs, port scripts, and host scripts are not cleared by
another unit's failure. Normalization and finding extraction are unchanged.

Both heavy stages return skipped-unit counts. An eligible deep call that returns no host is a
skipped unit. When the existing circuit breaker allows the pipeline to continue:

- zero skips: `partial_result=false`, `terminated_by=completed`;
- any port skip: `partial_result=true`, `interrupted_stage=ports`, `terminated_by=error`;
- deep skips only: `partial_result=true`, `interrupted_stage=deep_inspection`,
  `terminated_by=error`.

Cancellation, deadline expiry, and circuit-breaker termination retain their existing cause and
current stage. No fallback Nmap process starts after cancellation. For an arbitrary-time partial
scan, evidence not yet collected by the single deep authority cannot be promised; all evidence
already accepted remains present and incompleteness is explicit.

## Files and symbols

| Area | Files | Change |
|------|-------|--------|
| Mode policy | `hardware-agent/src/agent/config.py` | Keep one `deep_stage_scripts()` catalog and add `effective_version_intensity()` with floor 7. |
| Port enumeration | `hardware-agent/src/agent/discovery/port_discovery.py` | Remove `-sV`/NSE from regular and both NSPi port paths while preserving selectors, OS placement, timeouts, result types, and merge behavior. |
| Deep enrichment | `hardware-agent/src/agent/discovery/vulnerability_detection.py` | Disable repeat DNS with `-n`; retain open-port targeting, scripts, thresholds, OS option, and timeout options. |
| Stage integration | `hardware-agent/src/agent/scanner/stages.py` | Use effective intensity, retain NSPi/Modbus behavior, handle empty eligible results, return skip counts, and report actual arguments. |
| Finalization | `hardware-agent/src/agent/scanner/runner.py` | Convert isolated port/deep skips into truthful partial metadata without bypassing NSPi OT work. |
| Tests | existing unit/integration files | Capture exact argv, catalogs, two-pass union, OS/timeout behavior, evidence merging, and partial finalization. |

## Verification

- Every port-stage argv has zero `-sV` and zero NSE flags.
- Every eligible host has exactly one deep `-sV` and one complete mode catalog.
- Port scopes, NSPi timeouts/pacing, operating-system output, and Modbus behavior remain covered.
- Effective version intensity is at least 7 and honors higher configured values.
- Mixed successes/failures retain evidence and cannot finish as complete.
- Full hardware-agent pytest and Ruff gates pass on synchronized `main`.
