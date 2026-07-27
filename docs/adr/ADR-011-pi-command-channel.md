# ADR-011: Pi command channel (WebSocket v1)

> **Amendment 2026-07-24 (algorithm):** this ADR reuses ADR-005's agent-auth rules on the WS
> upgrade. [`ADR-005`](ADR-005-security-model.md) §1 was amended from **HMAC-SHA256** to **Ed25519
> asymmetric signatures** (backend stores only the device's public key; ADR-015 retired). Wherever
> this ADR says "HMAC," read **Ed25519 signature** — the upgrade envelope (canonical string,
> headers, empty-body hash, skew, nonce, `401`/`403` rules) is **unchanged**; only the signature
> algorithm and the stored credential change. Decision record:
> [`docs/research/device-auth-hmac-vs-asymmetric.md`](../research/device-auth-hmac-vs-asymmetric.md).

## Context

September MVP scope is **Control** ([`BACKEND.md` B10](../roadmap/BACKEND.md)): operators trigger scans from the web UI; the Pi executes and pushes results via the existing ingest path.

[`ADR-005`](ADR-005-security-model.md) assumed a **one-way push** agent (Pi → API only). Control requires a **backend → Pi command channel**. This ADR records that amendment and locks the v1 contract decided in [`BACKEND.md` B6](../roadmap/BACKEND.md).

Constraints:

- Pi sits behind NAT — **outbound-only** connectivity ([`PI.md`](../roadmap/PI.md)).
- No external broker ([`ADR-009`](ADR-009-database-stack.md)).
- Agent auth: **Ed25519 signature** per device ([`ADR-005`](ADR-005-security-model.md) as amended 2026-07-24, [`AUTH.md`](../roadmap/AUTH.md) Phase 1).
- Browser auth: **JWT Bearer** on business APIs; refresh on `/auth/*` only.

## Decision

### 1. Transport — outbound WebSocket (v1)

The Pi daemon maintains a persistent **WSS** connection:

`wss://{api}/api/v1/agents/{agent_id}/commands`

- Backend **pushes** scan commands when an operator triggers **Scan now**.
- Postgres stores `commands` rows for lifecycle and audit.
- **NSPi ops:** single Railway API replica (in-memory WS registry). Scale-out later needs sticky sessions or shared registry — out of September scope.

HTTP long-poll fallback remains documented in [`PI.md`](../roadmap/PI.md) only if WebSocket blocks cutover; not v1.

### 2. Ed25519 signature on WebSocket upgrade

Use the **same signature rules as ADR-005** (Ed25519 as amended 2026-07-24) on the HTTP upgrade request (not a separate ticket protocol).

Required headers on upgrade: `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256` (empty body hash), `X-Signature`.

Canonical string (v1):

```text
GET
/api/v1/agents/{agent_id}/commands
X-Device-Id
X-Timestamp
X-Nonce
X-Body-SHA256
```

`{agent_id}` in the path must match `X-Device-Id`. Reject upgrade on invalid, expired, or replayed signatures (`401` / `403` per ADR-005), **and on a path/header mismatch**.

**`agent_id` is a UUID** (decided 2026-07-13). The two values must be byte-equal, so they cannot be
typed differently; UUID matches every other identifier in the system (`scan_id`, `command_id`,
`host_id`). Humans read `display_name`, never the id.

`POST /api/v1/scans` ingest continues to use the ADR-005 POST canonical string unchanged.

### 3. WebSocket message envelope (typed JSON)

Every frame is JSON with a required `type` field.

> **Normative home (decided 2026-07-13):** the frames are **`AgentCommandFrame` and
> `AgentStatusFrame` in [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml)**
> (`components/schemas`), referenced from the WS upgrade operation. The examples below are
> illustrative; the schemas are the contract. OpenAPI cannot *validate* WebSocket frames — accepted:
> both ends are hand-written against the spec, and **one contract artifact** beats a second file that
> tooling would have to be taught about. Frames are **not** added to `contracts/schemas/*.json`, which
> is legacy.

**Backend → Pi — `command`:**

```json
{
  "type": "command",
  "command_id": "uuid",
  "scan_id": "uuid",
  "scan_mode": "nspi",
  "subnet": "10.0.0.0/24"
}
```

**Pi → Backend — `status`:**

```json
{
  "type": "status",
  "command_id": "uuid",
  "status": "running",
  "error_code": null
}
```

**Pi → Backend — `hello`** (decided 2026-07-13, closes the WS half of C2):

```json
{
  "type": "hello",
  "agent_version": "0.2.0",
  "available_subnets": [
    { "interface": "eth0", "cidr": "10.0.0.0/24" },
    { "interface": "wlan0", "cidr": "192.168.1.0/24" }
  ]
}
```

Sent by the Pi **on every connect**, before any `status` frame. The Pi is deliberately **dual-homed**
(ethernet on the target subnet, wifi for internet) so it sees more than one network and **cannot guess
which to scan** — a human picks once, and `POST /commands` therefore never asks a non-technical admin
for a CIDR. The backend caches `available_subnets` against the agent (they are *reported*, not stored
as truth — the Pi is the authority on its own interfaces).

**Out of this ADR:** how an admin *chooses* `target_subnet`, and how `AgentDetail` exposes it. That is
the HTTP half of C2 and belongs to the frontend-contract-asks epic.

Allowed Pi `status` values on the wire: `running`, `uploading`, `done`, `failed`.

- Backend sets `delivered` when the `command` frame is sent; Pi’s first `running` moves DB to `running`.
- Large scan payloads are **not** sent on WS — only on `POST /api/v1/scans`.
- Headless `fatal` maps to `failed`, including when scanning succeeded but the result could not be
  persisted. In that write-failure case the daemon may still hold the payload returned in memory,
  but there is no result JSON to upload.

**Idempotency:** duplicate `command` delivery with the same `command_id` → Pi acks without re-running the scan.

### 4. Command lifecycle (HTTP + DB)

`queued` → `delivered` → `running` → `uploading` → `done` | `failed` | `expired`

| State | Owner |
|-------|--------|
| `queued`, `delivered`, `expired` | Backend |
| `running`, `uploading`, `done`, `failed` (reported) | Pi via WS (+ ingest for `done`) |

**Enqueue:** `POST /api/v1/agents/{agent_id}/commands` creates `commands` row + **stub** `scans` row (`scan_id` assigned at enqueue).

**Delivery:**

- Pi **online** (open WS): deliver immediately.
- Pi **offline:** up to **2** delivery retries, then **`503`** + `code: device_offline`.

**Concurrency:** one active scan per Pi (`running` or `uploading`). New trigger → **`409`** + `code: device_busy`.

**Terminal states — the split is `delivered_at`** (C12, decided 2026-07-13):

| Case | State | When it is set |
|------|-------|----------------|
| Delivery gave up after the 2 retries — the Pi **never took the job** | `expired` | Synchronously, with the `503 device_offline` |
| Pi error, ingest failure, WS drop mid-scan, or stale `running` — the Pi **took the job and broke** | `failed` | On report, or by the running timeout |

A headless `fatal` is a Pi-reported `failed`, including a result-write failure after the scan
pipeline completed. The daemon may retain the returned payload in memory, but must not report
`uploading` or `done` when no result JSON was persisted.

**Timeouts:** the `running` stale threshold is **config/env** (not fixed in this ADR). WS drop mid-scan uses that same running timeout → `failed`; operator re-triggers. There is **no second timeout for `expired`** — an undelivered command is resolved at enqueue, not swept later.

### 5. Stub scan (`GET /api/v1/scans/{scan_id}`)

After enqueue, scan exists before ingest. Return **`200`** with stub body:

- `status: pending`
- empty `hosts` / `findings` arrays
- optional `command_id` link

> **Superseded in part by [`ADR-013`](ADR-013-ingest-host-vocabulary-unification.md) (2026-07-22):**
> this section originally kept the `POST /api/v1/scans` ingest payload field names as `devices`
> while the read side used `hosts`. That freeze is lifted — ingest now speaks `hosts` /
> `HostPayload` / `hosts_received` too. `X-Device-Id` (§2, the agent identity header) is unaffected.

When ingest completes, same endpoint returns full scan (`status: completed` or `failed`).

### 6. HTTP surface (September)

| Method | Path | Auth |
|--------|------|------|
| WSS | `/api/v1/agents/{agent_id}/commands` | Ed25519-signed upgrade |
| POST | `/api/v1/agents/{agent_id}/commands` | JWT |
| GET | `/api/v1/agents/{agent_id}` | JWT |
| GET | `/api/v1/commands/{command_id}` | JWT |
| GET | `/api/v1/hosts/…` | JWT |
| POST | `/api/v1/scans` | Ed25519 signature |
| GET | `/api/v1/scans/{scan_id}` | JWT |
| POST | `/api/v1/auth/*`, invites | JWT or public accept |

Host inventory path is **`/hosts`** (breaking rename from `/devices`). OpenAPI: [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).

### 7. Data model (summary)

```
org
 └── agents
      └── commands
           └── scans (stub at enqueue)
                └── hosts (discovered machines)
```

`online` on an agent is derived from the API WS registry, not a DB column.

DDL detail: **Alembic migrations** (source of truth for columns). This ADR does not duplicate every column.

## Consequences

- **ADR-005** is amended: agent channel is **bidirectional** (commands down, results up).
- API is **stateful** (WS connection registry); NSPi runs **one API replica**.
- Frontend polls `GET /commands/{id}` and `GET /scans/{id}` after **Scan now**.
- Pi daemon required for September Control ([`PI.md`](../roadmap/PI.md)); TUI remains dev-only.
- Contract-first: OpenAPI updated to September slice (B6 + [`AUTH.md`](../roadmap/AUTH.md) Phase 1).

## Out of scope (v1)

- Queue-for-later when Pi offline (reject after retries).
- Device secret rotation UX (Phase 2).
- HTTP poll command delivery (fallback only).
- Multi-replica WS without sticky sessions.

## References

- [`ADR-005`](ADR-005-security-model.md) — Ed25519 device signature + JWT
- [`BACKEND.md` B6](../roadmap/BACKEND.md) — roadmap decision log
- [`AUTH.md`](../roadmap/AUTH.md) — browser sessions and invites
- [`PI.md`](../roadmap/PI.md) — daemon and installer provisioning
- [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml)
