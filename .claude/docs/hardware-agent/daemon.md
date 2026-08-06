---
type: Entry Point
title: daemon — the unattended command executor
description: The long-lived device process that accepts backend commands, runs one headless scan at a time, uploads through ingest, and reports lifecycle status.
resource: hardware-agent/src/agent/daemon.py
tags: [hardware-agent, daemon, command-channel, ingest, lifecycle, asyncio]
timestamp: 2026-08-06T00:00:00Z
---

# daemon — the unattended command executor

## Purpose

`agent.daemon` (DMI-66, spec 026) is the coordinator that finally joins the two halves that already
existed: the [command channel](/hardware-agent/command-channel.md) that carries work in, and the
[headless scan](/hardware-agent/cli.md) + [ingest client](/hardware-agent/transport.md) that do the
work and send results back. Bare `dmitri agent` starts it.

It adds **no** scan pipeline. It calls `run_headless_scan` exactly as the one-shot CLI does, with no
new runner parameter, and applies the backend's `scan_id` only at the existing ingest override.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `CommandRecord` | Ledger entry: `status`, optional `error_code`, and `pending` — whether that status still needs delivery after a disconnect. | `daemon.py:32` |
| `AgentDaemon(client, ingest, *, run_scan=run_headless_scan)` | The coordinator. `run_scan` is the injectable headless runner, which is why no literal `run_headless_scan(` call appears in this module. | `daemon.py:38` |
| `.run()` | Wires `handle_command` / `replay_pending` into the client loop; closes the socket and the owned ingest client in `finally`. | `daemon.py:53` |
| `.close()` | Cancels any in-flight scan task first, then closes the socket and the owned ingest client — so nothing is still uploading through a client that is being torn down. | `daemon.py:59` |
| `.handle_command(command)` | The `on_command` callback: park guard, duplicate replay, busy rejection, then start the one owned task. | `daemon.py:72` |
| `.replay_pending()` | The `on_connected` seam — resends pending status after hello, before any new command is acted on. | `daemon.py:86` |
| `._execute(command)` | Owns the scan task; converts any exception to `failed` and clears `_active` in `finally`. | `daemon.py:91` |
| `._run_command(command)` | The state machine below. | `daemon.py:100` |
| `run_daemon()` | Loads `load_ingest_config()` once, constructs both clients, runs the loop. An `IngestConfigError` prints and exits `20` before anything is constructed. | `daemon.py:146` |

## The state machine

```text
valid idle command → running
  ├─ fatal outcome, no payload, or no persisted result path → failed   (no ingest call)
  └─ completed | partial, with both payload and path        → uploading
       ├─ ingest accepted     → done
       └─ any other outcome   → failed
```

| Frames emitted | When |
|---|---|
| `running, uploading, done` | `completed` or `partial`, ingest `accepted` |
| `running, failed/scan_failed` | `fatal`, missing payload, or an unexpected scan exception |
| `running, failed/result_unavailable` | payload exists, result was never persisted — no upload attempted |
| `running, uploading, failed/ingest_failed` | any non-`accepted` ingest outcome |
| `failed/device_busy` | a *different* command arrives while one is running or uploading |

The five error codes (`device_busy`, `invalid_command`, `scan_failed`, `result_unavailable`,
`ingest_failed`) are the whole vocabulary; transport-specific ingest categories are deliberately not
exposed on the wire.

The gate order in `_run_command` is payload → result path → fatal, not fatal first. That is
load-bearing: `run_headless_scan` only ever returns a `None` result path together with a `fatal`
outcome, so checking `fatal` first would make `result_unavailable` unreachable.

### Threading

The receive loop never runs nmap or HTTP. Both blocking calls — `run_headless_scan` and
`ScanIngestClient.submit` — go through `asyncio.to_thread`, which is what keeps the socket
answering duplicates and busy rejections while a scan subprocess is mid-flight.

### The early-`running` race

The backend commits its stub scan *after* sending the command frame, so a prompt `running` can
overtake the commit and be dropped by the backend's `scan_id IS NOT NULL` guard. The daemon emits
`running` once anyway and never sleeps, retries, or waits for an ack — later `uploading`/`done`/
`failed` advance monotonically and are authoritative. Integration acceptance therefore checks the
terminal state, not every intermediate row in command history.

## How it connects

* **Upstream** — bare `dmitri agent` via [`_run_agent`](/hardware-agent/cli.md), after the same
  `_check_nmap()` preflight the one-shot path uses.
* **Downstream** — [`CommandChannelClient`](/hardware-agent/command-channel.md) for lifecycle,
  [`run_headless_scan`](/hardware-agent/cli.md) for the scan, and
  [`ScanIngestClient.submit(payload, scan_id=…)`](/hardware-agent/transport.md) for the upload.
* The backend side is the command channel and ingest route
  ([backend/routers](/backend/routers.md), [backend/services](/backend/services.md)).

## Notes / gotchas

* **The ledger is process-lifetime, not a queue.** Nothing is persisted. A crash ends active work
  and the backend's disconnect grace + stale sweep own the eventual `failed`. Commands are never
  queued locally while disconnected.
* A socket drop does **not** cancel a running scan. Status changes are recorded pending and replayed
  on reconnect. DMI-66 adds no cancellation parameter to `ScanRunner` or `run_headless_scan`.
* Ingest `forbidden` is the HTTP permanent-revocation signal: the daemon records
  `failed/ingest_failed`, makes **one** best-effort status send, closes the socket, and parks. It
  redials nothing and accepts nothing further.
* There is no daemon-side ingest retry. The ingest client's existing three-attempt policy is
  authoritative and its outcome is final.
* The `invalid_command` branch is currently unreachable — `AgentCommand.scan_mode` is a `Literal`
  over `config.SCAN_MODES` and the CIDR is validated at the frame boundary, so `InvalidScanInput`
  cannot escape `validate_inputs`. It is kept because spec 026 pins all five codes and the two mode
  lists could drift.
* Exit code `20` is overloaded on the bare-agent path: missing nmap and an invalid ingest
  configuration both exit `20`, distinguishable only by their stderr text.
* Scan preemption, command/daemon generation leases, and late-work fencing are **out of scope** —
  DMI-101 owns them. A daemon evicted by `4000/replaced` stays parked until externally terminated.
  `close()` cancels the scan task at its `await` boundary, but `asyncio.to_thread` cannot stop the
  worker thread, so a scan may still be mid-nmap or mid-upload as the process exits. Whatever it
  produces after that point is discarded by design.

# Citations

[1] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[2] [ADR-012 — headless exit-code contract](../../../docs/adr/ADR-012-headless-exit-code-contract.md)
[3] [spec 026 — Pi agent daemon](../../../specs/026-pi-agent-daemon/ARCHITECTURE.md)
[4] [spec 026 — cross-process contract](../../../specs/026-pi-agent-daemon/INTEGRATION.md)
