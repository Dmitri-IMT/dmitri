---
type: Infrastructure
title: Deployment (install scripts + Railway)
description: Dev-environment installers and the three-service Railway + Supabase deploy topology, with frontend build and backend env-var wiring.
resource: install.sh
tags: [infra, deployment, railway, install, env]
timestamp: 2026-08-22T00:00:00Z
---

# Deployment (install scripts + Railway)

## Purpose

Two concerns live here: bootstrapping a **local dev environment** and describing the **hosted
deploy topology**. `install.sh` (bash) and `install.ps1` (PowerShell) at the repo root are the
automated installers — they install `uv` and `nmap`, sync Python deps for `hardware-agent` and
`backend`, install a `dmitri` TUI launcher on PATH, seed `backend/.env`, and, when Docker + the
Supabase CLI are present, start the local Supabase stack and run Alembic migrations. The hosted
side is three Railway services in the `nspi` environment: an `api` web service and `worker`
background process built from `backend/`, plus a `frontend` static site built from `frontend/`;
the database remains on Supabase (see [supabase](./supabase.md)).
**Current state:** the backend services and the Railway frontend deployment are wired for the
hosted pilot. Physical Pi provisioning, service-manager packaging, key provisioning and clock
synchronization remain outside this deploy layer.

## Key files / settings

### Railway services

| Service | Config file | Start command / server | Health check |
|---------|-------------|------------------------|--------------|
| `api` (FastAPI web) | `backend/railway.api.toml` | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` | `/api/v1/health` (`healthcheckTimeout = 300`) |
| `worker` (background) | `backend/railway.worker.toml` | `python -m api.worker_main` | none (no inbound traffic) |
| `frontend` (static SPA) | `frontend/Dockerfile` + `frontend/Caddyfile` | Caddy on Railway's `$PORT` | none (static hosting) |

The `api` and `worker` use `builder = "RAILPACK"`, `watchPatterns = ["backend/**"]`, and
`restartPolicyType = "ALWAYS"`; both deploy from Root Directory `/backend` and differ only by
config file / start command. The `frontend` service uses Root Directory `/frontend`, passes
`VITE_API_URL` as a Docker build argument, and serves the Vite `dist/` output with Caddy.
Backend Config Paths are absolute from the repo root (`/backend/railway.api.toml`) — they do not
follow Root Directory.

### Install scripts (`install.sh` / `install.ps1`)

| Responsibility | Where |
|----------------|-------|
| Install `uv` (via astral.sh installer) if missing | `install.sh:51-71` |
| Install `nmap` (brew / apt / dnf; winget / choco on Windows) | `install.sh:126-165` |
| `uv sync --extra dev` for `hardware-agent` (and `backend` unless `--agent-only`) | `install.sh:167-175` |
| Install a `dmitri` launcher into `~/.local/bin` on PATH | `install.sh:110-124` |
| Seed `backend/.env` from `backend/.env.example` (never overwrites) | `install.sh:191-208` |
| Start local Supabase, recreate scratch `dmitri_test` DB (needs Docker + Supabase CLI) | `install.sh:257-283` |
| Run Alembic (`DATABASE_URL_DIRECT` set in shell only) after tests | `install.sh:235-255` |
| Optional pre-commit pre-push hooks (`--hooks`) | `install.sh:285-292` |
| Post-install pytest smoke checks (skip with `--skip-verify`) | `install.sh:312-336` |
| Print the local Vite origin required for the backend CORS allowlist and emailed auth links | `install.sh:465-489` |

Flags: `--agent-only` (Pi-friendly; skips backend infra), `--skip-verify`, `--hooks`
(`-AgentOnly` / `-SkipVerify` / `-Hooks` in PowerShell).

### Environment variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `DATABASE_URL` | Runtime pooled connection (6543, `dmitri_runtime`) — the only DB URL Railway holds on either backend service | `backend/.env.example` |
| `DATABASE_URL_DIRECT` | Admin/migration connection (5432, `postgres`) — required by Alembic, **forbidden** on any Railway service | `backend/alembic/env.py`; exported transiently in operator shell |
| `NVD_API_KEY` | Optional NVD enrichment key | `backend/.env.example`; sealed on backend services if used |
| Enrichment tuning (`ENRICHMENT_*`, `KEV_*`, `EPSS_*`, `NVD_*`) | Worker poll/cache/base-URL settings | `backend/.env.example` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated trusted browser origins; empty by default so CORS fails closed. Local Web setup needs `http://localhost:5173`; hosted services supply their frontend origin. | `backend/.env.example`; sealed on the API service |
| `APP_BASE_URL` | Browser origin used to build invite/reset links; set to the local Vite origin for development and the frontend service origin when hosted. | `backend/.env.example`; sealed on the API service |
| `VITE_API_URL` | Public API origin without `/api/v1`; embedded during the frontend Vite build | `frontend/.env.example`; Railway frontend build variable |
| `GITHUB_PAT` | Optional Cursor MCP token — repo-root `.env` only, unrelated to deploy | `.env.example` |

## How it connects

- **Database:** [supabase](./supabase.md) — the hosted Supabase Postgres 17 instance both
  backend Railway services connect to via the sealed pooled `DATABASE_URL`.
- **Schema provisioning:** [migrations](/backend/migrations.md) — Alembic (`upgrade head`) must
  run against a fresh DB before either backend service boots cleanly; the health route returns
  `503` until the schema exists.
- **What runs on Railway:** the [backend](/backend/overview.md) `api` and `worker` plus the
  frontend static site. The API serves the contracted [health route](/backend/api.md), the worker
  runs the enrichment poll loop, and Caddy serves the Vite bundle with SPA fallback.
- **Build status / topology:** [overview](/overview.md). Deploy targets are Railway
  (backend API + worker + frontend static site) and Supabase (DB).

## Notes / gotchas

- **`DATABASE_URL_DIRECT` must never reach a Railway service.** It carries the administrative
  credential and is only exported transiently from the operator's local `.env` for a single
  `alembic` command, then unset. Re-run `railway variable list --json` after provisioning to
  confirm it is absent.
- **Transaction pooler (6543) + prepared statements:** the shipped engine disables prepared
  statements (`prepare_threshold=None`); migrations always use the 5432/session path via
  `DATABASE_URL_DIRECT`, never 6543.
- **Config Path does not follow Root Directory** — always use the absolute-from-repo-root path,
  or Railway silently uses defaults.
- **One backend build, two services:** `watchPatterns = ["backend/**"]` means a worker-only change
  rebuilds `api` and vice versa. The frontend has its own Docker build context and does not use
  the backend Railpack configs.
- **`$PORT` binding:** `api` must bind `0.0.0.0:$PORT` and Caddy must listen on Railway's `$PORT`;
  the API health check fails if the API binds a hardcoded or loopback-only port.
- **Frontend build and routing:** `VITE_API_URL` is required and has no localhost fallback.
  `Caddyfile` rewrites `/health` to a successful static response and falls back to `index.html`
  for React Router deep links.
- **Browser origins are deployment-specific.** The installer copies the fail-closed backend
  example unchanged, then both shell mirrors print the exact
  `CORS_ALLOWED_ORIGINS=http://localhost:5173` and `APP_BASE_URL=http://localhost:5173` edits
  required before local Web access and emailed auth links work against the local SPA.
- **Free-tier pauses:** Railway's trial credit and Supabase's 7-day idle pause both silently
  stop a long-running deployment — move to paid plans / add a keep-alive before `nspi` needs to
  run 24/7.
- Installers degrade gracefully: without Docker or the Supabase CLI they print manual
  instructions and skip infra (`INFRA_OK=0`), still leaving a working agent + TUI.

# Citations

- [ADR-007 — deployment architecture](../../docs/adr/ADR-007-deployment-architecture.md)
- [ADR-009 — database stack](../../docs/adr/ADR-009-database-stack.md)
- [docs/cloud/README.md](../../docs/cloud/README.md)
- [docs/cloud/railway/SETUP.md](../../docs/cloud/railway/SETUP.md)
- [docs/cloud/supabase/SETUP.md](../../docs/cloud/supabase/SETUP.md)
