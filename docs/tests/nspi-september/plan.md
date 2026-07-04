# NSPi September — internet-dependency plan

> **What this is:** the decision path for running Dmitri on the **NSPi network, which has no
> internet access**. Today every scan mode runs the `vulners` NSE script
> (`hardware-agent/src/agent/config.py`), which calls `vulners.com` live during the scan, and the
> backend enrichment engine (`backend/src/api/services/nvd.py`) calls the NVD/KEV/EPSS APIs live.
> Neither works on an air-gapped network. This plan validates the cheapest fix first, then commits
> to an offline architecture only if that fails.
>
> **Results:** [`results.md`](results.md) · **Neighbours:** [`../../roadmap/PI.md`](../../roadmap/PI.md),
> [`../../roadmap/BACKEND.md`](../../roadmap/BACKEND.md), [`../../roadmap/TASKS.md`](../../roadmap/TASKS.md).
> **ADRs:** [`ADR-011`](../../adr/ADR-011-pi-command-channel.md).

---

## The two internet dependencies (they stand or fall together)

The NSPi network has no internet, so **two** things break, not one:

| Dependency | Where | Needs internet for |
|------------|-------|--------------------|
| `vulners` NSE script | scanner (`config.py`, every mode) | CPE→CVE lookup at `vulners.com` during the scan |
| Backend enrichment + upload | `nvd.py`, `kev.py`, `epss.py`, `POST /scans` | reaching the cloud backend and the NVD/KEV/EPSS APIs |

Because both need the *same* missing thing — a route to the public internet — a single bridge
(operator laptop dual-homed to wifi) would solve **both** at once. That is what Phase 1 tests.

---

## Phase 1 — Validate dual-homing (do this first, no build)

**Hypothesis:** an operator laptop connected to **both** the NSPi network (to scan) **and** university
wifi (for the internet) lets nmap reach NSPi targets while `vulners` and the backend upload reach the
internet over wifi — the OS routing table splits the two flows by destination.

### Pre-flight checks

- [x] NSPi subnet and university wifi subnet **do not overlap** (NSPi `192.168.0.0/24` vs wifi on a
      separate range).
- [x] From the laptop on wifi, outbound internet works (used for `vulners` during scan).

### Setup

- [x] Ethernet → NSPi network with a **static IP and no default gateway** (or NSPi interface route
      metric set *higher* than wifi).
- [x] Wifi → university, holding the **default route** (`0.0.0.0/0`).
- [x] Confirmed: NSPi subnet reachable over ethernet; internet over wifi.

#### Step-by-step: connecting to both networks at once (Windows)

The goal is a laptop where **wifi carries internet** and **ethernet carries only NSPi traffic**. The
OS routing table decides per-packet which interface to use, so the two connections coexist as long as
exactly one interface owns the default route.

1. **Connect wifi first.** Join university wifi normally and confirm internet works
   (`curl https://vulners.com`). This interface keeps DHCP and its default gateway — it owns
   `0.0.0.0/0`.

2. **Plug in ethernet to the NSPi switch.** Do **not** let it grab a default gateway. Set the
   ethernet adapter to a **static IP** on the NSPi subnet with the **gateway field left blank**:
   - Settings → Network → Ethernet → *Edit IP assignment* → Manual → IPv4 on.
   - IP address: a free address on the NSPi subnet (e.g. `192.168.0.x`).
   - Subnet mask/prefix: match NSPi (e.g. `255.255.255.0` / prefix `24`).
   - Gateway: **leave empty**. DNS: leave empty.
   - Or via PowerShell (admin):
     ```powershell
     New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.0.10 -PrefixLength 24
     ```
     (no `-DefaultGateway`, so ethernet never becomes the default route).

3. **Verify the split.** Run `Get-NetRoute -DestinationPrefix 0.0.0.0/0` — the only default route
   should list the **wifi** interface. Run `Get-NetRoute` and confirm the NSPi subnet
   (e.g. `192.168.0.0/24`) routes via **ethernet**. `Get-NetIPConfiguration` shows both adapters up.

4. **If ethernet insists on a gateway** (some setups auto-assign one), raise its route metric so wifi
   wins the tie for internet-bound traffic:
   ```powershell
   Set-NetIPInterface -InterfaceAlias "Ethernet" -InterfaceMetric 50
   Set-NetIPInterface -InterfaceAlias "Wi-Fi"   -InterfaceMetric 10
   ```
   Lower metric = higher priority, so wifi (10) beats ethernet (50) for `0.0.0.0/0`.

5. **Prove both flows before scanning.** From the laptop, `ping` a known NSPi device (rides ethernet)
   **and** `curl https://vulners.com` (rides wifi) — both must succeed **at the same time**. If either
   fails, fix routing before running the scan; a failure here is the routing problem, not a scan bug.

### Run

- [x] Run `nspi` and `quick` scans against `192.168.0.0/24` from the laptop (2026-07-03).

### Success criteria

| Criterion | Result |
|-----------|--------|
| Scan **completes** (nmap reached NSPi subnet over ethernet) | **Partial** — Quick ✅; NSPi cancelled during port stage (see [`results.md`](results.md)) |
| At least one finding has a **`vulners` source** with a CVE | **Pass** — manual nmap + Quick scan |
| `POST /scans` upload succeeds | **Not tested** |

> **Honest caveat (already known):** even if this passes, it only unblocks the **laptop-operated NSPi
> pilot**. The production Pi appliance sits permanently on NSPi with **no second uplink**, so dual-homing
> can never run there. Phase 1 buys the pilot; it does not solve the appliance. See Phase 2.

---

## Decision gate

| Outcome | Next |
|---------|------|
| **Phase 1 passes** ✅ | Document the dual-home setup as the **NSPi pilot operating procedure** (this folder). **Close the field test** — no retest planned. Proceed with the roadmap (T4/T5/T6/T7). Pilot uses **Quick scan** on dual-homed laptop; NSPi mode fix ([`TASKS.md` T4.1](../../roadmap/TASKS.md)) proceeds in dev without blocking. Offline appliance question **deferred**. |
| **Phase 1 fails** | The pilot itself needs offline scanning → go to **Phase 2** (write the ADR + downstream design). |

**Gate (2026-07-03):** Phase 1 **passes** for the supervised laptop pilot. Dual-homing works; `vulners`
reaches the internet while scanning the air-gapped subnet. NSPi scan mode has a separate product bug
(tracked in T4.1), not a routing failure.

---

## Phase 2 — Offline scanning ADR (only if Phase 1 fails, or when the appliance must be air-gapped)

Write **`docs/adr/ADR-0NN-nspi-offline-scanning.md`** covering the decisions below. This is the
architecture, captured so it survives. None of it is speculative build work — it is the *correct shape*
for an air-gapped Pi regardless of the factory scenario.

### Scanner

- Drop `vulners` from the `nspi` profile (`config.py`). `nmap -sV` already yields **CPEs offline** — no
  internet needed. The scanner produces raw observations only.

### Enrichment (the real work, server-side, already mostly built)

- The cross-check **already exists**: `enrichment.py` + `nvd.py` + `risk.py`. Offline = swap the **one**
  online seam, `NvdClient._query` (`nvd.py:26`), for a local data source. Everything downstream
  (`parse_nvd_matches`, findings, risk) is unchanged.
- **NVD** is the hard part (CPE version-range matching). **Do not hand-roll it.** Run a maintained local
  NVD service (e.g. `go-cve-dictionary`) as a **separate process** and point `NvdClient.base_url` at it.
- **KEV** = one CISA JSON file; **EPSS** = a daily CSV. Both are trivial file mirrors.

### Licensing

- Vuls / `go-cve-dictionary` are **GPLv3**. For **NSPi-only** this is accepted (per project owner).
- Running the Go tool as a **separate process over HTTP** is the weakest GPL coupling and needs almost no
  new code. Reimplement matching in Python **only** if a *commercial, shipped* product later needs it
  license-clean — and then do it **clean-room from the public NIST/NVD CPE-2.3 spec**, never by porting
  GPL source (a line-by-line translation is still a derivative work). Get legal sign-off if it ships for money.

### Downstream — "how the rest works"

- **Backend API / contract:** no contract change. Enrichment already runs server-side and async
  (`enrichment_job` queue); offline is a config change (`base_url` → local mirror), not a schema change.
  The `vulners` source label disappears from findings; NVD/KEV/EPSS labels stay.
- **Where the backend runs (the crux):** on NSPi there is no internet, so the Pi **cannot reach a cloud
  backend either**. Two deployment shapes — pick one in the ADR:
  - **(a) Laptop/edge bridge** — an operator machine on-site relays scan upload + enrichment to the cloud
    (this is just Phase 1 generalized; fine for a supervised pilot).
  - **(b) On-site stack** — backend + local NVD mirror + frontend run **inside** NSPi; CVE data refreshed
    out-of-band; results sync to cloud later (or never). This is the true air-gap product.
- **Frontend:** consumes the same contract — no change. Findings still flow via `/scans` and `/hosts`.
  In shape (b) the SPA is served from the on-site stack (Railway-static today → local host).
- **Mirror freshness:** define how/when the local NVD/KEV/EPSS data is refreshed (cadence, who runs it,
  how it reaches the air-gapped side). This is the only genuinely *new* operational surface.

---

## Status

- [x] Phase 1 dual-home test — **done 2026-07-03** ([`results.md`](results.md)).
- [x] Decision gate — **Phase 1 passes**; pilot SOP is dual-homed laptop + Quick scan.
- [x] Field test **closed** — findings accepted; no retest scheduled.
- [ ] Phase 2 ADR — **deferred** (not needed for supervised pilot).
- [ ] NSPi port-stage fix (T4.1) — **dev work only**; not gated on another NSPi visit.
