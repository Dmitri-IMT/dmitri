# DMI-64 — Command enqueue + delivery + status transitions

**Branch:** `feature/dmi-64-command-enqueue-delivery-status-transitions` (from `main` @ `a7444cb`)
**Issue:** [DMI-64](https://linear.app/dmitri-imt/issue/DMI-64/command-enqueue-delivery-status-transitions)
**Layer:** `backend/`

Lightweight plan — not the full Peirce pipeline. No ARCHITECTURE.md / TASKS.md for this slice.

---

## What this builds

The write + push half of "Scan now": an admin triggers a scan, the backend records it,
pushes it down the already-open WebSocket to the Pi, and walks the command through its
lifecycle as the Pi reports back.

The read half (`GET /agents`, `available_subnets`, `target_subnet`) is **DMI-78** and must
not be built here.

## What already exists (DMI-59 + DMI-62, both merged)

| Piece | Location | State |
|---|---|---|
| `Command` / `Agent` models | `models/command.py` | `scan_mode`, `subnet`, `delivered_at` present |
| Lifecycle state machine (pure) | `services/command_lifecycle.py` | missing one edge — see D2 |
| WS connection registry | `services/agent_connections.py` | `is_online`, `get_socket`, `set_hello` |
| WS frame handling | `services/agent_ws.py` | `status` frames validate then **get discarded** |
| Frame schemas | `schemas/agent_frames.py` | `AgentCommandFrame`, `AgentStatusFrame`, `AgentErrorFrame` |
| Ed25519 agent auth | `dependencies/agent_auth.py` | `require_agent`, `require_agent_ws` |
| Admin JWT guard | `dependencies/auth.py:54` | `require_admin` |
| Fake-agent test fixtures | `tests/conftest.py` | `ws_upgrade_headers`, `agent_keypair`, `provisioned_agent`, registry reset |

**`contracts/openapi/openapi.yaml` already specifies both endpoints** — `POST /api/v1/agents/{agent_id}/commands`
(line 429), `GET /api/v1/commands/{command_id}` (line 564), `CommandDetail` (1990), and the
`device_busy` / `device_offline` error bodies (1253–1296). The spec is the source of truth for
request/response shapes. Do not invent them.

Error envelope is `{error: {code, message}}` via `ErrorResponse`; the handler at `main.py:48`
already produces it from `HTTPException`.

---

## Decisions

### D1 — A rejected trigger leaves no scan row ✅ decided 2026-07-31

When delivery fails, `POST /commands` returns `503 device_offline` and the command is set
`expired` synchronously (ADR-011 §4). **The stub `scans` row is created only after delivery
succeeds.** An `expired` command has `scan_id = NULL`.

**Why.** `command_lifecycle.py` maps `expired → scan status "failed"`, and `list_scans`
(`services/read.py:179-181`) filters only by `org_id` and optional explicit status. So creating
the stub unconditionally means every offline click permanently adds a hosts-less failed scan to
the operator's primary screen. The command row is the audit trail and survives; the scan row
should mean *a Pi accepted work*.

**The rule that keeps this safe:** nothing ever infers "it failed" from a missing scan row.
`command.status` is the signal — `expired` is explicit and written in the same transaction.
The null `scan_id` is a *consequence* of `expired`, never a *marker* of it.

Enforced in the DB rather than by convention, in the same migration:

```sql
CHECK (scan_id IS NOT NULL OR status IN ('queued', 'expired'))
```

**Amended 2026-07-31, during Task 10.** As first written this read `status = 'expired'`, which
made the pre-delivery row unrepresentable: `enqueue()` inserts `queued` with a null `scan_id`,
and D9's crash table requires exactly that row ("after insert, before send → row says `queued`").
The two decisions contradicted each other. `queued` joins `expired` as the second and last
pre-delivery status; both mean *no Pi has accepted work yet*.

The invariant this enforces is unchanged: a `scan` row exists **iff** a Pi accepted the command,
so no future code can drift into inferring failure from the null. `command.status` remains the
only signal.

**Known cost:** enqueue becomes non-atomic in a new way — write command, `await` the socket
send, then write the scan. A crash in between leaves a `delivered` command with no scan. That
is recoverable: the stale sweeper (D4) marks it `failed`.

### D2 — C12 is `failed`; the state machine is missing the edge ✅ decided 2026-07-31

A Pi that took the command and went dark is `failed`. `expired` means only "never reached the
Pi", set synchronously with the `503`. The dividing line is `delivered_at`.

`_LEGAL_EDGES` currently has `delivered: {running, expired}` — so a Pi that takes a command and
dies before reporting `running` has **no legal terminal state**. Add `delivered → failed`.

BACKEND.md B6 3a/3e already document this correctly (resolved 2026-07-13). No doc change needed;
DMI-78's C12 bullet was stale and has been closed out.

### D3 — Delivery fails fast ✅ decided 2026-07-31

`is_online()` is a dict lookup, so "retry twice" against it is a no-op. No socket registered →
`503` immediately. Retries apply only to a `send_text` that throws on a dead-but-still-registered
socket. An offline Pi stays offline for minutes; making the operator wait before "Pi seems to be
offline" reads as broken.

### D4 — Stale commands are swept by the worker, with a defensive sweep at enqueue ✅ revised 2026-07-31

> Supersedes the original "evaluate lazily on read" decision. That was justified by "no scheduler,
> no worker changes" — which was **wrong**: `services/worker.py:run_worker_loop` already exists and
> polls every 5s as its own Railway service. A sweep is a few lines in `run_worker_once`.

Staleness must be **written, not derived**. `_SCAN_STATUS_BY_COMMAND_STATUS` mirrors command status
onto the `scans` row, so a command going `failed` must flip its scan too. Deriving staleness at
serialisation time would make `GET /commands/{id}` say `failed` while `GET /scans` (DMI-82, shipped)
still says `processing` — two endpoints disagreeing about one scan.

| Writer | Why |
|---|---|
| **Worker**, on its existing poll | the DB converges within ~5s for *every* reader, including `GET /scans` |
| **Enqueue**, for the target agent, before the busy check | a dead worker must not permanently wedge the product's core action — D6's unique index would otherwise block that agent forever |
| ~~`GET /commands/{id}`~~ | **stays a pure read** |

Two callers of one `sweep_stale_commands()` function. Each covers a distinct failure: the worker
covers timeliness for all readers, the enqueue call covers worker death.

Config: `command_running_timeout_seconds` (alias `COMMAND_RUNNING_TIMEOUT_SECONDS`), following the
existing `Field(default=..., alias=...)` style in `core/config.py`.

### D5 — Busy check blocks on any non-terminal status ✅ decided 2026-07-31

BACKEND.md 3d says "running or uploading", but a command stuck in `queued`/`delivered` would then
let a second job onto the Pi. Block on all four non-terminal states.

### D6 — "One scan at a time" is enforced by the database ✅ decided 2026-07-31

`active_command_for()` reads, then `enqueue()` writes — a double-clicked "Scan now" button
(DMI-89) produces two near-simultaneous POSTs that both pass the check. Two non-terminal
commands then wedge the agent: the Pi reports against only one `command_id`, and the other
blocks every future trigger until the sweeper clears it.

```sql
CREATE UNIQUE INDEX uq_commands_active_agent ON commands (agent_id)
  WHERE status IN ('queued', 'delivered', 'running', 'uploading');
```

The losing insert raises `IntegrityError`, which the route translates to the same
`409 device_busy`. Declarative, and no locks held across the `await` in `deliver`.

Rejected: `SELECT ... FOR UPDATE` on the agent row — `enqueue` is followed by an awaited
WebSocket send, and holding a row lock across an `await` is the long-transaction antipattern.

### D7 — Session per frame on the WS handler ✅ decided 2026-07-31

Not a new decision — `docs/research/sync-vs-async-db-stack.md` already mandated it as a design
rule (Caveat 2, lines 34-36; lines 179-180: *"Do not hold a DB session across a long-lived WS
loop — check out a session per message/command inside the threadpool call"*). DMI-62 shipped
neither the per-frame session nor the threadpool offload. Step 7 is what makes the drift
dangerous, so the fix belongs here.

Full analysis: [`docs/research/ws-session-lifetime.md`](../../docs/research/ws-session-lifetime.md).

- `run_agent_channel` takes a session **factory**, not a session; `handle_agent_frame` opens
  `with Session(get_engine())` per frame.
- The blocking DB work moves off the event loop via `run_in_threadpool`.
- Why it hasn't broken yet: a committed session holds no pool connection, and `commit()` expires
  the identity map. The safety is **accidental** — step 7 adds read-then-write paths that don't
  commit on every branch, which removes it.
- Security: pinned pool slot × blocked event loop is the top risk (CWE-400/770; `pool_size=5` +
  `max_overflow=10` are unset defaults, `pool_timeout` 30s). Stale identity-map reads bypassing a
  transition guard is second (CWE-367).
- **No platform backstop** — verified against the live Supabase project 2026-07-31:
  `idle_in_transaction_session_timeout = 0`, and the `postgres` role this app connects as sets
  neither that nor `statement_timeout`. A leaked transaction persists until the process exits.

Cost: edits DMI-62's merged `run_agent_channel` / `handle_agent_frame` signatures and ~6 call
sites in `tests/test_agent_ws.py` — all of which already inject the session, so a factory
parameter keeps them injectable.

### D8 — Lifecycle transitions are applied atomically ✅ decided 2026-07-31

Session scoping only *shrinks* the TOCTOU window on `apply_status`; it does not close it. The
guard must be an atomic `UPDATE commands SET status = :next WHERE id = :id AND status = :expected`,
with a zero-rowcount result meaning "someone else moved it" — not read-validate-write.

Distinct from D6: D6 closes the *enqueue* race, D8 closes the *transition* race.

### D9 — Monotonic transitions, atomic writes, no process memory ✅ decided 2026-07-31

Three writers touch a command row — the HTTP enqueue path, the WS frame path, and the sweeper.
They share no memory, no session and (after D7) no transaction. So the row is the only truth, and
the design must satisfy: one atomic statement per transition, idempotent and order-independent,
and **no lifecycle state in process memory** (a Railway restart wipes it; there is no second
replica to inherit it).

**Pi-owned transitions use a monotonic rank**, not pairwise edges:

```
queued 0 → delivered 1 → running 2 → uploading 3 → done/failed 4
```

```sql
UPDATE commands SET status = :next, started_at = COALESCE(started_at, :now)
WHERE id = :id AND agent_id = :agent_id AND rank(status) < rank(:next)
```

Zero rows updated means "already past this" — the correct silent outcome for a duplicate frame
(required by ADR-011 §3 idempotency), a retry, or a frame that lost a race. Not an error.

**This is what resolves the Q4 race.** The Pi replies `running` in milliseconds, before the
enqueue path commits `delivered`; `0 < 2` so the transition applies and `delivered_at` backfills
via `COALESCE`. No special case, no buffering.

> **Corrected 2026-07-31, after implementation.** The rank alone does *not* resolve Q4 once D1's
> CHECK exists. The rank permits `queued → running`, but that command has no `scan_id` yet, and
> `CHECK (scan_id IS NOT NULL OR status IN ('queued', 'expired'))` rejects the resulting row —
> verified against the live DB, `CheckViolation` in the WS handler. `apply_status` therefore also
> guards on `scan_id IS NOT NULL`, which turns the early frame into the same silent zero-rowcount
> no-op this section already prescribes for a lost race. The Pi's later `uploading`/`done` frames
> apply normally once delivery has set `scan_id`. Cost: that scan goes `pending → processing`
> without passing through `accepted`.

**Rank alone is too permissive for backend-owned states** — it would allow `delivered → expired`,
breaking C12. Split by owner:

| Transitions | Writer | Guard |
|---|---|---|
| `running`, `uploading`, `done`, `failed` | Pi via WS — **racy** | monotonic rank, atomic conditional UPDATE |
| `delivered`, `expired` | enqueue path only — **serialized** by D6 | explicit `WHERE status = 'queued'` |
| `failed` (timeout) | sweeper | explicit `WHERE status IN (...) AND <stale>` |

**The sweeper must also cover `queued`.** A command inserted but never sent, where the process
dies before writing `expired`, leaves a `queued` row that nothing reaps — and D6's unique index
then blocks that agent permanently. Stale `queued` → `expired` (correct: it never reached the Pi).

Rejected: buffering early frames in memory. The buffer is unbounded, lives on the single replica,
and an agent can drive it — a memory-exhaustion path, not merely complexity.

Crash-point recovery:

| Crash point | Row says | Recovered by |
|---|---|---|
| after insert, before send | `queued` | sweeper → `expired` |
| after send, before `delivered` commit | `queued` | the Pi's `running` frame (rank 0 < 2) |
| after `delivered`, mid-scan | `delivered` | sweeper → `failed` |
| after `running` | `running` / `uploading` | sweeper → `failed` |

### D10 — Unknown command vs late command ✅ decided 2026-07-31

D9 makes a zero-rowcount UPDATE silent (duplicates, races). The DMI-62 carry-over requires an
`AgentErrorFrame` for an *unknown* `command_id`. Same rowcount, opposite behaviour — so the fast
path stays one statement, and only a zero rowcount triggers a scoped existence check:

```python
rows = UPDATE ... WHERE id=:id AND agent_id=:agent AND rank(status) < rank(:next)
if rows == 0:
    if not EXISTS(SELECT 1 FROM commands WHERE id=:id AND agent_id=:agent):
        send AgentErrorFrame("unknown command_id")   # socket stays open, nothing written
    # else: duplicate or late frame — silent
```

A command belonging to another agent is treated as unknown from this connection's perspective
(per the DMI-62 comment). That is deliberate: it stops the error frame becoming an oracle for
probing other orgs' command IDs.

### D11 — Staleness is decided by connection loss, not elapsed time ✅ decided 2026-07-31

The Pi's own worst-case runtime (`hardware-agent/src/agent/config.py:100-127`, summed per mode)
is 35 min (`quick`) to 130 min (`max`), and `CreateCommandRequest` accepts all five modes. A
single duration timeout must therefore be sized for `max`, which would wedge an agent for ~2.5h
after a dead 35-minute quick scan. Mirroring the Pi's table in backend config would put the same
constants in two repos with nothing keeping them in sync.

Instead: a command is stale only when the agent is **not connected** and a short grace has
elapsed. A connected Pi is never wrongly failed regardless of scan duration, and the backend
needs no knowledge of scan timings. ADR-011 already points this way — *"WS drop mid-scan uses
that same running timeout → failed"*.

Config: `command_disconnect_grace_seconds`, **default 900 (15 min)**. It must comfortably exceed
the Pi's reconnect backoff, or an API deploy would fail live scans. That backoff is defined by
the daemon in DMI-66, which is unbuilt — so 15 min is a deliberately generous placeholder, to be
pinned once DMI-66 lands. Flagged in that issue rather than left implicit here.

Resolved against D4 by D12.

### D12 — Connection state is projected into the database ✅ decided 2026-07-31

D11 makes staleness depend on "is this agent connected?", but that lives in an in-memory dict in
the **API** process while D4's sweeper runs in the **worker** — a separate Railway service
(BACKEND.md B4/B5). `agents.last_seen_at` alone cannot substitute: the Pi sends no frames between
`running` and `uploading`, so up to 35 minutes of silence is normal for a *healthy* agent.

So the registry gets a durable projection. The API is its only writer, and the deployment is
single-replica (ADR-011), which is what makes the projection trustworthy.

**The projection lives in its own module — `services/agent_presence.py` (new).**
`agent_connections.py` stays exactly what it is: a pure in-memory registry with an asyncio lock
and no I/O. Mixing durable writes into it would put two concerns in one file and add a third
touch to DMI-62's merged code. The call sites already have a session —
`routers/agents.py:connect_agent_commands` is where `register()` and the `finally: unregister()`
already sit, so the presence writes go next to them, not inside the registry.

| Event | `agent_presence` call | Write |
|---|---|---|
| on connect | `mark_connected(session, agent_id, now)` | `connected_at = now()`, touch `last_seen_at` |
| on disconnect (`finally`) | `mark_disconnected(session, agent_id)` | `connected_at = NULL` |
| API startup | `reconcile_all(session)` | `UPDATE agents SET connected_at = NULL` — recovers from a hard crash where `unregister` never ran |

`touch_agent_last_seen` moves out of `agent_ws.py` into this module — it is the same concern
(agent presence), and D7 is already rewriting how it takes a session, so it is not extra churn.

The sweep predicate becomes pure SQL, so the worker needs no memory access:

```sql
WHERE status IN ('queued','delivered','running','uploading')
  AND agents.connected_at IS NULL
  AND now() - agents.last_seen_at > :grace
```

**Why `last_seen_at` is the right clock.** It only has to be meaningful once the agent is already
disconnected — the `connected_at IS NULL` guard excludes healthy mid-scan silence entirely. So no
separate `disconnected_at` column is needed.

**Hard-crash exposure is bounded by restart time:** if the API is SIGKILLed, `unregister` never
runs and the flag stays set until boot clears it. Railway restarts in seconds.

Bonus: DMI-78's `online` field gains a durable source instead of reading process memory.

---

## Where the work lands

| Work | Home | Why |
|---|---|---|
| OpenAPI `scan_id` → nullable on **both** `CommandDetail` (1993) and `CommandSummary` (1975) | **DMI-64** | It's the contract for code in this PR |
| `Command.scan_id` nullable + CHECK constraint + D6 index + `agents.connected_at` migration | **DMI-64** | Same change |
| ADR-011 §4 amendment (stub scan conditional on delivery) | **DMI-64** | Two paragraphs; not worth its own ticket |
| BACKEND.md B6 3b note | **DMI-64** | Travels with the ADR |
| "`scan_id` can be null" heads-up | **comment on DMI-89** | Frontend must not link to a scan that doesn't exist |
| Revocation not enforced on live sockets | **new issue** | Separate concern (WS auth lifecycle), lands after DMI-64 |

---

## Implementation steps

0. **WS session lifetime (D7)** — `services/agent_ws.py` + `routers/agents.py`: `run_agent_channel`
   takes a session factory; `handle_agent_frame` opens `with Session(get_engine())` per frame,
   called via `run_in_threadpool`. Prerequisite for step 7, not a drive-by.
   *Verify:* `tests/test_agent_ws.py` (~6 call sites, all already inject the session).

1. **Lifecycle ranks (D9)** — `services/command_lifecycle.py`: replace pairwise `_LEGAL_EDGES` with
   a monotonic rank for Pi-owned statuses; keep explicit guards for `delivered`/`expired`; add
   `is_terminal()` (busy check + sweeper both need it).
   *Verify:* extend `tests/test_command_lifecycle.py` — `queued → running` applies, duplicate frame
   is a silent no-op, `done → failed` does not apply, `delivered → expired` rejected.

2. **Migration** — `Command.scan_id` nullable + the D1 CHECK constraint + the D6 partial unique
   index + `agents.connected_at` (nullable, D12).
   *Verify:* upgrade/downgrade round-trip, mirroring `tests/test_command_migration.py`.

2b. **Connection projection (D12)** — `services/agent_presence.py` (new): `mark_connected`,
   `mark_disconnected`, `reconcile_all`, and `touch_agent_last_seen` moved in from `agent_ws.py`.
   Called from `routers/agents.py` (connect / `finally`) and `main.py` (startup).
   **`agent_connections.py` is not modified.**
   *Verify:* `tests/test_agent_presence.py` — connect sets, disconnect clears, startup reconciles
   a stale flag left by a hard crash.

3. **Command service** — `services/commands.py` (new): `enqueue`, `active_command_for`,
   `apply_status` (atomic conditional UPDATE, D9), `sweep_stale_commands`. All DB work lives here.
   *Verify:* `tests/test_commands_service.py`, unit-level, no HTTP.

4. **Delivery** — same module, `async def deliver(...)`: no socket → `expired` + raise offline;
   socket → send `AgentCommandFrame`, set `delivered_at`, then create the stub scan.
   *Verify:* `AsyncMock` socket (pattern in `tests/test_ws_fixtures.py`) — success, throwing send, no socket.

5. **POST route** — `routers/agents.py` + `schemas/commands.py` (new). Mount `require_admin`.
   Sweep the agent's stale commands (D4) → busy check → insert. `IntegrityError` from the D6 index
   maps to the same `409 device_busy`.
   *Verify:* `tests/test_enqueue_command.py` — 201, 403 viewer, 409 busy, 409 on the concurrent
   insert, 503 offline with the row `expired` **and no scan row**, 404 unknown agent, cross-org isolation.

6. **GET /commands/{command_id}** — `routers/commands.py` (new), registered in `main.py`. **Pure read.**
   *Verify:* other org → 404; `scan_id: null` serialises on an expired command.

7. **Wire the WS status path** — `services/agent_ws.py`: replace the discard at the `status` branch
   with `apply_status`.
   *Verify:* extend `tests/test_agent_ws_channel.py`.

8. **Worker sweep (D4)** — `services/worker.py:run_worker_once` also calls `sweep_stale_commands`.
   *Verify:* stale `running`/`delivered` → `failed`, stale `queued` → `expired`, scan mirror updated.

9. **Records catch up (D1)** — in this PR, not a separate issue:
   - `contracts/openapi/openapi.yaml`: `scan_id` out of `required` on `CommandDetail` and
     `CommandSummary`; reword the `GET /commands/{command_id}` 200 description ("linked scan_id").
   - `docs/adr/ADR-011-pi-command-channel.md` §4: the stub scan is created on **successful
     delivery**; `expired` commands carry no `scan_id`; state the enforcing invariant
     `CHECK (scan_id IS NOT NULL OR status IN ('queued', 'expired'))` **and the reasoning** — the next reader
     should not have to rediscover why.
   - `docs/roadmap/BACKEND.md` B6 3b: `scan_id` is generated at enqueue but **persisted** only on
     delivery.
   *Verify:* run the `architecture-adr-sync` skill — no drift reported between ADR-011,
   BACKEND.md and the merged code.

**Gate:** `uv run ruff check src tests` and `uv run pytest`. Never `ruff format` in `backend/`.

---

## Open questions

**None blocking.** The grilling session of 2026-07-31 resolved every structural fork into D1–D12
above. For traceability: Q2 → D7, Q3 → D6, Q4 → D9, Q5 → D4 (revised), Q6 → D10, Q7 → D11,
Q8 → D12.

Settled during implementation, no decision needed — recorded so they are not re-litigated:

- Unknown or cross-org `agent_id` on `POST /commands` → **`403`**, not `404`. The OpenAPI operation
  lists only 401/403/409/503/500 (no 404 response is defined).
- Response is **`201` + `CommandSummary`**; request body is `CreateCommandRequest`
  (`openapi.yaml:1958`).
- The stub scan takes `timestamp = now()` at creation and inherits `org_id` from the agent row.
- The Pi's reported `error_code` is persisted onto `Command.error_code` — the column already
  exists, and DMI-75 ("Give a failed scan a readable reason") builds on it.

Carried into other issues rather than resolved here:

- **`command_disconnect_grace_seconds = 900`** is a generous placeholder. The Pi's reconnect
  backoff is defined by DMI-66, which is unbuilt; pin the value once that lands.
- **Revocation is not enforced on live sockets** → [DMI-97](https://linear.app/dmitri-imt/issue/DMI-97/revoking-a-device-does-not-drop-its-live-websocket)
  (High, blocked by this issue).
- **`scan_id` can be null** → to be raised on DMI-89 so the frontend never links to a scan that
  does not exist.
