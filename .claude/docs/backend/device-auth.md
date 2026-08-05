---
type: Module
title: Backend device auth — Ed25519 signatures, nonces, the agent gate
description: The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, the transport-agnostic authenticate_agent core, and its require_agent / require_agent_ws adapters.
resource: backend/src/api/dependencies/agent_auth.py
tags: [backend, auth, device, ed25519, signatures, nonces, replay, agents, websocket]
timestamp: 2026-08-05T00:00:00Z
---

# Backend device auth — Ed25519 signatures, nonces, the agent gate

## Purpose

The device gate (spec 017 / DMI-61) is how a Pi proves *which agent it is* on every request, as
distinct from the JWT gate in [auth](/backend/auth.md) that authenticates *people*. It is
**asymmetric**: the device holds an Ed25519 private key born on the device and never transmitted;
the backend stores only that agent's 32-byte `public_key` in the clear on the `agents` row. A
database leak therefore exposes nothing forgeable, which is why ADR-015 (secret-at-rest encryption)
was retired rather than implemented.

Three modules make it up — a pure signature layer, a nonce store, and the gate that sequences them.
**DMI-62 mounts the WebSocket adapter** on `WebSocket /api/v1/agents/{agent_id}/commands`, and
**DMI-63 mounts the HTTP `require_agent` adapter** on `POST /api/v1/scans`. The device-side
counterpart that produces these proofs is [transport](/hardware-agent/transport.md) (DMI-65) —
built, but not yet driven by a Pi daemon (DMI-66).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `canonical_string()` | Joins the six signed fields with `\n` in ADR-005 §1 order — `METHOD`, `PATH`, `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256`. Byte-exactness is the contract. | `backend/src/api/services/device_sig.py:41` |
| `body_sha256()` | Hex sha256 of the raw request body; the empty body hashes to the well-known `e3b0c442…b855`. | `backend/src/api/services/device_sig.py:52` |
| `parse_timestamp()` | `datetime.fromisoformat` **plus** a `tzinfo is None` rejection — a naive timestamp raises `MalformedSigHeaders` rather than blowing up later on aware/naive subtraction. | `backend/src/api/services/device_sig.py:56` |
| `DeviceSigHeaders` / `parse_headers()` | Frozen dataclass of the five signature headers; `parse_headers` raises `MalformedSigHeaders` for a missing header, non-hex signature or body hash, non-UUID device id, out-of-range nonce, or a **64-hex signature** (the old HMAC width — accepting it would silently downgrade the scheme). | `backend/src/api/services/device_sig.py:33`, `:66` |
| `verify()` | Ed25519 verification that never lets `cryptography`'s `InvalidSignature` — or any other exception — escape; every failure becomes `SignatureError`, and messages name the failure mode, never key material. | `backend/src/api/services/device_sig.py:109` |
| `generate_keypair()` / `sign()` | 32-byte private/public keypair and a signing helper, for tests and the provisioning CLI. No production request path signs. | `backend/src/api/services/device_sig.py:126`, `:133` |
| `remember_nonce()` | Inserts `(agent_id, nonce, expires_at)` and lets the `uq_agent_nonces_agent_id_nonce` constraint be the replay detector — never SELECT-then-INSERT, which would race. On `IntegrityError` it rolls back **before** raising `NonceReplayError`, leaving the caller's session usable. | `backend/src/api/services/nonces.py:16` |
| `prune_expired_nonces()` | One indexed `DELETE … WHERE expires_at < :now`, strict `<`, so a row expiring exactly at `now` survives. | `backend/src/api/services/nonces.py:27` |
| `authenticate_agent()` | The transport-agnostic core holding the 8-step order exactly once: parse headers → `expected_agent_id` check → agent lookup → revoked check → skew → body hash → signature → nonce. Imports nothing from FastAPI. | `backend/src/api/dependencies/agent_auth.py:37` |
| `require_agent()` | The thin HTTP adapter — awaits the body, passes `request.url.path` (resolved, never a route template), and maps `AgentRevoked`→403 / `AgentUnauthenticated`→401. Holds no skew, signature, or nonce logic of its own. | `backend/src/api/dependencies/agent_auth.py:109` |
| `require_agent_ws()` | The thin WebSocket adapter — passes `websocket.url.path`, `body=b""`, `expected_agent_id=agent_id`, same error mapping via pre-accept `HTTPException`. Never calls `accept()`. | `backend/src/api/dependencies/agent_auth.py:128` |
| `AgentIdentity` | The gate's result: `agent_id` + `org_id`, both read from the `agents` row. | `backend/src/api/dependencies/agent_auth.py:20` |

## How it connects

- **Data** — `agents.public_key` and the `agent_nonces` table come from
  [migrations `20260724_11` and `20260724_09`](/backend/migrations.md), mapped in
  [`models/command.py`](/backend/models.md).
- **Config** — `DEVICE_SIG_MAX_SKEW_SECONDS` (default 300) is a `Settings` field; see
  [config](/backend/api.md). There is deliberately **no** nonce-retention knob — the nonce's own
  `expires_at` bounds retention.
- **Provisioning** — an agent's public key reaches the database through
  [`backend-provision-agent`](/backend/management.md), never over HTTP.
- **Downstream** — `require_agent_ws` is mounted on the [agents router](/backend/routers.md)
  (`connect_agent_commands`); `require_agent` (HTTP) is still unmounted.

## Notes / gotchas

- **Statuses are not interchangeable.** A *known but revoked* agent gets **403**; everything else —
  missing or malformed header, unknown device, skew, body-hash mismatch, bad signature, replay —
  gets **401**. Conflating them would tell an attacker which device ids exist.
- **`org_id` always comes from the `agents` row**, never from anything the request asserts, so a
  device cannot claim another tenant.
- **The nonce is recorded only after the signature verifies.** Recording earlier would let an
  unauthenticated caller burn nonces at will.
- **A burned nonce is not rolled back.** `remember_nonce` commits, so the gate durably consumes the
  nonce before any route handler's later work runs; a failure after the gate costs the caller a full
  signature-envelope rebuild. This is the deliberate safe-by-default trade — an availability cost,
  never a security hole — and DMI-62/63 must be built knowing it.
- **Comparisons are constant-time where it matters** — `hmac.compare_digest` for the body hash,
  `device_sig.verify` for the signature; no `==` on either.
- **`device_sig.py` is the only module in the repo that imports `cryptography`**, pinned by a
  structural test.
- **`require_agent_ws` maps validation failures to 403** — `main.py` registers a
  `WebSocketRequestValidationError` handler that denies malformed `{agent_id}` paths with HTTP 403
  before the gate runs (see [api](/backend/api.md)).

# Citations

[1] [specs/017-auth-middleware-invite-flow](../../../specs/017-auth-middleware-invite-flow/TRUTH.md)
[2] [docs/adr/ADR-005-security-model.md](../../../docs/adr/ADR-005-security-model.md)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[4] [docs/roadmap/AUTH.md](../../../docs/roadmap/AUTH.md)
[5] [specs/018-agent-ws-command-channel](../../../specs/018-agent-ws-command-channel/TRUTH.md)
