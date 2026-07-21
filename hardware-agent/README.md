# Hardware Agent

Python-based service intended to run on a Raspberry Pi 4 with Raspberry Pi OS Lite. It orchestrates Nmap scans, normalizes output, and writes JSON payloads for the TUI workflow.

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
```

## Integration Points
- Scan mode and subnet are chosen in the TUI or passed to `dmitri agent <mode> <subnet>`.
- Produces JSON payloads compatible with the shared contracts in `../contracts/`.
- Writes the normalized payload to `hardware-agent/artifacts/` for later analysis.

Detailed implementation notes: `../docs/implementation/NSE-VULNERABILITY-PIPELINE.md`
