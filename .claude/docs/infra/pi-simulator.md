---
type: Infrastructure
title: Local Pi simulator
description: The ephemeral Docker harness that runs the real agent, backend, worker, Postgres, and a Samba scan target.
resource: simulator.sh
tags: [infra, docker, simulator, hardware-agent, samba, integration]
timestamp: 2026-08-25T00:00:00Z
---

# Local Pi simulator

## Purpose

`simulator.sh` and `docker/pi-simulator/` provide a local, full-wire Pi substitute for generating
real scan data. The local mode builds the production agent package into a Debian container, creates
an isolated Postgres database, migrates and seeds one throwaway organization and agent, starts the
real API and worker, and scans a Samba service on the fixed `172.31.7.0/24` bridge. The harness is
deliberately ephemeral: scans live only until `./simulator.sh stop` removes its volumes.

The alternate `--nspi` mode is connect-only. It starts the agent and target without a local API,
database, migration, seed, or automatic provisioning, and requires credentials for a manually
provisioned agent in a dedicated throwaway organization.

## Key files / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `simulator.sh` | Selects local or `--nspi` compose, requires the ignored `.env`, dispatches `start`, `scan`, `stop`, `logs`, and help. | `simulator.sh:23-148` |
| `start` | A running stack is a no-op; a cold start removes old volumes, rebuilds, and starts detached. | `simulator.sh:63-81` |
| `scan` | Refuses deployed mode; locally logs in as the seeded admin, finds the simulated agent, and enqueues the requested mode/subnet. | `simulator.sh:83-129` |
| `compose.yaml` | Defines Postgres 16, one-shot migration and seed jobs, API, worker, real agent, and Samba target on `172.31.7.0/24`. | `docker/pi-simulator/compose.yaml:1-98` |
| `compose.nspi.yaml` | Starts only the real agent and target and requires `BACKEND_URL`, `DEVICE_ID`, and `DEVICE_PRIVATE_KEY` from the operator's ignored env file. | `docker/pi-simulator/compose.nspi.yaml:1-22` |
| `seed.sh` | Bootstraps the local org/admin, provisions an Ed25519 agent, and writes its environment to the shared volume with mode 600. | `docker/pi-simulator/seed.sh:1-41` |
| `agent.Dockerfile` / `agent-entrypoint.sh` | Installs Nmap plus the real `hardware-agent`, imports the seeded environment into `/etc/dmitri/agent.env`, then execs `dmitri agent`. | `docker/pi-simulator/agent.Dockerfile:1-17`; `docker/pi-simulator/agent-entrypoint.sh:1-6` |
| `target.Dockerfile` / `smb.conf` | Runs Samba with guest access on TCP 139/445, supplying real service and host-script output for the Nmap pipeline. | `docker/pi-simulator/target.Dockerfile:1-12`; `docker/pi-simulator/smb.conf:1-10` |
| `.env.example` | Supplies local-only DB/auth settings and the seeded admin identity; deployed credentials are intentionally absent. | `docker/pi-simulator/.env.example:1-20` |

## How it connects

- The container runs the real [`AgentDaemon`](/hardware-agent/daemon.md),
  [`CommandChannelClient`](/hardware-agent/command-channel.md), scan engine
  ([scanner](/hardware-agent/scanner/index.md)), and ingest client
  ([transport](/hardware-agent/transport.md)).
- Local API, worker, migrations, and persistence are the same backend modules mapped under
  [backend](/backend/index.md); only the database and credentials are isolated for the harness.
- The parent [deployment map](./deployment.md) covers the ordinary installers and hosted Railway +
  Supabase topology. The operator-facing commands and T1–T8 checks live in the
  [simulator runbook](../../../docker/pi-simulator/README.md).

## Notes / gotchas

- `simulator.sh` intentionally has no `.ps1` mirror. It is a Linux-container harness whose Windows
  path is not tested; this is the registered exception to the root-script mirror rule
  (`simulator.sh:13-18`).
- Local mode owns host ports 8000 and 55432 (`compose.yaml:22-23,39-43`); stop a hand-run backend
  before starting it.
- The agent needs `NET_RAW` and `NET_ADMIN` to perform the real scan (`compose.yaml:73-82`). Dropping
  those capabilities is a failure-path check, not a supported run configuration.
- `--nspi scan` is always refused because the container would report its laptop bridge as customer
  scan data (`simulator.sh:83-88`). Connecting at all remains a manual operator action after
  confirming the agent belongs to a throwaway org, never the pilot org.
- `.dockerignore` excludes every `.env`, virtual environment, cache, and frontend build artifact
  from image contexts; secrets must not be baked into either image (`.dockerignore:1-10`).

# Citations

[1] [Spec 037 task ledger](../../../specs/037-local-pi-simulator/TASKS.md)
[2] [Pi simulator runbook](../../../docker/pi-simulator/README.md)
[3] [Simulator research](../../../docs/research/pi-simulator-and-integration-test-harness.md)
