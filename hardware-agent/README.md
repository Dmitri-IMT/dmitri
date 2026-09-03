# Hardware Agent

Python-based service intended to run on a Raspberry Pi with Raspberry Pi OS Lite. `ADR-001` targets a Pi 4 Model B 4 GB; the board actually in hand since 2026-08-21 is a **Pi 3 (1 GB)**, whose fit is unproven — see `docs/roadmap/PI.md`. It orchestrates Nmap scans, normalizes output, and writes JSON payloads for the TUI workflow.

## Responsibilities
- Manage scan scheduling per subnet configuration.
- Execute Nmap using safe defaults and capture XML/JSON output.
- Convert raw results to the contracts defined in `../contracts/schemas`.
- Execute curated NSE scripts, including `vulners`, to correlate services with CVEs.
- device health metrics reporting (planned).

## Current Status
- A working multi-stage pipeline is implemented under `src/agent`:
  - host discovery with `nmap -sn`
  - batched port discovery (`-F` for quick; `--top-ports` / `-p-` for extensive and MAX, per mode)
  - deep inspection with `-sV` plus curated NSE scripts
  - vulnerability correlation with `vulners` plus SMB, SSH, HTTP, and TLS context scripts
- XML output is parsed into normalized devices, ports, and findings.
- The TUI entrypoint writes a JSON payload compatible with the shared contracts.
- `nspi` adds a sequential Modbus stage after the existing 14 NSE scripts.
  `inventory` reuses `modbus-discover` and a bounded FC43/MEI 14 fallback.
  `read_only_mapping` additionally performs bounded FC01-FC04 reads from a
  local profile or the conservative built-in baseline. Neither submode sends
  writes. Exact FC43 Schneider M340/M580 fingerprints can enter the existing
  CPE/NVD enrichment path.

## Running the Agent

The entry point is the `dmitri` CLI, which launches the TUI:

```bash
cd hardware-agent
uv run dmitri
# or
uv run dmitri start
```

If your environment cannot see the script entrypoint:

```bash
uv run python -m agent.cli
```

Headless scans (no TUI):

```bash
uv run dmitri agent quick 192.168.1.0/24
uv run dmitri agent nspi 192.168.1.0/24
uv run dmitri agent nspi read_only_mapping 192.168.1.0/24
```

The headless command prints the exact result-file path to stdout. Modbus data is
stored under each host's `industrial_services` property. See the
[inventory](../docs/tests/nspi-modbus-inventory.md) and
[read-only mapping](../docs/tests/nspi-modbus-read-only-mapping.md) laboratory
checklists. An optional mapping policy is loaded from
`~/.config/dmitri/ot-policy.json` or `DMITRI_OT_POLICY_PATH`.

## Integration Points
- Scan mode and subnet are chosen in the TUI or passed to
  `dmitri agent <mode> [<nspi-submode>] <subnet>`.
- Produces JSON payloads compatible with the shared contracts in `../contracts/`.
- Writes the normalized payload to `hardware-agent/artifacts/` for later analysis.

Detailed implementation notes: `../docs/implementation/NSE-VULNERABILITY-PIPELINE.md`
