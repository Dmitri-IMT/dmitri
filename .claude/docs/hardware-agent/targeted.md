---
type: Module
title: Service-targeted checks and tool provisioning
description: Bounded service checks, native SSH audit report parsing, and Raspberry Pi tool prerequisites.
resource: hardware-agent/src/agent/targeted/
tags: [hardware-agent, targeted, coverage, provisioning]
timestamp: 2026-10-16T00:00:00Z
---

# Service-targeted checks

## Purpose

The targeted stage runs bounded checks against selected services and records completed,
failed, timed-out and skipped units separately. Missing tools or data leave honest coverage
gaps; they are not interpreted as a clean result.

## Key classes / functions

| Symbol | What it does | Source |
|--------|--------------|--------|
| `TargetedExecutor` | Owns bounded subprocesses, reports and cleanup. | `hardware-agent/src/agent/targeted/executor.py` |
| `run_ffuf` / `run_nikto` | Preserve startup diagnostics and partial findings; native tool time limits are detected in stdout and stderr. | `hardware-agent/src/agent/targeted/web.py` |
| `run_ssh_audit` | Executes the JSON audit with `--skip-rate-test`; parses native 3.9.0 algorithm/notes lists and legacy mapping sections, rejects malformed rows and mismatched targets, and ignores post-quantum-only advice. | `hardware-agent/src/agent/targeted/ssh.py` |
| `provision-targeted-tools.sh` | Installs pinned ffuf, Nikto, testssl and enum4linux-ng, the DIRB common wordlist and runtime dependencies; verifies those and the agent venv's ssh-audit. `--verify-only` performs local checks without installation or network access. | `hardware-agent/scripts/provision-targeted-tools.sh` |
| `provision-pi.sh` | Installs the agent package and provisions targeted tools while holding the scan/update lock, before declaring the appliance ready. | `hardware-agent/scripts/provision-pi.sh` |

## How it connects

The [runner](./scanner/runner.md) treats any targeted failure, skip, timeout or omitted
unit as a partial scan. The shared [daemon](./daemon.md) and local front doors use this
same pipeline. The root `install.sh --agent-only` also invokes tool provisioning on ARM.

## Notes / gotchas

- Installing the Python package alone does not install the external tools or wordlist.
- A partial scan may still have complete Nmap discovery and port coverage. Inspect the
  per-tool reason codes instead of treating every partial result as a scan crash.
- The SSH regression fixture `tests/fixtures/ssh_audit_3_9_0.json` comes from a Pi loopback
  audit; the target is replaced with a documentation address and host fingerprints removed.
- Tool availability checks do not guarantee completion against every real target. Target
  failures, deadlines and output limits continue to produce partial results.
- Zero counters mean no selected units for that tool, not an availability check. Selection
  requires open TCP endpoints: SMB for enum4linux-ng, cleartext FTP for ftp-check and
  cleartext Telnet for telnet-check. Filtered ports do not qualify; the last two checks are
  native Python adapters and need no separate executable.
- A valid JSON report does not prove completion. Nikto's explicit host error-limit abort
  is an execution error even with exit code zero. testssl error statuses and native
  scanProblem/FATAL records also produce execution errors; vulnerability score exits
  50–200 remain supported. Valid findings collected before an error are retained, while
  testssl runtime error records are excluded from findings.
- ffuf's native maximum-runtime message is a unit timeout even when it exits zero with
  valid partial JSON. Only candidates that pass the existing web validation contribute
  findings; cancellation and stage/overall deadlines retain precedence.
- Targeted units run serially. Extensive uses the greater of 30 minutes and the selected
  units' existing timeout allowances plus five seconds per unit for process/reader cleanup.
  The 96-unit plan cap bounds that budget; an explicit overall scan deadline still wins.
  NSPi keeps its 30-minute budget and max its 60-minute budget. Remaining units are skipped
  with stage_budget when that budget expires; tool timeouts are recorded separately.
  Additional time allows more units to run, but does not guarantee responsive targets.
- Printers follow the regular selection rules; there is no host-wide printer exclusion.
- Each subprocess gets a private temporary `XDG_CONFIG_HOME`, so ffuf can create its
  configuration and scraper directories under the hardened systemd service. Reports and
  configuration are removed together after execution; the service keeps `ProtectHome=true`.
- Cancellation uses `scan_cancelled`, including the currently running tool. It is distinct
  from the stage budget. Completed units log the tool, endpoint, outcome, reason, exit code
  and a bounded, sanitized diagnostic to the service journal.
