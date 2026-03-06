# Architecture Overview

## System Components
1. **Hardware Agent (Raspberry Pi 4, Python + Nmap)**
   - Discovers hosts within the configured subnet and orchestrates Nmap scans.
   - Normalizes raw scan output into the JSON contracts defined under `contracts/`.
   - Publishes results to the backend via REST over HTTPS.
2. **Backend API (FastAPI + PostgreSQL)**
   - Receives scan payloads, validates against shared schemas, and persists structured data.
   - Exposes endpoints for mobile clients and future administrative tools.
   - Coordinates long-running jobs (full scans, enrichment, reporting queues).
3. **Database (PostgreSQL)**
   - Stores devices, ports, findings, scan metadata, and audit logs.
   - Maintains referential integrity for reporting and trend analysis.
4. **Mobile App (Flutter)**
   - Presents dashboards, scan history, and detailed findings to end users.
   - Initiates scans indirectly through backend endpoints (future scope).
5. **Infrastructure Layer**
   - Docker-based local environment for backend + database.
   - CI workflows for linting, tests, and contract validation.

## Data Flow
1. **Scan Initiation**: Agent triggers a quick or full Nmap run against a target subnet.
2. **Normalization**: Agent converts results into the `scan_result` JSON schema, attaching device/port/finding details.
3. **Transport**: Payloads are sent over HTTPS to the backend ingestion endpoint.
4. **Processing**: Backend validates data, stores it in PostgreSQL, and prepares summaries for clients.
5. **Presentation**: Mobile app requests aggregated data through the backend''s REST API and renders user-friendly reports.

## Deployment Model
- Hardware runs Raspberry Pi OS Lite with a systemd service defined in `hardware-agent/system/agent.service`.
- Backend and PostgreSQL run in Docker containers for local development; production deployment targets (e.g., cloud VM/Kubernetes) will be defined later.
- Contracts within `contracts/` serve as the source of truth for all inter-service communication.

## Integration Points
- **Agent ? Backend**: REST API that accepts JSON payloads described in `contracts/schemas/scan_result.schema.json`.
- **Backend ? Mobile**: FastAPI will expose read endpoints documented in `docs/api.md` and `contracts/openapi/openapi.yaml`.
- **Backend ? External APIs (future)**: NVD API for CVE enrichment and LLM providers for user-friendly explanations.
