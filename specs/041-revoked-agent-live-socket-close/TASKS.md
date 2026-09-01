# Tasks — Revocation takes effect on the live agent connection (`041-revoked-agent-live-socket-close`)

5 tasks. **All COMPLETED** (1 review rejection, on #2).

> **Blast radius is `backend/`, not `hardware-agent/`.** Spawn `test-engineer` and
> `code-reviewer` as usual, but note two deviations from their defaults:
>
> - Tests go in **`backend/tests/`**, not `hardware-agent/tests/`. Every test file below
>   already exists — extend it, do not create a parallel one.
> - The gate runs **from `backend/`**, and **`./database.sh` must run from the repo root
>   first**. Without a live `dmitri_test`, `conftest.py` *skips* every DB-backed test and a
>   bare `uv run pytest` prints a green result that proves nothing. Report the suite green
>   only from a run with **zero** database-test skips.
>
> ```bash
> ./database.sh                    # repo root — start Supabase, ensure dmitri_test
> cd backend
> uv run ruff check src tests
> uv run pytest
> ```
>
> **Never run `ruff format` (or any repo-wide formatter) in `backend/`** — backend code is
> formatted by hand; `ruff check` is its only Python gate.

> **Five tasks, below the usual 6–12 aim.** This is a `size:S` feature that adds no files and
> no migration — every change is an edit to one of four existing modules. Splitting further
> would produce tasks whose only gate is a grep, and two tasks already share `agent_ws.py`
> and must serialize. See ARCHITECTURE.md "New files and naming".

> **Frozen — do not modify:** `backend/tests/test_require_agent_ws.py`. Its
> `test_revoked_device_refused_with_403` is the regression guard proving the upgrade-time
> `403` still works. It must pass untouched at every task boundary.

---

## Task 1: Close-code constants, `close_revoked()`, and the published contract row
- **Description**: Give the registry named close codes and a best-effort revoked-close, and
  publish the new code in the API contract. Per ARCHITECTURE.md §4 and the naming table.
  `4000` is today a bare literal in `register()` (`agent_connections.py:34`); replace it with
  `CLOSE_REPLACED = 4000` and add `CLOSE_REVOKED = 4001` beside it at module level.
  `close_revoked(websocket)` returns immediately unless `websocket.application_state is
  WebSocketState.CONNECTED`, wraps `close()` in `try/except Exception` (mirroring `register`'s
  existing best-effort close), and **does not** unregister and **does not** touch presence —
  the route's `finally` owns both. Add one row to the "Close codes" table in the
  `connectAgentCommandsWebSocket` description in `contracts/openapi/openapi.yaml` (~line 483):
  `4001` `revoked` / "The device is revoked; the backend will not accept it again." / **Stay
  down.** Leave the neighbouring `403` paragraph alone.
- **Absorbed**: The OpenAPI contract-table row. It is a one-row doc edit that cannot carry a
  behavioural test of its own, but `test_contract_fidelity.py` already parses that file via
  `CONTRACT_PATH`, so it is gated here rather than deferred — and `4001` is born in this task,
  so the constant and its published meaning land together.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/agent_connections.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_agent_connections.py`,
  `backend/tests/test_contract_fidelity.py`]
- **Tests**: `test_agent_connections.py` proves `CLOSE_REPLACED == 4000`, that `register` still
  evicts a displaced socket with it, that `close_revoked` closes with `4001`/`"revoked"`, that
  it is a no-op on a socket that is not `CONNECTED`, and that it swallows a raising `close()`.
  `test_contract_fidelity.py` proves `4001` appears in the published close-code table.
- **Success Criteria**:
  - `CLOSE_REPLACED = 4000` and `CLOSE_REVOKED = 4001` exist at module level in
    `agent_connections.py`; no bare `4000` or `4001` literal remains in that module's body.
  - `register()` closes a displaced socket using `CLOSE_REPLACED`; its behaviour is otherwise
    byte-for-byte unchanged.
  - `close_revoked()` never raises, never unregisters, and never writes presence.
  - The OpenAPI close-code table lists `4001` with "stay down" as the client action.
  - `uv run ruff check src tests` and `uv run pytest` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Presence helpers — `agent_is_revoked` and `touch_unless_revoked`
- **Description**: Add the two revocation reads the gates need, per ARCHITECTURE.md §1, §3 and
  the naming table. `agent_is_revoked(session, agent_id) -> bool` is the plain sync read used by
  the delivery gate (Task 5 calls it through `run_in_threadpool`).
  `touch_unless_revoked(session, agent_id, now) -> bool` returns `True` when the agent is
  revoked and leaves `last_seen_at` untouched; otherwise it bumps `last_seen_at` and returns
  `False` — **one `session.get(Agent, …)` serves both the check and the bump**, which is what
  keeps the frame gate at one `Agent` SELECT. Add `async_touch_unless_revoked` as its
  threadpool wrapper for the hello branch. `touch_agent_last_seen`, `mark_connected`,
  `mark_disconnected` and `reconcile_all` stay unchanged. **Fail closed:** neither helper may
  swallow an exception from the read — a failed lookup propagates and is never reported as "not
  revoked" (TRUTH.md business rules; ARCHITECTURE.md Constraints).
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/agent_presence.py`,
  `backend/tests/test_agent_presence.py`]
- **Tests**: `test_agent_presence.py` proves `agent_is_revoked` for revoked / not-revoked /
  unknown-agent-id; that `touch_unless_revoked` returns `True` and leaves `last_seen_at`
  **unchanged** for a revoked agent; that it returns `False` and bumps it otherwise; and that a
  raising read propagates rather than returning `False`.
- **Success Criteria**:
  - A revoked agent's `last_seen_at` is not advanced by `touch_unless_revoked`.
  - `touch_unless_revoked` issues exactly one `Agent` load per call.
  - Neither helper catches and downgrades an exception from the read.
  - The four pre-existing presence functions are unmodified.
  - `uv run ruff check src tests` and `uv run pytest` pass.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Frame gate — the `status` and `hello` paths
- **Description**: Re-check revocation on the two frames that already do database work, per
  ARCHITECTURE.md §1. In `_apply_status_frame`, call `touch_unless_revoked` **first inside the
  existing `sync_work`, before `apply_status`** — the ordering is what guarantees "no command
  lifecycle transition is written" — and widen the return to
  `Literal["ok", "unknown_command", "revoked"]`. Do **not** re-read the `Agent` after
  `apply_status`: it commits (`commands.py:157`) or rolls back (`:147`), and a rollback expires
  the row regardless of `expire_on_commit`, so a second read would cost a second SELECT. In the
  `hello` branch, replace `async_touch_agent_last_seen` with `async_touch_unless_revoked` and
  run it **before** `agent_connections.set_hello` — a revoked device must not refresh the
  `available_subnets` the registry feeds to `AgentDetail` and the trigger-time subnet check.
  On a revoked result, close via `agent_connections.close_revoked` and return.
  `async_touch_agent_last_seen` loses its only caller here; remove it as an orphan of this
  change. **`run_agent_channel` is untouched** — do not change its loop condition, do not add a
  `RuntimeError` catch, and do not edit its `WebSocketDisconnect` comment.
- **Absorbed**: The end-to-end channel verification. It cannot stand alone — it is the proof
  that this task's close propagates through the route's existing `finally`, and it asserts on
  code this task changes.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`backend/src/api/services/agent_ws.py`,
  `backend/tests/test_agent_ws.py`, `backend/tests/test_agent_ws_channel.py`]
- **Tests**: `test_agent_ws.py` (unit, mocked `WebSocket`) proves revoked + `status` →
  `apply_status` never called, socket closed once with `4001`; revoked + `hello` → `set_hello`
  never called and the registry keeps its previous `available_subnets`; healthy agent →
  unchanged handling with **no extra session** (extend
  `test_two_frames_use_distinct_sessions_closed_per_frame` and `test_no_session_outlives_ws_loop`);
  and fail-closed — when the revocation read raises, `apply_status` is never called and the
  error is not swallowed. `test_agent_ws_channel.py` (end-to-end `TestClient`) proves an agent
  revoked mid-connection that sends `status` sees close `4001`, its seeded `Command` row and
  scan status are unchanged, and after the handler exits `agents.connected_at IS NULL` and
  `is_online` is false, with `run_agent_channel` exiting without raising.
- **Success Criteria**:
  - A revoked agent's `status` frame writes no command lifecycle transition and no scan status.
  - A revoked agent's `hello` frame does not reach `set_hello`.
  - A well-formed `status` frame from a healthy agent still costs **one** `Agent` SELECT and one
    session — no regression in the session-counting tests.
  - `run_agent_channel` is unmodified, comment included.
  - `async_touch_agent_last_seen` is gone and has no remaining callers.
  - `test_require_agent_ws.py` passes unmodified.
  - `uv run ruff check src tests` and `uv run pytest` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Frame gate — the no-database rejection branches
- **Description**: Close the socket for a revoked agent on frames that never reach the database,
  per ARCHITECTURE.md §1. Invalid JSON, a non-dict payload, a schema-invalid `hello` or
  `status`, an inbound `command`, a missing `type` and an unknown `type` are today rejected with
  an `AgentErrorFrame` and no DB touch. TRUTH.md requires the socket to close on **any** frame
  from a revoked agent, so funnel these branches through one new `_reject_frame` helper: send
  the same error frame, then pay **one** revocation query, then close via `close_revoked` if
  revoked. Malformed frames are the rare path, so the well-formed paths pay nothing extra. The
  "unknown command_id" error at the tail of the `status` branch keeps plain `send_error` — that
  branch has already established the agent is not revoked, and must not query twice.
- **Dependencies**: Task 3
- **Target Files**: [`backend/src/api/services/agent_ws.py`, `backend/tests/test_agent_ws.py`]
- **Tests**: `test_agent_ws.py` proves revoked + each malformed frame shape → the error frame is
  sent **and then** the socket closes with `4001`; healthy + malformed → the error frame is sent
  and the socket stays usable (`test_invalid_frames_send_error_and_keep_socket_usable` must
  still pass); and the unknown-`command_id` path does not issue a second revocation query.
- **Success Criteria**:
  - Every no-DB rejection branch routes through `_reject_frame`; none closes the socket inline.
  - The error frame is sent before the close, so the Pi can read why.
  - A healthy agent's malformed frame leaves the connection open, exactly as today.
  - The unknown-`command_id` branch still uses `send_error` and adds no query.
  - `uv run ruff check src tests` and `uv run pytest` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Delivery gate — refuse to push a command to a revoked agent
- **Description**: Stop the backend writing a command onto a revoked agent's socket, per
  ARCHITECTURE.md §3 — this is what closes the gap for a revoked agent that is idle and has sent
  no frame. In `commands.deliver()`, read revocation via
  `await run_in_threadpool(agent_presence.agent_is_revoked, session, command.agent_id)`,
  **hoisted above the `if` and evaluated before the `or`** so short-circuiting cannot hide it,
  then fold the result into the existing missing-socket branch: close the socket if one is
  registered, `_expire_queued_command`, raise `DeviceOfflineError`. The read **must** go through
  `run_in_threadpool` — `deliver()` is `async def` on the event loop, every existing DB touch in
  it (`:277`, `:294`, `:297`) is already offloaded, and under ADR-011's single replica one
  blocking pool wait stalls every live agent socket. Reuse the existing outcome verbatim:
  command → `expired` with `error_code=device_offline`, **no `scan_id` and no stub `scans` row**,
  and the route's existing `DeviceOfflineError` → `503 device_offline` mapping. Add no new error
  code and no new terminal status. Do not move the check into `_claim_agent`: the command row
  does not exist yet there, and deciding at claim time while acting at delivery time is a
  time-of-check/time-of-use gap.
- **Absorbed**: The `.claude/docs/backend/services.md` code-map write-back, as the last
  implementation task. It is a doc edit with no test of its own and is owned by `/docs-sync`,
  which runs at the end of the pipeline — note the revoked close and the per-frame check there.
- **Dependencies**: Task 1, Task 2
- **Target Files**: [`backend/src/api/services/commands.py`,
  `backend/tests/test_command_delivery.py`, `backend/tests/test_enqueue_command.py`,
  `.claude/docs/backend/services.md`]
- **Tests**: `test_command_delivery.py` proves `deliver()` with a registered socket for a revoked
  agent never calls `send_text`, closes the socket with `4001`, leaves the command `expired` with
  `error_code=device_offline` and `scan_id is None`, writes no `ScanRecord`, and raises
  `DeviceOfflineError`; plus fail-closed — when the revocation read raises, `send_text` is never
  called and the error propagates rather than being swallowed into a delivery.
  `test_enqueue_command.py` proves the same path at the route level: `POST
  /api/v1/agents/{id}/commands` for a revoked agent whose socket is still registered returns
  `503` with `code: device_offline`, the command row is `expired`, and no stub scan exists.
- **Success Criteria**:
  - A revoked agent with an open, registered socket is never sent a `command` frame.
  - The revocation read is awaited through `run_in_threadpool` and is not inside the `if`
    condition — no synchronous DB call runs on the event loop in `deliver()`.
  - The refusal reuses `expired` / `error_code=device_offline` / `503 device_offline`; no new
    error code, no new terminal status, no stub `scans` row.
  - `_claim_agent`, `enqueue`, `apply_status` and `sweep_stale_commands` are unmodified.
  - `test_require_agent_ws.py` passes unmodified.
  - `uv run ruff check src tests` and `uv run pytest` pass with **zero** database-test skips.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 ─┬─→ #3 → #4        (agent_ws.py — #4 serializes behind #3, same file)
    │
#2 ─┴─→ #5             (commands.py — parallel with #3/#4)
```

Track A: **#1** (registry + contract) and **#2** (presence helpers) are independent — run both now.
Track B: **#3 → #4** (frame gate, both in `agent_ws.py`, must serialize).
Track C: **#5** (delivery gate, `commands.py`) runs parallel to Track B once #1 and #2 land.

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Close-code constants, `close_revoked()`, contract row | COMPLETED |
| 2 | Presence helpers — `agent_is_revoked` / `touch_unless_revoked` | COMPLETED |
| 3 | Frame gate — `status` and `hello` paths | COMPLETED |
| 4 | Frame gate — no-database rejection branches | COMPLETED |
| 5 | Delivery gate — refuse to push to a revoked agent | COMPLETED |

## Acceptance-criteria coverage

Every row in TRUTH.md's acceptance table maps to at least one task:

| TRUTH.md scenario | Task |
|---|---|
| Frame from revoked agent | #3 (`status`, `hello`), #4 (malformed) |
| Status frame does not land | #3 |
| Connected projection cleared | #3 (end-to-end channel test) |
| Delivery refused to revoked agent | #5 |
| Reconnect still refused | #3, #5 (frozen guard `test_require_agent_ws.py`) |
| Healthy agent unaffected | #3 (session-counting), #4 (socket stays usable) |
| Lookup failure fails closed | #2 (helpers), #3 (frame), #5 (delivery) |
| Close code documented | #1 |
| Gates | every task |

Out of scope per TRUTH.md and therefore **not** tasked: a revoke endpoint or admin UI, key
rotation, any change to the upgrade-time check, user-session revocation, proactive disconnect at
the instant of revocation, and bounding the idle-socket window.
