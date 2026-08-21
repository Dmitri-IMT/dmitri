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

- **Hardware: a Raspberry Pi 3 is in possession as of 2026-08-21** (exact model — B or B+ — to confirm). This is **not** the board [`ADR-001`](../adr/ADR-001-hardware-selection.md) selected: that ADR specifies a Pi 4 Model B 4 GB and explicitly **rejected** the Pi 3 B+ for **1 GB RAM** and **USB 2.0 I/O**. The ADR is annotated, not reversed — the Pi 4 remains the documented target. Still to do: flash, provision and **prove the pipeline actually fits in 1 GB** before the September E2E — see [Hardware acquisition](#hardware-acquisition--open).
- **Dev today:** `hardware-agent/` runs on a developer machine (Windows/Linux), not on a Pi. Scans are launched **locally** via `ScanRunner` (`scanner/runner.py`), from the TUI or `dmitri agent`.
- **Output today:** normalized JSON on disk (`AGENT_OUTPUT_PATH` / `artifacts/`). Payload matches `contracts/schemas` — ingestible by `POST /api/v1/scans` when transport exists.
- **Planned egress:** Pi → backend `POST /api/v1/scans` with per-device **Ed25519 signature** ([`ADR-005`](../adr/ADR-005-security-model.md), amended 2026-07-24; private key on the Pi, backend verifies with the public key) — **implemented on both sides but not yet wired**: the backend route landed with DMI-63 and the device client (`agent.transport.ScanIngestClient`) with DMI-65. What is missing is the daemon that calls it (DMI-66).
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

**Unblocked, with a caveat:** a Raspberry Pi 3 is now in hand, so September Scenario B has a real
appliance. But it is the board ADR-001 rejected, so "we have hardware" is not the same as "the
hardware is adequate" — the 1 GB RAM and USB 2.0 constraints are unproven against this pipeline
and are now the top Pi-side risk. **DMI-109** measures then decides, producing **ADR-018**; it blocks DMI-57 so the installer playbook is written once against a settled baseline. Two BOM items from ADR-001 do **not** fit a Pi 3: the USB-C PSU
(the Pi 3 uses micro-USB) and the Pi 4 case/cooler (different footprint).

**B2B model ([`AUTH.md`](AUTH.md)):** a **technical installer** deploys the Pi on-site (vendor,
integrator, or customer IT). The **org admin** never provisions keys — they only use the web app
after the agent is online. Consumer pairing flows (QR, local setup pages for business users) are
**out of scope** for September.

| Step | Who | Status |
|------|-----|--------|
| ~~Procure BOM per ADR-001 (Pi 4 4GB, …)~~ — **board acquired 2026-08-21, but a Pi 3, not the Pi 4** | Vendor | ⚠️ |
| Confirm the exact Pi 3 model (B vs B+) — decides Ethernet ceiling (100 Mbit vs ~300 Mbit over USB 2.0) | Installer | 🔓 |
| Source a **micro-USB** PSU and a Pi 3 case/cooler — the ADR-001 USB-C PSU and Pi 4 case do not fit | Vendor | 🔓 |
| **Benchmark the full pipeline on the Pi 3**: peak RSS under 1 GB, subnet sweep wall-time, `ScanRunner` parallelism. Feeds the go/no-go on a new hardware ADR | Installer | 🔓 |
| Flash Raspberry Pi OS Lite; headless SSH; static IP or DHCP reservation | Installer | 🔓 |
| Install `nmap`, `uv`, agent package; verify scan on hardware | Installer | 🔓 |
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
