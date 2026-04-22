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

## Windows one-command runner

For Windows, the recommended path is now:

```powershell
cd hardware-agent
.\run-agent.ps1
```

or:

```cmd
cd hardware-agent
run-agent.cmd
```

What this runner does automatically:

- creates `hardware-agent/.venv` if needed
- installs the Python dependencies
- detects the local Nmap installation
- checks whether `vulners` is already available in Nmap
- downloads a local copy of `vulners.nse` if needed
- keeps subnet autodetection enabled unless you explicitly pass one
- runs `python -m agent.main`

Optional examples:

```powershell
.\run-agent.ps1 -Mode full
.\run-agent.ps1 -Mode full -Subnet 192.168.15.0/24
.\run-agent.ps1 -Mode quick -OutputPath C:\temp\scan.json
```

Useful environment variables:

- `AGENT_NMAP_PATH`: explicit path to `nmap`
- `AGENT_SCAN_SUBNET`: optional target subnet; when omitted the agent auto-detects the active IPv4 subnet
- `AGENT_SCAN_MODE`: `quick` or `full`
- `AGENT_NMAP_SCRIPTS`: comma-separated NSE scripts, defaults to `vulners,smb2-security-mode`
- `AGENT_MIN_CVSS`: minimum CVSS threshold forwarded from `vulners`
- `AGENT_MAX_WORKERS`: number of concurrent batches/hosts processed by the agent
- `AGENT_HOST_BATCH_SIZE`: number of hosts grouped into each full port-scan batch
- `AGENT_OUTPUT_PATH`: JSON output file location

## Running with Docker

The repository now includes a dedicated image for the hardware agent with:

- Python runtime
- Nmap installed inside the image
- `vulners.nse` downloaded during image build
- default command `python -m agent.main`

### Quick start

1. Copy the environment template:

```bash
cd hardware-agent
cp .env.example .env
```

2. Adjust `.env` with the target subnet and desired mode.
   If `AGENT_SCAN_SUBNET` is omitted, the agent resolves the active subnet automatically.

3. Build and run:

```bash
docker compose up --build
```

The resulting JSON payload is written to `hardware-agent/artifacts/`.

### Linux / Raspberry Pi recommended mode

For the agent to scan the real LAN, the container should share the host network namespace:

```bash
docker compose -f docker-compose.yml -f docker-compose.host.yml up --build
```

This is the recommended way to run the scanner on Raspberry Pi or native Linux.

### Windows / Docker Desktop note

Docker Desktop runs Linux containers behind virtualization. Because of that, a container may not see the same LAN surface as a native process running on Windows. The image still builds and runs, but LAN scanning results can differ from native execution.

For development and validation:

- use the container to validate packaging and runtime behavior
- prefer native execution or Linux/Raspberry Pi for real LAN scanning results

## Integration Points
- Reads configuration from `config.py` (to be wired to environment variables).
- Produces JSON payloads compatible with the backend contracts in `../contracts/`.
- Backend transport is still pending and will target the API defined in `../contracts/openapi/openapi.yaml`.

Detailed implementation notes: `../docs/implementation/NSE-VULNERABILITY-PIPELINE.md`
