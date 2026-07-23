---
type: Package Overview
title: Dmitri — system overview
description: What Dmitri is, its components, the end-to-end scan flow, and what is built vs planned.
resource: README.md
tags: [overview, architecture, scan-pipeline]
timestamp: 2026-07-22T00:00:00Z
---

# Dmitri — system overview

**Dmitri** is a network vulnerability scanner built as a university capstone (TCC). The end-state
product is an embedded **Raspberry Pi appliance** that joins a local network, runs **Nmap + NSE**
to discover hosts / ports / services / CVEs, normalizes results to a shared JSON contract, and (in
later phases) ships them to a cloud backend that enriches and risk-scores findings for a web UI.

Current deployment target: the university's **NSPi** industrial-robotics lab (PLCs from
Schneider/Beckhoff/Balluff/Altus on Ethernet; the Pi joins over Wi-Fi).

> **Build status.** Only the **Pi agent + TUI** ([`hardware-agent`](/hardware-agent/overview.md)) is
> in active development. The [`backend`](/backend/overview.md) is working code; its **read path**
> (`GET /hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings`) is wired, but **ingest is not** —
> nothing uploads a scan over HTTP yet, Pi hardware is not yet acquired, and there is no frontend.
> The only live coupling between agent and backend today is the shared [`contracts`](/contracts.md)
> schema. Treat the ingest side of backend/contract docs as **planned / not yet wired**.
> `docs/architecture/ARCHITECTURE.md` describes target state.

## Components

| Component | Doc | Status | Purpose |
|-----------|-----|--------|---------|
| Hardware agent + TUI | [hardware-agent](/hardware-agent/overview.md) | **active** | Runs the Nmap scan pipeline, normalizes output, Textual TUI + headless CLI. |
| Backend API + worker | [backend](/backend/overview.md) | read path wired, ingest not | FastAPI read endpoints + Postgres persistence + a worker that enriches CVEs (NVD/KEV/EPSS) and risk-scores them. |
| Shared contracts | [contracts](/contracts.md) | active seam | OpenAPI + example JSON binding agent, backend, and (future) frontend. |
| Infra / DB | [infra](/infra/index.md) | partial | Supabase-managed Postgres, install scripts, Railway deploy config. |
| Frontend (React) | — | planned | Not scaffolded (ADR-008). |

## End-to-end flow

**Agent side (runs today):**

1. Operator launches the TUI (`dmitri` / `dmitri start`) or runs headless
   (`dmitri agent <mode> <subnet>`). Entry: [cli](/hardware-agent/cli.md) →
   [tui](/hardware-agent/tui.md) or `headless.py`.
2. [`ScanRunner`](/hardware-agent/scanner/runner.md) drives the pipeline on a worker thread:
   **host discovery** (`-sn -PE`) → **port discovery** (batched, threaded; nmap args vary per mode)
   → **deep inspection** (`-sV` + NSE, `vulners` CVE correlation) → **normalize**.
   See [discovery](/hardware-agent/discovery.md) and [stages](/hardware-agent/scanner/stages.md).
3. Raw Nmap XML → [`ScanPayload`](/hardware-agent/normalize.md) (Pydantic contract).
4. [`workspace`](/hardware-agent/scanner/workspace.md) writes the normalized JSON to disk. **The flow
   ends here today — no upload.** Headless returns an outcome with exit codes 0/10/20 (ADR-012).

**Backend side (ingest not yet wired; read path is):**

5. (Planned) Pi `POST /api/v1/scans` (HMAC) → [`persist_scan`](/backend/services.md) writes
   scans/scan_hosts/ports/services/cpes/findings, resolves each host's durable identity
   (`upsert_hosts_for_scan`), and enqueues `enrichment_jobs`.
6. A separate [worker](/backend/services.md) claims jobs (`FOR UPDATE SKIP LOCKED`), enriches CVEs
   against **NVD**, **CISA KEV**, and **FIRST EPSS**, upgrades finding confidence, and re-runs the
   explainable [risk scorer](/backend/services.md).
7. **(Wired)** `GET /hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings` —
   [routers](/backend/routers.md) — read that persisted state back over HTTP.

## Scan modes

Chosen in the TUI; the `scan_mode` value follows the `ScanMode` enum in the contract. The exact
per-mode nmap args come from `discovery_arguments()` / `deep_stage_scripts()` — see
[discovery](/hardware-agent/discovery.md) and [config](/hardware-agent/cli.md).

| Mode | `scan_mode` | Port stage (actual args) |
|------|-------------|--------------------------|
| Quick | `quick` | Default top-1000 ports (`-sV -O`) + quick NSE script set. |
| Standard | `standard` | Default top-1000 ports + standard NSE script set. |
| Extensive | `extensive` | Top-10 000 ports (`--top-ports 10000`); `vulners.mincvss = 3.0`. |
| MAX | `max` | All ports (`-p-`, `--min-rate 1000`), full NSE; `vulners.mincvss = 1.0` (~45 min+). |
| NSPi | `nspi` | Two-pass: top-1000 + OT-specific ports (`NSPI_PORTS`), merged. |

Legacy `full` mode is being removed in favor of `max`.

## Tech stack

- **hardware-agent** — Python 3.13, Textual (TUI), Pydantic v2, Nmap + NSE, stdlib threads, `uv`.
- **backend** — Python 3.11+, FastAPI, SQLModel/SQLAlchemy 2, psycopg, Alembic, httpx, `uv`.
- **infra** — Supabase (managed Postgres 17), Railway (API + worker services).

# Citations

[1] [README.md](../../README.md)
[2] [CONTEXT.md](../../CONTEXT.md) — domain glossary
[3] [docs/architecture/ARCHITECTURE.md](../../docs/architecture/ARCHITECTURE.md) — target-state architecture
[4] [docs/README.md](../../docs/README.md) — human knowledge-base index
[5] [specs/015-read-path](../../specs/015-read-path/TRUTH.md)
