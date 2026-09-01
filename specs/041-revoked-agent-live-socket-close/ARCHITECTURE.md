# ARCHITECTURE — Revocation takes effect on the live agent connection

Implements `TRUTH.md` (DMI-97). Backend only (`layer:backend`, `size:S`). No `DESIGN.md` and no
`INTEGRATION.md`: no screen changes, no TUI, no hardware-agent change, and the feature stays
inside one layer.

> The spec template is written for the `hardware-agent/` scan pipeline. This feature lives in the
> API's Pi command channel instead, so "system context" describes the command channel; the
> mandatory sections (file/naming table, testing expectations, gates) are unchanged.

## System context

The pipeline this feature sits in is the **backend → Pi command channel** (ADR-011):

```
operator "Scan now"  →  POST /api/v1/agents/{id}/commands
                          → commands._claim_agent()   (queued row)
                          → commands.deliver()        (send frame on the live socket)   ← [D] delivery gate
Pi daemon            →  WSS /api/v1/agents/{id}/commands  (Ed25519-signed upgrade)      ← unchanged 403 gate
                          → routers/agents.connect_agent_commands()
                             accept → agent_connections.register() → async_mark_connected()
                             → agent_ws.run_agent_channel()  (receive loop)
                                → agent_ws.handle_agent_frame()  (hello / status / …)   ← [F] frame gate
                             finally: unregister() + async_mark_disconnected()
```

Revocation is recorded today only as `agents.revoked_at` set by hand in the database. It is read
once, at upgrade time, by `dependencies/agent_auth.authenticate_agent`. **That upgrade path does
not change.** This feature adds the two gates marked above:

- **[F] frame gate** — every inbound frame re-checks revocation; a frame from a revoked agent has
  no effect and its socket is closed with the revoked close code.
- **[D] delivery gate** — a command is never written onto the socket of a revoked agent, even one
  that has sent nothing since being revoked.

Both gates close the socket. The existing `finally` in `connect_agent_commands` then unregisters
and calls `async_mark_disconnected`, which sets `Agent.connected_at = None` — this is what
satisfies TRUTH's "connected projection cleared". No new disconnect logic is written.

## Prior art

`docs/research/revocation-on-live-connections.md` (2026-09-01) checked this design against the
revocation literature and the deployed field. Summary: what this spec builds is **pull-based
revocation** (on-demand validation) — a named, standard class, not an improvisation. It is what
OCSP and OpenSSH's `RevokedKeys` do, and NIST SP 800-207 tenet 6 names "new resource requested"
as a legitimate re-authorization trigger. Deployed push systems are slower than intuition
suggests: AWS IoT promises "within a few minutes" after certificate deactivation, Entra CAE "up
to 15 minutes". **No design change was warranted.** The research did correct two performance
claims and add the fail-closed and event-loop rules recorded below.

## Design decisions

### 1. Where the per-frame re-check lives (and why not a second query)

The rule is one re-check per inbound frame **without adding a second DB round trip to the frames
that already do DB work**.

- **`status` frames** — `agent_ws._apply_status_frame` already opens a session inside
  `run_in_threadpool` and already loads the `Agent` row (via `touch_agent_last_seen`, which does
  `session.get(Agent, agent_id)`). The revocation check is placed **first** inside that same
  `sync_work`, before `apply_status`, and the ordering guarantees the acceptance criterion "no
  command lifecycle transition is written".

  **The identity map does not make this free.** `apply_status` commits
  (`commands.py:157`) or rolls back (`:147`) between the check and
  `touch_agent_last_seen`; `expire_on_commit` defaults to `True` (SQLAlchemy 2.0.51
  `orm/session.py:1510`), and a rollback expires the row *regardless* of that flag. A naive
  ordering therefore costs **two** `Agent` SELECTs per status frame, not one.

  **So fold the check into the touch.** Reuse the same `touch_unless_revoked` helper the hello
  branch uses (below), run it **before** `apply_status`, and let one `session.get(Agent, …)`
  serve both the revocation decision and the `last_seen_at` bump:

  ```
  revoked = touch_unless_revoked(session, agent_id, now)   # one SELECT, commits the touch
  if revoked:
      return "revoked"
  applied = apply_status(...)                              # reads Command rows, not Agent
  ```

  `apply_status` touches `commands`/`scans`, never `agents`, so nothing re-reads the expired
  `Agent`. Net cost: **one `Agent` SELECT per status frame — unchanged from today.** The
  behavioural delta is that `last_seen_at` is now committed before the lifecycle write rather
  than after; for a healthy agent both orders end identically, and `test_status_touches_without_prior_hello`
  still holds.
- **`hello` frames** — the hello branch already makes exactly one DB trip
  (`async_touch_agent_last_seen`). It is replaced by `async_touch_unless_revoked`, the same single
  trip, which returns whether the agent is revoked and skips the `last_seen_at` bump when it is.
  **`hello` is checked**, because it is the frame that populates `available_subnets` in the
  registry, and those values feed `AgentDetail` and the `subnet_not_reported` check at trigger
  time. Letting a revoked device refresh what the backend believes about its networks would be a
  write of attacker-supplied state, so the check runs **before** `agent_connections.set_hello`.
  For a healthy agent this is a pure reorder (DB trip, then registry write) with identical effect.
- **Frames with no DB phase** (invalid JSON, non-dict, schema-invalid `hello`/`status`, an
  inbound `command`, missing or unknown `type`) — these are already rejected with an
  `AgentErrorFrame` and never touch the database. TRUTH still requires the socket to close on
  *any* frame from a revoked agent, so these branches funnel through one new helper,
  `agent_ws._reject_frame`, which sends the same error frame and then pays for **one** revocation
  query before closing. Malformed frames are the rare path; the well-formed paths pay nothing.
  The existing "unknown command_id" error at the end of the `status` branch keeps plain
  `send_error` — that branch has already established the agent is not revoked.

`agent_connections`, `mark_connected` / `mark_disconnected` and the registry semantics are
otherwise untouched.

### 2. How the socket is closed from the frame path

One best-effort coroutine, `agent_connections.close_revoked(websocket)`:

- returns immediately unless `websocket.application_state is WebSocketState.CONNECTED`, so a
  socket already closed (by `register`'s `4000 replaced` eviction, or by the client) is never
  closed twice;
- wraps `websocket.close(...)` in `try/except Exception`, matching `register`'s existing
  best-effort close of a displaced socket;
- does **not** unregister and does **not** touch presence — the route's `finally` owns both, and
  duplicating them would double-write `connected_at`.

Interaction with `run_agent_channel`: the close happens inside `handle_agent_frame`, i.e. **between
receives, on the same task**. The loop's guard is
`while websocket.application_state == WebSocketState.CONNECTED`, so it re-evaluates after the
frame is handled and exits normally — `receive_text()` is never re-entered on the closed socket.
That is why the documented hazard in `run_agent_channel` (a *foreign* task closing the socket from
under a parked `receive_text()`, which raises a bare `RuntimeError`) is **not** reached by this
path, and the existing `WebSocketDisconnect` handling and its comment must stay exactly as they
are. Do not add a `RuntimeError` catch and do not change the loop condition.

Exit ordering after a revoked frame: `close_revoked` → loop condition false → return →
route `finally` → `agent_connections.unregister` → `async_mark_disconnected` → `connected_at`
NULL, `is_online` false, agent no longer eligible for delivery.

### 3. The outbound delivery path

The check goes in `commands.deliver`, in the **same branch as the missing socket**, and reuses the
existing offline outcome verbatim — no new error code:

```
socket = agent_connections.get_socket(command.agent_id)
revoked = await run_in_threadpool(
    agent_presence.agent_is_revoked, session, command.agent_id
)
if socket is None or revoked:
    if socket is not None:
        await agent_connections.close_revoked(socket)
    await run_in_threadpool(_expire_queued_command, session, command.id)
    raise DeviceOfflineError
```

**The revocation read MUST go through `run_in_threadpool`, and MUST be evaluated before the
`or` — not short-circuited inside the `if`.** `deliver()` is `async def` running on the event
loop; every existing DB touch in it (`commands.py:277`, `:294`, `:297`) is already offloaded. An
inline synchronous read would be the one blocking DB call left on the loop thread, and under
ADR-011's single replica a pool wait there stalls **every** live agent socket — the defect
`docs/research/sync-vs-async-db-stack.md` Caveat 2 and `ws-session-lifetime.md` §5.1(b) both
warn about. Hoisting it out of the `if` also keeps the cost honest and constant rather than
hidden behind a short-circuit.

Consequences, all pre-existing behaviour: command → `expired` with `error_code=device_offline`,
**no `scan_id` and no stub `scans` row** (ADR-011 §4 CHECK constraint), and
`routers/agents.py` maps `DeviceOfflineError` → `ApiError(503, code="device_offline")`.

Why `deliver` and not `_claim_agent`: `_claim_agent` runs before the command row exists, so
refusing there would leave no audit row, and TRUTH requires "the command reaches its terminal
non-delivered state".

**What it costs, honestly: one primary-key `SELECT`, and that SELECT is the point.**
An earlier draft claimed the read was free because `_claim_agent` had already loaded the `Agent`
on the same session. That is wrong: `_claim_agent` ends in `enqueue()`, which commits
(`commands.py:68`), and `expire_on_commit` defaults to `True`, so the row is expired before
`deliver()` runs. The read is real. Do not try to remove it — reading the flag earlier, while the
object is still live, would decide revocation at *claim* time and act on it at *delivery* time,
which is a time-of-check/time-of-use gap (CWE-367). The fresh read is what makes the answer
correct at the moment the command would actually go out. It reuses the same session and the same
checked-out connection; it does not open a second session or a second connection.

The revoked device's socket is closed here too, satisfying TRUTH's "next inbound frame or next
delivery attempt — whichever comes first". The close is observed by the agent's own handler task,
whose `finally` clears presence as in §2.

### 4. Close code `4001 revoked` — one named constant, one home

`4000` currently exists **only as a literal** inside `agent_connections.register`
(`backend/src/api/services/agent_connections.py:34`). Both codes become module-level constants at
the top of that same module, next to the registry that owns socket lifecycle:

| Constant | Value | Reason | Client action |
|----------|-------|--------|---------------|
| `CLOSE_REPLACED` | `4000` | Another connection took the slot | Stay down |
| `CLOSE_REVOKED` | `4001` | Device permanently revoked | Stay down |

`register` is edited to use `CLOSE_REPLACED` instead of the literal — the only change to that
function. `agent_ws` and `commands` import `close_revoked`, never the raw integer.

> **SETTLED 2026-09-01:** the operator confirmed `4001`. It is a contract value — DMI-66 keys the
> daemon's reconnect behaviour on it — so treat it as fixed; changing it later means a coordinated
> change at both ends. Implement it as the named constant below and nowhere else. No
> `HUMAN_INFRA_REQUIRED`: no new hardware, daemon, or tooling is needed for this feature.

## Data model / contracts

- **No migration, no model change.** `Agent.revoked_at`, `Agent.connected_at` and
  `Agent.last_seen_at` already exist in `backend/src/api/models/command.py`.
- **No new HTTP status, no new `code` value.** The revoked-delivery outcome reuses
  `503` / `device_offline`.
- **No frame-schema change.** `AgentHelloFrame` / `AgentStatusFrame` / `AgentCommandFrame` /
  `AgentErrorFrame` are untouched, so `test_contract_fidelity.py`'s schema comparison is unaffected.
- **New constants:** `CLOSE_REPLACED = 4000`, `CLOSE_REVOKED = 4001` in `agent_connections.py`.
- **Contract text:** one row added to the "Close codes" table in the
  `connectAgentCommandsWebSocket` description in `contracts/openapi/openapi.yaml` (~line 483):

  | `4001` `revoked` | The device is revoked; the backend will not accept it again. | **Stay down.** |

  The neighbouring paragraph already says a `403` on upgrade means revoked-or-malformed-id; leave
  it as is.
- **ADR-011 needs no amendment** — it carries no close-code table (verified); the published
  contract in `openapi.yaml` is the normative home for close codes, and the frame envelope is
  unchanged.

### Internal signature changes (all private to the two services)

| Symbol | Before | After |
|--------|--------|-------|
| `agent_presence.agent_is_revoked` | — | new: `(session, agent_id) -> bool` — sync; the delivery gate calls it via `run_in_threadpool` |
| `agent_presence.touch_unless_revoked` | — | new: `(session, agent_id, now) -> bool` (True = revoked, `last_seen_at` not touched). One `session.get(Agent, …)` serves both the check and the bump; used by the `status` path inside its existing `sync_work` |
| `agent_presence.async_touch_unless_revoked` | — | new: threadpool wrapper of the above, used by the `hello` branch |
| `agent_ws._apply_status_frame` | `-> bool` (unknown command) | `-> Literal["ok", "unknown_command", "revoked"]` |
| `agent_ws._reject_frame` | — | new: error frame, then close if revoked |
| `agent_connections.close_revoked` | — | new: `(websocket) -> None`, best-effort |

Public call sites are unchanged: `run_agent_channel`, `handle_agent_frame`, `deliver` and
`enqueue_for_agent` keep their signatures, so `routers/agents.py` needs no edit.

## New files and naming (mandatory)

**No new files.** Every change is an edit to an existing module.

| Layer | Path | Change |
|-------|------|--------|
| Registry | `backend/src/api/services/agent_connections.py` | Add `CLOSE_REPLACED = 4000`, `CLOSE_REVOKED = 4001`, `close_revoked(websocket)`; `register()` uses `CLOSE_REPLACED` instead of the literal `4000` |
| Presence | `backend/src/api/services/agent_presence.py` | Add `agent_is_revoked(session, agent_id)`, `touch_unless_revoked(session, agent_id, now)` and its `async_` wrapper; `touch_agent_last_seen`, `mark_connected`, `mark_disconnected`, `reconcile_all` unchanged |
| WS channel | `backend/src/api/services/agent_ws.py` | `_apply_status_frame` calls `touch_unless_revoked` **before** `apply_status` (one `Agent` SELECT serves check + touch); hello branch uses `async_touch_unless_revoked` **before** `set_hello`; new `_reject_frame` used by the no-DB rejection branches; close via `agent_connections.close_revoked`. `run_agent_channel` unchanged (loop condition and `WebSocketDisconnect` comment must not be touched) |
| Commands | `backend/src/api/services/commands.py` | `deliver()` treats a revoked agent as offline: `await run_in_threadpool(agent_is_revoked, …)` hoisted above the `if`, then close the socket, `_expire_queued_command`, raise `DeviceOfflineError`. `_claim_agent`, `enqueue`, `apply_status`, `sweep_stale_commands` unchanged |
| Contract | `contracts/openapi/openapi.yaml` | One row in the close-code table of `connectAgentCommandsWebSocket` (~line 483) |
| Code map | `.claude/docs/backend/services.md` | Registry and WS rows mention the revoked close and the per-frame check (owned by `/docs-sync`, run at the end of the pipeline) |

### Call-site accounting (CLAUDE.md integration rule)

The CLAUDE.md rule names `ScanRunner` (`hardware-agent/src/agent/scanner/runner.py`) and
`ScanProgressScreen` (`hardware-agent/src/agent/tui/screens/scan_progress.py`) as the paths that
bypass the orchestrator. **Neither is involved here**: this feature adds no parameter to the
hardware-agent orchestrator or runner and touches no file under `hardware-agent/`. The rule's
intent — account for *every* call site of every changed symbol — is discharged as follows
(grepped, complete):

| Changed symbol | Call sites | Status |
|----------------|-----------|--------|
| `agent_connections.register` | `routers/agents.py:145` | Unchanged signature; literal → constant only |
| `touch_agent_last_seen` | `agent_presence.py:59` (`async_touch_agent_last_seen`), `agent_ws.py:59` (`_apply_status_frame`) | Both keep working; hello stops using the async wrapper |
| `async_touch_agent_last_seen` | `agent_ws.py:99` (hello branch) — the only caller | Replaced by `async_touch_unless_revoked`; keep the old wrapper only if another caller appears, otherwise remove it as an orphan of this change |
| `_apply_status_frame` | `agent_ws.py` status branch — the only caller | Updated for the new return type |
| `handle_agent_frame` | `agent_ws.py:145` (`run_agent_channel`) — the only caller | Signature unchanged |
| `run_agent_channel` | `routers/agents.py:150` | Signature unchanged; `finally` untouched |
| `deliver` | `commands.py:374` (`enqueue_for_agent`) — the only caller | Signature unchanged |
| `enqueue_for_agent` | `routers/agents.py:115` | Signature unchanged; existing `DeviceOfflineError → 503` mapping reused |

## Constraints

- **No new infrastructure.** No `HUMAN_INFRA_REQUIRED`. No open decisions: close code `4001` is
  confirmed (§4).
- **The upgrade-time gate is frozen.** `dependencies/agent_auth.authenticate_agent` and
  `require_agent_ws` must not change; the `403` for a revoked device stays exactly as it is.
- **No proactive disconnect.** Nothing in the system writes `revoked_at` yet, so there is no event
  to hook; the two gates are the whole mechanism (TRUTH "Out of scope").
- **One session and one connection per frame — not one query.** Reuse the per-frame session and
  its checked-out connection; do not open a second session, a second connection, or a second
  threadpool hop. Fold the revocation read into the `Agent` load the frame already performs
  (§1). One primary-key `SELECT` is expected and required. **Do not set
  `expire_on_commit=False` to avoid it** — `docs/research/ws-session-lifetime.md` §3 identifies
  that as the wrong move on this route, and a rollback expires the row regardless of the flag.
- **Fail closed.** If the revocation read raises, the frame must not be processed and the command
  must not be delivered; the error propagates. Never treat a failed revocation lookup as "not
  revoked". This is the transferable lesson from the PKI measurement literature, where soft-fail
  silently disables revocation checking altogether (Liu et al., IMC 2015 §2.2).
- **No blocking DB call on the event loop.** Every revocation read reached from `async def` code
  goes through `run_in_threadpool` (§3). Under ADR-011's single replica, one blocking pool wait
  stalls every live agent socket.
- **No new error code and no new terminal command status.** Reuse `expired` /
  `error_code=device_offline` / `503 device_offline`.
- **No temporary code** (CLAUDE.md): the revoked path ships complete, not as a stub behind the
  absent revoke endpoint.

## Testing expectations

All tests are backend `pytest` under `backend/tests/`, mirroring the files that already cover each
area. No new test file is needed.

| Test file | Cases to add | Mirror |
|-----------|--------------|--------|
| `backend/tests/test_agent_connections.py` | `CLOSE_REPLACED == 4000` and `register` still closes a displaced socket with it; `close_revoked` closes with `4001`/`"revoked"`; `close_revoked` is a no-op on a socket that is not `CONNECTED` and swallows a raising `close()` | existing register/eviction tests in the same file |
| `backend/tests/test_agent_presence.py` | `agent_is_revoked` true / false / unknown agent id; `async_touch_unless_revoked` returns True and leaves `last_seen_at` unchanged for a revoked agent, False and bumps it otherwise | existing `mark_connected` / `touch_agent_last_seen` tests |
| `backend/tests/test_agent_ws.py` (unit, mocked `WebSocket`) | Revoked + `status` frame → `apply_status` not called, no command row written, socket closed once with `4001`; revoked + `hello` → `set_hello` not called, registry keeps its previous `available_subnets`; revoked + malformed frame → error frame **then** close; healthy agent → unchanged frame handling and **no extra session** (extend the existing session-counting tests `test_two_frames_use_distinct_sessions_closed_per_frame` / `test_no_session_outlives_ws_loop`); **fail-closed:** when the revocation read raises, `apply_status` is never called and the error is not swallowed | `test_status_touches_without_prior_hello`, `test_invalid_frames_send_error_and_keep_socket_usable` |
| `backend/tests/test_agent_ws_channel.py` (end-to-end `TestClient`) | Agent revoked mid-connection sends `status` → client sees close `4001`, the seeded `Command` row is unchanged, its scan status is unchanged, and after the handler exits `agents.connected_at IS NULL` / `is_online` false; `run_agent_channel` exits without raising | `test_disconnect_marks_agent_offline_without_bumping_last_seen`, `test_running_frame_on_queued_applies_and_backfills_delivered_at` |
| `backend/tests/test_command_delivery.py` | `deliver()` with a registered socket for a revoked agent → `send_text` never called, socket closed with `4001`, command `expired` with `error_code=device_offline` and `scan_id is None`, no `ScanRecord` row, `DeviceOfflineError` raised. **Fail-closed:** when the revocation read raises, `send_text` is never called and the error propagates — it is not swallowed into a delivery | `test_deliver_no_socket_raises_offline_without_awaiting_send`, `test_deliver_send_failure_expires_without_scan` |
| `backend/tests/test_enqueue_command.py` | `POST /api/v1/agents/{id}/commands` for a revoked agent whose socket is still registered → `503` with `code: device_offline`, command row `expired`, no stub scan (route-level proof of the same path) | `test_device_offline_expires_command_without_scan` |
| `backend/tests/test_require_agent_ws.py` | **Regression guard only — do not modify.** `test_revoked_device_refused_with_403` must still pass unchanged | — |
| `backend/tests/test_contract_fidelity.py` | The `connectAgentCommandsWebSocket` description in `contracts/openapi/openapi.yaml` lists `4001` in its close-code table (the file is already parsed there via `CONTRACT_PATH`) | the existing contract-text assertions in that file |

Healthy-agent regression is covered by the whole existing `test_agent_ws_channel.py` /
`test_command_delivery.py` suites passing unchanged — no expected-value edits to them are allowed
by this feature.

## Gates

Run from `backend/`, with the test database up first so DB-backed tests do not silently skip
(a bare run prints a green result while skipping ~251 tests and proves nothing):

```bash
./database.sh            # from the repo root — start Supabase and ensure dmitri_test
cd backend
uv run ruff check src tests
uv run pytest
```

**Never run `ruff format` (or any repo-wide formatter) in `backend/`** — backend code is formatted
by hand; `ruff check` is its only Python gate. Report the suite as green only from a run with
zero database-test skips.
