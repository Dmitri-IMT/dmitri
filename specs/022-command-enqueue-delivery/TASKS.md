# Tasks — Command enqueue + delivery + status transitions (`022-command-enqueue-delivery`)

10 tasks. **Unblocked now: #1, #2, #3**

**Governing spec**: `plan.md` (this directory). This slice ran the lightweight plan, not the
full Peirce pipeline — there is no `ARCHITECTURE.md`/`DESIGN.md`. Every `Target Files` path
below comes from `plan.md` §"Implementation steps" and §"Where the work lands"; decisions are
cited as **D1**–**D12** from `plan.md` §Decisions.

**Contract source of truth**: `contracts/openapi/openapi.yaml` already specifies
`POST /api/v1/agents/{agent_id}/commands` (line 429), `GET /api/v1/commands/{command_id}`
(line 564), `CommandDetail` (1990), `CreateCommandRequest` (1958) and the
`device_busy`/`device_offline` bodies (1253–1296). **Do not invent request/response shapes.**

**Blast radius: `backend/` (Python).** Spawn `test-engineer` and `code-reviewer`.
Gate: `uv run ruff check src tests` **and** `uv run pytest`, both from `backend/`.
**Never run `ruff format` in `backend/`** (`.claude/CLAUDE.md`).

Out of scope — do not build: `GET /agents`, `available_subnets`, `target_subnet` (DMI-78);
revoking a device dropping its live socket (DMI-97); pinning
`command_disconnect_grace_seconds` to the Pi's real backoff (DMI-66).

---

## Task 1: Per-frame WS session lifetime (D7)
- **Description**: Per `plan.md` step 0 / D7. `run_agent_channel` takes a session **factory**
  instead of a `Session`; `handle_agent_frame` opens `with Session(get_engine())` per frame and
  the blocking DB work is dispatched via `run_in_threadpool` so it leaves the event loop. Update
  the ~6 call sites in `tests/test_agent_ws.py` (all already inject a session, so a factory
  parameter keeps them injectable). Rationale in `docs/research/ws-session-lifetime.md`.
  Prerequisite for Task 9, not a drive-by.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/agent_ws.py`, `backend/src/api/routers/agents.py`,
  `backend/tests/test_agent_ws.py`, `backend/tests/test_agent_ws_channel.py`]
- **Tests**: `backend/tests/test_agent_ws.py` — proves a session is opened and closed **per
  frame** (two frames on one channel use two sessions), that no session outlives the WS loop,
  and that existing hello/status/error frame handling is unchanged.
- **Success Criteria**:
  - `run_agent_channel` signature accepts a callable factory; no `Session` object is held across
    the channel's `await` loop anywhere in `agent_ws.py`.
  - Frame DB work runs under `run_in_threadpool`.
  - `uv run pytest tests/test_agent_ws.py tests/test_agent_ws_channel.py` passes; full suite green.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Monotonic lifecycle ranks (D9, D2)
- **Description**: Per `plan.md` step 1 / D9 / D2. Replace the pairwise `_LEGAL_EDGES` map in
  `command_lifecycle.py` with a monotonic rank for Pi-owned statuses
  (`queued 0 → delivered 1 → running 2 → uploading 3 → done/failed 4`). Keep **explicit** guards
  for the backend-owned `delivered`/`expired` transitions — rank alone would permit
  `delivered → expired` and break C12. Add the missing `delivered → failed` edge (D2). Add
  `is_terminal()`, needed by both the busy check and the sweeper. Pure module — no DB access.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/command_lifecycle.py`,
  `backend/tests/test_command_lifecycle.py`]
- **Tests**: `backend/tests/test_command_lifecycle.py` — `queued → running` applies (skipping
  `delivered`), a duplicate frame at the same rank is a silent no-op, `done → failed` does not
  apply, `delivered → expired` is rejected, `delivered → failed` is allowed, `is_terminal()`
  true for exactly `done`/`failed`/`expired`.
- **Success Criteria**:
  - `_SCAN_STATUS_BY_COMMAND_STATUS` mirroring is preserved for every status.
  - Ranking is order-independent and idempotent: applying the same target twice yields "no
    change" the second time, not an error.
  - `uv run ruff check src tests` clean.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: Migration — nullable `scan_id`, CHECK, active-command index, `agents.connected_at`
- **Description**: Per `plan.md` step 2 / D1 / D6 / D12. One Alembic revision that makes
  `commands.scan_id` nullable, adds
  `CHECK (scan_id IS NOT NULL OR status = 'expired')` (D1 — makes "no scan row" and "expired"
  provably equivalent), adds the D6 partial unique index
  `uq_commands_active_agent ON commands (agent_id) WHERE status IN ('queued','delivered','running','uploading')`,
  and adds nullable `agents.connected_at` (D12). Update the ORM models to match.
- **Absorbed**: the two new settings in `core/config.py` — `command_running_timeout_seconds`
  (alias `COMMAND_RUNNING_TIMEOUT_SECONDS`, D4) and `command_disconnect_grace_seconds`
  (default **900**, D11) — following the existing `Field(default=..., alias=...)` style. Config
  constants with no branching cannot carry their own test; they ship with the schema change
  their consumers read alongside.
- **Dependencies**: —
- **Target Files**: [`backend/alembic/versions/20260731_13_command_delivery.py`,
  `backend/src/api/models/command.py`, `backend/src/api/core/config.py`,
  `backend/tests/test_command_delivery_migration.py`]
- **Tests**: `backend/tests/test_command_delivery_migration.py`, mirroring
  `tests/test_command_migration.py` — upgrade/downgrade round-trip; the CHECK rejects a
  non-`expired` command with null `scan_id`; the partial unique index rejects a second
  non-terminal command for one agent but permits one after the first goes terminal;
  `agents.connected_at` exists and defaults to NULL.
- **Success Criteria**:
  - `alembic upgrade head` then `downgrade -1` leaves the schema as before.
  - Both new settings are readable from `Settings` with their documented defaults/aliases.
  - `uv run pytest tests/test_command_delivery_migration.py tests/test_command_models.py` passes.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 4: Connection presence projection (D12)
- **Description**: Per `plan.md` step 2b / D12. New `services/agent_presence.py` with
  `mark_connected(session, agent_id, now)` (sets `connected_at`, touches `last_seen_at`),
  `mark_disconnected(session, agent_id)` (clears `connected_at`), and `reconcile_all(session)`
  (`UPDATE agents SET connected_at = NULL`, run at API startup to recover from a hard crash
  where `unregister` never ran). Move `touch_agent_last_seen` out of `agent_ws.py` into this
  module — same concern, and Task 1 already rewrote how it takes a session. Wire the calls
  where `register()` / `finally: unregister()` already sit in
  `routers/agents.py:connect_agent_commands`, plus startup in `main.py`.
  **`services/agent_connections.py` is not modified** — it stays a pure in-memory registry.
- **Dependencies**: Task 1, Task 3
- **Target Files**: [`backend/src/api/services/agent_presence.py`,
  `backend/src/api/services/agent_ws.py`, `backend/src/api/routers/agents.py`,
  `backend/src/api/main.py`, `backend/tests/test_agent_presence.py`]
- **Tests**: `backend/tests/test_agent_presence.py` — connect sets `connected_at` and bumps
  `last_seen_at`; disconnect clears it; disconnect still runs when the channel raises;
  `reconcile_all` clears a stale flag left by a simulated hard crash.
- **Success Criteria**:
  - `git diff` shows **zero** changes to `services/agent_connections.py`.
  - `touch_agent_last_seen` has exactly one definition, in `agent_presence.py`.
  - Startup reconciliation is registered on the app lifespan, not called per-request.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Command service — enqueue, busy check, atomic transitions, sweep (D5, D6, D8, D9, D11)
- **Description**: Per `plan.md` step 3. New `services/commands.py` holding **all** DB work for
  commands: `enqueue`, `active_command_for` (D5 — blocks on all four non-terminal statuses, not
  just running/uploading), `apply_status` (D8/D9 — a single atomic conditional
  `UPDATE ... WHERE id AND agent_id AND rank(status) < rank(:next)`, zero rowcount meaning
  "already past this", **never** read-validate-write), and `sweep_stale_commands`. The sweep
  predicate is pure SQL over the D12 projection —
  `status IN (non-terminal) AND agents.connected_at IS NULL AND now() - agents.last_seen_at > :grace`
  — mapping stale `queued → expired` (it never reached the Pi) and stale
  `delivered`/`running`/`uploading` → `failed`, mirroring onto the scan row in the same
  transaction. No HTTP, no lifecycle state in process memory (D9).
- **Dependencies**: Task 2, Task 3, Task 4
- **Target Files**: [`backend/src/api/services/commands.py`,
  `backend/tests/test_commands_service.py`]
- **Tests**: `backend/tests/test_commands_service.py`, unit-level, no HTTP — `active_command_for`
  returns a `queued` and a `delivered` command (D5); `apply_status` applies a forward rank,
  no-ops silently on a duplicate/backward frame, and refuses a command belonging to another
  agent; `sweep_stale_commands` fails stale non-terminal commands, expires stale `queued`, leaves
  a **connected** agent's long-running command untouched (D11), and mirrors the new status onto
  the linked scan.
- **Success Criteria**:
  - `apply_status` issues one `UPDATE` per transition and returns whether a row changed; no
    `SELECT`-then-`UPDATE` guard anywhere in the module.
  - A command whose agent is connected is never swept, regardless of elapsed time.
  - `uv run ruff check src tests` clean.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: Delivery over the open socket (D1, D3)
- **Description**: Per `plan.md` step 4. `async def deliver(...)` in `services/commands.py`: no
  registered socket → set the command `expired` and raise offline **immediately** (D3 — retrying
  a dict lookup is a no-op; an offline Pi stays offline for minutes); socket present → send the
  `AgentCommandFrame`, set `delivered_at`, and only **then** create the stub `scans` row (D1 —
  a rejected trigger leaves no scan row; the stub inherits `org_id` from the agent and takes
  `timestamp = now()`). Retries apply only to a `send_text` that throws on a
  dead-but-still-registered socket.
- **Dependencies**: Task 5
- **Target Files**: [`backend/src/api/services/commands.py`,
  `backend/tests/test_command_delivery.py`]
- **Tests**: `backend/tests/test_command_delivery.py` using an `AsyncMock` socket (pattern in
  `tests/test_ws_fixtures.py`) — successful send writes `delivered_at` **and** a stub scan; a
  throwing `send_text` retries then leaves the command `expired` with **no scan row**; no
  registered socket raises offline without ever awaiting a send.
- **Success Criteria**:
  - No stub scan exists in the DB for any command that ends `expired` (the D1 CHECK holds).
  - The no-socket path performs zero retries and zero awaits on the registry.
  - Frame sent matches `schemas/agent_frames.py:AgentCommandFrame` and carries `scan_mode` and
    `subnet`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: `POST /api/v1/agents/{agent_id}/commands` (D4, D5, D6)
- **Description**: Per `plan.md` step 5. New `schemas/commands.py` (`CreateCommandRequest`,
  `CommandSummary`, `CommandDetail` — shapes taken verbatim from `contracts/openapi/openapi.yaml`)
  and the route in `routers/agents.py` mounted behind `require_admin` (`dependencies/auth.py:54`).
  Order of operations: sweep **this agent's** stale commands (D4 — a dead worker must not
  permanently wedge the product's core action) → busy check → insert → `deliver`. An
  `IntegrityError` from the D6 partial unique index maps to the **same** `409 device_busy` body.
  Unknown or cross-org `agent_id` → **403**, not 404 (the OpenAPI operation defines no 404).
  Success is **201 + `CommandSummary`**.
- **Dependencies**: Task 6
- **Target Files**: [`backend/src/api/schemas/commands.py`, `backend/src/api/routers/agents.py`,
  `backend/tests/test_enqueue_command.py`]
- **Tests**: `backend/tests/test_enqueue_command.py` — 201 happy path; 403 for a viewer token;
  403 for an unknown and for a cross-org `agent_id`; 409 `device_busy` from the read-side check;
  409 `device_busy` from the D6 `IntegrityError` on a simulated concurrent insert; 503
  `device_offline` leaving the row `expired` **and no scan row**; the enqueue-time sweep clears a
  stale command that would otherwise wedge the agent.
- **Success Criteria**:
  - Both 409 paths return a byte-identical error body (`{error: {code: "device_busy", …}}`).
  - Response validates against `CommandSummary` in `contracts/openapi/openapi.yaml`.
  - No route handler contains DB logic that belongs in `services/commands.py`.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 8: `GET /api/v1/commands/{command_id}` (pure read)
- **Description**: Per `plan.md` step 6. New `routers/commands.py`, registered in `main.py`,
  serving `CommandDetail`. **Pure read** — D4 explicitly excludes this endpoint from sweeping, so
  no writes on this path. Cross-org access → 404.
- **Absorbed**: the `contracts/openapi/openapi.yaml` edits from step 9 — `scan_id` out of
  `required` on **both** `CommandDetail` (1993) and `CommandSummary` (1975), and the reworded
  `GET /commands/{command_id}` 200 description ("linked scan_id"). The contract change is what
  this task's null-`scan_id` serialisation test asserts against, via `test_contract_fidelity.py`.
- **Dependencies**: Task 5, Task 7
- **Target Files**: [`backend/src/api/routers/commands.py`, `backend/src/api/main.py`,
  `contracts/openapi/openapi.yaml`, `backend/tests/test_get_command.py`]
- **Tests**: `backend/tests/test_get_command.py` — 200 for own org; 404 for another org's
  command and for an unknown id; `scan_id: null` serialises correctly on an `expired` command;
  the response does **not** mutate command status (re-read shows the same row).
- **Success Criteria**:
  - `uv run pytest tests/test_contract_fidelity.py` passes with `scan_id` optional on both
    schemas.
  - No `INSERT`/`UPDATE`/`commit` in `routers/commands.py`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 9: Wire the WS `status` frame to `apply_status` (D9, D10)
- **Description**: Per `plan.md` step 7 / D10. In `services/agent_ws.py`, replace the discard at
  the `status` branch with a call to `apply_status`. Fast path stays one statement; only a **zero
  rowcount** triggers the scoped existence check — if no command with that id exists *for this
  agent*, reply with an `AgentErrorFrame("unknown command_id")` and keep the socket open, writing
  nothing; otherwise the frame is a duplicate or a late frame and is **silently** ignored. A
  command belonging to another agent is deliberately treated as unknown, so the error frame
  cannot become an oracle for probing other orgs' command ids. Persist the Pi's reported
  `error_code` onto `Command.error_code` (column already exists; DMI-75 builds on it).
- **Dependencies**: Task 1, Task 5
- **Target Files**: [`backend/src/api/services/agent_ws.py`,
  `backend/tests/test_agent_ws_channel.py`]
- **Tests**: `backend/tests/test_agent_ws_channel.py` — a `running` frame on a `queued` command
  applies and backfills `delivered_at` via `COALESCE` (the D9 Q4 race); a duplicate `running`
  frame is silently ignored with no error frame; an unknown `command_id` yields exactly one
  `AgentErrorFrame` and the socket stays open; another agent's `command_id` yields the same
  "unknown" frame and writes nothing; a `failed` frame persists `error_code`.
- **Success Criteria**:
  - Duplicate frames produce no error frame and no DB write.
  - The existence check runs **only** on a zero rowcount, never on the happy path.
  - Linked scan status mirrors the command status after each applied frame.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 10: Worker sweep + records catch-up (D4)
- **Description**: Per `plan.md` steps 8 and 9. `services/worker.py:run_worker_once` also calls
  `sweep_stale_commands` on its existing 5s poll, so the DB converges for **every** reader
  including `GET /scans` (D4 — staleness is written, not derived).
- **Absorbed**: the remaining step-9 doc write-backs, which carry no independently testable
  artifact — `docs/adr/ADR-011-pi-command-channel.md` §4 (the stub scan is created on
  **successful delivery**, `expired` commands carry no `scan_id`, and the enforcing invariant
  `CHECK (scan_id IS NOT NULL OR status = 'expired')` **with the reasoning**, so the next reader
  need not rediscover it) and `docs/roadmap/BACKEND.md` B6 3b (`scan_id` is generated at enqueue
  but **persisted** only on delivery). Per the skill, doc write-backs land on the last
  implementation task. The OpenAPI half of step 9 is in Task 8, where a test gates it.
- **Dependencies**: Task 5, Task 8, Task 9
- **Target Files**: [`backend/src/api/services/worker.py`,
  `docs/adr/ADR-011-pi-command-channel.md`, `docs/roadmap/BACKEND.md`,
  `backend/tests/test_worker_sweep.py`]
- **Tests**: `backend/tests/test_worker_sweep.py` — one `run_worker_once` turns a stale
  `running` and a stale `delivered` command into `failed`, a stale `queued` into `expired`,
  updates the mirrored scan status, and leaves a connected agent's command alone; the sweep does
  not disturb the worker's existing enrichment work.
- **Success Criteria**:
  - `GET /commands/{id}` and `GET /scans` report the same status for a swept command.
  - The `architecture-adr-sync` skill reports **no drift** between ADR-011, `BACKEND.md` and the
    merged code.
  - Full gate green: `uv run ruff check src tests` **and** `uv run pytest` from `backend/`.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 (WS session lifetime) ─┬─────────────────────────────► #9 (WS status wiring)
#3 (migration + config) ──┼─► #4 (presence) ─┐            ▲
#2 (lifecycle ranks) ─────┴──────────────────┴─► #5 ──────┘
                                                 │ (command service)
                                                 ├─► #6 (deliver) ─► #7 (POST) ─► #8 (GET)
                                                 └──────────────────────────────────┘
                                                                                    │
                                    #5, #8, #9 ─────────────────────────────────────┴─► #10
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Per-frame WS session lifetime (D7) | COMPLETED |
| 2 | Monotonic lifecycle ranks (D9, D2) | COMPLETED |
| 3 | Migration — nullable `scan_id`, CHECK, index, `connected_at` | COMPLETED |
| 4 | Connection presence projection (D12) | COMPLETED |
| 5 | Command service — enqueue, busy, transitions, sweep | COMPLETED |
| 6 | Delivery over the open socket (D1, D3) | COMPLETED |
| 7 | `POST /agents/{agent_id}/commands` | COMPLETED |
| 8 | `GET /commands/{command_id}` (pure read) | COMPLETED |
| 9 | Wire the WS `status` frame to `apply_status` | COMPLETED |
| 10 | Worker sweep + records catch-up (D4) | COMPLETED |

All 10 tasks COMPLETED. Two operator-approved amendments landed with Task 10: the D1 CHECK
widened to `scan_id IS NOT NULL OR status IN ('queued', 'expired')` (see `plan.md` D1,
amended 2026-07-31), and `20260715_01_baseline.py`'s `CREATE ROLE dmitri_runtime` made
idempotent — which unskipped 249 DB tests and exposed a real `deliver()` FK-ordering bug.
Final gate: **625 passed, 0 skipped**, `ruff check` clean.
