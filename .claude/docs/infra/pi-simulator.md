---
type: Infrastructure
title: Local Pi simulator
description: Docker harness for the real agent/backend plus the legacy SMB target and an isolated multi-service targeted-scan lab.
resource: simulator.sh
tags: [infra, docker, simulator, hardware-agent, samba, integration]
timestamp: 2026-10-22T00:00:00Z
---

# Local Pi simulator

## Purpose

`simulator.sh` and `docker/pi-simulator/` provide a local, full-wire Pi substitute for generating
real scan data. The standard local mode builds the production agent package into a Debian
container, creates an isolated Postgres database, migrates and seeds one throwaway organization
and agent, starts the real API and worker, and scans the legacy Samba service on the
`172.31.7.0/24` bridge. The separate `lab-start`/`lab-scan`/`lab-verify`/`lab-stop` workflow
uses a Compose overlay and project to add five synthetic vulnerable service targets on internal
`172.31.13.0/28`; scan CIDR is `172.31.13.0/29`, with agent `.13` and gateway `.14`
outside it; application services remain off the target network.
The isolated project protects stopped data in the standard simulator. Both workflows are local
and ephemeral when their matching stop command removes their volumes.

The alternate `--nspi` mode is connect-only. It starts the agent and target without a local API,
database, migration, seed, or automatic provisioning, and requires credentials for a manually
provisioned agent in a dedicated throwaway organization.

## Key files / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `simulator.sh` | Selects local or `--nspi` compose, requires the ignored `.env`, and dispatches standard simulator and targeted-lab commands. On Git Bash, disables MSYS argument path conversion so `/verify_targeted_scan.py` reaches Docker unchanged. | `simulator.sh:23-186` |
| `start` | A running stack is a no-op; a cold start removes old volumes, rebuilds, and starts detached. | `simulator.sh:63-81` |
| `scan` | Refuses deployed mode; locally logs in as the seeded admin, finds the simulated agent, and enqueues the requested mode/subnet. | `simulator.sh:83-129` |
| `lab-start` | Reconciles/rebuilds the isolated lab Compose project, reuses prior agent provisioning, and retains its scan database volume and standard simulator data. | `simulator.sh:95-105` |
| `compose.yaml` | Defines Postgres 16, migration/seed jobs, API, worker, real agent, and legacy Samba target on `172.31.7.0/24`. | `docker/pi-simulator/compose.yaml:1-90` |
| `compose.lab.yaml` | Adds the internal `172.31.13.0/28` network, five fixed-IP targets, dual-homed agent at `.13` outside the `/29` scan CIDR, and verifier mount. | `docker/pi-simulator/compose.lab.yaml:1-65` |
| `verify_targeted_scan.py` | Fetches one persisted extensive scan, validates host/port coverage, targeted/NSE/Vulners observations, and prints findings with their evidence. Nikto evidence remains inconclusive under the production parser. | `docker/pi-simulator/verify_targeted_scan.py:1-202` |
| `compose.nspi.yaml` | Starts only the real agent and target and requires `BACKEND_URL`, `DEVICE_ID`, and `DEVICE_PRIVATE_KEY` from the operator's ignored env file. | `docker/pi-simulator/compose.nspi.yaml:1-22` |
| `seed.sh` | Bootstraps the local org/admin, provisions an Ed25519 agent, and writes its environment to the shared volume with mode 600. | `docker/pi-simulator/seed.sh:1-41` |
| `agent.Dockerfile` / `agent-entrypoint.sh` | Installs Nmap/NSE, pinned ffuf, Nikto, testssl and enum4linux-ng plus the real `hardware-agent`; imports the seeded environment into `/etc/dmitri/agent.env`, then execs `dmitri agent`. | `docker/pi-simulator/agent.Dockerfile`; `docker/pi-simulator/agent-entrypoint.sh:1-6` |
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

The physical-Raspberry target-only lab is a separate project at `docker/targeted-lab/`; it
starts six targets and no agent/backend/database. It requires Docker Engine on a bridged
Linux VM with macvlan support. See its README and the `053-targeted-scan-lab` architecture.

- `simulator.sh` intentionally has no `.ps1` mirror. Its Git Bash path is tested; `MSYS_NO_PATHCONV`
  prevents the Linux verifier path from being rewritten before the Docker CLI receives it.
- The lab chooses `172.31.13.0/29` within the agent-reported Docker network `172.31.13.0/28`.
  Backend enqueue and preferred-subnet validation accept contained IPv4 subnets and continue to
  reject invalid or external networks; this keeps the agent `.13` and gateway `.14` outside scan.
- Nikto retains broad tuning and uses 700 s native / 800 s unit limits after direct HTTP/HTTPS measurements of 565/582 s. Final scan `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` passed strict verification (5 hosts, 90 findings); payload: `../../scan-results/targeted-lab-2026-10-22.json`.
  HTTPS lab measurements of 565 s and 582 s. The final integrated scan `b1dd4b7b-865a-4962-b2e4-df111a4e4a0f` passed the strict verifier
  with five hosts and 90 findings; payload: `../../scan-results/targeted-lab-2026-10-22.json`.
- Local mode owns host ports 8000 and 55432 (`compose.yaml:22-23,39-43`); stop a hand-run backend
  before starting it.
- Targeted lab services have no published host ports and only attach to the internal lab network;
  only the agent also joins it (`compose.lab.yaml`). The agent needs outbound DNS/HTTPS for
  remote Vulners version correlation.
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
