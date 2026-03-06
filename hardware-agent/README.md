# Hardware Agent

Python-based service intended to run on a Raspberry Pi 4 with Raspberry Pi OS Lite. It orchestrates Nmap scans, normalizes output, and forwards JSON payloads to the backend.

## Responsibilities (Future Phases)
- Manage scan scheduling (quick/full) per subnet configuration.
- Execute Nmap using safe defaults and capture XML/JSON output.
- Convert raw results to the contracts defined in `../contracts/schemas`.
- Handle retries, buffering, and authentication when talking to the backend API.
- Report device health metrics (CPU, memory, connectivity).

## Current Status
- Basic project skeleton under `src/agent` with placeholders for discovery, scanning, normalization, transport, and utilities.
- Systemd service and installation script templates live in `system/`.
- No scanning logic is implemented yet; focus remains on structure.

## Integration Points
- Reads configuration from `config.py` (to be wired to environment variables).
- Sends HTTP requests to backend endpoints documented in `docs/api.md`.
