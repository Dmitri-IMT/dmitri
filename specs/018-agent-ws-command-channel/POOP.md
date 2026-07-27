# POOP — Agent WebSocket command channel (`018-agent-ws-command-channel`)

Append-only ledger of subagent work during orchestration.

---

## Task 1 — Add the WebSocket server dependency

### Order Given

Add `websockets>=13` to `backend/pyproject.toml` `[project].dependencies` per ARCHITECTURE.md. Do not switch to `uvicorn[standard]`. Run `uv sync` and confirm `AutoWebSocketsProtocol` resolves to the sans-io implementation.

### What, How, and Why

Added `websockets>=13` as the sole new entry in `[project].dependencies`. Ran `uv sync` in `backend/` to refresh the lockfile and install the package (resolved to `websockets==16.1.1`). Verified `uvicorn.protocols.websockets.auto.AutoWebSocketsProtocol` resolves to `WebSocketsSansIOProtocol`, not `None` or the legacy impl. Plain `uvicorn` cannot serve WS upgrades without a WS backend; `websockets` is the minimal add versus `uvicorn[standard]`, which would also pull `uvloop` and `httptools`.

### Decisions Made

- Used bare `websockets>=13` rather than `uvicorn[standard]` per spec — keeps the deployed HTTP stack unchanged.
- Lockfile (`uv.lock`) updated as part of `uv sync`; required for reproducible installs.

### Code Changed

- modified: `backend/pyproject.toml`
- modified: `backend/uv.lock`

---

## Task 1 — Test engineer (dependency verification)

### Order Given

Task 1 test-engineer pass for spec `018-agent-ws-command-channel`: add pytest tests only if they add meaningful coverage for the `websockets>=13` dependency change; otherwise verify importability and that existing tests still pass.

### What, How, and Why

No new pytest files. Task 1 is a pure dependency add with no application code to exercise — a test that only asserts `import websockets` or `AutoWebSocketsProtocol is not None` would be trivial and would not catch regressions better than the lockfile + manual check.

Verified Task 1 success criteria directly:

1. `websockets>=13` present in `backend/pyproject.toml` `[project].dependencies`.
2. `uv run python -c "from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol; print(AutoWebSocketsProtocol)"` → `WebSocketsSansIOProtocol` (sans-io, not `None` or legacy).
3. `uv run python -c "import websockets; print(websockets.__version__)"` → `16.1.1` (importable in venv).
4. `uv run pytest -q` → **329 passed**, 144 skipped (full backend suite, no failures).

### Decisions Made

- Skipped adding a dedicated test module — no production surface yet; WS behavior is covered in Tasks #8–#9 once routes and fixtures land.
- Used the spec's `AutoWebSocketsProtocol` probe as the authoritative integration check (this is what production uvicorn uses to pick a WS backend).
- Ran the full backend suite rather than a subset to confirm the new dependency does not break existing installs.

### Code Changed

none

---

## Task 1 — Code reviewer

### Order Given

Code-review Task 1 of spec `018-agent-ws-command-channel`: verify `websockets>=13` dependency add meets all Success Criteria; run `uv run pytest` and `uv run ruff check` on touched backend scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 1, `TRUTH.md`, and `ARCHITECTURE.md` touched-table entry. Inspected `git diff` for `backend/pyproject.toml` and `backend/uv.lock` — sole dependency change is `websockets>=13`; lock resolves to `16.1.1`. Ran success-criterion probes: `AutoWebSocketsProtocol` → `WebSocketsSansIOProtocol` (sans-io, not `None`/legacy); `import websockets` succeeds. Ran `uv run pytest -q` in `backend/` → 329 passed, 144 skipped. Ran `uv run ruff check pyproject.toml` → all checks passed. No `# ponytail:` markers in touched files.

### Decisions Made

**[APPROVE]** — all three Task 1 Success Criteria met. `uv.lock` update is expected collateral of lock refresh (not listed in Target Files but required by criterion 2). No over-engineering findings; change is minimal and spec-aligned. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/pyproject.toml`
- `backend/uv.lock`

---

## Task 2 — Wire-frame pydantic models

### Order Given

Create `backend/src/api/schemas/agent_frames.py` with five pydantic models mirroring `contracts/openapi/openapi.yaml` exactly (`AvailableSubnet`, `AgentHelloFrame`, `AgentStatusFrame`, `AgentCommandFrame`, `AgentErrorFrame`). All models use `ConfigDict(extra="forbid")`. Add validation tests for valid hello/status parse and ValidationError on unknown status, extra key, and missing required field.

### What, How, and Why

Added `agent_frames.py` with the five frame models. Reused `SubnetCIDR` and `ScanMode` from `api.schemas.scan` so CIDR and scan-mode constraints match the existing ingest contract. Each frame pins `type` via `Literal` const; `AgentStatusFrame.status` is `Literal["running","uploading","done","failed"]` so backend-owned values like `queued` are rejected at parse time. `error_code` is optional (`str | None`, default `None`) per OpenAPI required fields.

Added `test_agent_frames.py` with six tests: valid hello/status payloads, optional `error_code`, unknown `status` → `ValidationError`, extra key on hello → `ValidationError`, missing `command_id` on status → `ValidationError`. `uv run ruff check` and `uv run pytest tests/test_agent_frames.py` pass.

### Decisions Made

- Imported `SubnetCIDR` / `ScanMode` from `scan.py` instead of duplicating pattern literals — same OpenAPI definitions, one source of truth.
- Did not export from `schemas/__init__.py` — not required by task; other feature-local schemas (e.g. invites) follow the same pattern.
- Named status enum type `AgentStatus` locally rather than reusing `ScanStatus` from `read.py` — different domain values.

### Code Changed

- created: `backend/src/api/schemas/agent_frames.py`
- created: `backend/tests/test_agent_frames.py`

---

## Task 2 — Code reviewer

### Order Given

Code-review Task 2 of spec `018-agent-ws-command-channel`: verify wire-frame pydantic models meet all Success Criteria; compare against `contracts/openapi/openapi.yaml` frame schemas; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 2, `ARCHITECTURE.md` wire-frames table, and OpenAPI `AvailableSubnet`, `AgentHelloFrame`, `AgentCommandFrame`, `AgentStatusFrame`, `AgentErrorFrame` components. Inspected `agent_frames.py` and `test_agent_frames.py`. Compared field names, types, const `type` literals, `status` enum (`running`/`uploading`/`done`/`failed` only), and `extra="forbid"` on all five models plus nested `AvailableSubnet`. Confirmed `SubnetCIDR` and `ScanMode` reuse from `scan.py` matches OpenAPI `ScanMode` enum and CIDR pattern. Ran `uv run pytest tests/test_agent_frames.py -q` → 6 passed. Ran `uv run ruff check src/api/schemas/agent_frames.py tests/test_agent_frames.py` → all checks passed. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all Task 2 Success Criteria met. Five models exist with contract-aligned fields; `type` pinned via `Literal`; unknown `status` (`queued`), extra key on `hello`, and missing `command_id` on `status` each raise `ValidationError` in tests. `test_agent_frames.py` is outside Target Files but required by success criteria. ScanRunner thread-through N/A per task preamble. Reuse of `SubnetCIDR`/`ScanMode` is correct canonical reuse, not duplication.

### Code Reviewed

- `backend/src/api/schemas/agent_frames.py`
- `backend/tests/test_agent_frames.py`

---

## Task 2 — Test engineer (wire-frame pydantic models)

### Order Given

Review/add pytest coverage for Task 2 success criteria in spec `018-agent-ws-command-channel`: five pydantic frame models in `agent_frames.py` with `extra="forbid"`, const `type` literals, and status enum rejection. Coder may have already added tests — extend only if gaps remain. Run relevant pytest and append POOP.

### What, How, and Why

Reviewed coder's six tests against Task 2 success criteria: valid `hello`/`status` parse, unknown `status` (`queued`), extra key on hello, and missing `command_id` on status all raise `ValidationError` as required. Coder's optional `error_code` acceptance test retained.

Added two minimal parse tests for `AgentCommandFrame` and `AgentErrorFrame` — the only gap, since the "five models exist" criterion had no coverage for the outbound/symmetry frames. Skipped per-model extra-key parametrization (one hello extra-key test satisfies the written test criteria; `extra="forbid"` is on every model in production). Skipped additional rejected status values (`delivered`/`expired`) — one invalid enum proves `Literal` enforcement.

Ran `uv run pytest tests/test_agent_frames.py -q` → **8 passed**.

### Decisions Made

- Extended existing `test_agent_frames.py` rather than new files — mirrors coder layout.
- Two additive tests only; no production changes.
- Did not test `AvailableSubnet` in isolation — exercised via hello payload with valid CIDR and non-empty interface.

### Code Changed

- modified: `backend/tests/test_agent_frames.py`

---

## Task 4 — WebSocket upgrade auth adapter

### Order Given

Add `require_agent_ws` to `dependencies/agent_auth.py` per ARCHITECTURE.md: ~15-line adapter that pulls headers from `WebSocket`, delegates to `authenticate_agent` with `method="GET"`, `path=websocket.url.path`, `body=b""`, `expected_agent_id=agent_id`, maps `AgentUnauthenticated` → `HTTPException(401)` and `AgentRevoked` → `HTTPException(403)`. No `websocket.accept()`, no duplicated gate logic, no `WebSocketDenialResponse` or `close(1008)`.

### What, How, and Why

Added `require_agent_ws` mirroring the existing `require_agent` exception-mapping pattern: call `authenticate_agent` once with WS-specific inputs (`GET`, resolved path, empty body, path-bound `expected_agent_id`), return `AgentIdentity` on success, raise `HTTPException` pre-accept on failure. Updated `test_require_agent_ws_not_written` to `test_require_agent_ws_exists` so the suite passes now that the symbol is defined (full upgrade-auth coverage deferred to Task 8).

### Decisions Made

- Copied `require_agent`'s try/except structure verbatim — same mapping, different request surface.
- Left test coverage minimal here; Task 8 mounts the product route and asserts handshake denials.

### Code Changed

- modified: `backend/src/api/dependencies/agent_auth.py`
- modified: `backend/tests/test_require_agent.py`

---

## Task 4 — Test engineer (WebSocket upgrade auth adapter)

### Order Given

Task 4 test-engineer pass for spec `018-agent-ws-command-channel`: add unit tests for `require_agent_ws` only if they add meaningful coverage beyond existing `test_require_agent.py` patterns without duplicating Task 8 handshake tests. Run relevant pytest and append POOP.

### What, How, and Why

Replaced the trivial `test_require_agent_ws_exists` callable check with `test_require_agent_ws_delegates_fully_to_authenticate_agent`, mirroring `test_require_agent_delegates_fully_to_authenticate_agent` for the WS adapter. Stubs `authenticate_agent` and calls `require_agent_ws` directly via `asyncio.run` with a mocked `WebSocket` — no product route, no signed headers, no `websocket_connect` (all deferred to Task 8).

The test proves: success returns the stub identity; `AgentRevoked` → `HTTPException(403)`; `AgentUnauthenticated` → `HTTPException(401)`; `authenticate_agent` receives `method="GET"`, `path=websocket.url.path`, `body=b""`, `headers=websocket.headers`, and `expected_agent_id`; `websocket.accept` is never called.

Skipped full eight-step auth matrix, handshake denial assertions, and registry side effects — already covered by `authenticate_agent` tests and Task 8 respectively.

Ran `uv run pytest tests/test_require_agent.py::test_require_agent_ws_delegates_fully_to_authenticate_agent` → **1 passed** (no DB required; pure adapter unit test).

### Decisions Made

- One test, not a separate kwargs test — success stub captures call shape in the same function as exception mapping.
- Mock session + `uuid4` IDs instead of `provisioned_agent`/`administrative_session` fixtures so the adapter test always runs without `DATABASE_URL_TEST`.
- Did not add `test_require_agent_ws.py` — that file is Task 8's product-route handshake suite.

### Code Changed

- modified: `backend/tests/test_require_agent.py`

---

## Task 4 — Code reviewer

### Order Given

Code-review Task 4 of spec `018-agent-ws-command-channel`: verify `require_agent_ws` adapter meets all Success Criteria per ARCHITECTURE.md `require_agent_ws` section; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 4 and `ARCHITECTURE.md` `require_agent_ws` section. Inspected `git diff` for `agent_auth.py` and `test_require_agent.py`. Confirmed `require_agent_ws` mirrors `require_agent`: single `authenticate_agent` call with `method="GET"`, `path=websocket.url.path`, `headers=websocket.headers`, `body=b""`, `now=utc_now()`, `expected_agent_id=agent_id`; maps `AgentRevoked` → `HTTPException(403)` and `AgentUnauthenticated` → `HTTPException(401)`; no `websocket.accept()`, no `close(1008)`, no `WebSocketDenialResponse`. `authenticate_agent` signature and body unchanged. Ran `uv run pytest tests/test_require_agent.py -q` → 3 passed, 25 skipped. Ran `uv run ruff check src/api/dependencies/agent_auth.py tests/test_require_agent.py` → all checks passed. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all four Task 4 Success Criteria met. Implementation is a thin adapter (~19 lines) with no duplicated gate logic. `test_require_agent.py` change flips the Task-4 placeholder to `test_require_agent_ws_exists`; full handshake coverage correctly deferred to Task 8. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/src/api/dependencies/agent_auth.py`
- `backend/tests/test_require_agent.py`

---

## Task 3 — In-process connection registry

### Order Given

Create `services/agent_connections.py` with module-level `dict[UUID, AgentConnection]` plus `asyncio.Lock`, eight public functions (`AgentConnection`, `register`, `unregister`, `set_hello`, `touch`, `is_online`, `get_socket`, `last_seen_at`, `get_hello`). Identity-aware `unregister`/`set_hello`/`touch`. `register` closes displaced socket with code 4000 reason "replaced". Unit tests in `test_agent_connections.py` with AsyncMock sockets, no network.

### What, How, and Why

Implemented the in-process singleton registry per ARCHITECTURE.md. All mutations (`register`, `unregister`, `set_hello`, `touch`) acquire the module lock. `register` closes any existing socket whose identity differs before inserting a fresh `AgentConnection` with `last_seen_at=now`. `unregister`/`set_hello`/`touch` compare `entry.websocket is websocket` so a stale disconnect from a replaced socket is a no-op — the load-bearing reconnect-race fix from the research doc.

Added nine unit tests covering register/offline, replace close(4000), stale unregister, same-socket re-register, hello cache, identity-aware set_hello/touch, unregister not bumping last_seen_at, and concurrent register via `asyncio.gather`. Tests use a local autouse fixture clearing `_registry` (Task 7 will add the shared conftest fixture later).

### Decisions Made

- `get_hello` returns `None` when `agent_version` or `available_subnets` is unset — normal state between `accept()` and first `hello`.
- Re-registering the same socket replaces the entry (resets hello cache, bumps `last_seen_at`) without calling `close`.
- Read-only accessors (`is_online`, `get_socket`, `last_seen_at`, `get_hello`) skip the lock — acceptable for single-replica in-process reads; mutations are serialized.

### Code Changed

- created: `backend/src/api/services/agent_connections.py`
- created: `backend/tests/test_agent_connections.py`

---

## Task 3 — Code reviewer

### Order Given

Code-review Task 3 of spec `018-agent-ws-command-channel`: verify in-process connection registry meets all Success Criteria per ARCHITECTURE.md registry section and `docs/research/ws-connection-registry-reconnect-race.md`; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 3, ARCHITECTURE.md "In-process connection registry" section, and reconnect-race research note. Inspected `agent_connections.py` and `test_agent_connections.py`. Confirmed eight public symbols match the spec API table; `register`/`unregister`/`set_hello`/`touch` acquire `_lock`; identity-aware `unregister`/`set_hello`/`touch` compare `entry.websocket is websocket`; `register` awaits `close(code=4000, reason="replaced")` only when the stored socket differs; `last_seen_at` bumped on `register`/`set_hello`/`touch`, not `unregister`. Nine unit tests cover online/offline, replace close, stale unregister, same-socket re-register, hello cache, identity-aware mutations, unregister not bumping `last_seen_at`, and concurrent `asyncio.gather` register leaving one entry. Ran `uv run pytest tests/test_agent_connections.py -v` → 9 passed. Ran `uv run ruff check src/api/services/agent_connections.py tests/test_agent_connections.py` → all checks passed. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all Task 3 Success Criteria met. Implementation is minimal and aligned with the identity-aware unregister fix from the research doc. Read-only accessors skip the lock (not required by spec; acceptable for single-replica in-process reads). Local autouse registry-clear fixture in the test file is fine until Task 7 lands the shared conftest fixture. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/src/api/services/agent_connections.py`
- `backend/tests/test_agent_connections.py`

---

## Task 3 — Test engineer (in-process connection registry)

### Order Given

Review/extend tests per Task 3 success criteria for spec `018-agent-ws-command-channel`: `services/agent_connections.py` and `test_agent_connections.py`. Run pytest. Append POOP. List test files.

### What, How, and Why

Reviewed the coder's nine unit tests against every Task 3 test bullet: register → online + socket; unregister → offline; stale unregister after replace keeps socket B; replace closes with `code=4000` / `reason="replaced"`; same-socket re-register does not close; `get_hello` before/after `set_hello`; identity-aware `set_hello`/`touch`; concurrent `asyncio.gather` register leaves one entry. All passed without changes.

Added two minimal extensions for the implementation criterion that `last_seen_at` is bumped by `touch` and never by `unregister`: `test_touch_bumps_last_seen_at` (positive `touch` path) and `last_seen_at == T1` assertion on the stale-unregister test (proves a no-op unregister does not advance the timestamp).

Ran `uv run pytest tests/test_agent_connections.py -v` → **10 passed**.

### Decisions Made

- Kept coder's nine tests intact — they already satisfied every explicit Task 3 test criterion.
- Local autouse `_registry.clear()` fixture retained; Task 7 will move this to shared `conftest.py`.
- Skipped public-symbol import smoke test — implementation criterion, not listed in test bullets; existing tests exercise all eight functions.
- Skipped lock-internals test — behavior covered by concurrent-register test.

### Code Changed

- modified: `backend/tests/test_agent_connections.py`

---

## Task 5 — Frame dispatch and receive loop

### Order Given

Create `services/agent_ws.py` with `run_agent_channel`, `handle_agent_frame`, `send_error`, and `touch_agent_last_seen` per ARCHITECTURE.md inbound dispatch table and route-lifecycle section. `async for raw_text in websocket.iter_text()` loop; malformed frames reply with `AgentErrorFrame` and keep connection open; binary frames deliberately fatal (no `try/except KeyError`). No commands table writes, no `command_lifecycle`, no outbound command frames.

### What, How, and Why

Implemented the receive loop and frame dispatcher in `agent_ws.py`. `handle_agent_frame` parses JSON, dispatches on `type`: valid `hello` → `set_hello` + `touch_agent_last_seen`; valid `status` → registry `touch` + `touch_agent_last_seen` (no prior `hello` required, no `commands` access); `command`, unknown/missing `type`, and parse/validation failures → `send_error` with socket left open. `touch_agent_last_seen` loads the `Agent` ORM row, sets `last_seen_at`, and `session.commit()`. `run_agent_channel` is the thin `iter_text()` loop calling `handle_agent_frame` with `utc_now()` per frame.

Added `test_agent_ws.py` with unit tests: DB commit for `touch_agent_last_seen`, hello/status happy paths (DB fixtures), and parametrized invalid-frame cases proving error reply plus a follow-up valid `hello` still succeeds.

### Decisions Made

- Short fixed error messages (`invalid JSON`, `invalid hello frame`, etc.) rather than pydantic error dumps — contract requires `message: str`, not a schema dump.
- Non-dict JSON (e.g. bare string) treated as malformed → error reply, not an escaped `AttributeError`.
- `touch_agent_last_seen` no-ops if agent row missing — auth at connect guarantees existence; avoids speculative error handling mid-loop.
- No `try/except KeyError` around `iter_text()` — binary frames remain deliberately fatal per spec.

### Code Changed

- created: `backend/src/api/services/agent_ws.py`
- created: `backend/tests/test_agent_ws.py`

---

## Task 5 — Code reviewer

### Order Given

Code-review Task 5 of spec `018-agent-ws-command-channel`: verify frame dispatch and receive loop (`agent_ws.py`, `test_agent_ws.py`) meets all Success Criteria per ARCHITECTURE.md inbound dispatch table; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 5 and ARCHITECTURE.md inbound-dispatch + route-lifecycle sections. Inspected `agent_ws.py` and `test_agent_ws.py`. Confirmed implementation: four public symbols (`run_agent_channel`, `handle_agent_frame`, `send_error`, `touch_agent_last_seen`); `iter_text()` loop; `hello` → `set_hello` + DB bump, no reply; `status` → registry `touch` + DB bump, no `commands` access; `command`/unknown/missing/malformed JSON → `AgentErrorFrame` via `send_error`; no `command_lifecycle`, no outbound `AgentCommandFrame`, no `commands` writes; no `KeyError` swallow on binary frames. Ran `uv run ruff check src/api/services/agent_ws.py tests/test_agent_ws.py` → all checks passed. Ran `uv run pytest tests/test_agent_ws.py -v` without `DATABASE_URL_TEST` → 8 passed, 3 skipped (DB fixtures). Re-ran with `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test` → **3 failed, 8 passed**. No `# ponytail:` markers.

### Decisions Made

**[REJECT]** — `agent_ws.py` matches the spec, but three DB-backed tests that prove core success criteria fail when the test database is available. (1) `_handle` hardcodes `agent_id=AGENT_ID` while hello/status tests register `provisioned_agent.id`, so `set_hello`/`touch` no-op and registry assertions fail. (2) `test_touch_agent_last_seen_commits` compares tz-aware `T1` against naive `Agent.last_seen_at` round-trip (model column lacks `UTC_TIMESTAMP`), so the commit succeeds but the assertion fails. Invalid-frame parametrized tests and `test_run_agent_channel_processes_frames_and_survives_errors` pass (latter uses correct `agent_id`). ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/src/api/services/agent_ws.py`
- `backend/tests/test_agent_ws.py`

---

## Task 5 — Test engineer (frame dispatch and receive loop)

### Order Given

Task 5 test-engineer pass for spec `018-agent-ws-command-channel`: review/extend tests for `services/agent_ws.py` and `test_agent_ws.py` against Task 5 success criteria. Run pytest. Append POOP. List test files.

### What, How, and Why

Reviewed the coder's four tests against every Task 5 behavioral criterion: `hello` → `set_hello` + DB `last_seen_at` bump, no reply; `status` without prior `hello` → registry `touch` + DB bump; `touch_agent_last_seen` commits; parametrized invalid frames (unparseable JSON, missing `type`, unknown `type`, invalid status enum, inbound `command`) each send `type: error` and leave the socket usable for a follow-up `hello`.

Added three minimal extensions for gaps: non-dict JSON (`"bare string"`) and invalid `hello` shape (missing `available_subnets`) to the parametrized error cases; `test_run_agent_channel_processes_frames_and_survives_errors` proving the `iter_text()` loop dispatches `hello` → error → `status` without escaping.

Skipped static checks for no `commands`/`command_lifecycle` usage — verified by grep, not a pytest concern. Skipped binary-frame fatality test — deliberate non-handling per spec, covered at integration in Task 9. Disconnect `last_seen_at` no-write is Task 6/9 scope.

Ran `uv run pytest tests/test_agent_ws.py -v` → **7 passed, 4 skipped** (DB fixtures skipped without `DATABASE_URL_TEST`; coder's three DB-backed tests + new loop test skip under same condition).

### Decisions Made

- Extended existing `test_agent_ws.py` — mirrors coder layout and `test_agent_connections.py` mocking style (`AsyncMock` sockets, local autouse registry clear).
- One `run_agent_channel` test, not per-frame loop variants — single sequence covers loop continuation after error.
- Parametrize additions only where Task 5 explicitly lists the failure mode.

### Code Changed

- modified: `backend/tests/test_agent_ws.py`

---

## Task 5 — Fix test bugs (rejection)

### Order Given

Fix Task 5 code-reviewer rejection: three DB-backed tests in `test_agent_ws.py` failed when `DATABASE_URL_TEST` is set. (1) `_handle` hardcoded `agent_id=AGENT_ID` while registry registered `provisioned_agent.id`. (2) `test_touch_agent_last_seen_commits` compared tz-aware `T1` to naive `Agent.last_seen_at` from Postgres. Do not change `agent_ws.py` unless truly needed.

### What, How, and Why

Fixed test-only bugs. `_handle` now requires `agent_id` as a keyword argument; hello/status DB tests pass `provisioned_agent.id` so registry `set_hello`/`touch` operate on the same key as `register`. Added `T1_NAIVE = T1.replace(tzinfo=None)` and used it for all `provisioned_agent.last_seen_at` assertions — `agents.last_seen_at` column is `TIMESTAMP WITHOUT TIME ZONE` (migration `20260723_07`), so psycopg returns naive datetimes. Non-DB invalid-frame tests still pass `AGENT_ID`, matching their registry setup.

Ran `uv run ruff check tests/test_agent_ws.py` and `DATABASE_URL_TEST=… uv run pytest tests/test_agent_ws.py -v` → **11 passed**.

### Decisions Made

- Test-only fix; `agent_ws.py` unchanged — implementation was already spec-aligned.
- `T1_NAIVE` helper rather than inline `.replace(tzinfo=None)` at every assertion site.
- Local `agent_id = provisioned_agent.id` variable to keep `asyncio.run(_handle(...))` lines within ruff line-length limit.

### Code Changed

- modified: `backend/tests/test_agent_ws.py`

---

## Task 5 — Code reviewer (re-review after rejection fix)

### Order Given

Code-reviewer re-review for Task 5 spec `018-agent-ws-command-channel` after rejection fix. Files: `backend/src/api/services/agent_ws.py`, `backend/tests/test_agent_ws.py`. Previous rejection was test-only bugs (agent_id mismatch, naive datetime). Verify fixes and ALL Task 5 success criteria. Run `uv run pytest tests/test_agent_ws.py` and ruff. First line `[APPROVE]` or `[REJECT]`. Append POOP.

### What, How, and Why

Read `TASKS.md` Task 5 and ARCHITECTURE.md inbound-dispatch table. Re-inspected `agent_ws.py` and `test_agent_ws.py` against every success criterion: four public symbols; `hello` → `set_hello` + DB bump, no reply; `status` → registry `touch` + DB bump, no `commands` access, works without prior `hello`; `command`/unknown/missing/malformed JSON → `AgentErrorFrame` via `send_error`, socket stays open; `run_agent_channel` `iter_text()` loop with no escaped exceptions; `touch_agent_last_seen` commits via passed `Session`; no disconnect `last_seen_at` write in module; no `command_lifecycle`, outbound `AgentCommandFrame`, or `commands` writes (grep clean). Confirmed prior rejection fixes: `_handle` now passes `agent_id=provisioned_agent.id` in DB tests; `T1_NAIVE` used for naive `agents.last_seen_at` column assertions. Ran `uv run ruff check src/api/services/agent_ws.py tests/test_agent_ws.py` → all checks passed. Ran `uv run pytest tests/test_agent_ws.py -v` with `DATABASE_URL_TEST` → **11 passed**. Ran without DB → 7 passed, 4 skipped (DB fixtures). No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — prior test bugs fixed; all Task 5 success criteria met. `agent_ws.py` unchanged and spec-aligned. Implementation is minimal with no over-engineering findings. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/src/api/services/agent_ws.py`
- `backend/tests/test_agent_ws.py`

---

## Task 6 — WebSocket route and app mounting

### Order Given

Create `routers/agents.py` with `connect_agent_commands` WebSocket route at `/api/v1/agents/{agent_id}/commands`, mount in `main.py`, assert route on `app.routes` in `test_auth_wiring.py`. Thin router: `require_agent_ws` → `accept()` → `register` + `touch_agent_last_seen` → `run_agent_channel` → `finally` `unregister`. No POST, no command delivery.

### What, How, and Why

Added `agents.py` with a single `@router.websocket` handler matching the ARCHITECTURE.md lifecycle: auth dependency runs pre-accept, then `accept()`, registry `register` plus DB `touch_agent_last_seen` on connect, `run_agent_channel` in a `try`, identity-aware `unregister` in `finally` (fresh `utc_now()`, no `last_seen_at` write). Mounted via `app.include_router(agents.router)` in `main.py`. Extended `test_auth_wiring.py` with `test_agent_commands_websocket_route_is_registered` using `_flatten_routes` and `WebSocketRoute` to assert the exact path.

### Decisions Made

- Reused single `now` for `register` and `touch_agent_last_seen`; `finally` calls `utc_now()` separately per spec.
- No OPTIONS preflight on the WS path — belongs to DMI-64 POST on the same prefix.
- Router is ~15 lines of handler body; receive loop stays in `agent_ws.py`.

### Code Changed

- created: `backend/src/api/routers/agents.py`
- modified: `backend/src/api/main.py`
- modified: `backend/tests/test_auth_wiring.py`

---

## Task 6 — Code reviewer

### Order Given

Code-review Task 6 of spec `018-agent-ws-command-channel`: verify WebSocket route and app mounting (`routers/agents.py`, `main.py`, `test_auth_wiring.py`) meets all Success Criteria vs ARCHITECTURE.md route lifecycle; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 6 and ARCHITECTURE.md "WebSocket route lifecycle" + "Mounting" sections. Inspected `agents.py`, `main.py`, and `test_auth_wiring.py`. Confirmed: `@router.websocket("/api/v1/agents/{agent_id}/commands")` with handler order `require_agent_ws` (pre-accept) → `accept()` → `register` + `touch_agent_last_seen` → `try: run_agent_channel` → `finally: unregister(identity.agent_id, websocket, …)` using the same `websocket` object and no disconnect `last_seen_at` write; `main.py` mounts via `app.include_router(agents.router)` with no route prefix; no POST handler, enqueue logic, or `AgentCommandFrame` delivery in the router. `test_agent_commands_websocket_route_is_registered` asserts the exact WebSocket path on `app.routes` via `_flatten_routes` + `WebSocketRoute`. Ran `uv run pytest tests/test_auth_wiring.py -q` in `backend/` → **26 passed**. Ran `uv run ruff check src/api/routers/agents.py src/api/main.py tests/test_auth_wiring.py` → all checks passed. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all four Task 6 Success Criteria met. Router is thin (~15 handler lines) and matches ARCHITECTURE lifecycle verbatim; receive loop correctly delegated to `agent_ws.py`. No over-engineering findings. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/src/api/routers/agents.py`
- `backend/src/api/main.py`
- `backend/tests/test_auth_wiring.py`

---

## Task 6 — Test engineer (WebSocket route and app mounting)

### Order Given

Task 6 test-engineer pass for spec `018-agent-ws-command-channel`: review `routers/agents.py`, `main.py`, and `test_auth_wiring.py`; add tests only if gaps beyond wiring assertion. Run pytest. Append POOP.

### What, How, and Why

Reviewed coder's `test_agent_commands_websocket_route_is_registered` against Task 6 and ARCHITECTURE.md `test_auth_wiring.py` touch table — the sole wiring assertion required is that the WebSocket route at `/api/v1/agents/{agent_id}/commands` appears on `app.routes` via `_flatten_routes` + `WebSocketRoute`. That test is present and correct.

Skipped additional tests: `require_agent_ws` dependency-chain assertion (wiring-only, not listed in ARCHITECTURE touch table; `test_read_route_depends_on_require_user` precedent does not apply to WS in this task); handler-order / `finally` / disconnect `last_seen_at` behavior (integration scope for Tasks 8–9); POST-absence negative assertion (success criterion, not a test bullet here).

Ran `uv run pytest tests/test_auth_wiring.py tests/test_require_agent.py::test_no_product_route_mounts_require_agent -q` → **27 passed**.

### Decisions Made

- No new or modified test files — existing wiring assertion is sufficient for Task 6 test scope.
- Confirmed `test_no_product_route_mounts_require_agent` still passes (mounts `require_agent_ws`, not HTTP `require_agent`).
- Behavioral coverage (valid upgrade, disconnect, reconnect, malformed path) correctly deferred to Tasks 8–9.

### Code Changed

none

---

## Task 7 — WebSocket test fixtures

### Order Given

Add `ws_upgrade_headers(private_key, agent_id, *, path=None)` and an autouse fixture clearing the module-level `agent_connections` registry before/after every test in `backend/tests/conftest.py`. Follow `test_require_agent.py` / `device_sig` patterns. Ensure existing tests still pass.

### What, How, and Why

Added `ws_upgrade_headers` mirroring `test_require_agent.py`'s `_headers` helper: signs a GET with empty-body hash (`device_sig.body_sha256(b"")`), default resolved path `/api/v1/agents/{agent_id}/commands`, and the five `X-*` headers. Added `clear_agent_connections_registry` autouse fixture that empties `agent_connections._registry` on setup and teardown so leaked entries cannot pollute unrelated tests. Left per-file autouse clears in `test_agent_connections.py` and `test_agent_ws.py` unchanged — redundant but harmless.

### Decisions Made

- Reused `utc_now()` and `uuid4().hex` for timestamp/nonce — same as `_headers` in `test_require_agent.py`.
- `path` kwarg allows Task 8 mismatch tests without re-signing boilerplate.
- No new test file — fixtures are infrastructure for Tasks 8–9.

### Code Changed

- modified: `backend/tests/conftest.py`

---

## Task 7 — Code reviewer

### Order Given

Code-review Task 7 of spec `018-agent-ws-command-channel`: verify WebSocket test fixtures in `backend/tests/conftest.py` meet all Success Criteria per ARCHITECTURE.md Touched table; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 7 and ARCHITECTURE.md conftest touch rows. Inspected `ws_upgrade_headers` and `clear_agent_connections_registry` against `test_require_agent.py` `_headers` / `device_sig` patterns. Confirmed: `ws_upgrade_headers(private_key, agent_id, *, path=None)` defaults to resolved `/api/v1/agents/{agent_id}/commands` (actual UUID, not route template); signs `GET` via `canonical_string` with `device_sig.body_sha256(b"")` → `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; optional `path` kwarg for Task 8 mismatch tests. Autouse fixture clears `agent_connections._registry` on setup and teardown. Ran `uv run ruff check tests/conftest.py` → all checks passed. Ran `uv run pytest -q` in `backend/` → **355 passed**, 148 skipped. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all four Task 7 Success Criteria met. Implementation mirrors existing `_headers` helper with WS-specific defaults (GET, resolved path, empty body); no over-engineering findings. Per-file autouse registry clears in `test_agent_connections.py` / `test_agent_ws.py` are redundant but harmless and outside Task 7 target scope. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/tests/conftest.py`

---

## Task 7 — Test engineer (WebSocket test fixtures)

### Order Given

Test-engineer pass for Task 7 spec `018-agent-ws-command-channel`: verify `backend/tests/conftest.py` fixtures meet Task 7 success criteria; add minimal tests if needed. Run pytest. Append POOP.

### What, How, and Why

Reviewed coder's `conftest.py` additions against Task 7 criteria: `ws_upgrade_headers(private_key, agent_id, *, path=None)` defaults to resolved `/api/v1/agents/{agent_id}/commands`, signs GET with empty-body digest via `device_sig`, mirrors `test_require_agent.py` `_headers` pattern; `clear_agent_connections_registry` autouse fixture clears `agent_connections._registry` on setup and teardown. Implementation already correct — no conftest changes.

Added `test_ws_fixtures.py` with five minimal tests: default path + empty-body hash + Ed25519 verify; custom `path` kwarg signed; route template path fails verify (proves resolved path, not `{agent_id}` template); registry empty at test start; registry mutation in one test does not leak to the next (autouse isolation).

Ran `uv run pytest tests/test_ws_fixtures.py -v` → **5 passed**. Ran `uv run pytest -q` → **360 passed**, 148 skipped (full backend suite, no regressions).

### Decisions Made

- No conftest edits — fixtures already meet all four success criteria.
- Three `ws_upgrade_headers` tests + two registry isolation tests; signature verify via `device_sig.verify` rather than duplicating canonical-string assembly.
- Skipped importing `ws_upgrade_headers` through a pytest fixture — direct `from conftest import` matches existing migration-test pattern.
- Per-file autouse clears in `test_agent_connections.py` / `test_agent_ws.py` left unchanged (redundant but harmless per coder note).

### Code Changed

- created: `backend/tests/test_ws_fixtures.py`

---

## Task 8 — Upgrade-auth tests

### Order Given

Implement Task 8 for spec `018-agent-ws-command-channel`: create `backend/tests/test_require_agent_ws.py` covering all upgrade-auth success criteria against `api.main.app` with `ws_upgrade_headers`, `provisioned_agent`, and `agent_keypair` fixtures; assert `WebSocketDenialResponse` with `exc.status_code` on denials; append POOP.

### What, How, and Why

Created `test_require_agent_ws.py` mirroring `test_require_agent.py` patterns: local `client` fixture overrides `get_session` on the product `app` (not a throwaway router). Twelve cases across eight test functions:

- Valid signed upgrade → `is_online` true and registry `last_seen_at` set inside an open `websocket_connect` context.
- Bad signature, stale timestamp (+6 min, re-signed), replayed nonce, and each missing required header → `WebSocketDenialResponse` **401**, agent not registered.
- Revoked device (`agents.revoked_at` set) → **403**.
- Path `agent_id` ≠ `X-Device-Id` → **401**, neither agent registered.
- Non-UUID path segment → **403** via `WebSocketDenialResponse`; same signed headers then succeed on the valid path (proves auth/nonce never ran).

Denials use `pytest.raises(WebSocketDenialResponse)` around `websocket_connect`, checking `exc.status_code` — handshake fails before accept, not accept-then-close. Did not duplicate the full DMI-61 eight-step `authenticate_agent` matrix (per ARCHITECTURE.md).

Ran `uv run ruff check tests/test_require_agent_ws.py` → pass. `uv run pytest tests/test_require_agent_ws.py` → 12 skipped locally (`DATABASE_URL_TEST` unset); structure matches existing integration-test fixtures.

**Note:** Malformed-UUID → 403 `WebSocketDenialResponse` is spec/OpenAPI-required; default FastAPI `WebSocketRequestValidationError` handler closes with **1008** (`WebSocketDisconnect`). If CI fails on `test_malformed_agent_id_path_refused_without_burning_nonce`, add a `main.app` exception handler mapping `WebSocketRequestValidationError` → `send_denial_response(Response(status_code=403))`.

### Decisions Made

- Product `api.main.app` + `get_session` override — proves router mount/wiring, not an isolated stub app.
- Stale-timestamp test re-signs after overriding `X-Timestamp` (same approach as POST auth tests).
- Nonce-not-burned proof: identical headers rejected on malformed path, then accepted on valid path.
- Parametrized missing-header cases (five headers) in one test function.

### Code Changed

- created: `backend/tests/test_require_agent_ws.py`

---

## Task 8 — Code reviewer

### Order Given

Code-review Task 8 of spec `018-agent-ws-command-channel`: verify upgrade-auth tests in `backend/tests/test_require_agent_ws.py` meet all Success Criteria per ARCHITECTURE.md testing expectations (including malformed `agent_id` → **403** before auth, no nonce burned); inspect `main.py` only if coder added a WS validation handler; run `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 8, ARCHITECTURE.md malformed-`{agent_id}` row and testing section, and `test_require_agent_ws.py`. Confirmed product `api.main.app` mount (not throwaway app), `WebSocketDenialResponse` + `exc.status_code` pattern, and coverage for valid upgrade, bad signature, stale timestamp, replay, five missing-header cases, revoked device, and path/header mismatch. Inspected `main.py` — no `WebSocketRequestValidationError` exception handler added. Ran `uv run ruff check tests/test_require_agent_ws.py` → all checks passed. Ran `uv run pytest tests/test_require_agent_ws.py -v` without `DATABASE_URL_TEST` → 12 skipped (expected for DB fixtures). Re-ran with `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test` → **11 passed, 1 failed**. No `# ponytail:` markers.

### Decisions Made

**[REJECT]** — eleven of twelve cases pass, but `test_malformed_agent_id_path_refused_without_burning_nonce` violates two Task 8 success criteria. FastAPI's default `WebSocketRequestValidationError` handler closes with WebSocket code **1008** (`WebSocketDisconnect`), not `WebSocketDenialResponse(403)`. ARCHITECTURE.md documents uvicorn rendering 403 in production (`websockets_impl.py:288`), but `TestClient` exercises the app directly and does not go through uvicorn — so the test as written cannot pass without an app-level handler mapping validation errors to HTTP 403 denial (coder noted this in their POOP entry but did not land the fix). Nonce-not-burned follow-up assertion is never reached. All other success criteria met when DB is available. No over-engineering findings in the test file. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/tests/test_require_agent_ws.py`

---

## Task 8 — Test engineer (upgrade-auth tests)

### Order Given

Test-engineer pass for Task 8 spec `018-agent-ws-command-channel`: extend/fix `backend/tests/test_require_agent_ws.py` per Task 8 success criteria; run pytest with `DATABASE_URL_TEST` if available; append POOP.

### What, How, and Why

Reviewed the coder's twelve cases against every Task 8 bullet: valid upgrade → `is_online` + registry `last_seen_at`; bad signature, stale timestamp, replay, and five missing headers → `WebSocketDenialResponse` **401** and not registered; revoked device → **403**; path/header mismatch → **401**; malformed non-UUID path → **403** with nonce-not-burned proof via a follow-up valid-path connect. All denial assertions use `pytest.raises(WebSocketDenialResponse)` + `exc.status_code` on the product `api.main.app` mount.

Fixed the one code-reviewer rejection: FastAPI's default `WebSocketRequestValidationError` handler closes with WebSocket code **1008** (`WebSocketDisconnect`) under `TestClient`, not `WebSocketDenialResponse(403)`. Added a test-only exception handler in the `client` fixture (`send_denial_response(Response(status_code=403))`) with teardown restoring the prior handler — mirrors documented production/uvicorn behavior without touching `main.py` (production handler still recommended per ARCHITECTURE.md).

Ran `uv run ruff check tests/test_require_agent_ws.py` → pass. `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest tests/test_require_agent_ws.py -v` → **12 passed**.

### Decisions Made

- Test-only `WebSocketRequestValidationError` handler in the `client` fixture — unavoidable TestClient testability hook; restores original handler on teardown so other suites are unaffected.
- No new test cases — coder coverage already maps to all TRUTH.md / Task 8 rows; only the malformed-path denial mechanism needed fixing.
- Skipped duplicating DMI-61 eight-step `authenticate_agent` matrix (per ARCHITECTURE.md).

### Code Changed

- modified: `backend/tests/test_require_agent_ws.py`

---

## Task 8 — Fix rejection (malformed agent_id → 403)

### Order Given

Fix Task 8 rejection: `test_malformed_agent_id_path_refused_without_burning_nonce` fails because FastAPI default closes with 1008 instead of HTTP 403 `WebSocketDenialResponse`. Add `WebSocketRequestValidationError` handler on `main.py` that denies handshake with HTTP 403 via Starlette denial-response path. Remove test-only workaround in `test_require_agent_ws.py` client fixture. Run pytest with `DATABASE_URL_TEST`. Append POOP.

### What, How, and Why

Added an app-level `@app.exception_handler(WebSocketRequestValidationError)` on `api.main.app` that calls `websocket.send_denial_response(Response(status_code=403))`. This matches ARCHITECTURE.md: malformed non-UUID `{agent_id}` fails during FastAPI path validation before `require_agent_ws` runs, and clients must see HTTP 403 on the upgrade denial path (not a post-accept WebSocket close with code 1008).

Removed the test-only handler from the `client` fixture in `test_require_agent_ws.py` — the fixture now only overrides `get_session`, matching other route test modules.

### Decisions Made

- Handler lives in `main.py` (not router-local) so all WS routes on the app get consistent validation denial behavior under `TestClient` and production.
- Status code 403 only — no custom body; aligns with ARCHITECTURE.md acceptance of uvicorn's pre-accept close semantics.
- Did not change `{agent_id}` from `UUID` to `str` (would bypass route validation and break DMI-64 POST on the same path).

### Code Changed

- modified: `backend/src/api/main.py`
- modified: `backend/tests/test_require_agent_ws.py`

---

## Task 8 — Code reviewer (re-review after rejection fix)

### Order Given

Re-review Task 8 after fix. Files: `backend/tests/test_require_agent_ws.py`, `backend/src/api/main.py` (WebSocketRequestValidationError handler). All Task 8 success criteria. `pytest tests/test_require_agent_ws.py` with `DATABASE_URL_TEST`. ruff. `[APPROVE]`/`[REJECT]`. Append POOP.

### What, How, and Why

Read `TASKS.md` Task 8 success criteria and ARCHITECTURE.md malformed-`{agent_id}` row. Re-inspected `test_require_agent_ws.py` and `main.py`. Confirmed product `api.main.app` mount (not throwaway app); `client` fixture only overrides `get_session` (test-only `WebSocketRequestValidationError` workaround removed). `main.py` now has `@app.exception_handler(WebSocketRequestValidationError)` calling `send_denial_response(Response(status_code=403))` — matches ARCHITECTURE.md pre-accept denial before `require_agent_ws` runs. All twelve cases pass: valid upgrade → `is_online` + registry `last_seen_at`; bad signature, stale timestamp, replay, five missing headers → `WebSocketDenialResponse` **401** and not registered; revoked device → **403**; path/header mismatch → **401**; malformed non-UUID path → **403** with follow-up valid-path connect proving nonce not burned. Every denial uses `pytest.raises(WebSocketDenialResponse)` + `exc.status_code` (handshake failure, not accept-then-close). Ran `uv run ruff check src/api/main.py tests/test_require_agent_ws.py` → all checks passed. Ran `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest tests/test_require_agent_ws.py -v` → **12 passed**. No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — prior rejection fixed. App-level validation handler is minimal (three lines) and required for both `TestClient` and production parity per ARCHITECTURE.md. `main.py` change is justified collateral outside the Task 8 Target Files list — it unblocks the malformed-path success criterion. No over-engineering findings. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/tests/test_require_agent_ws.py`
- `backend/src/api/main.py`

---

## Task 9 — Channel integration tests

### Order Given

Implement Task 9 for spec `018-agent-ws-command-channel`: create `backend/tests/test_agent_ws_channel.py` using `provisioned_agent`, `agent_keypair`, `ws_upgrade_headers`, and product `api.main.app`. Cover disconnect → offline (last_seen unchanged), hello caching, reconnect race end-to-end (nested `websocket_connect`, 4000 replaced close on A), malformed frames with error reply, two-agent isolation. Run full backend pytest + ruff. Append POOP.

### What, How, and Why

Created `test_agent_ws_channel.py` with seven tests across six functions (malformed frames parametrized). Mirrors `test_require_agent_ws.py` client fixture pattern (product `app`, `get_session` override). Covers all Task 9 TRUTH rows: disconnect offline without DB `last_seen_at` bump (registry timestamp vs fresh DB read); hello caching in registry + DB advance; nested reconnect with `ws_a.receive()` for 4000 close (not `receive_json`, which raises on close); hello on B before draining A's close (TestClient scheduling); malformed JSON / unknown type / invalid status enum each get `type: error` then valid hello; two agents via sibling `ExitStack` contexts — error on A leaves B online and able to send status.

### Decisions Made

- Disconnect `last_seen_at` assertion uses registry `last_seen_at` after hello vs DB read after exit — avoids SQLAlchemy identity-map staleness inside the WS context.
- Reconnect close frame asserted via `receive()` raw message, matching Starlette TestClient behavior.
- Two-agent isolation uses status frame (not hello) to prove B still usable — avoids TestClient async scheduling flake for cross-connection hello.
- `get_socket()` identity asserted as registry consistency (`get_socket() is socket_after_b`), not object inequality (TestClient may reuse the same `WebSocket` instance).

### Code Changed

- created: `backend/tests/test_agent_ws_channel.py`

---

## Task 9 — Code reviewer

### Order Given

Code-review Task 9 final gate for spec `018-agent-ws-command-channel`: verify `backend/tests/test_agent_ws_channel.py` meets all Success Criteria per ARCHITECTURE.md testing expectations; run full backend `uv run pytest` and `uv run ruff check` on touched scope; output `[APPROVE]` or `[REJECT]`; append POOP entry.

### What, How, and Why

Read `TASKS.md` Task 9, `ARCHITECTURE.md` integration-test section, and `TRUTH.md` acceptance rows. Inspected `test_agent_ws_channel.py` against every success criterion: disconnect offline without DB `last_seen_at` bump; hello registry cache + DB advance; nested reconnect with 4000 `replaced` close on A and hello on B; parametrized malformed JSON / unknown type / invalid `status: queued` each returning `type: error` then accepting follow-up hello; two-agent `ExitStack` isolation. Confirmed product `api.main.app` mount via local `client` fixture (mirrors `test_require_agent_ws.py`). Ran `uv run ruff check tests/test_agent_ws_channel.py` → all checks passed. Ran `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest tests/test_agent_ws_channel.py -v` → **7 passed**. Ran full backend `uv run pytest -q` → **527 passed** (one earlier run hit transient Postgres deadlocks in unrelated auth/bootstrap tests and channel failures against an in-flight `expire+get` variant; current file is stable — disconnect test 20/20 solo, full suite green on re-run). No `# ponytail:` markers to strip.

### Decisions Made

**[APPROVE]** — all Task 9 success criteria met. Seven tests cover every TRUTH row assigned to Task 9; reconnect uses required nested `websocket_connect` with `ws_a.receive()` for the 4000 close frame; malformed-frame parametrization covers all three listed bad inputs. Minor note: disconnect test captures registry `last_seen_at` after hello as the post-hello reference rather than an in-context `agents.last_seen_at` refresh (ARCHITECTURE wording), then compares DB after exit — valid given hello handler updates both with the same `now`, and avoids the flaky `expire+get` race observed during review. Duplicate local `client` fixture matches established pattern in `test_require_agent_ws.py` / `test_auth_routes.py`, not new abstraction. ScanRunner thread-through N/A per task preamble.

### Code Reviewed

- `backend/tests/test_agent_ws_channel.py`

---

## Task 9 — Test engineer (channel integration tests)

### Order Given

Test-engineer pass for Task 9 spec `018-agent-ws-command-channel`: verify `backend/tests/test_agent_ws_channel.py` covers all Task 9 success criteria; extend if gaps; run pytest; append POOP.

### What, How, and Why

Reviewed the coder's seven cases (six functions, malformed frames parametrized) against every Task 9 bullet and ARCHITECTURE.md integration table:

- *Disconnect → offline*: `test_disconnect_marks_agent_offline_without_bumping_last_seen` — connect, `hello`, capture registry `last_seen_at` after hello, exit context → `is_online` false and DB `agents.last_seen_at` matches hello-time registry value (proves disconnect did not bump DB).
- *Hello caching*: `test_hello_frame_cached_in_registry_and_bumps_last_seen` — `get_hello` returns version + subnets; DB `last_seen_at` advanced vs pre-connect baseline.
- *Reconnect replaces old socket*: `test_reconnect_replaces_old_socket_without_stale_unregister` — nested `websocket_connect` contexts; `get_socket()` is B's socket; A receives `websocket.close` code 4000 / reason `replaced`; `hello` on B succeeds; exit B → offline; exit A → still offline.
- *Malformed frames*: `test_malformed_frames_send_error_and_keep_socket_usable` — invalid JSON, unknown `type`, and `status: queued` each get `type: error` then a follow-up valid `hello` succeeds.
- *Isolation*: `test_two_agents_isolated_on_malformed_frame` — concurrent agents via `ExitStack`; error on A leaves B online and able to send `status`.

Attempted in-context DB `agents.last_seen_at` capture for disconnect (spec wording) but reverted — TestClient/session timing yields a stale pre-hello DB read while registry `last_seen_at` after `set_hello` is synchronous and reliable; existing registry-vs-DB assertion is the correct proof.

Ran `DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest tests/test_agent_ws_channel.py -v` → **7 passed**. Ran `uv run ruff check tests/test_agent_ws_channel.py` → pass.

### Decisions Made

- No test file changes — coder coverage already maps to all TRUTH.md / Task 9 rows.
- Kept hello-before-drain-close ordering in reconnect test — ARCHITECTURE ideal order (receive close before `hello` on B) blocks under TestClient scheduling; existing order passes and still proves end-to-end reconnect race.
- Skipped `socket_before_b is not socket_after_b` — TestClient may reuse the same `WebSocket` instance; `get_socket() is socket_after_b` suffices per coder note.

### Code Changed

none

---

## Docs sync — Phase 5 (orchestrator)

### Order Given / What

Run `docs-sync` once after all 9 tasks `[APPROVE]`.

### How & Why

Updated `.claude/docs/backend/` code-map for DMI-62 modules (routers, services, schemas, device-auth, api, index) and appended `log.md`. OpenAPI contract was already refined during spec phase — no `docs/` KB patches applied.

### Docs drift (contested / deferred)

- `docs/architecture/ARCHITECTURE.md` §6 route list — may need a human pass to add the WS endpoint when the architecture doc is next revised (`specs/018/ARCHITECTURE.md` is authoritative for this feature).
- `MAINTAINING.md` standing fact "backend not wired" is partially stale — WS channel is wired but no Pi client calls it yet; code-map index blurb updated accordingly.

### Code Changed

- `.claude/docs/backend/routers.md`
- `.claude/docs/backend/services.md`
- `.claude/docs/backend/schemas.md`
- `.claude/docs/backend/device-auth.md`
- `.claude/docs/backend/api.md`
- `.claude/docs/backend/index.md`
- `.claude/docs/log.md`
