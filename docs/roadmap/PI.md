# Roadmap — Pi Agent

> **Status:** built for **local scanning**. The Pi runs discovery → enumeration → service detection →
> NSE → normalization via the TUI, then **writes JSON to `hardware-agent/artifacts/`**. There is
> **no HTTP client to the backend** in the repo (`transport/` described in older docs was never
> added). There is **no inbound path** to ask the Pi to scan on demand. Closing that gap is the
> headline product decision below.
>
> **Sources:** [`ARCHITECTURE.md §2.1`](../architecture/ARCHITECTURE.md), [`ADR-001`](../adr/ADR-001-hardware-selection.md),
> [`ADR-002`](../adr/ADR-002-scanning-tools-selection.md), [`ADR-004`](../adr/ADR-004-scan-methodology.md),
> [`ADR-005`](../adr/ADR-005-security-model.md). **Neighbours:** [`BACKEND.md`](BACKEND.md), [`SECURITY.md`](SECURITY.md).

## Current state

- **Hardware: none in possession.** Target BOM per [`ADR-001`](../adr/ADR-001-hardware-selection.md): Raspberry Pi 4 (4 GB), headless, ALFA Wi-Fi adapter. **Must acquire and configure before September E2E** — see [Hardware acquisition](#hardware-acquisition--open).
- **Dev today:** `hardware-agent/` runs on a developer machine (Windows/Linux), not on a Pi. Scans are launched **locally** via the TUI's `ScanRunner`.
- **Output today:** normalized JSON on disk (`AGENT_OUTPUT_PATH` / `artifacts/`). Payload matches `contracts/schemas` — ingestible by `POST /api/v1/scans` when transport exists.
- **Planned egress:** Pi → backend `POST /api/v1/scans` with per-device **HMAC-SHA256** ([`ADR-005`](../adr/ADR-005-security-model.md)) — **not implemented** on either side.
- **September scope:** [`BACKEND.md` B10](BACKEND.md#b10--september-mvp-) = **Control** — command channel (B6) and headless **`dmitri agent` daemon** are in scope.

✅ **RECONCILED:** ADR-005 originally assumed a *one-way push* agent. Control requires the backend
to **command** the Pi, so the agent channel is now **bidirectional** — amended in
[`ADR-011`](../adr/ADR-011-pi-command-channel.md) and reflected in the ADR-005 status note. The HMAC
rules are reused for the WebSocket upgrade.

## The gap: remote-commandable Pi

Goal: from the web app, an operator triggers a scan (mode + target) and the Pi executes it,
then pushes results back through the **existing** ingestion path. We need a **command channel**
from backend → Pi. The hard constraint: the Pi typically sits **behind NAT/firewall** with **no
stable inbound address**, and we deliberately avoided an external broker
([`ADR-009`](../adr/ADR-009-database-stack.md) chose a Postgres job queue over a broker).

### Transport decision ✅

**Option C — outbound WebSocket** for September v1.

- Pi daemon dials `wss://…/api/v1/agents/{agent_id}/commands` and keeps the connection open.
- Backend pushes scan commands down the socket when an operator triggers "Scan now".
- Postgres stores command rows for lifecycle and audit ([`BACKEND.md` B6](BACKEND.md#b6--pi-command-channel-)).
- **Pros chosen:** instant trigger; live online/offline; still outbound-only (NAT-friendly).
- **Accepted cost:** stateful API (connection registry, reconnect, heartbeat); Railway NSPi likely **one API replica** or sticky sessions until scaled.

### Options not chosen (reference)

**A. Pi pulls a command queue (polling / long-polling)** — deferred; simpler fallback if WS blocks September.
**B. Pi exposes HTTP** — poor fit for NAT.
**D. External broker (MQTT / Redis)** — contradicts ADR-009.

**Action:** ~~write ADR-011~~ ✅ [`ADR-011`](../adr/ADR-011-pi-command-channel.md). Channel auth in [`SECURITY.md`](SECURITY.md).

### Command handling on the Pi ✅

Matches [`BACKEND.md` B6](BACKEND.md#b6--pi-command-channel-):

- Accept WS message with backend-assigned `command_id` + `scan_id` + `scan_mode` + `subnet`.
- **Idempotent** on `command_id` — duplicates ack without re-scan.
- **One scan at a time** — reject/ignore new commands while `running` or `uploading`.
- Status over WS: `running` → `uploading` → `done` \| `failed`.
- Ingest uses the command's **`scan_id`** (not a locally generated UUID).

### Interface reporting 🔓 — new, blocks the first scan

**The Pi must report the networks it can see.** On WS connect (and on reconnect, since interfaces
change), the daemon enumerates its own interfaces and sends the backend a list of
**`available_subnets`** — for each: the CIDR, the interface name, and whether it holds the default
route.

**Why this exists.** `POST /commands` requires a `subnet` CIDR, and **nobody can supply one**. The
org admin is non-technical and does not know their CIDR ([`AUTH.md`](AUTH.md) — they never touch
provisioning). And the Pi **cannot guess**: it is deliberately **dual-homed** ([NSPi field
test](../tests/nspi-september/plan.md)) — ethernet onto the target subnet with **no default
gateway**, wifi for internet so CVE enrichment can reach `vulners.com` while scanning an isolated
network. It therefore sees **two** networks, and scanning the wrong one (the host site's own wifi)
would be useless and hostile.

So the Pi **reports**, a human **chooses once**, and the backend **stores** the choice as
`agent.target_subnet` ([`BACKEND.md` B11-C2](BACKEND.md#b11--frontend-contract-asks-)). Thereafter
`[Scan now]` is a single button and no CIDR is ever typed
([`ui/FLOWS.md` B4](../ui/FLOWS.md#b4--scan-now-command-flow)).

- **Reported, not stored on the Pi** — the backend holds `target_subnet`; the Pi holds nothing.
- The default-route flag is what lets the UI label the choices honestly (the interface *with* the
  default route is the internet link, and is almost never the scan target).
- Until a `target_subnet` is chosen, the agent is online but **cannot be scanned** — the first-run
  flow makes choosing it the step before the first scan.

---

## Hardware acquisition & installer provisioning

**Blocker:** no Raspberry Pi owned yet. September Scenario B needs a real appliance on the network.

**B2B model ([`AUTH.md`](AUTH.md)):** a **technical installer** deploys the Pi on-site (vendor,
integrator, or customer IT). The **org admin** never provisions secrets — they only use the web app
after the agent is online. Consumer pairing flows (QR, local setup pages for business users) are
**out of scope** for September.

| Step | Who | Status |
|------|-----|--------|
| Procure BOM per ADR-001 (Pi 4 4GB, PSU, microSD, case/cooling, ALFA Wi-Fi) | Vendor | 🔓 |
| Flash Raspberry Pi OS Lite; headless SSH; static IP or DHCP reservation | Installer | 🔓 |
| Install `nmap`, `uv`, agent package; verify scan on hardware | Installer | 🔓 |
| Create `agents` row + secret on backend; hand secret to installer once | Vendor playbook | 🔓 |
| Write `/etc/dmitri/agent.env` (`DEVICE_ID`, `DEVICE_SECRET`, `BACKEND_URL`) | Installer (SSH) | 🔓 |
| Enable `dmitri-agent.service`; verify WSS + ingest | Installer | 🔓 |
| Scheduled reboot policy — daemon reconnects via systemd | Installer / docs | 🔓 |

Track spend against ADR-001 budget (R$ 1.250 BOM). Parallelize with cloud work; E2E cannot ship without this.

## Pi runtime (September Control)

Production Pi runs a **headless daemon** (`dmitri agent`), not the TUI:

1. **systemd** starts `dmitri agent` on boot (reads `/etc/dmitri/agent.env`).
2. Daemon opens an **outbound WebSocket** to the backend and stays connected (reconnect on drop).
3. On command message: runs the **same scan pipeline as the TUI** (`ScanRunner` / stages → `nmap` subprocesses).
4. Uploads results via `POST /api/v1/scans`; sends command status over WS; waits for next command.
5. **TUI** remains for local dev/debug only — not the September demo path.

**Ops (planned):** `Restart=always` for process crashes; **scheduled machine reboot** every few days — daemon reconnects via systemd after reboot. Open connection = **online** in the UI.

## Other Pi-layer direction

- **Provisioning:** B2B **installer playbook** only for September — secret on Pi via `/etc/dmitri/agent.env`; rotation Phase 2 ([`AUTH.md`](AUTH.md)).
- **Packaging:** ship the agent as a service (systemd) on Raspberry Pi OS Lite; today it is run interactively on dev machines.
- **Health/heartbeat:** the command channel naturally carries "Pi is alive" — surface it in the frontend device view.

## Milestones

-1. **Hardware acquisition + base configure** — procure Pi per ADR-001; OS Lite, SSH, nmap, agent smoke test on real hardware.
0. HTTP transport client + HMAC signing (Pi submit + backend verify) — closes the unwired contract gap.
1. ADR-011 ✅ ([`ADR-011`](../adr/ADR-011-pi-command-channel.md)). → *unblocks everything below*
2. `dmitri agent` daemon + systemd; **WebSocket client** + connection registry on API; Postgres command table for lifecycle/audit.
2b. **Interface reporting** — daemon enumerates its subnets and reports them on connect; backend stores the operator's `target_subnet`. Blocks the first web-triggered scan ([B11-C2](BACKEND.md#b11--frontend-contract-asks-)).
3. "Trigger scan from web" end-to-end (frontend → backend → WS → Pi → results → frontend).
4. **Installer provisioning playbook** documented (vendor); scheduled reboot policy — rotation deferred Phase 2.
5. (fallback) HTTP poll delivery if WS ops block cutover — same command schema.

## Ripple

Changing the command channel **must** update [`BACKEND.md`](BACKEND.md) (queue + endpoints),
[`SECURITY.md`](SECURITY.md) (channel auth), and likely [`FRONTEND.md`](FRONTEND.md)
(trigger UX + device online state). Any change here that contradicts
[`ADR-005`](../adr/ADR-005-security-model.md) is a **⚠️ REVALIDATE** trigger.
