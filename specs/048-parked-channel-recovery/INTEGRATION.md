# INTEGRATION — Parked Pi recovery, admin revoke and restore

Two real boundaries: **backend ↔ frontend** (HTTP, published in `contracts/openapi/openapi.yaml`)
and **Pi ↔ backend** (WebSocket close codes, upgrade and upload refusals). Design rationale is in
`ARCHITECTURE.md`. Screens are in `DESIGN.md`.

## 1. Backend ↔ frontend contract

### 1.1 Changed schemas

`AgentSummary` and `AgentDetail` both gain one **required, nullable** property:

```yaml
revoked_at:
  type:
    - string
    - 'null'
  format: date-time
```

Added to each schema's `required` list (as `last_seen_at` is). All other fields are unchanged.
The frontend rule: `revoked_at !== null` ⇒ show **Revoked** with that timestamp, and ignore `online`
for the presence word. Otherwise show `online ? Online : Offline`.

```json
{
  "agent_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "display_name": "DMITRI-NSPI-01",
  "online": false,
  "last_seen_at": "2026-09-15T13:58:40Z",
  "revoked_at": "2026-09-15T14:03:12Z",
  "target_subnet": "192.168.0.0/24",
  "active_command_id": null
}
```

### 1.2 New operations

| Operation | Method + path | Auth | Body | Success |
|---|---|---|---|---|
| `revokeAgent` | `POST /api/v1/agents/{agent_id}/revoke` | `FrontendBearerAuth`, role `admin` | none | `200` `AgentDetail` |
| `restoreAgent` | `POST /api/v1/agents/{agent_id}/restore` | `FrontendBearerAuth`, role `admin` | none | `200` `AgentDetail` |

Semantics:

- **Revoke:** if `revoked_at` is null, set it to the server clock and commit. Then close the
  agent's live socket with `4001 revoked`, if there is one. If `revoked_at` is already set, it is
  kept (the date is not bumped). Returns the device.
- **Restore:** if `revoked_at` is set, clear it. `display_name`, `target_subnet`, and the public
  key are kept. Returns the device. The Pi reconnects on its next hourly attempt. The response
  does not show it online.
- Both are idempotent. A repeat call returns `200` with the current state.
- The response's `online` can still be `true` for a moment right after a revoke (the socket
  handler unregisters asynchronously). The frontend never shows `online` while `revoked_at` is set.

### 1.3 Error mapping

All errors use the existing envelope `{"error": {"code", "message", "details"}}`.

| Case | Status | `code` | Frontend behaviour (DESIGN.md) |
|---|---|---|---|
| No / invalid bearer token | `401` | `unauthorized` | Existing session handling |
| Caller is a viewer | `403` | `forbidden` (`Admin role required`) | Action is not shown. A direct call shows the action's error line |
| Unknown id, or device of another org | `404` | `not_found` (`Agent not found`), the same body for both | Error line; a later re-read shows not found |
| Server failure | `500` | `internal_server_error` (existing `InternalServerError` response) | Error line (`Couldn't revoke/restore this device. Try again.`) |

No `409`/`422`: revoke and restore have no preconditions. No new `code` value.

### 1.4 Unchanged, but affected

- `PATCH /api/v1/agents/{agent_id}` on a revoked device returns `409 device_offline`, because a
  revoked device is never registered and has no hello. The UI hides `Change` for a revoked device.
- `POST /api/v1/agents/{agent_id}/commands` on a revoked device: `503 device_offline` (spec 041).
  The UI hides the scan trigger.

## 2. Sequences

### 2.1 Admin revokes a connected Pi

1. Frontend → `POST /agents/{id}/revoke`.
2. Backend commits `revoked_at = now` and calls `close_revoked(socket)` → WS close `4001 revoked`.
3. Backend → `200 AgentDetail` (`revoked_at` set). Frontend invalidates `queryKeys.agents.all`.
4. Independently, the backend socket handler's `finally` unregisters and sets `connected_at = NULL`.
   The route does not wait for this, so `online` in the response can still be `true` (§1.2).
5. Pi `recv()` raises `ConnectionClosed(4001)` → park `revoked`. The daemon cancels any in-flight
   scan task and logs `command channel parked (revoked); next attempt at T+1h`.

### 2.2 Hourly attempt while still revoked

1. At T+1h, the Pi clears the park and dials with a fresh Ed25519 proof.
2. Backend `authenticate_agent` → `AgentRevoked` → upgrade `403`. The nonce is still recorded.
3. Pi → park `refused` → logs the next attempt at T+2h. The reason reads `refused`, because the
   Pi cannot tell a revoked device from a malformed id at `403`.

### 2.3 Admin restores

1. Frontend → `POST /agents/{id}/restore` → `200` with `revoked_at: null`, `online: false`.
2. At the Pi's next hourly attempt: upgrade accepted → `hello` → `register` → online. The ladder
   resets. Pending ledger statuses replay. Backend status frames for commands the sweep has already
   retired get the existing `error` frame and are ignored.

### 2.4 Upload refused

1. Pi `POST /api/v1/scans` → `403` (revoked device, or `ScanOwnershipError`).
2. Daemon sends status `failed` / `ingest_failed` (best effort), then `client.park("upload_refused")`.
3. The client drops the socket → the loop parks → the log line → 1 h wait → dial.

### 2.5 Replaced (twin daemons, see ARCHITECTURE R1)

1. Twin B connects. Backend `register` closes twin A's socket with `4000 replaced`.
2. A parks `replaced`, waits 1 h, dials. Backend closes B with `4000`. B parks. The pattern repeats hourly.

## 3. Pi ↔ backend refusal table (normative)

This replaces the "Client action" column of the close-code table in `connectAgentCommandsWebSocket`.

| Pi observes | Backend meaning | Pi `ParkReason` | Pi action |
|---|---|---|---|
| WS close `1000`, `1006`, `1012`, any `< 4000` | normal close / restart / network | — | Short backoff `1,2,5,10,30` s |
| Network error (`OSError`), other upgrade status (`404`, `5xx`) | transient | — | Short backoff |
| Upgrade `401` | bad signature envelope (skew, nonce, unknown device) | — | Short backoff, fresh proof |
| Upgrade `403` | revoked device, or malformed `{agent_id}` | `refused` | Park; retry once per hour |
| WS close `4000` `replaced` | a newer connection took the slot | `replaced` | Park; retry once per hour |
| WS close `4001` `revoked` | device revoked while connected | `revoked` | Park; retry once per hour |
| WS close other `>= 4000` | backend-defined refusal | `refused` | Park; retry once per hour |
| `POST /api/v1/scans` `403` | revoked, or the scan belongs to another device/org | `upload_refused` | Park; retry once per hour |

While parked, the Pi holds no socket, runs no scan, uploads nothing, and the process stays up. The
backend needs no knowledge of the Pi's park state. It only stores `revoked_at`.

Contract text for `openapi.yaml`:

| Code | Meaning | Client action |
|------|---------|---------------|
| `1012` | Backend restarting (deploy). | Redial promptly with backoff. |
| `1000` | Normal closure. | Redial with backoff. |
| `4000` `replaced` | Another connection for this `agent_id` took the slot; at most one live socket per agent. | **Park; retry once per hour.** |
| `4001` `revoked` | The device is revoked. | **Park; retry once per hour.** An admin restore lets the next attempt in. |

> A `403` on the upgrade means the device is revoked **or** `{agent_id}` is not a well-formed UUID.
> The Pi parks and retries once per hour. An admin restore (`POST /api/v1/agents/{agent_id}/restore`)
> lets the next attempt in. A `401` is retryable only after fixing the signature envelope (clock skew,
> fresh nonce).
