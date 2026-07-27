# TRUTH — Agent WebSocket command channel

## Narrative

The Pi daemon on the target network dials an outbound WSS connection to the backend at `/api/v1/agents/{agent_id}/commands`. The backend upgrades the connection by verifying an Ed25519 device signature, registers the agent as online in an in-process connection registry, and then speaks typed JSON envelopes over the persistent channel: commands flow down from the backend, statuses flow up from the Pi.

This is the first product route to use the device authentication built in DMI-61 (agent Ed25519 auth middleware), reusing that verification unchanged on a WebSocket upgrade rather than a plain request. The signature algorithm is asymmetric Ed25519 per ADR-005 §1 amended 2026-07-24; the upgrade envelope — canonical string, mandatory headers, empty-body hash, 5-minute clock skew, nonce anti-replay — is unchanged from ingest auth.

## Business rules

- Every device dials outbound WSS to `/api/v1/agents/{agent_id}/commands`; the backend never initiates connectivity.
- Upgrade succeeds only when Ed25519 signature verifies against the stored public key for `agent_id`.
- `agent_id` in the URL path must match `X-Device-Id` header exactly (UUID, byte-equal).
- A registered socket marks the agent online with a `last_seen_at` timestamp; disconnect marks offline. At most one live socket per agent — a reconnect replaces the previous socket without the old connection's cleanup marking the agent offline while the new socket is still open. The displaced connection is told it was replaced, so a device can tell "the backend went away, redial" apart from "another connection of mine already owns the slot, stay down".
- "Last seen" means the last moment the device actually spoke to the backend — set on connect and on every valid frame it sends, never by a backend-side event such as noticing a disconnect. A device that died at 14:00 reads "last seen 14:00" even though the backend only noticed at 14:00:40.
- An agent that disappears without closing cleanly (power loss, dead network path) is marked offline once the transport's own keepalive gives up — within roughly a minute, not instantly. Online is a recent-liveness claim, not a guarantee that the next send succeeds.
- Every frame on the channel is text JSON with a required `type` field. Unknown or missing type, or unparseable JSON → graceful error reply, connection stays alive. A non-text (binary) frame is outside the contract: the connection ends and the agent must reconnect.
- The Pi sends a `hello` frame on every connect with its version and available subnets; the backend caches these per agent.
- An agent is online from the moment its socket is accepted, before it has said anything. Its reported version and subnets are simply absent until a `hello` arrives — an online agent with nothing reported is a normal state, not an error. The backend does not require `hello` before accepting other frames: a device reconnecting mid-scan may have a status to report immediately.

## User stories

1. As a backend operator, I want the Pi to maintain a persistent bidirectional channel, so that commands can be pushed to it immediately after an operator triggers "Scan now".
2. As a Pi device, I want my upgrade request authenticated by my Ed25519 key pair, so that only authorized devices can join the command channel.
3. As a system, I want an in-process registry of agent connectivity states (online/offline/last_seen_at), so that command delivery decisions reflect real-time socket status without polling.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Valid Ed25519 upgrade → online | A Pi client with a valid Ed25519 keypair, correct signature on the upgrade request | It connects to WSS `/api/v1/agents/{agent_id}/commands` | The upgrade succeeds, the connection registry marks the agent as `online` with `last_seen_at` set to now |
| Disconnect → offline | An agent registered as online in the connection registry | Its WebSocket connection closes (clean or unclean) | The registry marks the agent as `offline`; the recorded last-seen time is left at the last frame the agent actually sent — a disconnect is a backend observation, not evidence of the device |
| Invalid signature → refused | A Pi client with a malformed, expired, or forged Ed25519 signature on the upgrade request | It connects to WSS `/api/v1/agents/{agent_id}/commands` | The upgrade is rejected (HTTP 401 for invalid/expired/replayed/unknown device; HTTP 403 only for a revoked device); no socket is registered |
| Hello frame caching | A connected agent | It sends a valid `hello` frame with `agent_version` and `available_subnets` | The in-process registry caches `agent_version` and `available_subnets` for that agent; `agents.last_seen_at` is updated. No HTTP read route in this issue — `GET /agents/{id}` is later |
| Malformed status frame | A connected client sends invalid JSON or a `status` frame with an unknown `status` value | The backend processes the frame | The backend returns an error reply without closing the connection or harming other connections in the pool |
| Malformed agent id in path | A device dials with an `{agent_id}` that is not a well-formed UUID | Upgrade is attempted | The upgrade is rejected with 403 before any signature check runs — accepted collision with the revoked-device status, since only a corrupted device config can produce it. Nothing is registered |
| Path/header mismatch | Agent dials with `{agent_id}` in path that does not match `X-Device-Id` header | Upgrade is attempted | The upgrade is rejected with 401 before verification proceeds |
| Reconnect replaces old socket | An agent is online on socket A | It reconnects on socket B before socket A's cleanup finishes | The registry shows the agent online on socket B; socket A's cleanup does not evict socket B |

## Out of scope (v1)

- No delivery/enqueue logic for commands when Pi is offline (next issue in the epic).
- No `command_id` existence checks on `status` frames — syntactically valid status is accepted silently; unknown IDs rejected in DMI-64.
- No multi-replica connection registry or sticky sessions (post-September).
- No application-level heartbeat frame and no background sweeper that evicts idle agents — liveness rides on the transport's keepalive.
- No Pi-side client implementation (separate issue).
- No Pi daemon provisioning or installer work.
- No `GET /agents` read API (hello/subnet data surfaced to operators later).

## Related specs

- Architecture & implementation: `ARCHITECTURE.md`
- Reconnect-race design rationale: `docs/research/ws-connection-registry-reconnect-race.md`
- Execution ledger: `POOP.md` (written during orchestration)
