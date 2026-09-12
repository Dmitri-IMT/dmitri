# Pi 4 baseline — provisioning, measurement and E2E results

> **Date:** 2026-09-11/12 · **Location:** home LAN · **Target:** `192.168.15.0/24` (11-12 live hosts) · **Device:** Raspberry Pi 4 Model B Rev 1.5, 4 GB, Ethernet
>
> **Backend:** hosted `nspi` — `https://api.peirce.dev` · **Issues:** DMI-57 (provisioning), DMI-109 (measurement), DMI-67 (E2E)

---

## Executive summary

| Question | Answer |
|----------|--------|
| Which board is actually in hand? | **Raspberry Pi 4 Model B Rev 1.5, 4 GB** — the ADR-001 target, not the Pi 3 previously believed |
| Does the pipeline fit in memory? | **Yes, with ~8× headroom** — 134 MiB peak in the heaviest mode |
| Is the pipeline memory-bound? | **No — network-bound.** Wall-time varies 4× across modes; peak RSS moves 36 MiB |
| Thermal or power pressure? | **None.** `get_throttled = 0x0` throughout; temperature *fell* during three of four runs |
| Does the full E2E work? | **Yes** — web → backend → WS → Pi → results → web, ~2 min, 12 hosts / 20 findings |
| Does the device recover on its own? | **Yes for offline/restart** (~2 s reconnect); **no** once the channel parks (DMI-155) |
| Go/no-go for the pilot demo | **GO**, conditional on DMI-143, DMI-144 and DMI-155 |

---

## Environment

| Item | Value |
|------|-------|
| Board | Raspberry Pi 4 Model B Rev 1.5 (`/proc/device-tree/model`) |
| RAM | 3 886 904 kB — 4 GB board |
| CPU | 4 cores, aarch64 |
| OS | Debian 13 (trixie) |
| Python (system) | 3.13.5 — does **not** satisfy `requires-python >=3.11,<3.13` |
| Python (agent) | 3.12.14, provisioned by `uv` 0.12.13 |
| nmap | 7.95 |
| Agent | `hardware-agent` 0.1.4 at `/opt/dmitri-agent`, run as root |
| Network | Ethernet, DHCP, `192.168.15.13/24` |
| Power | `vcgencmd get_throttled = 0x0` on every run |

The system Python cannot run the agent, so `uv` provisions its own 3.12. This is deliberate,
not a workaround — see [`../../PI-INSTALLER.md`](../../PI-INSTALLER.md) §3.

---

## 1. Scan measurement battery — headless path

`dmitri agent <mode> <subnet>`, as root, measured with `/usr/bin/time -v`.

| # | Mode | Outcome | Wall-time | Peak RSS | CPU | Temp before → after |
|---|------|---------|-----------|----------|-----|---------------------|
| 1 | `quick` | ✅ completed (0) | 2m 24s | 100 184 kB (~98 MiB) | 6% | 52.1 → 49.6 °C |
| 2 | `nspi` | ✅ completed (0) | 4m 34s | 103 208 kB (~101 MiB) | 4% | 49.1 → 47.2 °C |
| 3 | `standard` | ✅ completed (0) | 6m 36s | 103 956 kB (~102 MiB) | 4% | 49.6 → 47.7 °C |
| 4 | `max` | ✅ completed (0) | 9m 59s | **137 416 kB (~134 MiB)** | 7% | 47.2 → 48.7 °C |
| 5 | `quick` (from `/opt`) | ✅ completed (0) | 1m 51s | 99 316 kB | — | — |

**Peak across all modes: 137 416 kB ≈ 134 MiB.**

### What the numbers mean

* **Network-bound, not memory-bound.** Between the lightest and heaviest mode wall-time varies
  4×, while peak RSS moves 36 MiB. The cost of the heavy modes is network and NSE.
* **134 MiB is ~13 % of a 1 GB board.** ADR-001 rejected the Pi 3 because "1 GB de RAM é muito
  pouco para ferramental de scan e buffering de resultados". These numbers do not support that
  claim at this subnet size. They are **not** proof the Pi 3 suffices — slower I/O and a smaller
  page cache are untested.
* **No thermal pressure at all.** Temperature fell during runs 1-3 and the CPU never exceeded 7%.

### Run without root

`nmap` needs root for TCP/IP fingerprinting. Without it:

```
nmap failed with exit code 1: TCP/IP fingerprinting (for OS scan) requires root privileges.
```

Outcome `partial`, exit 10. This is why `dmitri-agent.service` runs as root.

---

## 2. Agent test suite on the device

```
uv run pytest -q  ->  643 passed, 0 failed  (37 s)
```

An earlier run showed 11 failures in `tests/test_contract_models.py`, all caused by a missing
`/opt/contracts/openapi/openapi.yaml` — the suite resolves the contract one level above the
agent directory. Not a device fault; the layout requirement is documented in the playbook §4.

---

## 3. End-to-end verification (DMI-67)

### 3.1 First attempt — failed

| Step | Result |
|------|--------|
| Command dispatched from web | ✅ |
| Delivered over WS | ✅ frame reached the Pi |
| Pi executed the pipeline | ✅ ~5 min, discovery → ports → NSE |
| Upload to backend | ❌ `POST /api/v1/scans` → **500**, ×3 attempts |
| Status visible in web | ❌ stuck on "Queued" for the whole run |

Single root cause:

```
psycopg.errors.UndefinedTable: relation "activity" does not exist
```

Migration `20260905_19_home_activity_feed.py` had never been applied to the hosted database.
It produced three symptoms at once:

1. `GET /api/v1/home` → 500 — the home page would not load
2. `POST /api/v1/scans` → 500 — the scan was lost; the result file remained on the Pi
3. `apply_status` calls `append_scan_activity` before its commit, so **every status update
   rolled back** — hence "Queued" while the device scanned

The `commands` row kept `status='queued'` with `scan_id=NULL`, proving the *delivery*
transaction had rolled back too — after its WebSocket frame had already been sent.

Recovery needed a manual `UPDATE` on the production database, and the row could only be set to
`expired`: `ck_commands_scan_id_or_expired` permits no other terminal state when `scan_id IS NULL`.

Also found: the newest deployment sat in `NEEDS_APPROVAL`, so the running API was five days
behind `main`.

### 3.2 Second attempt — passed

After applying the migration:

| Step | Result |
|------|--------|
| Command `02:22:07` → scan `924d6598-…` | ✅ |
| Delivered, `scan_id` recorded | ✅ |
| Pi executed and uploaded | ✅ |
| Command terminal state | ✅ `done`, no error |
| Scan state | ✅ `completed` |
| Read path | ✅ **12 hosts, 20 findings, 2 activity rows** |
| End to end | **~2 minutes** |

### 3.3 Error paths

| Path | Method | Result |
|------|--------|--------|
| `503 device_offline` | `systemctl stop dmitri-agent`, then trigger a scan | ✅ two attempts, both `expired` / `device_offline` **immediately**; UI reported the device offline |
| `409 device_busy` | Observed unintentionally, from the stuck command above | ✅ backend refused new scans — but the Pi was idle (DMI-144) |
| Reconnect after restart | `systemctl start dmitri-agent` | ✅ `command channel connected` in ~2 s, `NRestarts=0` |

The reconnect result verifies DMI-57's scheduled-reboot requirement on real hardware: the daemon
re-establishes the channel with no intervention.

---

## 4. Caveats — read before quoting these numbers

* **The subnet is small** — 11-12 live hosts on a /24. A customer network with hundreds of hosts
  will differ, and memory is likeliest to grow where results are buffered. Always state the
  subnet alongside these figures.
* **The TUI path is unmeasured.** Per `.claude/CLAUDE.md` the TUI has its own `ScanRunner` that
  bypasses `ScanOrchestrator.run()` — and that is the path a demo would use.
* **The ALFA Wi-Fi adapter was not present**, so USB-bus contention is unmeasured.
* **One run per mode.** No repeats, no variance, no confidence interval.
* **The Pi 3 comparison is not done** — the board was unavailable. DMI-109 stays open for it.
* The E2E ran against deployment `fabc876` (2026-09-06), not the newer approved build.

---

## 5. Issues raised by this campaign

| Issue | Severity | What |
|-------|----------|------|
| DMI-143 | Urgent | WS frame sent before the delivery transaction commits |
| DMI-144 | Urgent | A non-terminal command bricks the agent; no duration timeout |
| DMI-155 | Urgent | A parked command channel never reconnects |
| DMI-145 | High | No way to cancel a running scan |
| DMI-146 | High | A failed upload loses the scan; no resend queue |
| DMI-147 | High | No agent update mechanism (ADR) |
| DMI-148 | High | Scan status screen: presentation, copy, Retry |
| DMI-153 | High | Toast outside the design system; fixed width, no severity variants |
| DMI-154 | High | Automate provisioning with a script |
| DMI-149 | Medium | Per-stage progress exists on the device and is discarded |
| DMI-150 | Medium | Tooltip primitive was deferred and never built |
| DMI-151 | Medium | ESLint exempts `src/components/ui/**` |
| DMI-152 | Medium | TopBar identity and the FOUNDATIONS no-avatar rule |

**None of these break a test.** The agent suite is green at 643 passed and the backend suite
passes. Every one required real hardware, a hosted backend, or an unapplied migration to appear
— which is the argument for running this campaign again after the urgent fixes land, and before
the demo rather than during it.
