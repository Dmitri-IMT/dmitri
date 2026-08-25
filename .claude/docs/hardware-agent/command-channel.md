---
type: Module
title: command-channel — the signed WebSocket client and shared signer
description: "The signed device WebSocket: strict hello/command/status frames, visible connection loss/recovery, and the pinned reconnect ladder."
resource: hardware-agent/src/agent/transport/command_channel.py
tags: [hardware-agent, transport, websocket, ed25519, signatures, reconnect, daemon]
timestamp: 2026-08-25T00:00:00Z
---

# command-channel — the signed WebSocket client

## Purpose

`agent.transport.command_channel` (DMI-66, spec 026) is the device end of the backend's
`GET /api/v1/agents/{device_id}/commands` WebSocket. It owns everything about the socket — URL
conversion, the signed upgrade, frame validation, send serialization and reconnect timing — and
nothing about scans. Command execution belongs to the [daemon](/hardware-agent/daemon.md); the
client only hands it validated `AgentCommand`s and carries `AgentStatus` frames back.

`agent.transport.signing` is the small shared helper it and the [ingest
client](/hardware-agent/transport.md) both sign through. DMI-66 extracted it out of `ingest.py`
so one function builds every Ed25519 envelope — the `POST /api/v1/scans` one and the `GET`
upgrade one — from the same canonical string.

**Scan result payloads never travel this socket.** Lifecycle frames go here; results go through
ingest. That split is the contract, not an implementation detail.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `build_device_signature_headers(method, path, body, device_id, private_key_bytes)` | Builds the five proof headers from a fresh timestamp, nonce, body SHA-256 and signature. Stores nothing; the key never reaches an attribute, a log or an exception message. | `transport/signing.py:10` |
| `AvailableSubnet` | `interface`, `cidr`, required `is_default_route`. Mirrors the contract component. | `command_channel.py:41` |
| `AgentHello` | `type="hello"`, `agent_version`, `available_subnets`. | `command_channel.py:49` |
| `AgentCommand` | `type="command"`, `command_id`, `scan_id`, `scan_mode` (`Literal` over `config.SCAN_MODES`), `subnet`. | `command_channel.py:57` |
| `AgentStatus` | `type="status"`, `command_id`, `status`, nullable `error_code`. | `command_channel.py:67` |
| `CommandChannelClient(config, *, connect, sleep, detect_subnets, agent_version)` | The client. All four seams are injectable, which is what lets the tests run the full reconnect ladder with no socket and no wall clock. | `command_channel.py:111` |
| `.run(on_command, on_connected=None)` | The connect → hello → replay → receive loop. Returns **only** when parked. | `command_channel.py:144` |
| `.send_status(status)` | Returns `False` rather than raising when disconnected — the daemon records that as pending. | `command_channel.py:170` |
| `_websocket_origin(backend_url)` | `http://`→`ws://`, `https://`→`wss://`. No scheme check: `load_ingest_config` has already rejected anything that is not http/https. | `command_channel.py:83` |
| `_permanent_reason(exc)` | The park/retry decision — see below. | `command_channel.py:92` |
| `_parse_command(raw)` | Strict parse; returns `None` for anything that is not a valid `command` frame. | `command_channel.py:237` |

### The upgrade envelope

The signed canonical string is
`"\n".join(("GET", "/api/v1/agents/{device_id}/commands", device_id, timestamp, nonce, body_sha256))`
with the body hash being SHA-256 of **zero bytes**. The `{device_id}` in the path and the
`X-Device-Id` header are byte-for-byte the same canonical UUID text — the backend checks that they
match. Every dial rebuilds the whole envelope; no header value survives an attempt, which is what
lets a Pi whose clock was wrong at boot recover on a later retry without operator action.

### Hello-first ordering

`_serve_once` (`command_channel.py:184`) does connect → send hello → mark ready → log the
connection → `on_connected()`
→ first `recv()`, in that order, on **every** connection including reconnects. The subnet list is
re-enumerated per hello via [`detect_available_subnets`](/hardware-agent/utils.md), never cached, so
the backend registry always replaces its list with current device state. `on_connected` is the
daemon's pending-status replay seam — which is why replay is guaranteed to land after hello and
before any newly delivered command.

### Reconnect and park

Backoff is the fixed ladder `1, 2, 5, 10, 30` seconds, capped at 30, and resets **only** after an
upgrade *and* a successful hello send — a socket that dies during the handshake keeps climbing.

| Result | Action |
|---|---|
| Network failure, normal close, backend restart, upgrade `401` | Retry with a completely fresh proof |
| Upgrade `403` | Park |
| Close `4000` reason `replaced` | Park — another daemon owns the device slot |
| Any other close code `>= 4000` | Park |
| Any other upgrade status (`404`, `500`, …) | Retry — treated as transient backend-side |
| Unusable `BACKEND_URL` | Raise before dialing |

The `>= 4000` floor (`_PERMANENT_CLOSE_FLOOR`, `command_channel.py:25`) is a deliberate
placeholder: the WebSocket private range is reserved for backend-defined terminal conditions, and
the only 4xxx close the backend emits today is `4000/replaced`. **DMI-97 owns the concrete
live-revocation close code** — when it lands, replace the floor with that specific code so a future
retryable 4xxx close is not silently parked.

## How it connects

* Signs through [`build_device_signature_headers`](./command-channel.md), shared with the
  [ingest client](/hardware-agent/transport.md).
* Enumerates via [`detect_available_subnets`](/hardware-agent/utils.md).
* Driven by [`AgentDaemon`](/hardware-agent/daemon.md), which supplies `on_command` and
  `on_connected`.
* Talks to the backend WS route and its frame schemas ([backend/schemas](/backend/schemas.md),
  [backend/services](/backend/services.md)); the normative shapes live in
  [contracts](/contracts.md).

## Notes / gotchas

* `AgentCommand.subnet` layers an `ipaddress.IPv4Network` check on top of the contract's
  `SubnetCIDR` regex, because the regex alone accepts `999.0.0.0/99`. The inbound edge is
  deliberately stricter than the contract.
* An `asyncio.Lock` serializes every send. Without it the receive loop and the scan task could
  interleave frames on the wire — the lock is load-bearing, not defensive.
* Diagnostics carry only an exception class name and an integer status or close code. No key, no
  signature, no signed URL, no response body, no raw exception text ever reaches a log.
* Each successful hello emits `command channel connected` (`command_channel.py:189-193`), while a
  retryable loss emits the existing sanitized `command channel lost` warning. Together they make
  reconnects visible without exposing the signed upgrade headers.
* The module reads `ConnectionClosed.code` / `.reason`, which `websockets` 17 deprecates in favour
  of `.rcvd.code` / `.rcvd.reason`. The deprecated accessors are the *correct* ones here — they fold
  the `rcvd is None` case into `1006`, which the reconnect classifier depends on. Any future
  migration must preserve that fallback.
* `websockets` became a direct hardware-agent dependency here (`hardware-agent/pyproject.toml`).

# Citations

[1] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[2] [ADR-005 — security model](../../../docs/adr/ADR-005-security-model.md)
[3] [spec 026 — Pi agent daemon](../../../specs/026-pi-agent-daemon/ARCHITECTURE.md)
[4] [spec 026 — cross-process contract](../../../specs/026-pi-agent-daemon/INTEGRATION.md)
