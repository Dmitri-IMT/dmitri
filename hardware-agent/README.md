# Hardware Agent

Python-based service intended to run on a Raspberry Pi 4 with Raspberry Pi OS Lite. It orchestrates Nmap scans, normalizes output, and forwards JSON payloads to the backend.

## Responsibilities
- Manage scan scheduling (quick/full) per subnet configuration.
- Execute Nmap using safe defaults and capture XML/JSON output.
- Convert raw results to the contracts defined in `../contracts/schemas`.
- Execute curated NSE scripts, including `vulners`, to correlate services with CVEs.
- Handle retries, buffering, and authentication when talking to the backend API.
- Report device health metrics (CPU, memory, connectivity).

## Current Status
- A working multi-stage pipeline is implemented under `src/agent`:
  - host discovery with `nmap -sn`
  - port discovery (`-F` for quick scans, `-p-` for full scans)
  - service detection with `-sV`
  - vulnerability correlation with curated NSE scripts and `vulners`
- XML output is parsed into normalized devices, ports, and findings.
- The CLI entrypoint writes a JSON payload compatible with the shared contracts.
- Systemd service and installation script templates still live in `system/`.

## Running the Agent

```bash
cd hardware-agent
python -m agent.main --subnet 192.168.1.0/24 --mode full
```

Useful environment variables:

- `AGENT_NMAP_PATH`: explicit path to `nmap`
- `AGENT_SCAN_SUBNET`: default target subnet
- `AGENT_SCAN_MODE`: `quick` or `full`
- `AGENT_NMAP_SCRIPTS`: comma-separated NSE scripts, defaults to `vulners,smb2-security-mode`
- `AGENT_MIN_CVSS`: minimum CVSS threshold forwarded from `vulners`
- `AGENT_MAX_WORKERS`: number of concurrent batches/hosts processed by the agent
- `AGENT_HOST_BATCH_SIZE`: number of hosts grouped into each full port-scan batch
- `AGENT_OUTPUT_PATH`: JSON output file location

## Integration Points
- Reads configuration from `config.py` (to be wired to environment variables).
- Produces JSON payloads compatible with the backend contracts in `../contracts/`.
- Backend transport is still pending and will target the API defined in `../contracts/openapi/openapi.yaml`.

Detailed implementation notes: `../docs/implementation/NSE-VULNERABILITY-PIPELINE.md`
