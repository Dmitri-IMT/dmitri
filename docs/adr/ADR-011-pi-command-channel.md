# ADR-011: Pi command channel (WebSocket v1)

> **Amendment 2026-07-24 (algorithm):** this ADR reuses ADR-005's agent-auth rules on the WS
> upgrade. [`ADR-005`](ADR-005-security-model.md) §1 was amended from **HMAC-SHA256** to **Ed25519
> asymmetric signatures** (backend stores only the device's public key; ADR-015 retired). Wherever
> this ADR says "HMAC," read **Ed25519 signature** — the upgrade envelope (canonical string,
> headers, empty-body hash, skew, nonce, `401`/`403` rules) is **unchanged**; only the signature
> algorithm and the stored credential change. Decision record:
> [`docs/research/device-auth-hmac-vs-asymmetric.md`](../research/device-auth-hmac-vs-asymmetric.md).

> **Amendment 2026-08-13 (delivery retries withdrawn):** wherever this ADR says delivery fails
> "after retries," read **on a single attempt**. Delivery is one send against the live socket; no
> socket, or a send that throws, sets `expired` and returns `503 device_offline` immediately. The
> retries were specified but never built, and they cannot work as specified: `deliver()` holds one
> socket object, and `send_text` throws only when that connection is already closed, so further
> calls on it are guaranteed to fail. A retry that could succeed would have to wait for the Pi to
> **reconnect** — seconds — inside the operator's request, which is the queue-for-later this ADR
> puts out of scope below. Retries also do nothing for the failure that actually occurs: a
> half-open socket where the send *succeeds* into a black hole, which the presence projection and
> the stale sweep catch (`failed` / `agent_disconnected`). **Retrying is the operator triggering
> the scan again.**

> **Amendment 2026-09-14 (durable-first delivery):** the backend records delivery **before** it
> sends the frame. `deliver()` inserts the stub `scans` row, sets `delivered` and `scan_id`, and
> commits; then it makes the single send attempt. A send that throws is logged and the request still
> returns `201` with the `delivered` command. The Pi never saw the job; once the agent is marked
> disconnected, the stale sweep moves the command to `failed` / `agent_disconnected` — the same
> path as the half-open socket above. `503 device_offline` + `expired` now means only: no socket,
> a revoked agent, or the command left `queued` before the delivery commit.

> **Amendment 2026-09-15 (DMI-171):** a send that throws after the delivery commit now fails the
> command **in the same request**: `failed` / `agent_disconnected`, `completed_at` set, the stub
> scan mirrored to `failed`, one `scan_failed` activity. The request still returns `201`, now with
> the `failed` command. Waiting for the stale sweep left a Pi whose socket stayed open answering
> `409 device_busy` until it disconnected or hit its duration budget.
>
> **Amendment 2026-09-16 (DMI-155, park policy):** no refusal is terminal for the Pi. On an upgrade
> `403`, a close `>= 4000` (including `4000 replaced` and `4001 revoked`), or a refused scan upload,
> the agent **parks** and retries **once per hour**. Parking no longer ends `run()`: the daemon keeps
> its process alive, logs `command channel parked (<reason>); next attempt at <UTC ISO>`, and starts
> no scan while parked. This replaces the earlier "stay down" client action, which left a refused
> appliance in a 10-second systemd restart loop that only an on-site SSH session could end.
> Revocation becomes reversible through the API: `POST /api/v1/agents/{agent_id}/revoke` and
> `POST /api/v1/agents/{agent_id}/restore` (admin only) write and clear `agents.revoked_at`, and a
> restored device is let in on its next hourly attempt.

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
for a CIDR. The backend holds `available_subnets` **only in the API process's connection registry**
for the life of the socket (they are *reported*, not stored as truth — the Pi is the authority on its
own interfaces). There is no column and no cache table; every read derives them afresh.

**Out of this ADR:** how an admin *chooses* `target_subnet`, and how `AgentDetail` exposes it. That is
the HTTP half of C2 and belongs to the frontend-contract-asks epic.

> **Implemented 2026-08-12 (DMI-78 / spec 031),** consistent with this ADR: `AgentDetail` carries
> `available_subnets` and `target_subnet`, and admin-only `PATCH /api/v1/agents/{agent_id}` records
> the choice. Only the choice persists (`agents.target_subnet`); the reported networks and `online`
> still do not. The chosen value is re-checked against the live report at trigger time, so a scan
> naming a network the Pi is no longer reporting is refused rather than run.

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

**Enqueue:** `POST /api/v1/agents/{agent_id}/commands` creates a `commands` row only
(`status=queued`, `scan_id` null). No stub scan yet.

**Delivery:**

- Pi **online** (open WS): set `delivered`, persist `scan_id`, create the **stub** `scans` row,
  and commit; then send the command frame once. A send that throws is logged, the command is set
  `failed` / `agent_disconnected` at once, and the trigger returns `201` with that command (see the
  2026-09-15 amendment).
- Pi **offline** (no socket, or revoked), or the command left `queued` before the delivery
  commit: set `expired` (still no `scan_id`, and `error_code=device_offline`), return **`503`** +
  `code: device_offline`. No retry — see the 2026-08-13 amendment.

**Why the stub waits for delivery.** `expired →` scan status `"failed"`, and `GET /scans`
lists by org without hiding host-less stubs. Creating a scan on every offline click would
pollute the operator's primary screen with failed empty scans. The command row is the audit
trail; a scan row means *a Pi accepted work*. An `expired` command therefore carries
**no `scan_id`**. The null is a *consequence* of `expired`, never a *marker* of it —
`command.status` is the signal. Enforced in DDL:

```sql
CHECK (scan_id IS NOT NULL OR status IN ('queued', 'expired'))
```

**Why two statuses.** A `scans` row exists **iff** a Pi accepted the command, so the null is
legal exactly in the pre-delivery window. `queued` (written by `enqueue()` before the frame is
sent) and `expired` (delivery gave up) are the only two pre-delivery statuses; every other
status implies a Pi took the job and therefore a persisted `scan_id`. Nothing infers failure
from the null — `command.status` stays the only signal.

**Concurrency:** one active scan per Pi (any non-terminal status). New trigger → **`409`** +
`code: device_busy`.

**Terminal states — the split is `delivered_at`** (C12, decided 2026-07-13):

| Case | State | When it is set |
|------|-------|----------------|
| Delivery gave up — the Pi **never took the job** | `expired` | Synchronously with `503 device_offline`, or by the worker/enqueue stale sweep for a stuck `queued` command |
| Pi error, ingest failure, WS drop mid-scan, a failed frame send after the delivery commit, or stale post-delivery — the Pi **took the job and broke** | `failed` | On report, at a failed frame send, or by the stale sweeper |

A headless `fatal` is a Pi-reported `failed`, including a result-write failure after the scan
pipeline completed. The daemon may retain the returned payload in memory, but must not report
`uploading` or `done` when no result JSON was persisted.

**Late results are discarded.** Once a command is terminal, `POST /api/v1/scans` rejects a result
for its scan with **`400`** (`ScanClosedError` in `services/persistence.py`) and the result is
dropped. This is deliberate, not a race to be repaired: terminal status is what releases the
one-active-scan-per-Pi lock above, so a replacement scan may already be running against the same
agent, and reviving the old scan row would corrupt it. The agent keeps its local artifact, but
nothing will accept it — recovery is a **new scan**, not a resubmission. Ingest clients must treat
this `400` as final and must not retry or requeue it.

**Timeouts / stale sweep:** connection-loss grace is **config/env**
(`COMMAND_DISCONNECT_GRACE_SECONDS`). The enrichment worker sweeps globally on its poll; enqueue
sweeps the target agent before the busy check. Stale `queued` → `expired`; stale
`delivered`/`running`/`uploading` → `failed` (and mirrored scan status). Staleness is
**written**, not derived at read time.

### 5. Stub scan (`GET /api/v1/scans/{scan_id}`)

After **successful delivery**, the stub scan exists before ingest. Return **`200`** with stub body:

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
           └── scans (stub on successful delivery)
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

- Queue-for-later when Pi offline (reject on the first failed attempt).
- Device secret rotation UX (Phase 2).
- HTTP poll command delivery (fallback only).
- Multi-replica WS without sticky sessions.

## References

- [`ADR-005`](ADR-005-security-model.md) — Ed25519 device signature + JWT
- [`BACKEND.md` B6](../roadmap/BACKEND.md) — roadmap decision log
- [`AUTH.md`](../roadmap/AUTH.md) — browser sessions and invites
- [`PI.md`](../roadmap/PI.md) — daemon and installer provisioning
- [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml)
