# ARCHITECTURE — Agent WebSocket command channel (DMI-62)

Implements `TRUTH.md`. This is a **BACKEND** feature (`backend/src/api/…`, FastAPI + SQLModel).
It touches no hardware-agent code, no `scanner/`, no `tui/`: there are no Textual screens and no
`ScanRunner` / `ScanProgressScreen` call sites, so the `.claude/CLAUDE.md` ScanRunner thread-through
rule is **N/A here**. Single layer — **no `INTEGRATION.md`**.

**No new infrastructure.** Reuses DMI-61's `authenticate_agent` core, `device_sig`, and `nonces`.
The connection registry is an in-process `dict` on the API process — no Redis, no sticky sessions,
no new Railway service. Nothing here requires new hardware, daemons, or external tooling.

## System context

Epic DMI-47 ("Command channel") eventually lets an operator trigger **Scan now**, deliver a command
over WSS, receive Pi `status` frames, and ingest results. DMI-59 landed the `agents` / `commands`
tables and lifecycle rulebook; DMI-61 landed Ed25519 device auth (`authenticate_agent` +
`require_agent`) but mounted it on **no** product route.

**DMI-62 lands the outbound WSS endpoint, the WS auth adapter, the in-process connection registry,
and inbound frame parsing for `hello` / `status`.** It does **not** enqueue commands, push
`command` frames, or apply `status` transitions to `commands` rows — that is DMI-64+.

Where this sits in the FastAPI stack:

```
Pi daemon (later, DMI-57/65)
  │  outbound WSS GET /api/v1/agents/{agent_id}/commands
  │  + Ed25519 upgrade headers (ADR-005 / ADR-011 §2)
  ▼
routers/agents.py::connect_agent_commands
  │  Depends(require_agent_ws)          ← DMI-62 (before accept)
  │  services/agent_connections.py      ← register / unregister / is_online
  │  services/agent_ws.py               ← receive loop, frame dispatch
  ▼
dependencies/agent_auth.py
  authenticate_agent (DMI-61 core, unchanged order)
  require_agent_ws (DMI-62 adapter — body=b"", no HTTPException)

Later (not DMI-62):
  POST /api/v1/agents/{agent_id}/commands  → enqueue + deliver via registry.get_socket
  GET  /api/v1/agents/{agent_id}           → AgentDetail.online from is_online()
```

Contract source: `contracts/openapi/openapi.yaml` — WS upgrade at
`/api/v1/agents/{agent_id}/commands` (`operationId: connectAgentCommandsWebSocket`) and frame
schemas `AgentHelloFrame`, `AgentCommandFrame`, `AgentStatusFrame`. OpenAPI does not validate
WebSocket frames; pydantic models in `schemas/agent_frames.py` mirror the contract.

ADR-011 §1: single Railway API replica; registry is process-local by design.

## Data model / contracts

### WebSocket upgrade auth envelope (frozen — ADR-011 §2, DMI-61 core)

| Field | Value |
|-------|-------|
| HTTP method | `GET` (upgrade) |
| Resolved path | `/api/v1/agents/<uuid>/commands` — **never** the route template `{agent_id}` |
| Body | empty — `body=b""`; `X-Body-SHA256` must be `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Headers | `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Body-SHA256`, `X-Signature` (same as `AgentSignatureAuth`) |
| Path/header binding | `{agent_id}` path param must equal `X-Device-Id` — enforced via `expected_agent_id` on the core |
| Malformed `{agent_id}` | Not a UUID → FastAPI path validation fails **during dependency solving**, so `require_agent_ws` never runs; `WebSocketRequestValidationError` closes pre-accept, which uvicorn renders as **`403`** (`websockets_impl.py:288`). Do **not** switch the param to `str` and hand-parse to force a `401`; that would discard route validation here and in DMI-64's `POST` on the same path. **Amended during implementation:** rather than lean on the ASGI server to render FastAPI's default `close(1008)` as a `403`, DMI-62 installs an app-level `WebSocketRequestValidationError` handler in `main.py` that denies with an explicit `403` — `openapi.yaml` publishes `403` for a non-UUID `{agent_id}`, and this makes that contract hold on any server advertising the `websocket.http.response` extension instead of varying by ASGI implementation. The pydantic error dump is deliberately dropped, not forwarded as a close *reason*: it is far past RFC 6455's 123-byte limit |
| Failure mapping | `AgentUnauthenticated` → upgrade denied **`401`** (this includes *unknown device* — `authenticate_agent` raises `AgentUnauthenticated`, not `AgentRevoked`, for an unregistered `X-Device-Id`, deliberately giving no enumeration oracle); `AgentRevoked` → **`403`** |

Deny the handshake **before** `websocket.accept()` by raising
`fastapi.HTTPException(status_code=401|403)` **inside the dependency**. On a WebSocket scope
Starlette's `ExceptionMiddleware` handles `HTTPException` like any other scope and
`Response.__call__` rewrites the sends as `websocket.http.response.start` /
`.body` (`starlette/responses.py:154-165`), so the client sees a real HTTP `401`/`403` on the
upgrade. Verified empirically against the installed starlette `1.3.1` / fastapi `0.139.0`:
a dependency raising `HTTPException(401)` on an `@app.websocket` route yields
`WebSocketDenialResponse(401)` at the client. No socket is registered on failure.

Confirmed to survive production, not just `TestClient`: `websockets_sansio_impl` advertises
`scope["extensions"]["websocket.http.response"]` (line 217) and handles
`websocket.http.response.start` / `.body` (lines 412, 461), so the `401`/`403` reaches a real client
over uvicorn. It also honors `ws_ping_interval` / `ws_ping_timeout` (lines 100-101, 278, 305) — the
keepalive the offline-detection rule depends on.

`starlette.testclient.WebSocketDenialResponse` is **client-side only** (`httpx.Response` +
`WebSocketDisconnect`, raised *by* `TestClient`). Do not raise it from server code — tests assert on
it, the adapter never constructs it. The explicit alternative,
`await websocket.send_denial_response(Response(status_code=401))`, requires the
`websocket.http.response` ASGI extension to be present in `scope["extensions"]` and is more code for
the same wire result; use `HTTPException`. **This applies to the auth path only** — the
path-validation denial in `main.py` has no dependency to raise from (validation fails *before*
`require_agent_ws` runs), so it uses `send_denial_response` and does depend on that extension.

**Supersedes DMI-61's `1008` placeholder** (`specs/017-auth-middleware-invite-flow/ARCHITECTURE.md`
line 67): that was an undeferred implementation guess, not a product decision. DMI-61's authoritative
device-auth mapping is `401`/`403` via `AgentUnauthenticated` / `AgentRevoked`; this adapter preserves
that on the WS upgrade handshake. Do **not** `accept()` then `close(1008)`.

### `require_agent_ws` (DMI-62 owns — add to `dependencies/agent_auth.py`)

```python
async def require_agent_ws(
    websocket: WebSocket,
    agent_id: UUID,
    session: Session = Depends(get_session),
) -> AgentIdentity:
```

**Behavior (adapter only — no duplicated gate logic):**

1. Build `headers` from `websocket.headers` (Starlette's case-insensitive mapping is fine).
2. Call `authenticate_agent(session, method="GET", path=websocket.url.path, headers=headers,
   body=b"", now=utc_now(), expected_agent_id=agent_id)`.
3. On success: return `AgentIdentity`.
4. On `AgentRevoked`: `raise HTTPException(status_code=403, detail=str(exc))` (pre-accept).
5. On `AgentUnauthenticated`: `raise HTTPException(status_code=401, detail=str(exc))` (pre-accept).
6. Never call `websocket.accept()` inside the dependency — the route handler accepts after the
   dependency returns.

`require_agent` (HTTP) and `require_agent_ws` (WS) are the only two adapters; both delegate to
`authenticate_agent` and must not reimplement any of the eight gate steps.

### In-process connection registry (`services/agent_connections.py`)

Module-level singleton registry (`dict[UUID, AgentConnection]` + module-level `asyncio.Lock`).
All `register` / `unregister` mutations run under the lock. **Not** persisted; **not** shared across
replicas.

**Reconnect race (load-bearing):** when socket B replaces A, A's route `finally` can run after B is
registered. A blind `unregister(agent_id)` would mark B offline while B is still open. Fix:
**identity-aware unregister** — delete the registry entry only when `entry.websocket is websocket`.
See `docs/research/ws-connection-registry-reconnect-race.md`.

**`AgentConnection` dataclass (in-memory only):**

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | `UUID` | registry key |
| `websocket` | `WebSocket` | live socket reference for later delivery (DMI-64) |
| `connected_at` | `datetime` | UTC, set on register |
| `last_seen_at` | `datetime` | UTC; bumped on register and on every inbound frame — never on unregister |
| `agent_version` | `str \| None` | set from last valid `hello` while connected |
| `available_subnets` | `list[AvailableSubnet] \| None` | set from last valid `hello` while connected |

**Public API (exact names):**

| Function | Signature | Semantics |
|----------|-----------|-----------|
| `register` | `async (agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None` | Under lock: if an entry exists for `agent_id` and `existing.websocket is not websocket`, `await existing.websocket.close(code=4000, reason="replaced")`; insert/replace entry; agent is **online**. That close is **best-effort — wrap it in `try/except Exception`**: the replaced socket's client may already be gone, and uvicorn sets its internal `closed_event` in `asgi_receive` the instant it sees the disconnect, *before* the old handler resumes and reaches its `finally`. A `register` landing in that window would otherwise take a `RuntimeError` from `asgi_send`'s terminal branch, skip the entry insert, and kill the *new* socket while leaving the dead one registered. |
| `unregister` | `async (agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None` | Under lock: remove entry **only if** `entry.websocket is websocket`; else no-op (stale disconnect from a replaced socket). When removal happens, agent is **offline**. |
| `is_online` | `(agent_id: UUID) -> bool` | `agent_id in registry` |
| `get_socket` | `(agent_id: UUID) -> WebSocket \| None` | Returns the live socket or `None` (for DMI-64 delivery) |
| `last_seen_at` | `(agent_id: UUID) -> datetime \| None` | From registry if online; else `None` (callers that need DB `agents.last_seen_at` read the ORM row separately) |
| `set_hello` | `async (agent_id: UUID, websocket: WebSocket, *, agent_version: str, available_subnets: list[AvailableSubnet], now: datetime) -> None` | Under lock, **identity-aware** (no-op unless `entry.websocket is websocket`): store the reported version/subnets on the entry and bump its `last_seen_at`. The only writer for `get_hello`. |
| `touch` | `async (agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None` | Under lock, identity-aware: bump the entry's `last_seen_at`. Called for every valid inbound frame; separate from the `agents.last_seen_at` DB write. |
| `get_hello` | `(agent_id: UUID) -> tuple[str, list[AvailableSubnet]] \| None` | Returns cached `(agent_version, available_subnets)` from the live connection, or `None` if offline / no `hello` yet. **Internal API only** in DMI-62 — no HTTP route exposes it yet (`GET /agents/{id}` is later). **`None` on an online agent is a normal, reachable state** (registered at `accept()`, before any frame; or a Pi that never sends `hello`). DMI-64's trigger-scan and the future agents read API must handle it — `AgentDetail` renders an online agent with no reported subnets; do not assert it away or it becomes a `NoneType` crash on a live path. |

**`Agent` ORM row (`models/command.py`) — touched, not extended:**

- Update `agents.last_seen_at` on **register** and on **every valid inbound frame** (commit via the
  route's `Session`). **Never on unregister** — `AgentDetail.last_seen_at` (`openapi.yaml:1959`) is
  the operator-facing "Last seen", and a disconnect stamp records when *the backend gave up*, not
  when the device last spoke. With keepalive detection that stamp lands ~40s after a dead Pi
  actually stopped, i.e. it would render a lie. `online: false` already carries "and it's gone now".
- Write volume is a `hello` per connect plus a few `status` frames per scan — single-digit writes per
  scan. No throttle. This only stops being true if someone adds a chatty app-level heartbeat, which
  TRUTH rules out.
- **Do not** add DB columns for `agent_version` / `available_subnets` in DMI-62 — ADR-011 treats
  subnets as *reported*, cached on the live connection, not stored as truth. TRUTH "caches against
  the agent record" means the registry entry keyed by `agent_id`, plus `last_seen_at` on the ORM
  row.

`online` is **never** a DB column (ADR-011 §7, DMI-59) — derived only from `is_online()`.

### Wire frames (pydantic — `schemas/agent_frames.py`)

Mirror `contracts/openapi/openapi.yaml` components exactly (`extra="forbid"`).

| Model | `type` const | Direction | Notes |
|-------|--------------|-----------|-------|
| `AvailableSubnet` | — | nested | `interface: str`, `cidr: str` (CIDR pattern per contract) |
| `AgentHelloFrame` | `hello` | Pi → backend | `agent_version: str`, `available_subnets: list[AvailableSubnet]` |
| `AgentStatusFrame` | `status` | Pi → backend | `command_id: UUID`, `status: Literal["running","uploading","done","failed"]`, `error_code: str \| None` |
| `AgentCommandFrame` | `command` | backend → Pi | defined for symmetry / future send helper; **not** parsed from inbound frames in DMI-62 |
| `AgentErrorFrame` | `error` | backend → Pi | **`message: str` only** — graceful parse/validation failures. **Added to `openapi.yaml` by DMI-62** (see Touched); the Pi client is written from the contract, so an undocumented fourth frame type would reach the field as an unknown `type` |

**Inbound dispatch (`services/agent_ws.py`):**

| `type` | Action in DMI-62 |
|--------|------------------|
| `hello` | Validate → `registry` hello cache update → bump `agents.last_seen_at` → **no reply required** |
| `status` | Accepted with or without a prior `hello` on this socket — ordering is a client obligation in the contract, not a backend gate (a Pi reconnecting mid-scan may report status first). Validate frame shape and `status` enum → bump `last_seen_at` → **no `commands` lookup, no row write** (unknown `command_id` is accepted silently in DMI-62; existence check + `AgentErrorFrame` + lifecycle apply is **DMI-64**) |
| `command` | Treat as invalid inbound → `AgentErrorFrame` (Pi must not send commands) |
| missing / unknown / malformed JSON | `AgentErrorFrame` with a short message; **connection stays open** |
| **binary** (non-text) frame | **Out of contract — fatal.** `iter_text()` is `message["text"]` under the hood (`starlette/websockets.py:144`), so a binary frame raises `KeyError`, the loop exits, `finally` unregisters, and the socket closes. Deliberate: the only client is our own Pi daemon (DMI-57/65) and it sends text. Do **not** add a `try/except KeyError` to soften this |

On `ValidationError` or unknown `status` value: send `{"type":"error","message":"..."}` as JSON
text; do not re-raise; do not close the socket; do not affect other agents in the pool.

**Outbound `command` frames** are not sent in DMI-62 (no enqueue/delivery). `AgentCommandFrame`
exists so DMI-64 can call a shared `send_command_frame(websocket, frame)` without redefining the
shape.

### WebSocket route lifecycle (`routers/agents.py`)

```python
@router.websocket("/api/v1/agents/{agent_id}/commands")
async def connect_agent_commands(
    websocket: WebSocket,
    agent_id: UUID,
    identity: AgentIdentity = Depends(require_agent_ws),
    session: Session = Depends(get_session),
) -> None:
```

1. `require_agent_ws` runs (auth only).
2. `await websocket.accept()`.
3. `await register(identity.agent_id, websocket, now=utc_now())`; `touch_agent_last_seen(session, identity.agent_id, now)` — the public helper from `services/agent_ws.py`, not a private router-local copy.
4. `try`: `await run_agent_channel(websocket, session, agent_id=identity.agent_id)`.
5. `finally`: `await unregister(identity.agent_id, websocket, now=utc_now())` — registry only, **no `last_seen_at` write**.

**The receive loop lives in `services/agent_ws.py::run_agent_channel`, not in the router** — the
router is ~6 lines (accept, register, call, `finally` unregister). The loop body is

```python
async for raw_text in websocket.iter_text():
    await handle_agent_frame(session, websocket, agent_id=agent_id, raw_text=raw_text, now=utc_now())
```

`iter_text()` swallows `WebSocketDisconnect` itself (`starlette/websockets.py:144-149`), so a normal
disconnect ends the loop quietly — no `except WebSocketDisconnect` in our code, no exception noise
per disconnect. Its one gap is binary frames (see the dispatch table above); that is accepted, not
patched.

**DB session lifetime (accepted tradeoff).** `Depends(get_session)` is torn down when the *handler*
returns, so a connected agent parks one pooled connection for the whole socket lifetime. With
SQLAlchemy defaults (`pool_size=5`, `max_overflow=10`, `db/session.py:14`) that puts a **ceiling of
~15 concurrent agent sockets** before HTTP requests block on the pool — far above pilot scale (one
Pi per org, ADR-011 single replica), and the reason DMI-62 does **not** introduce a session-factory
dependency. Two guardrails:

- `session.commit()` after every write, so the socket never sits *inside* an open transaction
  (idle-in-transaction is the version that bloats Postgres); never wrap the receive loop in
  `session.begin()`.
- `pool_pre_ping` cannot help a connection that is never re-checked-out. If Postgres drops it while
  idle, the next `last_seen_at` write raises inside the loop, that one socket dies, and the Pi
  reconnects with a fresh connection. Accepted — do not add reconnect/retry logic in DMI-62.

Revisit if agent count approaches the pool ceiling.

**Mounting (`main.py`):** `from api.routers import agents` and `app.include_router(agents.router)`.
No `OPTIONS` handler for the WS path (browsers do not preflight WebSocket upgrades the same way;
the contract's `optionsAgentCommands` applies to the **POST** trigger on the same path prefix and
is DMI-64).

### Surfacing online status

| Consumer | DMI-62 behavior |
|----------|-----------------|
| `GET /api/v1/agents/{agent_id}` (`AgentDetail.online`) | **Not implemented** — route does not exist yet. |
| Internal / tests | `agent_connections.is_online(agent_id)` and `last_seen_at(agent_id)`. |
| DB | `agents.last_seen_at` updated on connect and on inbound frames only — informational, operator-facing. |

DMI-64 (trigger scan) and the future agents read API import `is_online` / `get_socket` from the
registry module — do not duplicate the dict elsewhere.

## New files and naming (mandatory)

Every path is repo-relative. Public symbols are the naming contract.

### Created

| Path | Kind | Public symbols | Note |
|------|------|----------------|------|
| `backend/src/api/services/agent_connections.py` | in-process registry | `AgentConnection` (dataclass); `register`, `unregister`, `set_hello`, `touch`, `is_online`, `get_socket`, `last_seen_at`, `get_hello` | singleton dict; one socket per `agent_id` |
| `backend/src/api/services/agent_ws.py` | WS logic | `run_agent_channel(websocket, session, *, agent_id) -> None`; `handle_agent_frame(session, websocket, *, agent_id, raw_text, now) -> None`; `send_error(websocket, message: str) -> None`; `touch_agent_last_seen(session, agent_id, now) -> None` | owns the `iter_text()` loop; dispatches by `type`; error replies stay on-wire |
| `backend/src/api/schemas/agent_frames.py` | pydantic | `AvailableSubnet`, `AgentHelloFrame`, `AgentStatusFrame`, `AgentCommandFrame`, `AgentErrorFrame` | mirror OpenAPI + internal error frame |
| `backend/src/api/routers/agents.py` | router | `router = APIRouter()`; `connect_agent_commands` (WS only in DMI-62) | path exactly `/api/v1/agents/{agent_id}/commands` |
| `backend/tests/test_agent_connections.py` | test | — | unit tests for registry API |
| `backend/tests/test_require_agent_ws.py` | test | — | adapter auth cases via WS handshake |
| `backend/tests/test_agent_ws_channel.py` | test | — | end-to-end WS connect, hello, status, error replies, disconnect |

### Touched

| Path | Change |
|------|--------|
| `backend/src/api/dependencies/agent_auth.py` | add `async def require_agent_ws(websocket, agent_id, session=Depends(get_session)) -> AgentIdentity` per above |
| `backend/src/api/main.py` | import `agents` router; `app.include_router(agents.router)`; app-level `WebSocketRequestValidationError` handler denying with an explicit `403` (see the malformed-`{agent_id}` row above) — app-wide by necessity, FastAPI exception handlers have no per-route scope, so any future WS route inherits it |
| `contracts/openapi/openapi.yaml` | **Already applied during spec refinement — do not redo, do not extend.** Added `components.schemas.AgentErrorFrame` (required `[type, message]`, `type` const `error`, `additionalProperties: false`); added the `error` row to the frame table in the WS endpoint description; added the **close-code table** (`1012` deploy → redial, `1000` normal → redial, `4000` `replaced` → stay down) and the text/binary rule; noted there that `403` covers a malformed non-UUID `{agent_id}` as well as a revoked device (the shared `responses/Forbidden` component is used by other routes and was left untouched). Implementers mirror this in `schemas/agent_frames.py` — no further contract edits in DMI-62 |
| `backend/tests/conftest.py` | add an **autouse** fixture that clears the module-level registry dict before and after every test — the registry is process-global, so a leaked entry makes an unrelated later test see an agent as online |
| `backend/tests/conftest.py` | add `ws_upgrade_headers(private_key, agent_id, *, path: str \| None = None) -> dict[str, str]` — builds signed GET headers for the resolved WS path (default `/api/v1/agents/{agent_id}/commands`) |
| `backend/tests/test_auth_wiring.py` | assert WS route `/api/v1/agents/{agent_id}/commands` is registered on `app.routes` |
| `backend/pyproject.toml` | add `websockets>=13` to `dependencies` — **required**: the venv has neither `websockets` nor `wsproto`, and plain `uvicorn>=0.23.2` (not `uvicorn[standard]`) cannot serve a WS upgrade at all. `TestClient` speaks ASGI directly and hides this, so the suite would go green while production rejects every upgrade. `>=13` matches what `uvicorn[standard]` itself requires; with it installed, `uvicorn.protocols.websockets.auto` selects the modern `websockets_sansio_impl` (not the deprecated legacy one). Prefer the bare dependency over `uvicorn[standard]`, which would also drag in `uvloop` + `httptools` and change the deployed HTTP stack |

**No migration in DMI-62** — `agents.last_seen_at` already exists (`models/command.py:20`).

**Metadata / registration call sites, checked explicitly:**

- `backend/src/api/models/__init__.py` — no change (`Agent` already imported).
- `backend/alembic/env.py` — no change.
- `backend/tests/conftest.py::_truncate_application_tables` — no change.

**No hardware-agent, `tui/`, or `scanner/` files are touched.**

## Constraints

- **Reuse `authenticate_agent` verbatim.** `require_agent_ws` is ~15 lines: extract headers/path,
  `body=b""`, `expected_agent_id=agent_id`, map errors to pre-accept denial. No second gate.
- **Single replica.** The registry is intentionally non-durable and non-shared. Multi-replica /
  sticky sessions are post-September (TRUTH out of scope).
- **One live socket per agent.** A new connection replaces the old under lock; the old socket is
  closed with **`4000` / `"replaced"`** (RFC 6455 §7.4.2 private-use range). Identity-aware
  `unregister` ensures the old socket's `finally` cannot evict the replacement (see research doc).

  `4000` is not decoration: it is the signal the Pi client (DMI-57/65) must key its reconnect
  behavior on. `1000` means "the backend went away — redial with backoff". **`4000` means "another
  connection of yours already owns the slot — do not redial."** With a single code for both, a
  displaced socket redials, evicts the socket that just replaced it, and the two connections
  ping-pong while the agent flaps online/offline. Every other server-initiated close stays `1000`.

  A third code arrives without us sending it: on graceful shutdown uvicorn closes every live socket
  with **`1012`** (service restart) and injects `websocket.disconnect`
  (`websockets_sansio_impl.py:142-151`), so the route `finally` runs and the registry drains — a
  Railway redeploy is clean, not a hang. All three codes go in the contract's close-code table so the
  Pi can tell "backend is redeploying, come right back" (`1012`) from "stay down" (`4000`).
- **No command delivery or lifecycle writes.** Do not insert `commands` rows, do not call
  `command_lifecycle.next_status`, do not send `AgentCommandFrame` in DMI-62.
- **Error replies must not kill the pool.** Malformed frames affect only the receiving connection's
  reply path; never call a global shutdown; never propagate parse exceptions out of the receive
  loop (catch, reply, continue).
- **Contract frozen means do not reshape existing frames.** Field names and allowed `status` values
  for `AgentHelloFrame` / `AgentCommandFrame` / `AgentStatusFrame` come from `openapi.yaml` and are
  not to be touched. The one permitted contract change in DMI-62 is **adding** `AgentErrorFrame`,
  which DMI-62 introduces and the Pi client must be able to parse.
- **Transport keepalive is load-bearing — do not disable it.** A Pi that loses power or its NAT
  mapping leaves a half-open socket: `receive_text()` never returns, the route `finally` never runs,
  and `is_online()` would report a dead agent as online (the exact predicate DMI-64 uses to choose
  deliver-vs-enqueue). Uvicorn's `websockets` implementation pings every 20s and drops the peer after
  a 20s timeout (`ws_ping_interval=20.0`, `ws_ping_timeout=20.0`, `uvicorn/config.py:203`); the ASGI
  disconnect then fires the normal `finally` → `unregister`. `backend/railway.api.toml:6` overrides
  neither value and **must not** grow `--ws-ping-interval 0` / `--ws-ping-timeout 0`. This is why
  DMI-62 ships **no** app-level heartbeat frame and **no** registry sweeper task.
- **Pre-accept denial only.** `HTTPException(401|403)` raised in the dependency — never
  `accept()` then `websocket.close(1008)`, and never raise `WebSocketDenialResponse` (client-side
  class).
- **Style** — no comments or docstrings in new code, including tests. Match existing FastAPI /
  SQLModel patterns (`utc_now`, `get_session`, pydantic `ConfigDict(extra="forbid")`).

## Testing expectations

Every `TRUTH.md` acceptance row maps to at least one test below. Use `TestClient` from
`starlette.testclient` against the real `api.main.app` with `get_session` overridden (same pattern
as `test_read_endpoints.py` / `test_require_agent.py`). WebSocket tests use
`client.websocket_connect(url, headers=ws_upgrade_headers(...))`.

### `backend/tests/test_require_agent_ws.py` (mirror `test_require_agent.py` WS half)

Mount is the **product route** on `main.app` (not a throwaway app) so wiring is proven.

- *Valid Ed25519 upgrade → online*: signed GET headers, `websocket_connect` succeeds,
  `is_online(agent_id)` is true, registry `last_seen_at` is set.
- *Invalid signature → refused*: bad `X-Signature` → handshake fails with **`401`**; `is_online`
  false.
- *Revoked device → refused*: valid sig, `agents.revoked_at` set → handshake fails with **`403`**.
- *Path/header mismatch*: path `agent_id` ≠ `X-Device-Id` → **`401`** before registry insert.
- *Malformed path `agent_id`*: non-UUID path segment → **`403`** (validation, not auth); assert the
  dependency never ran (e.g. no nonce burned) and nothing was registered.
- *Stale timestamp / replay / missing header*: each → **`401`**, not registered.
- Assert denials as `starlette.testclient.WebSocketDenialResponse` raised by `websocket_connect`,
  checking `exc.status_code`; the handshake must fail, not accept-then-close.

Also call `require_agent_ws` logic indirectly by exercising `authenticate_agent` with
`method="GET"`, `body=b""`, `expected_agent_id=` — already covered in DMI-61; do not duplicate
the full eight-step matrix here unless WS header extraction regresses.

### `backend/tests/test_agent_connections.py` (pure unit, no network)

- `register` then `is_online` true; `get_socket` returns the websocket mock.
- `unregister(agent_id, ws_a)` after register → `is_online` false; `get_socket` None.
- **Stale unregister:** register `ws_a`, register `ws_b` → `unregister(agent_id, ws_a)` → `is_online`
  still true; `get_socket` returns `ws_b`.
- Second `register` for same `agent_id` closes/evicts the first connection (mock `close` awaited with
  `code=4000`, `reason="replaced"`).
- `get_hello` returns `None` before hello; after caching hello data via handler/registry helper,
  returns the tuple.
- `last_seen_at` updates on register and on bump helper.

### `backend/tests/test_agent_ws_channel.py` (integration)

Use `provisioned_agent` + `agent_keypair` fixtures from `conftest.py`.

- *Disconnect → offline*: connect, send a `hello`, capture `agents.last_seen_at`, then exit the
  context → `is_online` false **and `agents.last_seen_at` is unchanged from the `hello`** (asserting
  the disconnect did *not* bump it).
- *Reconnect replaces old socket*: **verified feasible with `TestClient`** — nested
  `websocket_connect` contexts for the same `agent_id` work, and the displaced client observes
  `{"type": "websocket.close", "code": 4000, "reason": "replaced"}` via `a.receive()`. So the test
  is: open A, open B inside A's context, assert `is_online` and `get_socket() is` B's socket, assert
  A received the 4000 close, send `hello` on B successfully, exit B's context → `is_online` false,
  exit A's context → still false (A's stale cleanup is a no-op either way). The research doc's
  fallback ("if `TestClient` cannot hold two overlapping connections, rely on the unit test") does
  **not** apply — the end-to-end proof is required, not optional.
- *Hello frame caching*: after connect, send valid `AgentHelloFrame` JSON → `get_hello(agent_id)`
  returns version + subnets; `agents.last_seen_at` advanced.
- *Malformed status frame*: send invalid JSON → receive `type: error` reply; connection still open
  (send a second valid `hello` or ping text afterward).
- *Unknown status value*: `{"type":"status","command_id":"…","status":"queued"}` → error reply;
  connection stays open.
- *Unknown type*: `{"type":"nope"}` → error reply; connection stays open.
- *Two agents*: two provisioned agents connect concurrently; error on agent A does not disconnect
  agent B (two separate `websocket_connect` contexts).

### `backend/tests/test_auth_wiring.py` (touch)

- WS route `GET /api/v1/agents/{agent_id}/commands` (WebSocket) present on `app.routes`.

### Quality gates

`uv run pytest` and `uv run ruff check` both pass over the touched backend scope
(`TRUTH.md` "Suite green").
