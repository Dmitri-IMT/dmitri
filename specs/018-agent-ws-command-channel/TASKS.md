# Tasks — Agent WebSocket command channel (`018-agent-ws-command-channel`)

9 tasks. **Unblocked now: #1, #2, #4**

Backend-only feature (`backend/src/api/…`). No `hardware-agent/`, `scanner/`, or `tui/` files are
touched, so the CLAUDE.md `ScanRunner` / `ScanProgressScreen` thread-through rule is **N/A** here
(`ARCHITECTURE.md` opening section).

`contracts/openapi/openapi.yaml` was already updated during spec refinement — `AgentErrorFrame`,
the frame-table row, the close-code table, and the `403` note are **already in the contract**. No
task edits it.

---

## Task 1: Add the WebSocket server dependency
- **Description**: Add `websockets>=13` to `backend/pyproject.toml` `dependencies` per the ARCHITECTURE.md Touched table. Without it, `uvicorn` (pinned plain, not `uvicorn[standard]`) cannot serve a WS upgrade at all, and `TestClient` hides that because it speaks ASGI directly — the suite would pass while production rejects every upgrade. Do not switch to `uvicorn[standard]`; it would also pull in `uvloop` + `httptools` and change the deployed HTTP stack.
- **Dependencies**: —
- **Target Files**: [`backend/pyproject.toml`]
- **Success Criteria**:
  - `websockets>=13` appears in `[project].dependencies`; no other dependency changed.
  - `uv sync` (or equivalent lock refresh) resolves and the package is importable in the venv.
  - `python -c "from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol; print(AutoWebSocketsProtocol)"` reports the sans-io implementation, not `None` and not the legacy one.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Wire-frame pydantic models
- **Description**: Create `schemas/agent_frames.py` with the five models from the ARCHITECTURE.md "Wire frames" table, mirroring `contracts/openapi/openapi.yaml` exactly. All models use `ConfigDict(extra="forbid")`. `AgentCommandFrame` is defined for symmetry and is never parsed from inbound traffic in this issue.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/schemas/agent_frames.py`]
- **Success Criteria**:
  - `AvailableSubnet`, `AgentHelloFrame`, `AgentStatusFrame`, `AgentCommandFrame`, `AgentErrorFrame` exist with the exact field names and types in the ARCHITECTURE.md table.
  - Each frame model pins its `type` as a const/`Literal`; `AgentStatusFrame.status` is `Literal["running","uploading","done","failed"]` — `queued`/`delivered`/`expired` are rejected.
  - Unknown keys raise `ValidationError` (`extra="forbid"`) on every model.
  - Tests: valid `hello`/`status` payloads parse; an unknown `status` value, an unknown extra key, and a missing required field each raise `ValidationError`.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3: In-process connection registry
- **Description**: Create `services/agent_connections.py` per the ARCHITECTURE.md "In-process connection registry" section: module-level `dict[UUID, AgentConnection]` plus a module-level `asyncio.Lock`, with the eight public functions from the API table. `unregister`, `set_hello`, and `touch` are **identity-aware** — they no-op unless the stored entry's `websocket is` the passed socket. This is the load-bearing fix for the reconnect race (`docs/research/ws-connection-registry-reconnect-race.md`).
- **Dependencies**: Task 2
- **Target Files**: [`backend/src/api/services/agent_connections.py`, `backend/tests/test_agent_connections.py`]
- **Success Criteria**:
  - Public symbols exactly: `AgentConnection`, `register`, `unregister`, `set_hello`, `touch`, `is_online`, `get_socket`, `last_seen_at`, `get_hello`.
  - `register` on an occupied key awaits `existing.websocket.close(code=4000, reason="replaced")` and replaces the entry; re-registering the *same* socket object does not close it.
  - `unregister(agent_id, stale_socket)` is a no-op when the registry holds a different socket.
  - All mutations run under the module lock; `AgentConnection.last_seen_at` is bumped by `register`, `set_hello`, and `touch` — never by `unregister`.
  - Tests (`test_agent_connections.py`, pure unit, `AsyncMock` sockets, no network): register → `is_online` true and `get_socket` returns the mock; unregister → offline; **stale unregister after replace leaves the agent online on socket B**; replace awaits `close(code=4000, reason="replaced")`; `get_hello` is `None` before `set_hello` and returns the tuple after; concurrent `register` calls under `asyncio.gather` leave exactly one entry.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: WebSocket upgrade auth adapter
- **Description**: Add `require_agent_ws` to `dependencies/agent_auth.py` per the ARCHITECTURE.md `require_agent_ws` section. It is an adapter, ~15 lines: pull headers off the `WebSocket`, call the existing `authenticate_agent` with `method="GET"`, `path=websocket.url.path`, `body=b""`, `expected_agent_id=agent_id`, and map failures to a pre-accept denial. Do not reimplement any gate step and do not call `websocket.accept()` inside the dependency.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/dependencies/agent_auth.py`]
- **Success Criteria**:
  - `async def require_agent_ws(websocket: WebSocket, agent_id: UUID, session: Session = Depends(get_session)) -> AgentIdentity` exists and returns the identity on success.
  - `AgentUnauthenticated` → `HTTPException(401)`; `AgentRevoked` → `HTTPException(403)`; both raised before any `accept()`.
  - No `websocket.close(1008)` path and no `WebSocketDenialResponse` construction in server code.
  - `authenticate_agent` is called once, unmodified; no signature/nonce/skew logic is duplicated in the adapter.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Frame dispatch and receive loop
- **Description**: Create `services/agent_ws.py` with `run_agent_channel`, `handle_agent_frame`, `send_error`, and `touch_agent_last_seen` per the ARCHITECTURE.md "Inbound dispatch" table and route-lifecycle section. The loop is `async for raw_text in websocket.iter_text()`. Malformed input replies with an `AgentErrorFrame` and keeps the connection open; a binary frame is deliberately fatal (no `try/except KeyError`).
- **Dependencies**: Task 2, Task 3
- **Target Files**: [`backend/src/api/services/agent_ws.py`]
- **Success Criteria**:
  - `hello` → validates, calls `agent_connections.set_hello`, bumps `agents.last_seen_at`, sends no reply.
  - `status` → validates shape and enum, calls `touch`, bumps `agents.last_seen_at`; performs **no** `commands` lookup and **no** `commands` row write; is accepted with or without a prior `hello`.
  - `command`, unknown `type`, missing `type`, and unparseable JSON each send `{"type":"error","message":…}` and leave the socket open; no exception escapes the loop.
  - `touch_agent_last_seen` commits via the passed `Session`; nothing writes `agents.last_seen_at` on disconnect.
  - No `command_lifecycle` call, no `AgentCommandFrame` send, no `commands` insert anywhere in the module.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 6: WebSocket route and app mounting
- **Description**: Create `routers/agents.py` with the `connect_agent_commands` WebSocket route at exactly `/api/v1/agents/{agent_id}/commands`, and mount the router in `main.py`, per the ARCHITECTURE.md "WebSocket route lifecycle" and "Mounting" sections. The router stays thin: auth dependency, `accept()`, `register` + `touch_agent_last_seen`, `try` → `run_agent_channel`, `finally` → `unregister`. No `OPTIONS` handler (that belongs to DMI-64's POST).
- **Dependencies**: Task 4, Task 5
- **Target Files**: [`backend/src/api/routers/agents.py`, `backend/src/api/main.py`, `backend/tests/test_auth_wiring.py`]
- **Success Criteria**:
  - Route registered on `app.routes` as a WebSocket route with path exactly `/api/v1/agents/{agent_id}/commands`; asserted in `test_auth_wiring.py`.
  - Handler order matches the spec: `require_agent_ws` → `accept()` → `await register(...)` + `touch_agent_last_seen(...)` → `run_agent_channel(...)` → `finally: await unregister(agent_id, websocket, now=…)`.
  - The `finally` performs **no** `last_seen_at` write, and passes the same `websocket` object that was registered.
  - No POST handler, no enqueue logic, no `AgentCommandFrame` delivery in this task.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: WebSocket test fixtures
- **Description**: Add the two `conftest.py` fixtures from the ARCHITECTURE.md Touched table: `ws_upgrade_headers(...)`, which builds a signed Ed25519 GET envelope for the resolved WS path (empty-body hash, `X-Device-Id`/`X-Timestamp`/`X-Nonce`/`X-Body-SHA256`/`X-Signature`), and an **autouse** fixture that clears the module-level connection registry before and after every test. Follow the existing `device_sig` helper usage in `test_require_agent.py`.
- **Dependencies**: Task 3
- **Target Files**: [`backend/tests/conftest.py`]
- **Success Criteria**:
  - `ws_upgrade_headers(private_key, agent_id, *, path=None)` defaults `path` to `/api/v1/agents/{agent_id}/commands` and signs the **resolved** path, never the `{agent_id}` route template.
  - Its `X-Body-SHA256` is the empty-body digest `e3b0c442…b855`.
  - The autouse fixture empties the registry dict on setup and teardown, so a leaked entry cannot make a later test see an agent as online.
  - Existing tests still pass unchanged.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Upgrade-auth tests
- **Description**: Create `test_require_agent_ws.py` per the ARCHITECTURE.md testing expectations, mounting the **product route** on `api.main.app` (not a throwaway app) so wiring is proven. Denials are asserted as `starlette.testclient.WebSocketDenialResponse` raised by `websocket_connect`, checking `exc.status_code`. Covers the TRUTH.md rows *Valid upgrade → online*, *Invalid signature → refused*, *Path/header mismatch*, and *Malformed agent id in path*.
- **Dependencies**: Task 6, Task 7
- **Target Files**: [`backend/tests/test_require_agent_ws.py`]
- **Success Criteria**:
  - Valid signed upgrade succeeds; `is_online(agent_id)` true; registry `last_seen_at` set.
  - Bad `X-Signature`, stale timestamp, replayed nonce, and a missing required header each fail the handshake with **401**; nothing registered.
  - Revoked device (`agents.revoked_at` set) fails with **403**.
  - Path `agent_id` ≠ `X-Device-Id` fails with **401** before any registry insert.
  - Non-UUID path segment fails with **403** from route validation, the auth dependency never runs (no nonce burned), and nothing is registered.
  - Every failure is a failed handshake, not accept-then-close.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 9: Channel integration tests
- **Description**: Create `test_agent_ws_channel.py` per the ARCHITECTURE.md testing expectations, using the `provisioned_agent` + `agent_keypair` fixtures. Covers the TRUTH.md rows *Disconnect → offline*, *Hello frame caching*, *Malformed status frame*, and *Reconnect replaces old socket* end-to-end. Nested `websocket_connect` contexts for the same agent are confirmed to work — the reconnect-race proof is required, not optional.
- **Dependencies**: Task 6, Task 7
- **Target Files**: [`backend/tests/test_agent_ws_channel.py`]
- **Success Criteria**:
  - *Disconnect → offline*: connect, send `hello`, capture `agents.last_seen_at`, exit the context → `is_online` false **and `agents.last_seen_at` unchanged** (proving the disconnect did not bump it).
  - *Hello caching*: valid `hello` → `get_hello(agent_id)` returns version + subnets; `agents.last_seen_at` advanced.
  - *Reconnect*: open A, open B inside A's context → `is_online` true and `get_socket()` is B's socket; A receives `{"type":"websocket.close","code":4000,"reason":"replaced"}`; B can still send `hello`; exit B → offline; exit A → still offline.
  - *Malformed frames*: invalid JSON, `{"type":"nope"}`, and `{"type":"status",…,"status":"queued"}` each get a `type: error` reply with the socket still usable afterwards (a following valid `hello` succeeds).
  - *Isolation*: two provisioned agents connected concurrently — an error reply to agent A does not disconnect or affect agent B.
  - `uv run pytest` and `uv run ruff check` pass over the touched backend scope.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```
#1 (websockets dep) ─── independent, but land it first: nothing else proves prod WS works

#2 (frames) ──┬──────────────→ #5 (agent_ws) ──┐
              │                                 ├──→ #6 (router + mount) ──┬──→ #8 (auth tests)
              └──→ #3 (registry) ──┬────────────┘                          └──→ #9 (channel tests)
                                   │                                        ↑
#4 (require_agent_ws) ─────────────┼────────────────────────────────────────┘
                                   └──→ #7 (test fixtures) ────────────────→ #8, #9
```

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Add the WebSocket server dependency | COMPLETED |
| 2 | Wire-frame pydantic models | COMPLETED |
| 3 | In-process connection registry | COMPLETED |
| 4 | WebSocket upgrade auth adapter | COMPLETED |
| 5 | Frame dispatch and receive loop | COMPLETED |
| 6 | WebSocket route and app mounting | COMPLETED |
| 7 | WebSocket test fixtures | COMPLETED |
| 8 | Upgrade-auth tests | COMPLETED |
| 9 | Channel integration tests | COMPLETED |

## Acceptance-criteria coverage

| TRUTH.md scenario | Task(s) |
|---|---|
| Valid Ed25519 upgrade → online | #8 |
| Disconnect → offline | #9 |
| Invalid signature → refused | #8 |
| Hello frame caching | #9 |
| Malformed status frame | #9 |
| Malformed agent id in path | #8 |
| Path/header mismatch | #8 |
| Reconnect replaces old socket | #3 (unit), #9 (end-to-end) |
