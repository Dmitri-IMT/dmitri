# ARCHITECTURE — A parked Pi recovers on its own, and admins can revoke and restore devices

Implements `TRUTH.md` (DMI-155). Crosses three layers: hardware-agent (Pi daemon), backend
(FastAPI), frontend (React). The backend↔frontend HTTP contract and the Pi↔backend
close-code/refusal behaviour are in `INTEGRATION.md`. Screens, copy and `data-testid` values are
in `DESIGN.md`; this document owns contracts, module shapes and the file table.

> The spec template is written for the `hardware-agent/` scan pipeline. This feature does not touch
> discovery → port scan → NSE → normalization. It lives in the **Pi command channel** (ADR-011), the
> agents read/admin surface, and the device screens. The mandatory sections are unchanged.

## System context

```
                         ┌──────────────── backend ────────────────┐
Admin (web)  ── POST /api/v1/agents/{id}/revoke ──► agents.revoke_agent()      sets revoked_at
             ── POST /api/v1/agents/{id}/restore ─► agents.restore_agent()     clears revoked_at
             ── GET  /api/v1/agents[/{id}] ───────► AgentSummary/AgentDetail   + revoked_at
                                    │
                                    └─ revoke: agent_connections.close_revoked(socket)  → 4001
                         └─────────────────────────────────────────┘
Pi daemon    ── WSS upgrade ──► authenticate_agent: revoked → 403 (unchanged)
             ◄── close 4000 replaced / 4001 revoked (unchanged)
             ── POST /api/v1/scans ──► 403 on revoked or ScanOwnershipError (unchanged)

Pi (hardware-agent/src/agent/)
  daemon.AgentDaemon.run()
    └─ transport.command_channel.CommandChannelClient.run(on_command, on_connected, on_parked)
         connect → hello → receive loop
         transport error, not a park reason ─► short backoff 1,2,5,10,30 s   (unchanged)
         park reason ─► on_parked() → log reason + next attempt → sleep 3600 s → dial again
```

What exists today (verified in code, 2026-09-15):

- `command_channel.py:130` `_permanent_reason()` parks on upgrade `403`, close `4000 "replaced"`,
  and any close `>= 4000`. `run()` loops `while self._parked_reason is None` and **returns** when
  parked. `close()` parks too (`command_channel.py:218`).
- `daemon.py:146-147` parks on an upload `forbidden` outcome via `client.close(_FORBIDDEN_PARK)`.
- `daemon.py:53-57` `AgentDaemon.run()` awaits `client.run`, then `close()`. `run_daemon()`
  (`daemon.py:166`) returns after `asyncio.run`, `cli.py:70` returns, and the process exits 0.
  `dmitri-agent.service` has `Restart=always`, `RestartSec=10s` → the restart loop in TRUTH.
- Backend: `agent_connections.py` has `CLOSE_REPLACED = 4000`, `CLOSE_REVOKED = 4001`,
  `close_revoked(websocket)`. `agent_auth.authenticate_agent` raises `AgentRevoked` (→ `403`) when
  `agent.revoked_at is not None`. `Agent.revoked_at` exists (`models/command.py:19`). **No code
  writes it.**
- `routers/agents.py`: `GET` list/detail (`require_user`), `PATCH` target subnet and
  `POST .../commands` (`require_admin`). `services/agents.py` builds `AgentSummary`/`AgentDetail`
  from `_fields()`.

### Why the reason is derived on the backend, not reported by the Pi

At an upgrade `403` the WebSocket never opens, so the Pi has no channel to send anything on. After
a `4001`/`4000` close the socket is already gone. An upload `403` ends the HTTP request. In every
park case the Pi has nothing to report on. The backend already stores `revoked_at`, so the web app
shows **Revoked** from that column. All other not-connected states read **Offline** (TRUTH §Why a
device is not connected). The park reason stays in the Pi's log, for the recovery guide.

## Design decisions

### D1. Pi: park is an hourly wait inside `run()`, never a return

`CommandChannelClient.run()` becomes a loop that ends only on `close()` or task cancellation.

```
async def run(on_command, on_connected=None, on_parked=None) -> None:
    attempt = 0
    while not self._closed:
        if self._parked_reason is not None:
            if on_parked is not None:
                await on_parked()
            await self._wait_out_park()          # log, sleep(_PARK_RETRY_SECONDS), clear reason
            attempt = 0
            continue
        self._ready = False
        try:
            await self._serve_once(on_command, on_connected)
        except _TRANSPORT_ERRORS as exc:
            reason = _park_reason(exc)
            if reason is not None:
                self._set_parked(reason)
            else:
                LOGGER.warning("command channel lost: %s", _describe(exc))
        finally:
            await self._drop_socket()
        if self._closed or self._parked_reason is not None:
            continue
        if self._ready:
            attempt = 0
        await self._sleep(_BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)])
        attempt += 1
```

- **One policy for every reason.** `_PARK_RETRY_SECONDS = 3600.0`. No reason is terminal.
- **The hour runs through the injected `sleep`.** Tests pass the existing `Sleeper` fake and assert
  `3600.0` in `delays`. No real waiting.
- **The hourly attempt is an ordinary attempt.** `_wait_out_park()` clears `_parked_reason`
  before the next dial. A refusal parks again for another hour. A network failure on that attempt
  is not a park reason, so it uses the short ladder from `1 s` (`attempt = 0`). A successful hello
  resets the ladder as today, so "normal backoff resumes" holds.
- **Park reasons are a closed set** (`ParkReason = Literal["revoked", "replaced", "refused",
  "upload_refused"]`). `_permanent_reason()` is renamed `_park_reason()` and returns a code:

  | Pi observes | `ParkReason` |
  |---|---|
  | close `4001` | `revoked` |
  | close `4000` with reason `replaced` | `replaced` |
  | upgrade `403`; any other close `>= 4000` | `refused` |
  | `ScanIngestClient.submit` outcome `forbidden` (set by the daemon) | `upload_refused` |
  | upgrade `401`, network errors, close `< 4000`, other upgrade statuses | not a park (unchanged) |

  The `4001` branch is new: today it falls into the generic `>= 4000` branch. The `>= 4000` floor
  stays, now mapped to `refused`, because every reason retries hourly and nothing parks forever.
- **Log contract** (the recovery guide quotes it). Emitted once per park, at `ERROR`, with the
  existing logger `agent.transport.command_channel`:

  ```
  command channel parked (<reason>); next attempt at <UTC ISO-8601, seconds>
  ```

  Example: `command channel parked (revoked); next attempt at 2026-09-15T14:03:12+00:00`.
  `<reason>` is only a `ParkReason` literal. No key, signature, nonce or signed URL can appear
  (`TestSecretSafety` stays green). The time is `datetime.now(UTC) + timedelta(seconds=
  _PARK_RETRY_SECONDS)`, computed just before the sleep. The existing
  `command channel connected` `INFO` line marks the exit from park.
- **Log when the Pi sees the reason, not when the event happens.** Upload refusal can arrive while
  the loop is in a short backoff sleep, with no socket. The loop sees the reason when that sleep
  ends (at most 30 s later), then the hour starts. "Not before one hour" still holds.
- **`close()` stops. It does not park.** A new `_closed` flag ends the loop. `close()` sets it and
  drops the socket. `close()` now takes no `reason` argument (its only reason was the park reuse).
- **New `park(reason)` coroutine** for the daemon: it records the reason (first one wins, as
  `_park` does today) and drops the socket. `recv()` in `_serve_once` then raises, and the loop
  enters the park wait. It is the only public way to park from outside.
- **Shutdown while parked.** The hourly wait is one awaited `self._sleep(...)`. Cancellation
  (SIGINT → `asyncio.run` cancels the main task) raises `CancelledError` out of the sleep, through
  `run()`, into `AgentDaemon.run()`'s `finally: await self.close()`. This path is the same as
  today's backoff sleep. SIGTERM from systemd keeps Python's default action (the process ends). No
  signal handler is added.
- **`parked_reason` property stays**, so `AgentDaemon.handle_command`'s early return still covers
  a frame that was read before the park.

### D2. Pi daemon: parked means no work

- `AgentDaemon.run()` passes `on_parked=self._cancel_active` to `client.run`. On every park the
  in-flight scan task is cancelled before the wait. Its upload therefore never happens.
- `_run_command` replaces `await self._client.close(_FORBIDDEN_PARK)` with
  `await self._client.park("upload_refused")`. `_FORBIDDEN_PARK` is removed (orphan of this change).
- `handle_command` keeps `if self._client.parked_reason is not None: return`.
- **Ledger:** unchanged. Records stay in memory while parked. `replay_pending` resends
  undelivered statuses after the next successful hello, as today. A command left `running` on the
  backend by a cancelled scan is retired by the existing stale sweep
  (`commands.sweep_stale_commands`, agent disconnected past the grace period).
- `run_daemon()` and `cli.py` do not change. The process now exits only on a signal or a crash, so
  systemd restarts it only after a real failure.

### D3. Backend API shape: two action endpoints

`POST /api/v1/agents/{agent_id}/revoke` and `POST /api/v1/agents/{agent_id}/restore`. No body.
`200` with `AgentDetail`. Chosen over `PATCH /api/v1/agents/{agent_id}` with a `revoked` field
because:

- The existing `PATCH` has a fixed `UpdateAgentTargetSubnetRequest` body (`extra="forbid"`) and
  preconditions (`409 device_offline`, `422 subnet_not_reported`). Revoke and restore have none of
  those. Mixing them would make one operation carry two sets of error rules.
- Revoke has a side effect a field write does not show: it closes the live socket.
- Named verbs match TRUTH's domain language and give the frontend one call each.
- `POST` with idempotent semantics is fine here. A repeat call returns `200` and the same state.

Not `DELETE` (the `revokeInvite` shape): the device is not deleted, and restore must undo it.

Responses: `200 AgentDetail`, `401`, `403` (not admin, via `require_admin`), `404` (unknown or
foreign agent, the same body for both), `500`. No new error `code`. No `CORS` `options`
operation: the newest admin paths (`/users/{user_id}`, `/invites/{invite_id}`) rely on the CORS
middleware and publish none.

### D4. Backend services and router

In `backend/src/api/services/agents.py` (next to `set_target_subnet`, reusing `_agent` and
`_detail`):

```python
def revoke_agent(
    session: Session, *, agent_id: UUID, org_id: UUID, now: datetime
) -> AgentDetail | None:
    agent = _agent(session, agent_id, org_id)
    if agent is None:
        return None
    if agent.revoked_at is None:          # idempotent: keep the first revocation date
        agent.revoked_at = now
        session.add(agent)
        session.commit()
    return _detail(session, agent)

def restore_agent(
    session: Session, *, agent_id: UUID, org_id: UUID
) -> AgentDetail | None:
    agent = _agent(session, agent_id, org_id)
    if agent is None:
        return None
    if agent.revoked_at is not None:
        agent.revoked_at = None
        session.add(agent)
        session.commit()
    return _detail(session, agent)
```

`_fields()` adds `"revoked_at": agent.revoked_at`. `online` is **not** changed: it stays the
registry flag. The frontend gives `revoked_at` priority (Revoked replaces Online/Offline, per
`DESIGN.md`). This prevents a race: the revoke response can be built before the closed socket's
handler has unregistered.

Router, `backend/src/api/routers/agents.py`:

- `revoke_agent_route` is `async def` (it must `await` the close), `Depends(require_admin)`.
  It runs `revoke_agent` via `run_in_threadpool` (the sync-DB-on-event-loop rule from spec 041 §3).
  If the result is `None` it raises `HTTPException(404, "Agent not found")`. Then, **after the commit**,
  `socket = agent_connections.get_socket(agent_id)`, and if it is not `None`,
  `await agent_connections.close_revoked(socket)`. Commit first, so that a frame or delivery that
  races the close already sees the revocation through the spec 041 gates. On a repeat revoke the
  close is a no-op (no socket, or `close_revoked` sees a non-`CONNECTED` state).
- `restore_agent_route` is a plain `def` (no socket work), `Depends(require_admin)`, mirroring
  `update_agent_target_subnet_route`. `None` → `404`.
- The foreign-task close is the same kind that `register()` (4000) and `commands.deliver()` (4001)
  already do. `run_agent_channel`'s state-checked loop handles it. That loop is not touched.

**No activity-log row.** Admin mutations on users and invites do append activity (`users.py`,
`invites.py`). But TRUTH puts "Recording who revoked or restored a device" out of scope, and every
activity row carries `actor_user_id` and `actor_email`. So this feature adds no `ActivityKind`.

**No migration.** `agents.revoked_at` exists and is nullable. Restore writes `NULL`.

### D5. Frontend

- `frontend/src/api/agents.ts`: `revokeAgent(agentId): Promise<AgentDetail>` and
  `restoreAgent(agentId): Promise<AgentDetail>` (`apiClient.post`, no body).
- `frontend/src/hooks/useAgentRevocation.ts`: one hook with `revoke()` and `restore()`, the
  pending and error state for each, and on success invalidation of `queryKeys.agents.all` (list and
  detail, per `DESIGN.md` §5). It mirrors `useUpdateTargetSubnet.ts` (`readApiError`, `useToast`).
- `frontend/src/pages/agents/DeviceRevocation.tsx`: the revoke section and confirm dialog
  (`DialogShell`) and the revoked section with `Restore device`. It is gated with `AdminOnly`.
  Copy and test ids come from `DESIGN.md` §4 and §6.
- Display rule, used everywhere a presence word appears: `revoked_at != null` → `Revoked`
  (with `Timestamp`); otherwise `online ? 'Online' : 'Offline'`. It is applied in
  `deviceListColumns.tsx`, `AgentIdentity.tsx`, and the `Devices.tsx` `rowTone`.
- `DeviceDetail.tsx`: when revoked, do not render `ScanControl`, the target-subnet `Change`, or the
  revoke section. Render `DeviceRevocation` in its revoked form. Confirmed for DESIGN open
  question 4: `set_target_subnet` raises `AgentOfflineError` (`409`) when the registry has no hello.
  A revoked device is never registered, so a save could not succeed.
- Types come only from `npm run gen:types` → `frontend/src/types/openapi.d.ts`. Do not edit them by hand.

## Data model / contracts

| Item | Change |
|---|---|
| DB | None. `agents.revoked_at` already exists. No Alembic migration. |
| `AgentSummary`, `AgentDetail` (pydantic + `contracts/openapi/openapi.yaml`) | Add **required, nullable** `revoked_at: datetime \| None` (`type: [string, 'null']`, `format: date-time`, listed in `required`, the same shape as `last_seen_at`). |
| New operations | `revokeAgent` `POST /api/v1/agents/{agent_id}/revoke`; `restoreAgent` `POST /api/v1/agents/{agent_id}/restore`. `200 AgentDetail`, `401`, `403`, `404`, `500`. |
| WS close codes | Values unchanged (`4000`, `4001`). **Client action text changes** from "Stay down" to "Park; retry once per hour". The `403` paragraph changes from "permanent without human intervention" to "the Pi parks and retries once per hour; an admin restore lets the next attempt in". |
| Pi constants (`command_channel.py`) | Add `_PARK_RETRY_SECONDS = 3600.0`, `ParkReason` Literal. Keep `_BACKOFF_SCHEDULE`, `_PERMANENT_CLOSE_FLOOR`. |
| Pi public API (`CommandChannelClient`) | `run(on_command, on_connected=None, on_parked=None)`; new `async park(reason: ParkReason)`; `close()` loses its `reason` parameter and no longer parks; `parked_reason` becomes `ParkReason \| None`. |
| Pi daemon (`daemon.py`) | Remove `_FORBIDDEN_PARK`; pass `on_parked=self._cancel_active`; call `park("upload_refused")`. |
| Exit codes | None changed. `run_daemon` keeps `SystemExit(20)` on config error. |
| ADR-011 | Amendment 2026-09-15 (DMI-155): park policy. Every park reason retries hourly, the daemon never exits on park, admins revoke and restore through the API. |

## New files and naming (mandatory)

### hardware-agent

| Path | Change |
|---|---|
| `hardware-agent/src/agent/transport/command_channel.py` | `_PARK_RETRY_SECONDS`, `ParkReason`; `_permanent_reason` → `_park_reason` (adds `4001 → revoked`); `run()` gets the hourly wait and `on_parked`; new `park()`, `_set_parked()`, `_wait_out_park()`; `close()` stops without parking (`_closed` flag); park log line per D1 |
| `hardware-agent/src/agent/daemon.py` | `run()` passes `on_parked=self._cancel_active`; `_run_command` calls `park("upload_refused")`; remove `_FORBIDDEN_PARK` |
| `hardware-agent/tests/unit/test_command_channel.py` | Update `TestClassification` (park then one `3600.0` sleep then redial; `Dialer`'s `Halt` ends the run) and `test_close_parks_and_stops_the_loop` → close stops without parking; add the cases in Testing expectations |
| `hardware-agent/tests/unit/test_daemon.py` | `FakeClient.run` accepts `on_parked`; add `FakeClient.park`; update `TestForbiddenIngest` to assert `parked_reason == "upload_refused"` and `closed is False`; add park-cancels-active-scan case |
| `hardware-agent/dmitri-agent.service` | **No change** (`Restart=always` now fires only on real crashes) |

**CLAUDE.md integration rule.** `ScanRunner` (`hardware-agent/src/agent/scanner/runner.py`) and
`ScanProgressScreen` (`hardware-agent/src/agent/tui/screens/scan_progress.py`) are **not
involved**. This feature adds no parameter to the orchestrator or the runner. The daemon calls
`run_headless_scan`, and that signature is unchanged. Call sites of the changed Pi symbols (grepped):

| Symbol | Call sites | Status |
|---|---|---|
| `CommandChannelClient(...)` constructor | `daemon.py:177`; `test_command_channel.py:141,242` | Constructor unchanged |
| `CommandChannelClient.run` | `daemon.py:55`; `test_command_channel.py` `drive()` | `daemon.py` passes `on_parked`; `drive()` unchanged (optional arg) |
| `CommandChannelClient.close` | `daemon.py:61` (`AgentDaemon.close`), `daemon.py:147` (park reuse); `test_command_channel.py:459` | `:61` unchanged; `:147` → `park("upload_refused")`; test updated |
| `parked_reason` | `daemon.py:73`; tests | Unchanged |
| `AgentDaemon` / `run_daemon` | `cli.py:68-70`; `test_daemon.py`; `test_cli_agent.py` (patched) | Signatures unchanged |

### backend

| Path | Change |
|---|---|
| `backend/src/api/schemas/agents.py` | `revoked_at: datetime \| None` on `AgentSummary` and `AgentDetail` (required, no default) |
| `backend/src/api/services/agents.py` | `_fields()` adds `revoked_at`; new `revoke_agent(...)`, `restore_agent(...)` per D4 |
| `backend/src/api/routers/agents.py` | New `revoke_agent_route` (`async`, closes the socket after commit) and `restore_agent_route`; import `run_in_threadpool` |
| `contracts/openapi/openapi.yaml` | Paths `/api/v1/agents/{agent_id}/revoke` and `/restore` (`revokeAgent`, `restoreAgent`, `FrontendBearerAuth`); `revoked_at` on both schemas; close-code table and `403` paragraph text in `connectAgentCommandsWebSocket` |
| `backend/tests/test_agent_revocation_routes.py` | **New.** Route tests for revoke/restore (see Testing). A new admin surface that no existing test covers. Mirrors `test_agent_target_subnet_routes.py` |
| `backend/tests/test_agent_read_routes.py` | `test_list_agents_returns_org_rows_with_exact_keys` and detail key assertions include `revoked_at`; add a revoked row that reads `revoked_at` set |
| `backend/tests/test_contract_fidelity.py` | Add `revokeAgent` / `restoreAgent` rows to `test_admin_operations_are_published` (`{"200","401","403","404","500"}`); schema fingerprints for `AgentSummary`/`AgentDetail` already compare the new field |
| `backend/src/api/services/home.py` | `derive_home_events` skips an agent with `revoked_at` set (R4), beside the existing `is_online` skip |
| `backend/tests/test_home_events.py` | Case: a revoked, long-disconnected agent produces no `box_offline` event; an unrevoked one still does |
| `backend/src/api/services/agent_connections.py`, `agent_ws.py`, `commands.py`, `dependencies/agent_auth.py`, `routers/scans.py` | **No change** (reused: `get_socket`, `close_revoked`, the 403 gates) |

Backend call sites of changed symbols: `_fields()` is used only by `list_agents` and `_detail`
(`services/agents.py:35,46`), and both get the field automatically. `AgentSummary(`/`AgentDetail(` are built
only in `services/agents.py`. `services/home.py:109` gains the revoked skip (R4).

### frontend

| Path | Change |
|---|---|
| `frontend/src/types/openapi.d.ts` | Regenerated with `npm run gen:types` (never hand-edited) |
| `frontend/src/api/agents.ts` | `revokeAgent`, `restoreAgent` |
| `frontend/src/hooks/useAgentRevocation.ts` | **New.** Revoke/restore calls, pending/error state, invalidate `queryKeys.agents.all` |
| `frontend/src/pages/agents/DeviceRevocation.tsx` | **New.** Revoke section + `DialogShell` confirm; revoked section + `Restore device`; `AdminOnly`-gated actions; copy and test ids from `DESIGN.md` |
| `frontend/src/pages/DeviceDetail.tsx` | Mount `DeviceRevocation`; hide `ScanControl` and target-subnet `Change` when `revoked_at` is set |
| `frontend/src/pages/agents/AgentIdentity.tsx` | Presence line: `Revoked {Timestamp}` when `revoked_at` is set |
| `frontend/src/pages/agents/deviceListColumns.tsx` | Status cell: `Revoked` + `Timestamp` when `revoked_at` is set |
| `frontend/src/pages/Devices.tsx` | `rowTone` treats revoked as muted |
| `frontend/src/test/mswHandlers.ts` | `revoked_at: null` on every agent fixture; `http.post` handlers for `/agents/:agentId/revoke` and `/restore` |
| `frontend/src/pages/DeviceDetail.revocation.test.tsx` | **New.** Mirrors `Users.inviteRevoke.test.tsx` and `DeviceDetail.command.test.tsx` (the concern-split test files already used for detail/users actions) |
| `frontend/src/pages/Devices.test.tsx` | Add Revoked-vs-Offline row case |

### docs (touch points)

| Path | Change |
|---|---|
| `docs/PI-RECOVERY.md` | **New. Recovery guide** (deliverable). One section per park reason (`revoked`, `replaced`, `refused`, `upload_refused`): the log line to look for (`journalctl -u dmitri-agent`), what the Pi does alone, what a person does, whether a site visit is needed. Also cases that software cannot fix: power off, no network, `IngestConfigError`, repeated `401` (clock skew or wrong key), SD card failure. It states that a revoked Pi logs `revoked` once and then `refused` on later hourly attempts (INTEGRATION §3) |
| `docs/README.md` | Row in "UI & setup" table for `PI-RECOVERY.md` |
| `docs/PI-INSTALLER.md` | Troubleshooting row "Device shows Revoked / Pi log says `command channel parked`" → link to `PI-RECOVERY.md` |
| `docs/adr/ADR-011-pi-command-channel.md` | Amendment block 2026-09-15 (DMI-155): park policy and admin revoke/restore |
| `docs/roadmap/AUTH.md` | Lines 75-78: revoke UX delivered by DMI-155; rotation and re-pair stay Phase 2; line 194 narrowed accordingly |
| `docs/roadmap/BACKEND.md` | HTTP table (~181-185): add revoke/restore rows; agents table (~212): `revoked_at` written by admin revoke/restore, exposed on list/detail |
| `docs/roadmap/PI.md` | Line 128: "Except when the channel parks" → parks retry hourly (DMI-155) |
| `.claude/docs/hardware-agent/command-channel.md`, `.claude/docs/hardware-agent/daemon.md`, `.claude/docs/backend/routers.md`, `.claude/docs/backend/services.md`, `.claude/docs/frontend/devices-screen.md` | Owned by `/docs-sync` at the end of the pipeline, not by implementers |

## Constraints

- **No `HUMAN_INFRA_REQUIRED`.** No new hardware, daemon, service unit change, or tooling.
- **Frozen:** `authenticate_agent` / `require_agent_ws` / `require_agent` (the 403 stays), close
  code values, `run_agent_channel`, spec 041 frame and delivery gates, `ScanIngestClient`.
- **No blocking DB call on the event loop** in the async revoke route (use `run_in_threadpool`).
- **No temporary code.** The hourly retry, the admin endpoints and the guide ship complete.
- **Surgical:** no park-reason field in the API, no "retry now", no activity rows (TRUTH out of scope).

## Risks / open questions

- **R1 — Replaced twins alternate hourly. DECIDED 2026-09-16: option (a).** The deployment has one
  Pi, so two daemons with one identity is a setup mistake, not a running condition. The recovery
  guide says a person must find and remove the twin.
  Original analysis: `register()` lets the newest
  connection win and closes the older one with `4000`. The Pi receives `4000` only on a socket it
  still holds, so a `replaced` park almost always means two live daemons with one identity
  (a cloned SD card, or a second install). Under the one-hour policy, the parked twin A redials
  after an hour and takes the slot. Twin B gets `4000` and parks. An hour later B takes it back.
  The two alternate forever, and each switch cancels the evicted twin's in-flight scan. Options:
  (a) accept this, and in the recovery guide say `replaced` needs a person to find and remove the
  twin (site visit); (b) change the backend so the **existing** live connection wins and the newcomer
  is refused. This reverses ADR-011's newest-wins rule and breaks fast recovery from a half-open
  socket; (c) a longer interval for `replaced`, which contradicts user decision 1. **Not chosen.**
  The architecture above implements (a) by default, because it matches TRUTH as written.
- **R2 — In-flight nmap cannot be stopped. DECIDED 2026-09-16: accept.** TRUTH now says a parked Pi
  *starts* no scan and uploads nothing, and that a running scan's result is discarded.
  Original analysis: `run_headless_scan` runs in `asyncio.to_thread` and
  has no cancel hook. On park, the daemon cancels the awaiting task, so nothing is uploaded or
  reported. But the nmap subprocess thread runs to its natural end and writes its local result file.
  Today the same thing happens on shutdown (`asyncio.run` waits for executor threads). TRUTH "runs no
  scan" holds for new scans and for uploads, but not for a scan that is already running.
- **R3 — Revoked Pi's log says `refused` after the first hour. DECIDED 2026-09-16: accept.** The Pi
  does not read the `403` body; `docs/PI-RECOVERY.md` explains that `refused` after `revoked` means
  the device is still revoked.
  Original analysis: An upgrade `403` means revoked
  **or** a malformed id (ADR-005). The Pi cannot tell which, so later attempts log `refused`. The guide
  must explain this. No contract change is proposed.
- **R4 — Home "box offline for N days" event. DECIDED 2026-09-16: suppress it.** `derive_home_events`
  (`services/home.py:106-109`) skips an agent whose `revoked_at` is set, next to the existing
  `is_online` skip. No new event kind and no contract change: silence only (TRUTH out of scope).
- **R5 — Hourly `403` attempts burn nonces.** Each attempt stores one `agent_nonces` row (pruned
  on expiry). At 24 rows a day per parked device this is negligible. Noted only.
- **R6 — DESIGN open question 1** (show park reasons beyond Revoked) would need a Pi-reported or
  backend-inferred reason field. As explained above, the backend cannot infer `replaced` or
  `upload_refused` from what it stores. This architecture follows TRUTH's rules: Revoked vs Offline.

## Testing expectations

### hardware-agent — gate: `cd hardware-agent && uv run pytest` (black + ruff run from pre-push hooks)

`hardware-agent/tests/unit/test_command_channel.py` (mirror `TestClassification`, `Sleeper`,
`Dialer`; no real waiting):

| Case | Assert |
|---|---|
| Each park outcome (`403`, `4000 replaced`, `4001`, other `>=4000`) | One dial, then `sleeper.delays == [3600.0]`, then a second dial (`Halt`); `parked_reason` literal matches the D1 table |
| Refused attempt parks again | `Dialer(rejected(403), rejected(403))` → `delays == [3600.0, 3600.0]` |
| Replaced: no attempt within the hour | `Dialer(closed(4000,"replaced") mid-session)` → exactly one dial before the first `3600.0` sleep, no short-backoff delay recorded |
| Reconnect after park resumes short backoff | `Dialer(rejected(403), [], OSError())` (connect OK, then drop) → delays `[3600.0, 1.0, …]` |
| Network drop is not a park | existing `1006`/`OSError` ladder tests unchanged; no `3600.0` |
| `401` is not a park | existing `test_unauthorized_retries_with_a_completely_fresh_proof` unchanged |
| Park log line | `caplog` contains `command channel parked (revoked); next attempt at ` followed by an ISO timestamp |
| `on_parked` awaited once per park, before the sleep | ordering via a shared log list |
| `park("upload_refused")` during a live session | socket closed, next sleep `3600.0`, `parked_reason == "upload_refused"` |
| `close()` stops without parking | `run()` returns, `parked_reason is None`, no dial |
| Cancellation during the hourly wait | a `Sleeper` that raises `CancelledError` on `3600.0` → `CancelledError` propagates out of `run()` |
| Secret safety | existing `TestSecretSafety` still passes with the new log line |

`hardware-agent/tests/unit/test_daemon.py` (mirror `TestForbiddenIngest`, `TestShutdown`):
upload `forbidden` → `park("upload_refused")` called, `client.closed is False`, later command
ignored; `run()` passes `on_parked` and invoking it cancels an in-flight scan task, and no `uploading`/`done`
status follows; `TestShutdown` unchanged.

### backend — gate: `./database.sh --test` (or `./database.sh`, then from `backend/`, `DATABASE_URL_TEST=… uv run pytest`), then `uv run ruff check src tests`. **Never `ruff format`.** Green only with `DATABASE_URL_TEST` set on `dmitri_test`.

`backend/tests/test_agent_revocation_routes.py` (mirror `test_agent_target_subnet_routes.py`
fixtures and `test_agent_read_routes.py::test_detail_unknown_and_foreign_agent_return_identical_404`):

| Case | Assert |
|---|---|
| Admin revokes | `200`, body `revoked_at` set, row `revoked_at` set; `display_name` and `target_subnet` unchanged |
| Revoke closes the live socket | a registered `AsyncMock` socket in `CONNECTED` state receives `close(code=4001, reason="revoked")` once |
| Repeat revoke | `200`, `revoked_at` equals the first value (not bumped) |
| Admin restores | `200`, `revoked_at` `null`; `display_name`, `target_subnet`, `public_key` unchanged |
| Repeat restore on a never-revoked device | `200`, nothing changes |
| Viewer calls revoke / restore | `403` error envelope `code: forbidden`; row unchanged |
| Unauthenticated | `401` |
| Foreign-org and unknown id | identical `404` `code: not_found`; foreign row unchanged; no socket closed |
| Restored device passes the upgrade gate | `authenticate_agent` no longer raises `AgentRevoked` (mirror `test_require_agent_ws.py::test_revoked_device_refused_with_403`, inverted after restore) |

Plus `test_agent_read_routes.py` exact-key updates and a revoked-row case, and
`test_contract_fidelity.py` operation rows. `test_require_agent_ws.py` and the spec 041 suites
must pass with no edits.

### frontend — gates: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` (from `frontend/`, after `npm run gen:types`)

- `DeviceDetail.revocation.test.tsx`: admin sees `device-revoke-trigger`; cancel leaves no
  request sent; confirm posts `/revoke`, then the detail and list re-read and presence reads
  `Revoked`; revoked admin view has `device-restore` and no scan control; restore posts `/restore`;
  a `500` shows `device-revoke-error` / `device-restore-error`; viewer sees neither action.
- `Devices.test.tsx`: one fixture with `revoked_at` set reads `Revoked` + date, one with
  `online: false, revoked_at: null` reads `Offline`.
- Existing detail/list tests pass once fixtures carry `revoked_at: null`.
- Load the `frontend-conventions` skill before editing `frontend/src/`.

### Human validation (on device, not a gate)

On the Pi 4: revoke from the web app, then check `journalctl -u dmitri-agent` for the park line and
`systemctl show dmitri-agent -p NRestarts` for no change over one hour. Restore, then check that the
device is online within the hour.
