# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-07-22

* **Update**: Documented spec 015's read path. Backend: three new routers (`hosts.py`, `scans.py`,
  `findings.py`) mounted in `main.py` alongside `GET /api/v1/health` (new `backend/routers.md`
  doc); `services/read.py` (`list_hosts`/`get_host_detail`/`get_scan_detail`/`list_findings`) and
  `schemas/read.py` (nine read-response models, incl. `ScanHostView` with required `host_id` and
  `HostSummary` with `first_seen_at`). Persistence: `DeviceRecord`/`devices` renamed to
  `ScanHostRecord`/`scan_hosts` (a per-scan host observation); new durable `HostRecord`/`hosts`
  table (cross-scan identity, resolved by `services/hosts.py::upsert_hosts_for_scan`, ADR-014);
  `FindingRecord` gained a `finding_id` UUID; `ScanRecord` moved from `target_mode`/`scan_profile`
  to `scan_mode` + `status`. Four chained Alembic migrations (`20260722_03`–`_06`) implement this.
  Updated `backend/models.md`, `backend/schemas.md`, `backend/services.md`, `backend/migrations.md`,
  `backend/api.md`, `backend/overview.md`, `backend/index.md`. Contracts/Pi: ADR-013 retires
  `device`/`Device`/`DevicePayload` from the wire — `ScanIngestRequest.devices`→`hosts`,
  `DevicePayload`→`HostPayload`, `devices_received`→`hosts_received`; the prior `scan_mode` vs
  `target_mode`/`scan_profile` contract divergence is resolved (both sides now use `scan_mode`).
  Updated `contracts.md`, `hardware-agent/normalize.md`, `hardware-agent/scanner/stages.md`,
  `hardware-agent/scanner/runner.md`, `hardware-agent/scanner/models.md`,
  `hardware-agent/scanner/index.md`, `hardware-agent/tui.md`, `hardware-agent/overview.md`, and
  `glossary.md` (new `ScanHost` term; `Device` now "retired" not "deprecated, ingest-only").
  Refreshed `index.md` and `overview.md` at the repo root and `backend/index.md`.
* **Creation**: Added the `frontend/**` code-map section (`overview`, `api`, `app`, `index`) for the
  greenfield SPA scaffold shipped by spec 014 (frontend/): the two-Axios-instance auth client with
  the single-flight 401→refresh interceptor, the in-memory token store, the contract-typed API
  layer, and the boot-refresh + stub login/placeholder UI. Linked from the root `index.md` under a
  new "Frontend (scaffold only)" section; noted the new `frontend` CI job in `.github/workflows/ci.yml`.

## 2026-07-21

* **Update**: Corrected the README scan-modes table (Quick is default top-1000 + `vulners`, not
  `-F`) to match `discovery_arguments()`; removed the now-resolved divergence note from `overview.md`.
* **Initialization**: Created the OKF code-map bundle mapping the whole repo — top-level
  `overview` / `glossary` / `contracts`, the `hardware-agent/**` set (overview, cli, discovery,
  normalize, utils, tui, and the split `scanner/` package), the `backend/**` set (overview, api,
  models, schemas, services, migrations), the `infra/**` set (supabase, deployment), plus
  `MAINTAINING.md` and per-directory `index.md` files.
* **Note**: Corrected the scan-modes table in `overview.md` to match `discovery_arguments()` —
  Quick/Standard use the default top-1000 port set (not `-F`, as the README's product table states).
