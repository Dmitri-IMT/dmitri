---
type: Package Overview
title: Dmitri — system overview
description: What Dmitri is, its components, the end-to-end scan flow, and what is built vs planned.
resource: README.md
tags: [overview, architecture, scan-pipeline]
timestamp: 2026-08-06T00:00:00Z
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
> (`GET /hosts`, `/hosts/{id}`, `/scans/{id}`, `/findings`), auth, the command channel and — since
> DMI-63 — **ingest** (`POST /api/v1/scans`) are all wired. The
> [`frontend`](/frontend/overview.md) now has its first real vertical slice (login → Home) reading
> that wired read path.
> **DMI-66 closed the device end of the link**: bare `dmitri agent` now runs a
> [daemon](/hardware-agent/daemon.md) that dials the WS channel with an Ed25519 proof, reports its
> available subnets, executes commands through the existing headless scan, and uploads results
> through the ingest client. What is still missing is everything *physical*: Pi hardware is not yet
> acquired, and service-manager packaging, key provisioning and clock synchronization are out of
> DMI-66's scope — so the whole path is exercised against signed test requests and fake sockets
> rather than real hardware. `docs/architecture/ARCHITECTURE.md` describes target state.

## Components

| Component | Doc | Status | Purpose |
|-----------|-----|--------|---------|
| Hardware agent + TUI | [hardware-agent](/hardware-agent/overview.md) | **active** | Runs the Nmap scan pipeline, normalizes output, Textual TUI + headless CLI. |
| Backend API + worker | [backend](/backend/overview.md) | read path + auth + commands + ingest wired | FastAPI read/ingest endpoints + Postgres persistence + a worker that enriches CVEs (NVD/KEV/EPSS) and risk-scores them. |
| Shared contracts | [contracts](/contracts.md) | active seam | OpenAPI + example JSON binding agent, backend, and (future) frontend. |
| Infra / DB | [infra](/infra/index.md) | partial | Supabase-managed Postgres, install scripts, Railway deploy config. |
| Frontend (React) | [frontend](/frontend/overview.md) | login → Home slice wired | Vite + React 19 SPA on the frozen contract: session layer, routing, and the Home verdict screen (ADR-008). |

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
4. [`workspace`](/hardware-agent/scanner/workspace.md) writes the normalized JSON to disk. Headless
   returns an outcome with exit codes 0/10/20 (ADR-012). On the **remote** path the
   [daemon](/hardware-agent/daemon.md) continues from here: it uploads that payload under the
   backend's `scan_id` and reports `uploading` → `done` on the
   [command channel](/hardware-agent/command-channel.md). On the TUI and one-shot CLI paths the flow
   still ends at the local file.

**Backend side (all wired):**

5. Pi `POST /api/v1/scans` (Ed25519-signed) → `require_agent` authenticates the device →
   [`ingest_scan`](/backend/services.md) authorises the submission, then
   [`persist_scan`](/backend/services.md) writes
   scans/scan_hosts/ports/services/cpes/findings, resolves each host's durable identity
   (`upsert_hosts_for_scan`), and enqueues `enrichment_jobs` — all in one transaction. *(Both ends
   are live: the route since DMI-63, the Pi-side uploader since DMI-66.)*
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

- **hardware-agent** — Python 3.13, Textual (TUI), Pydantic v2, Nmap + NSE, stdlib threads, `uv`,
  plus `httpx` + `cryptography` (ingest) and `websockets` (command channel).
- **backend** — Python 3.11+, FastAPI, SQLModel/SQLAlchemy 2, psycopg, Alembic, httpx, `uv`.
- **infra** — Supabase (managed Postgres 17), Railway (API + worker services).

# Citations

[1] [README.md](../../README.md)
[2] [CONTEXT.md](../../CONTEXT.md) — domain glossary
[3] [docs/architecture/ARCHITECTURE.md](../../docs/architecture/ARCHITECTURE.md) — target-state architecture
[4] [docs/README.md](../../docs/README.md) — human knowledge-base index
[5] [specs/015-read-path](../../specs/015-read-path/TRUTH.md)
