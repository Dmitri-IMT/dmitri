# Roadmap — Pi Agent

> **Status:** **wired end to end and verified on hardware (2026-09-11).** The Pi runs discovery →
> enumeration → service detection → NSE → normalization, and `agent.transport` carries both
> directions: an outbound WebSocket command channel that accepts scan requests, and a signed
> ingest client that uploads results. A scan triggered from the web reached the device, executed
> and returned results in about two minutes — see
> [`../tests/pi4-baseline-2026-09/results.md`](../tests/pi4-baseline-2026-09/results.md).
>
> **Sources:** [`ARCHITECTURE.md §2.1`](../architecture/ARCHITECTURE.md), [`ADR-001`](../adr/ADR-001-hardware-selection.md),
> [`ADR-002`](../adr/ADR-002-scanning-tools-selection.md), [`ADR-004`](../adr/ADR-004-scan-methodology.md),
> [`ADR-005`](../adr/ADR-005-security-model.md). **Neighbours:** [`BACKEND.md`](BACKEND.md), [`SECURITY.md`](SECURITY.md).

## Current state

- **Hardware: a Raspberry Pi 4 Model B Rev 1.5 (4 GB) is provisioned and running as of 2026-09-11.** This *is* the board [`ADR-001`](../adr/ADR-001-hardware-selection.md) selected — the earlier belief that only a Pi 3 was in hand was wrong. ADR-001 still carries a divergence annotation describing a Pi 3; correcting it is DMI-109's deliverable and is not done here, since a roadmap document does not change an ADR's status. Read from the device: `/proc/device-tree/model` → `Raspberry Pi 4 Model B Rev 1.5`, `MemTotal` → 3 886 904 kB, `vcgencmd get_throttled` → `0x0`. A **Pi 3 (1 GB) is also held**, deliberately, as the comparison unit for DMI-109's 1 GB vs 4 GB benchmark. The agent is installed at `/opt/dmitri-agent` on Debian 13 (trixie) with `uv`-managed Python 3.12 — see [`../PI-INSTALLER.md`](../PI-INSTALLER.md).
- **Dev today:** `hardware-agent/` runs on a developer machine (Windows/Linux), not on a Pi. Scans are launched **locally** via `ScanRunner` (`scanner/runner.py`), from the TUI or `dmitri agent`.
- **Output today:** normalized JSON on disk (`AGENT_OUTPUT_PATH` / `artifacts/`). Payload matches `contracts/schemas` — ingestible by `POST /api/v1/scans` when transport exists.
- **Egress, working:** Pi → backend `POST /api/v1/scans` with per-device **Ed25519 signature** ([`ADR-005`](../adr/ADR-005-security-model.md), amended 2026-07-24; private key on the Pi, backend verifies with the public key). The backend route landed with DMI-63, the device client (`agent.transport.ScanIngestClient`) with DMI-65, and the daemon that calls it with DMI-66. Verified against the hosted stack on 2026-09-11: 12 hosts and 20 findings ingested from the real device.
- **September scope:** [`BACKEND.md` B10](BACKEND.md#b10--september-mvp-) = **Control** — command channel (B6) and headless **`dmitri agent` daemon** are in scope.

✅ **RECONCILED:** ADR-005 originally assumed a *one-way push* agent. Control requires the backend
to **command** the Pi, so the agent channel is now **bidirectional** — amended in
[`ADR-011`](../adr/ADR-011-pi-command-channel.md) and reflected in the ADR-005 status note. The Ed25519
signature rules are reused for the WebSocket upgrade.

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

**Unblocked.** The appliance is a **Raspberry Pi 4 Model B 4 GB** — the ADR-001 target — flashed,
provisioned and running the agent as of 2026-09-11. ADR-001's BOM applies without exception: the
USB-C PSU and the Pi 4 case both fit.

Measured on the device against `192.168.15.0/24` (Ethernet, no throttling in any run):

| Mode | Outcome | Wall-time | Peak RSS |
|---|---|---|---|
| `quick` | completed | 2m 24s | 98 MiB |
| `nspi` | completed | 4m 34s | 101 MiB |
| `standard` | completed | 6m 36s | 102 MiB |
| `max` | completed | 9m 59s | **134 MiB** |

**The pipeline is network-bound, not memory-bound:** wall-time varies 4× across modes while peak
RSS moves 36 MiB. The 134 MiB worst case is ~13 % of a 1 GB board, which is why **DMI-109 is no
longer a go/no-go on the Pi 3** — it becomes a comparative benchmark across the two boards held.
Two caveats on these numbers: the target subnet is small (4–12 hosts), and the TUI's separate
`ScanRunner` path is not yet measured.

**B2B model ([`AUTH.md`](AUTH.md)):** a **technical installer** deploys the Pi on-site (vendor,
integrator, or customer IT). The **org admin** never provisions keys — they only use the web app
after the agent is online. Consumer pairing flows (QR, local setup pages for business users) are
**out of scope** for September.

| Step | Who | Status |
|------|-----|--------|
| ~~Procure BOM per ADR-001 (Pi 4 4GB, …)~~ — **Pi 4 Model B Rev 1.5 4 GB confirmed on-device 2026-09-11** | Vendor | ✅ |
| ~~Benchmark the full pipeline~~ — headless path measured, peak 134 MiB, no throttling | Installer | ✅ |
| **Benchmark the Pi 3 (1 GB)** for the DMI-109 comparison, and the TUI's separate `ScanRunner` path | Installer | 🔓 |
| ~~Flash Raspberry Pi OS Lite; headless SSH~~ — running Debian 13 (trixie) | Installer | ✅ |
| Assign a **static IP or DHCP reservation** — the device is on DHCP today | Installer | 🔓 |
| ~~Install `nmap`, `uv`, agent package; verify scan on hardware~~ — `/opt/dmitri-agent`, 643 tests green, scan `completed` | Installer | ✅ |
| Generate the Ed25519 keypair **on the Pi**; register its **public key** with the backend (creates the `agents` row). No secret leaves the device. | Installer + vendor playbook | 🔓 |
| Write `/etc/dmitri/agent.env` (`DEVICE_ID`, `DEVICE_PRIVATE_KEY`, `BACKEND_URL`) | Installer (SSH) | 🔓 |
| Enable `dmitri-agent.service`; verify WSS + ingest | Installer | 🔓 |
| Scheduled reboot policy — daemon reconnects via systemd | Installer / docs | 🔓 |

Track spend against ADR-001 budget (R$ 1.250 BOM). Parallelize with cloud work; E2E cannot ship without this.

## Pi runtime (September Control)

Production Pi runs a **headless daemon** (`dmitri agent`), not the TUI:

1. **systemd** starts `dmitri agent` on boot (reads `/etc/dmitri/agent.env`).
2. Daemon opens an **outbound WebSocket** to the backend and stays connected (reconnect on drop).
3. On command message: runs the **same scan pipeline as the TUI** (`ScanRunner` / stages → `nmap` subprocesses).
4. Uploads results via `POST /api/v1/scans`; sends command status over WS; waits for next command.
   If result persistence fails after scanning, there is no file to upload: report `failed` even
   though the daemon may still hold the returned payload in memory.
5. **TUI** remains for local dev/debug only — not the September demo path.

**Ops (planned):** `Restart=always` for process crashes; **scheduled machine reboot** every few days — daemon reconnects via systemd after reboot. Open connection = **online** in the UI.

## Other Pi-layer direction

- **Provisioning:** B2B **installer playbook** only for September — Ed25519 private key on Pi via `/etc/dmitri/agent.env`, public key registered with the backend; rotation Phase 2 ([`AUTH.md`](AUTH.md)).
- **Packaging:** ship the agent as a service (systemd) on Raspberry Pi OS Lite; today it is run interactively on dev machines.
- **Health/heartbeat:** the command channel naturally carries "Pi is alive" — surface it in the frontend device view.

## Milestones

-1. **Hardware acquisition + base configure** — procure Pi per ADR-001; OS Lite, SSH, nmap, agent smoke test on real hardware.
0. HTTP transport client + Ed25519 signing (Pi submit + backend verify) — closes the unwired contract gap.
1. ADR-011 ✅ ([`ADR-011`](../adr/ADR-011-pi-command-channel.md)). → *unblocks everything below*
2. `dmitri agent` daemon + systemd; **WebSocket client** + connection registry on API; Postgres command table for lifecycle/audit.
2b. **Interface reporting** ✅ — daemon enumerates its subnets and reports them on connect; the backend stores the operator's `target_subnet` and refuses a scan naming a network the Pi is not reporting (DMI-78, [B11-C2](BACKEND.md#b11--frontend-contract-asks-)). The remaining gap to the first web-triggered scan is the Agents screen itself.
3. "Trigger scan from web" end-to-end (frontend → backend → WS → Pi → results → frontend).
4. **Installer provisioning playbook** documented (vendor); scheduled reboot policy — rotation deferred Phase 2.
5. (fallback) HTTP poll delivery if WS ops block cutover — same command schema.

## Ripple

Changing the command channel **must** update [`BACKEND.md`](BACKEND.md) (queue + endpoints),
[`SECURITY.md`](SECURITY.md) (channel auth), and likely [`FRONTEND.md`](FRONTEND.md)
(trigger UX + device online state). Any change here that contradicts
[`ADR-005`](../adr/ADR-005-security-model.md) is a **⚠️ REVALIDATE** trigger.
