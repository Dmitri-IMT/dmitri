# TRUTH — Agent WebSocket command channel

## Narrative

The Pi daemon on the target network dials an outbound WSS connection to the backend at `/api/v1/agents/{agent_id}/commands`. The backend upgrades the connection by verifying an Ed25519 device signature, registers the agent as online in an in-process connection registry, and then speaks typed JSON envelopes over the persistent channel: commands flow down from the backend, statuses flow up from the Pi.

This mounts the `require_agent` dependency built in DMI-61 (agent Ed25519 auth middleware) onto a WebSocket upgrade path. The signature algorithm is asymmetric Ed25519 per ADR-005 §1 amended 2026-07-24; the upgrade envelope — canonical string, mandatory headers, empty-body hash, 5-minute clock skew, nonce anti-replay — is unchanged from ingest auth.

## Business rules

- Every device dials outbound WSS to `/api/v1/agents/{agent_id}/commands`; the backend never initiates connectivity.
- Upgrade succeeds only when Ed25519 signature verifies against the stored public key for `agent_id`.
- `agent_id` in the URL path must match `X-Device-Id` header exactly (UUID, byte-equal).
- A registered socket marks the agent online with a `last_seen_at` timestamp; disconnect marks offline.
- Every frame on the channel is typed JSON with a required `type` field. Unknown or missing type → graceful error reply, connection stays alive.
- The Pi sends a `hello` frame on every connect with its version and available subnets; the backend caches these per agent.

## User stories

1. As a backend operator, I want the Pi to maintain a persistent bidirectional channel, so that commands can be pushed to it immediately after an operator triggers "Scan now".
2. As a Pi device, I want my upgrade request authenticated by my Ed25519 key pair, so that only authorized devices can join the command channel.
3. As a system, I want an in-process registry of agent connectivity states (online/offline/last_seen_at), so that command delivery decisions reflect real-time socket status without polling.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Valid Ed25519 upgrade → online | A Pi client with a valid Ed25519 keypair, correct signature on the upgrade request | It connects to WSS `/api/v1/agents/{agent_id}/commands` | The upgrade succeeds, the connection registry marks the agent as `online` with `last_seen_at` set to now |
| Disconnect → offline | An agent registered as online in the connection registry | Its WebSocket connection closes (clean or unclean) | The registry marks the agent as `offline` and updates `last_seen_at` to the disconnect timestamp |
| Invalid signature → refused | A Pi client with a malformed, expired, or forged Ed2h519 signature on the upgrade request | It connects to WSS `/api/v1/agents/{agent_id}/commands` | The upgrade is rejected (HTTP 401 for invalid/expired/replay; HTTP 403 for unknown/revoked device); no socket is registered |
| Hello frame caching | An agent connects and sends a `hello` frame with `agent_version` and `available_subnets` | The backend receives it | The backend caches the reported subnets against the agent record; subsequent reads surface them |
| Malformed status frame | A connected client sends invalid JSON or a `status` frame with an unknown `status` value | The backend processes the frame | The backend returns an error reply without closing the connection or harming other connections in the pool |
| Path/header mismatch | Agent dials with `{agent_id}` in path that does not match `X-Device-Id` header | Upgrade is attempted | The upgrade is rejected with 401 before verification proceeds |

## Out of scope (v1)

- No delivery/enqueue logic for commands when Pi is offline (next issue in the epic).
- No multi-replica connection registry or sticky sessions (post-September).
- No Pi-side client implementation (separate issue).
- No Pi daemon provisioning or installer work.

## Related specs

- Architecture & implementation: `ARCHITECTURE.md`
- Execution ledger: `POOP.md` (written during orchestration)
