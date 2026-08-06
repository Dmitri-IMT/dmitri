---
type: Module
title: transport — the signed scan-ingest client
description: The device-side ingest client: environment-loaded config, the Ed25519 request envelope, bounded retries, and the typed submission outcome.
resource: hardware-agent/src/agent/transport/ingest.py
tags: [hardware-agent, transport, ingest, ed25519, signatures, http, retry]
timestamp: 2026-08-06T00:00:00Z
---

# transport — the signed scan-ingest client

## Purpose

`agent.transport` (DMI-65, spec 025) is the device end of the ingest boundary: it takes a finished
[`ScanPayload`](/hardware-agent/normalize.md) in memory and `POST`s it to the backend's
`/api/v1/scans` under an Ed25519 proof that the backend's
[device gate](/backend/device-auth.md) can verify. It is the counterpart to that gate — same
canonical string, same five headers, opposite side of the wire.

It is **wired as of DMI-66**: [`AgentDaemon`](/hardware-agent/daemon.md) calls
`submit(payload, scan_id=command.scan_id)` in a worker thread once a remote command's scan has
produced both a payload and a durable result path. No TUI screen or scan stage invokes it — the
daemon is its only caller.

The client does no file I/O at all. It accepts an in-memory payload, never a path, so its caller
must persist the artifact first — success, failure and retry all leave the local result
byte-for-byte untouched. A backend-assigned `scan_id` is applied via `model_copy` to a throwaway
copy only, so neither the caller's model nor the artifact is mutated.

## Key classes / functions

| Name | What it does |
|------|--------------|
| `load_ingest_config(environ=None)` | Reads `BACKEND_URL` / `DEVICE_ID` / `DEVICE_PRIVATE_KEY` from a mapping or the process env (`ingest.py:121`). Parses only — no I/O, no file reads. |
| `IngestConfig` | Frozen slotted dataclass; **all three fields are `repr=False`** so no origin, id, or key can leak through a traceback (`ingest.py:38`). |
| `IngestConfigError` | Raised for a missing/malformed variable, before any request. Subclasses `ValueError`. Messages name the variable and expected shape, never the supplied value (`ingest.py:34`). |
| `ScanIngestClient(config, *, client=None)` | Owns an `httpx.Client` unless one is injected; `close()` closes only an owned one. Context-manager capable. The injected-client seam is what the tests drive with `httpx.MockTransport` (`ingest.py:130`). |
| `ScanIngestClient.submit(payload, *, scan_id=None)` | Serializes once, then runs the bounded retry loop and maps the response (`ingest.py:147`). |
| `ScanIngestClient._build_headers(body)` | Adds `Content-Type` to the five headers returned by the shared [`build_device_signature_headers`](/hardware-agent/command-channel.md) — DMI-66 extracted the envelope construction out of this module so the ingest `POST` and the WS `GET` upgrade sign through one function (`ingest.py:182`). |
| `SubmissionOutcome` | `Literal`: `accepted`, `unauthorized`, `forbidden`, `invalid`, `rejected`, `unavailable`, `protocol_error` (`ingest.py:23`). |
| `SubmissionResult` | Frozen slotted result carrying `outcome`, `scan_id`, `attempts`, `status_code`, `message` (`ingest.py:45`). Expected HTTP and network failures *return* one — nothing raises, exits, or prints. |

### The envelope

Body bytes come from `model_dump_json().encode("utf-8")` and are sent with `content=body`, never
`json=`, so the transmitted bytes and the digest cannot diverge. The signed string is
`"\n".join(("POST", "/api/v1/scans", device_id, timestamp, nonce, body_sha256))` — **no trailing
newline** — signed with Ed25519 and sent as lowercase hex in `X-Signature`, alongside
`X-Device-Id`, `X-Timestamp`, `X-Nonce` and `X-Body-SHA256`.

Only the *path* is signed, not scheme or authority — which is why `follow_redirects=False` is
passed explicitly per request: a redirect would move the request off the path it signed.

### Retry and mapping

Retries are fixed, not configurable: `_RETRY_DELAYS = (0.0, 0.25, 1.0)` gives three total attempts
with a 0.25 s and 1 s wait *before* attempts two and three, and no sleep after the final failure.
Only `httpx.TransportError` and `5xx` retry; every `4xx` returns immediately.

The envelope is rebuilt on **every** attempt while the body bytes stay identical. That is
load-bearing: the backend durably burns a verified nonce *before* it persists, so reusing headers
after any verified attempt turns a legitimate retry into a replay `401`.

| Response | Outcome |
|---|---|
| `202` matching `status`/`scan_id`/`hosts_received` | `accepted` |
| `401` | `unauthorized` (includes a stale proof from an unsynchronised device clock) |
| `403` | `forbidden` |
| `413`, `422` | `invalid` |
| `400` or any other `4xx` | `rejected` — a `400` closed scan is a deliberate discard, final; recovery is a new scan, not a resubmit |
| transport failure or `5xx`, three attempts spent | `unavailable` |
| redirect, unexpected `2xx`, malformed or contradictory `202` | `protocol_error` |

`message` is a fixed per-outcome string plus the numeric status code — nothing is interpolated from
the response body, the config, or the exception, which is what makes "secret-safe" checkable.

The read timeout is a deliberate 120 s (connect 10 s, write 60 s, pool 10 s). Backend ingest costs a
database round trip per host, per port and per finding, and a read timeout is a `TransportError` and
therefore retried — sizing it generously keeps attempt two off the wire while attempt one is still
inside its transaction.

## How it connects

* Consumes [`ScanPayload`](/hardware-agent/normalize.md) — the same model
  [workspace](/hardware-agent/scanner/workspace.md) writes to `results/`.
* Talks to the backend's `POST /api/v1/scans` ([routers](/backend/routers.md),
  [api](/backend/api.md)), verified by [device auth](/backend/device-auth.md).
* Upstream caller: [`AgentDaemon`](/hardware-agent/daemon.md), after
  [`run_headless_scan`](/hardware-agent/cli.md) returns both a payload and a durable result path.
* Shares its Ed25519 envelope construction with the
  [command channel](/hardware-agent/command-channel.md).

## Notes / gotchas

* `httpx` and `cryptography` became direct hardware-agent dependencies here
  (`hardware-agent/pyproject.toml`). `cryptography` is unavoidable — the stdlib has no Ed25519.
* `ScanIngestClient.__init__` no longer constructs the Ed25519 key object (DMI-66), so a
  hand-built `IngestConfig` with a malformed key now raises on the first `submit()` rather than at
  construction. `load_ingest_config` already rejects anything that is not 64 hex characters, so no
  production path can reach that late raise.
* There is **no** client-side payload revalidation and must not be one. The agent's `ScanPayload`
  and the backend's `ScanIngestRequest` are compatible by construction; a `422` means the two model
  sets have genuinely drifted, which is a deploy-skew signal worth surfacing rather than masking.
* CPEs are the known gap: the backend's `PortPayload.cpes` is optional with an empty default, and
  DMI-65 deliberately did not touch normalization to fill it. That needs its own scope decision.
* An accepted first submission and an idempotent re-acceptance are indistinguishable to the client —
  both get the same `202` with the same fields. `accepted` means "the service holds this scan", not
  "it stored it just now".
* `X-Device-Id` identifies the *agent*, not a host — one of the two deliberate survivors of the
  `device`→`host` rename.

# Citations

[1] [ADR-005 — security model](../../../docs/adr/ADR-005-security-model.md)
[2] [ADR-011 — Pi command channel](../../../docs/adr/ADR-011-pi-command-channel.md)
[3] [spec 025 — Pi ingest client and Ed25519 signing](../../../specs/025-pi-ingest-client-ed25519-signing/ARCHITECTURE.md)
