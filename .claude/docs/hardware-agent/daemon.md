---
type: Entry Point
title: daemon — the unattended command executor
description: The long-lived device process runs remote scans, reports compact progress, and delegates negotiated update requests to the persistent companion.
resource: hardware-agent/src/agent/daemon.py
tags: [hardware-agent, daemon, command-channel, ingest, lifecycle, asyncio, cancel]
timestamp: 2026-10-20T00:00:00Z
---

# daemon — the unattended command executor

## Purpose

`agent.daemon` (DMI-66, spec 026; remote cancel DMI-145 / spec 049) is the coordinator that finally
joins the two halves that already existed: the [command channel](/hardware-agent/command-channel.md)
that carries work in, and the [headless scan](/hardware-agent/cli.md) +
[ingest client](/hardware-agent/transport.md) that do the work and send results back. Bare
`dmitri agent` starts it.

It adds **no** scan pipeline. It calls `run_headless_scan` as the one-shot CLI does, adding only the
`bind_cancel` hook that lets parking **or** a remote cancel stop the scan, and applies the
backend's `scan_id` only at the existing ingest override. `LiveProgressReporter` converts scan
events to compact snapshots and hands them from the worker thread to this asyncio loop. A remote
cancel uploads any partial payload then reports `cancelled`; park/revoke stays silent (no upload,
no status).

The update path is a separate, negotiated companion channel. The daemon advertises
`agent_update_v1` only when backend support and local readiness are both true, forwards accepted
update frames over the restricted Unix socket, and supplies durable update context during hello.
Updater probe/socket failures degrade update capability without taking down scan-channel service.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `CommandStatus` | Wire statuses the daemon may report: `running`, `uploading`, `done`, `failed`, `cancelled`. | `daemon.py:31` |
| `CommandRecord` | Ledger entry: `status`, optional `error_code`, and `pending` — whether that status still needs delivery after a disconnect. | `daemon.py:35` |
| `_ScanStop` | Per-command, thread-safe stop latch with separate cancel and park flags. | `daemon.py:41` |
| `AgentDaemon(client, ingest, *, run_scan=run_headless_scan)` | The coordinator. `run_scan` is the injectable headless runner, which is why no literal `run_headless_scan(` call appears in this module. | `daemon.py:106` |
| `.run()` | Wires command, reconnect replay, park, and cancel callbacks into the client loop; closes the socket and ingest client in `finally`. | `daemon.py:126` |
| `.close()` / `._cancel_active()` | Stops and awaits active work on shutdown, then closes both clients. Park/revoke remains silent. | `daemon.py:137`, `:142` |
| `.handle_command(command)` / `.handle_cancel(command_id)` | Enforces park, duplicate, and busy guards; routes remote cancel to the active scan stop latch. | `daemon.py:151`, `:183` |
| `.replay_pending()` | After each hello, resends pending status and the newest progress snapshot only for active commands. | `daemon.py:192` |
| `._run_command(command)` | Runs the headless scan with `LiveProgressReporter`, flushes reconciled payload counts before `uploading`, then performs HTTP ingest. | `daemon.py:207` |
| `._record_progress()` / `._send_progress()` | Sequence and retain one compact snapshot per active command; send only on the asyncio loop, and discard progress after a terminal status. | `daemon.py:311`, `:349` |
| `_scan_outcome(result, *, cancelled)` | Pure map from a finished scan to `(status, error_code)`: `cancelled` whenever stopped; otherwise `failed/scan_failed` (no payload), `failed/result_unavailable`, `failed/scan_failed` (fatal), or `done`. | `daemon.py` |
| `._send` / `._update` | Deliver status; clear per-command progress state on terminal status and release the scan lock when terminal delivery succeeds. | `daemon.py:284`, `:295` |
| `run_daemon()` | Configures INFO logging to stdout, loads `load_ingest_config()` once, constructs both clients, and runs the loop. An `IngestConfigError` prints and exits `20` before anything is constructed. | `daemon.py:366` |
| `_request_updater()` / `_inspect_update_runtime()` | Send the closed local request vocabulary to the updater socket and expose checked readiness/context to hello; inspection failures disable update capability without stopping scans. | `daemon.py:59`, `:379` |

## The state machine

```text
valid idle command → running
  ├─ stop.parked                                  → silent return (no ingest, no status)
  ├─ no payload, stop.cancelled                   → cancelled
  ├─ no payload                                   → failed   (no ingest call)
  ├─ fatal / missing path, not cancelled          → failed   (no ingest call)
  └─ completed | partial | cancelled payload      → uploading
       ├─ stop.parked after upload                → silent return
       ├─ ingest accepted, stop.cancelled         → cancelled
       ├─ ingest accepted, otherwise              → done
       └─ any other outcome                       → failed
```

| Frames emitted | When |
|---|---|
| `running, uploading, done` | `completed` or non-cancel `partial`, ingest `accepted` |
| `running, uploading, cancelled` | remote cancel with a partial payload, ingest `accepted` |
| `running, cancelled` | remote cancel with no payload |
| `running, failed/scan_failed` | `fatal`, missing payload without a cancel, or an unexpected scan exception |
| `running, failed/result_unavailable` | payload exists, result was never persisted — no upload attempted (a cancel uploads instead) |
| `running, uploading, failed/ingest_failed` | any non-`accepted` ingest outcome |
| `failed/device_busy` | a *different* command arrives while one is running or uploading |
| *(none)* | park/revoke/shutdown stop — silent |

The five error codes (`device_busy`, `invalid_command`, `scan_failed`, `result_unavailable`,
`ingest_failed`) are the whole vocabulary; transport-specific ingest categories are deliberately not
exposed on the wire. `cancelled` carries `error_code: null`.

Accepted uploads log command id, scan id, and HTTP status. Failed uploads log those identifiers plus
the typed ingest outcome, status, and attempt count (`daemon.py:229-236`). The upstream response
message is deliberately excluded because it may echo credentials; private keys and bearer tokens
must never enter the daemon log.

The gate order in `_scan_outcome` is payload → result path → fatal, not fatal first — except when
the scan was cancelled: a stopped scan skips the missing-path and fatal refusals, so a partial payload
still uploads when its local copy failed to write (ingest needs only the payload; spec 049
decision 2). That is load-bearing: `run_headless_scan` only ever returns a `None` result
path together with a `fatal` outcome on non-cancel failures, so checking `fatal` first would make
`result_unavailable` unreachable.

### Threading

The receive loop never runs nmap or HTTP. Both blocking calls — `run_headless_scan` and
`ScanIngestClient.submit` — go through `asyncio.to_thread`, which is what keeps the socket
answering duplicates, busy rejections, and cancel frames while a scan subprocess is mid-flight.

The daemon passes `LiveProgressReporter` through `run_headless_scan(reporter=...)`. The scanner
worker hands compact snapshots to the asyncio loop with `call_soon_threadsafe`; only that loop
sends `AgentProgress` over the existing WebSocket. In-stage reports are coalesced to at most one
per two seconds, while stage boundaries and the final reconciled snapshot are sent promptly. The
final snapshot is sent before `uploading`; it corrects interim counts from the normalized payload
and stays below 100%. The daemon keeps only the latest snapshot and replays it after reconnect while
the command remains active.

### The early-`running` frame

The backend commits its stub scan **before** sending the command frame, so a prompt `running`
status finds `scan_id` already set and applies normally. The daemon emits `running` once anyway and
never sleeps, retries, or waits for an ack — later `uploading`/`done`/`failed`/`cancelled` advance
monotonically and are authoritative. Integration acceptance therefore checks the terminal state, not
every intermediate row in command history.

## How it connects

* **Upstream** — bare `dmitri agent` via [`_run_agent`](/hardware-agent/cli.md), after the same
  `_check_nmap()` preflight the one-shot path uses.
* **Downstream** — [`CommandChannelClient`](/hardware-agent/command-channel.md) for lifecycle
  (including `on_cancel` / `AgentCancel`), [`run_headless_scan`](/hardware-agent/cli.md) for the
  scan, and [`ScanIngestClient.submit(payload, scan_id=…)`](/hardware-agent/transport.md) for the
  upload after a remote cancel or a normal finish.
* The backend side is the command channel and ingest route
  ([backend/routers](/backend/routers.md), [backend/services](/backend/services.md)).

## Notes / gotchas

* **The ledger is process-lifetime, not a queue.** Nothing is persisted. A crash ends active work
  and the backend's disconnect grace + stale sweep own the eventual `failed`. Commands are never
  queued locally while disconnected.
* A socket drop does **not** cancel a running scan. Status changes are recorded pending and replayed
  on reconnect. Parking (and shutdown) stops a scan via `_cancel_active` → `request_park()`. A
  remote cancel uses `handle_cancel` → `request_cancel()`, uploads the partial, then reports
  `cancelled`. Only the park path is silent — also after a cancel's upload, because an accepted
  ingest already moved the command to its terminal status on the backend.
* Ingest `forbidden` records `failed/ingest_failed`, makes one best-effort status send, then calls
  `park("upload_refused")`. The shared command-channel policy drops the socket, waits one hour, and
  redials; no new scan starts while parked.
* There is no daemon-side ingest retry. The ingest client's existing three-attempt policy is
  authoritative and its outcome is final.
* The `invalid_command` branch is the live write-depth guard. `validate_nspi_depth` refuses
  `active_validation` (and a submode on a non-NSPi mode) before any probe. Headless maps that to
  `InvalidScanInput`.
* Exit code `20` is overloaded on the bare-agent path: missing nmap and an invalid ingest
  configuration both exit `20`, distinguishable only by their stderr text.
* Scan preemption, command/daemon generation leases, and late-work fencing are **out of scope** —
  DMI-101 owns them. Every park reason now retries hourly. Parking stops the running scan (nmap is
  terminated) and waits for the worker before it clears `_active`, so no second command can start
  beside it after the hourly redial. An ingest request already in progress may finish, but its
  return is ignored.

# Citations

[1] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[2] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
[3] [spec 026 — Pi agent daemon](../../../specs/026-pi-agent-daemon/ARCHITECTURE.md)
[4] [spec 026 — cross-process contract](../../../specs/026-pi-agent-daemon/INTEGRATION.md)
[5] [spec 048 — parked channel recovery](../../../specs/048-parked-channel-recovery/TRUTH.md)
[6] [spec 049 — remote scan cancel](../../../specs/049-remote-scan-cancel/plan.md)
