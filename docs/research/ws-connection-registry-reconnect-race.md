# Research: WebSocket connection registry reconnect races

> **Scope.** Dmitri DMI-62 lands an in-process `dict[UUID, AgentConnection]` at
> `GET /api/v1/agents/{agent_id}/commands` (single Railway replica per ADR-011).
> Business rule: **one live socket per `agent_id`**. A reconnect registers socket B,
> closes socket A, and A's route `finally` must call `unregister` without evicting B.
> This note compares solution patterns against primary sources (RFC 6455, ASGI, Starlette
> source, FastAPI docs, Python asyncio docs, Phoenix/Django Channels/Socket.IO first-party
> docs or source). Fetched 2026-07-27.

---

## TL;DR verdict

**Recommendation for Dmitri: `asyncio.Lock` around registry mutations *plus*
identity-aware unregister keyed on the `WebSocket` instance (or an equivalent
per-connection token captured at register time).** This is the smallest fix that
closes the T1–T3 race, matches FastAPI's own `ConnectionManager` disconnect pattern,
and needs no blocking "wait for old socket to die" in `register`.

- **The crux.** `unregister(agent_id)` in a blind `finally` is wrong: socket A's
  cleanup can run *after* socket B replaced the registry entry. A lock alone does
  not help — each operation is atomic, but A's `finally` still executes later.
- **Minimum fix.** `unregister(agent_id, websocket)` (or `connection_id` token):
  delete only when the stored entry still refers to *this* connection.
- **Register side.** Under the same lock: if an entry exists for `agent_id` and
  `existing.websocket is not websocket`, `await existing.websocket.close(...)` then
  replace the dict entry. Order of close vs assign does not eliminate the race
  without identity-aware unregister (see §4).
- **Not built into Starlette/FastAPI.** Frameworks give per-connection lifecycle
  hooks; "one logical client per key" is application responsibility.
- **Industry pattern.** Phoenix waits for the old channel process to exit before
  finishing a duplicate join; Django Channels keys cleanup on unique `channel_name`;
  Socket.IO treats transport `id` as ephemeral and expects an app-level session id.

---

## The race (Dmitri)

```
T1  Socket A accepted → register(agent_id, A)     registry[agent_id] = A
T2  Socket B accepted → register(agent_id, B)     close(A); registry[agent_id] = B
T3  Socket A finally → unregister(agent_id)       ❌ if blind: deletes B; agent offline
```

**Correct T3:** `unregister(agent_id, A)` is a no-op because registry holds B.

Concurrent route handlers for the same `agent_id` are expected on reconnect (Pi
daemon, network flap, systemd restart). RFC 6455 §7.1.4: the connection is
*closed* when the TCP connection closes; close handshakes can overlap when both
sides initiate close (§7.1.5 NOTE). Starlette maps that to `WebSocketDisconnect`
when `websocket.disconnect` is received or after `close()` — each `WebSocket`
object has its own `client_state` / `application_state` (`DISCONNECTED` is
per-instance). — https://datatracker.ietf.org/doc/html/rfc6455#section-7.1.4 —
https://github.com/encode/starlette/blob/master/starlette/websockets.py

ASGI: a WebSocket scope lives as long as the socket; the app receives
`websocket.disconnect` when the connection ends. — https://asgi.readthedocs.io/en/latest/specs/www.html#websocket

---

## Solution comparison

| Pattern | Fixes T1–T3? | Complexity | Notes |
|--------|----------------|------------|-------|
| **Identity-aware unregister** (`unregister(agent_id, websocket)`) | Yes | Low | Compare stored `websocket` (or `id(websocket)`) before delete. Matches FastAPI `ConnectionManager.disconnect(websocket)`. |
| **Generation / epoch counter** | Yes | Low–med | `register` bumps `gen`; handler captures `my_gen` in `finally: unregister(agent_id, gen=my_gen)`. Equivalent to token. |
| **Connection token / session id** | Yes | Low–med | UUID at register; same as generation but opaque. Socket.IO docs recommend app-level session id separate from transport id. |
| **CAS replace in register only** | No alone | Low | Atomic swap helps *install* B but not stale A `finally`. Must pair with identity check on unregister. |
| **`asyncio.Lock` only** | **No** | Low | Serializes RMW; does not stop A's `finally` after B's `register`. Still required for atomic register. — https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock |
| **Close old before register vs after** | No alone | — | Both orders leave A's handler running; Phoenix explicitly **awaits** old process death instead (§6). |
| **Block register until old `finally` completes** | Yes | High | Couples latency to slow clients; fragile on hung sockets. |
| **Phoenix-style: wait for old channel DOWN** | Yes | Med–high | Proven in production; heavier than identity check for a single dict. |

---

## Findings by pattern

### 1. Identity-aware unregister

**Mechanism.** `unregister(agent_id, websocket, *, now)` acquires the registry
lock, loads the entry, and deletes **only if** `entry.websocket is websocket`
(or `entry.connection_id == connection_id`).

**Pros.**

- Minimal API change from current `ARCHITECTURE.md` (`unregister` gains one
  positional/keyword arg).
- Directly mirrors FastAPI's official multi-client example: disconnect removes
  the specific `WebSocket` from `active_connections`, not "whatever is newest
  for this user". — https://fastapi.tiangolo.com/advanced/websockets/ (`manager.disconnect(websocket)` in `except WebSocketDisconnect`)
- No extra fields on `AgentConnection` if the `WebSocket` reference is enough.
- Stale `finally` becomes idempotent no-op — satisfies TRUTH "Disconnect → offline"
  for the *current* connection only.

**Cons.**

- Route `finally` must pass the same `websocket` object accepted at the top of
  the handler (trivial).
- Object identity is process-local (fine for ADR-011 single replica).
- If `get_socket` callers cache the `WebSocket` across reconnect, they can hold a
  stale reference — already true; document that delivery must call `get_socket`
  per send (DMI-64).

### 2. Generation / epoch counter

**Mechanism.** `AgentConnection` stores `generation: int`. `register` increments a
per-`agent_id` or global counter under lock. Handler does
`gen = register(...)` or reads it from the returned entry; `finally:
unregister(agent_id, generation=gen)`.

**Pros.**

- Same correctness as websocket identity; useful if cleanup runs where the
  `WebSocket` is no longer in scope.
- Integers compare cheaply; easy to log ("unregister stale gen 4, current 5").

**Cons.**

- Extra field and parameter plumbing.
- Strictly more moving parts than websocket identity for no gain in Dmitri's
  single-process dict.

**Equivalence.** Generation counter and connection token are the same pattern:
opaque id assigned at register, checked at unregister.

### 3. Connection token / session id

**Mechanism.** `register` assigns `connection_id = uuid4()`; store on
`AgentConnection`; pass to `unregister(agent_id, connection_id=...)`.

Socket.IO distinguishes the public transport `id` (ephemeral, new on every
reconnect) from a **session id** used for state recovery — app must supply
stable identity via auth, not transport id. — https://socket.io/docs/v4/troubleshooting-connection-issues/ — https://socket.io/docs/v4/connection-state-recovery

**Pros.**

- Explicit in logs and tests; no reliance on `WebSocket` object identity.
- Aligns with "app session id, not transport id" guidance from Socket.IO.

**Cons.**

- More surface area than `websocket` identity for an in-process registry.
- Dmitri already has `agent_id` as logical identity; token is a second id.

### 4. Compare-and-swap / atomic replace in `register`

**Mechanism.** Under lock:

```text
existing = registry.get(agent_id)
if existing and existing.websocket is not new_ws:
    await existing.websocket.close(code=4000)   # or 1000
registry[agent_id] = AgentConnection(...)
```

**Pros.**

- Required for "one socket per agent" regardless of unregister strategy.
- Prevents two entries for the same key.

**Cons.**

- **Does not solve T3** without identity-aware unregister. After T2, A's
  `finally` can still `del registry[agent_id]` if unregister is blind.

**Close before vs after assign.** Neither ordering removes the race:

| Order | What happens |
|-------|----------------|
| Close A, then register B | A's handler may still be in `receive` or `finally` after B is registered. |
| Register B, then close A | Same — A's `finally` runs after B owns the slot. |

Phoenix avoids relying on "old cleanup won't touch new" by **synchronously**
tearing down the old channel process and waiting for `{:DOWN, ...}` before
completing the duplicate join — https://github.com/phoenixframework/phoenix/blob/master/lib/phoenix/socket.ex (`shutdown_duplicate_channel/1`). Dmitri does not need that weight if unregister is identity-aware.

### 5. `asyncio.Lock` around registry operations

**Mechanism.** One module-level `asyncio.Lock`; `async with _lock:` around
`register` / `unregister` / `get_socket` reads that mutate or depend on consistency.

Python docs: lock guarantees one coroutine at a time in the critical section;
asyncio locks are **not thread-safe** (fine — registry is asyncio-only). —
https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock

**Pros.**

- Makes register's "close old + replace" atomic.
- Prevents lost updates if two registers race (unlikely for one Pi, possible in
  tests).

**Cons.**

- **Necessary but insufficient** for T1–T3. Illustration:

```text
# Lock does NOT prevent this interleaving:
B: register (lock) → registry = B → release
A: finally unregister(agent_id) (lock) → blind delete → release   # kills B
```

**Recommendation.** Keep the lock; pair with identity-aware unregister.

### 6. Starlette / FastAPI built-in patterns

**No first-party "connection registry per logical id".**

- Starlette documents accept / send / receive / close / `WebSocketDisconnect`; no
  deduplication. — https://www.starlette.io/websockets/
- FastAPI WebSocket guide: `ConnectionManager` holds `list[WebSocket]`; disconnect
  removes **that** websocket; broadcast iterates the list. No `agent_id` key; no
  reconnect replacement. — https://fastapi.tiangolo.com/advanced/websockets/
- FastAPI notes in-memory manager "only works with a single process" — same as
  ADR-011. Suggests `encode/broadcaster` for multi-process pub/sub, not connection
  dedup. — https://fastapi.tiangolo.com/advanced/websockets/
- `WebSocketDenialResponse` / pre-accept auth (DMI-62) is unrelated to registry
  races — failed upgrades never register.

**Implication.** DMI-62 registry is custom; reconnect safety is explicit design.

### 7. How other systems handle it (brief)

| System | Mechanism | Reconnect / duplicate behavior | Source |
|--------|-----------|--------------------------------|--------|
| **Phoenix Channels** | Transport holds map of topic → channel pid. Duplicate `phx_join` on same topic: log, `Process.exit(old, {:shutdown, :duplicate_join})`, **wait** for monitor DOWN, then join new channel. | Old channel `terminate/2` runs before new join completes; stale cleanup scoped to old pid. | https://github.com/phoenixframework/phoenix/blob/master/lib/phoenix/socket.ex — https://hexdocs.pm/phoenix/js/index.html (duplicate join subscriptions) |
| **Django Channels** | Each consumer gets unique `self.channel_name`; `group_add` on connect, `group_discard(self.channel_name)` on disconnect. | Replacing "one user per room" is app-level; cleanup keys on **channel_name**, not user id alone. Docs warn disconnect may not run on unclean failure. | https://channels.readthedocs.io/en/stable/topics/channel_layers.html — `channels/generic/websocket.py` `websocket_disconnect` |
| **Socket.IO** | Ephemeral `socket.id` per connection; optional connection-state recovery via private session id + offset. | Docs: do not use transport `id` as app identity; use auth/session id. Recovery restores rooms/data within `maxDisconnectionDuration`. | https://socket.io/docs/v4/server-socket-instance/ — https://socket.io/docs/v4/connection-state-recovery |

**Dmitri mapping.** Closest fit: **Django's channel_name identity** ≈
`unregister(agent_id, websocket)`. Phoenix's "wait for death" is the alternative
if you refuse to pass identity into unregister (not recommended here).

---

## Recommended design for `specs/018-agent-ws-command-channel`

### Registry API (adjust `ARCHITECTURE.md`)

```python
async def register(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None: ...
async def unregister(agent_id: UUID, websocket: WebSocket, *, now: datetime) -> None: ...
```

**`register` (under `_lock`):**

1. If `agent_id` in registry and `existing.websocket is not websocket`:
   `await existing.websocket.close(code=4000, reason="replaced")`. **Decided
   2026-07-27:** `4000`, not `1000` — the Pi keys its reconnect behavior on it
   (`1000` = redial with backoff, `4000` = another connection of yours owns the
   slot, stay down), which stops two sockets from ping-ponging each other out of
   the registry. RFC 6455 §7.4.2 reserves 4000–4999 for private use.
2. Insert/replace `AgentConnection(agent_id, websocket, connected_at=now, ...)`.
3. Bump `last_seen_at` on the connection object.

**`unregister` (under `_lock`):**

1. `entry = registry.get(agent_id)`.
2. If `entry is None` or `entry.websocket is not websocket`: return (stale
   cleanup).
3. Else: `del registry[agent_id]`.

**Route handler (`connect_agent_commands`):**

```python
try:
    ...
finally:
    await unregister(identity.agent_id, websocket, now=utc_now())
```

Do **not** use bare `unregister(agent_id)`.

**Optional:** store `connection_id: UUID` on `AgentConnection` for logging and
tests; unregister can check either websocket or token (pick one; don't require both).

**Out of scope (unchanged):** multi-replica registry, Redis presence, sticky
sessions (TRUTH v1).

### Close code note

Starlette `close()` sends `websocket.close` ASGI message; after accept, server
closes the socket (ASGI §websocket.close). — https://asgi.readthedocs.io/en/latest/specs/www.html#websocket —
https://github.com/encode/starlette/blob/master/starlette/websockets.py  
When the replaced socket's `receive` returns disconnect, its `finally` runs —
identity-aware unregister makes that safe.

---

## Testing strategies (pytest / TestClient)

### 1. Pure unit tests (`test_agent_connections.py`) — **primary**

No network; deterministic; exercises T1–T3 directly.

```python
# Pseudocode
ws_a, ws_b = AsyncMock(), AsyncMock()
await register(agent_id, ws_a, now=t0)
await register(agent_id, ws_b, now=t1)
ws_a.close.assert_awaited_once()

assert is_online(agent_id)
assert get_socket(agent_id) is ws_b

await unregister(agent_id, ws_a, now=t2)   # stale
assert is_online(agent_id)
assert get_socket(agent_id) is ws_b

await unregister(agent_id, ws_b, now=t3)
assert not is_online(agent_id)
```

Add: second `register` does not call `close` on the same socket if re-registering
the same `websocket` (edge case). Add: concurrent `register` for two mocks under
`asyncio.gather` with lock — final state has exactly one entry.

### 2. Ordering harness with `asyncio.Event`

For integration-style registry tests without flakiness:

- Mock `WebSocket` whose `receive_text` blocks on `Event("a_receive")`.
- Register A; start handler task; register B (closes A); assert online B;
  release A's disconnect; await A task; assert still online B.

This simulates delayed `finally` without `time.sleep`.

### 3. `TestClient` WebSocket tests (`test_agent_ws_channel.py`)

Starlette `TestClient.websocket_connect` runs the app in a portal/thread;
`websocket.disconnect` is injected on context exit. — https://github.com/encode/starlette/blob/master/starlette/testclient.py

**Valuable integration cases:**

- Connect agent → `is_online` → exit context → `not is_online`.
- Connect twice sequentially (second connection after first closed): second
  succeeds; registry consistent.
- **Reconnect race (integration):** open `ws1`, open `ws2` for same `agent_id`
  without closing `ws1` first → `is_online`; close `ws2` → offline; close `ws1`
  context → still offline. *This is the end-to-end proof.*
  **Verified 2026-07-27 against starlette 1.3.1:** nested `websocket_connect`
  contexts to the same route do work, and the displaced client sees
  `{"type": "websocket.close", "code": 4000, "reason": "replaced"}` from
  `ws1.receive()`. The earlier "if `TestClient` cannot hold two overlapping
  connections, fall back to the unit test" hedge is withdrawn.

**Avoid:** bare `time.sleep` for synchronization in CI.

### 4. Generation/token variant tests

If implementation uses `connection_id` instead of `websocket` in unregister,
assert `unregister(agent_id, connection_id=stale_id)` is no-op after replace.

### 5. Property / hammer (optional)

`hypothesis` or loop: N random register/unregister sequences with tracked
"current" socket; after each sequence, registry matches the last registered
socket still open.

---

## Implications for DMI-62 acceptance criteria

| TRUTH scenario | Race-safety requirement |
|----------------|-------------------------|
| Valid upgrade → online | `register` sets entry; `is_online` true. |
| Disconnect → offline | Only the **current** socket's `unregister` clears entry; stale `unregister` must not mark offline while B lives. |
| Two agents concurrent | Isolated keys; unchanged. |

Add an explicit acceptance row (or test comment): **"Reconnect replaces socket;
old disconnect does not evict new socket."**

---

## Sources

- RFC 6455 — WebSocket close / connection closed (§7.1.2–7.1.5): https://datatracker.ietf.org/doc/html/rfc6455#section-7.1.4
- ASGI WebSocket spec (scope lifetime, `websocket.disconnect`, `websocket.close`): https://asgi.readthedocs.io/en/latest/specs/www.html#websocket
- Starlette `WebSocket` state machine (per-instance `DISCONNECTED`): https://github.com/encode/starlette/blob/master/starlette/websockets.py
- Starlette `TestClient` / `WebSocketTestSession`: https://github.com/encode/starlette/blob/master/starlette/testclient.py
- Starlette WebSocket docs: https://www.starlette.io/websockets/
- FastAPI WebSocket guide (`ConnectionManager`, disconnect by instance, single process): https://fastapi.tiangolo.com/advanced/websockets/
- Python asyncio `Lock`: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
- Phoenix duplicate channel join (close old, wait for DOWN): https://github.com/phoenixframework/phoenix/blob/master/lib/phoenix/socket.ex
- Phoenix.js duplicate join behavior: https://hexdocs.pm/phoenix/js/index.html
- Django Channels — unique `channel_name`, disconnect cleanup: https://channels.readthedocs.io/en/stable/topics/channel_layers.html
- Django Channels `websocket_disconnect` → `group_discard`: https://github.com/django/channels/blob/master/channels/generic/websocket.py
- Socket.IO — ephemeral `id`, use app session id: https://socket.io/docs/v4/troubleshooting-connection-issues/
- Socket.IO connection state recovery (session id vs public id): https://socket.io/docs/v4/connection-state-recovery
- Dmitri `specs/018-agent-ws-command-channel/ARCHITECTURE.md` (registry API, route `finally`)
- Dmitri ADR-011 (single API replica, in-process registry)
