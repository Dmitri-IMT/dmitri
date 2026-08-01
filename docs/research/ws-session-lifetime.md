# Research: DB session lifetime for a long-lived writing WebSocket

> **Scope.** Dmitri's agent command channel (`GET /api/v1/agents/{agent_id}/commands`,
> DMI-62, ADR-011 single replica) resolves `session: Session = Depends(get_session)`
> on the WebSocket route and passes that one `Session` into `run_agent_channel`,
> which loops `async for raw_text in websocket.iter_text()` for the whole
> connection — hours or days for a Raspberry Pi holding a persistent outbound WSS
> socket. DMI-64 will make that session apply **command lifecycle state
> transitions** (read a `commands` row, validate the transition, write it).
> Production runs on Supabase Postgres through the Supavisor pooler on **6543 in
> transaction mode** (docs/roadmap/BACKEND.md B4+B5). Question: what is the
> correct and most secure session lifetime here?
> **Primary sources only; fetched 2026-07-31.** Versions in the repo venv:
> SQLAlchemy 2.0.51, FastAPI 0.139.0.

---

## TL;DR verdict

**Session-per-frame. Do not hold one `Session` across the connection.** The
strongest primary source is SQLAlchemy's own error documentation, which
describes this exact shape as a cause of pool exhaustion:

> "**The application is attempting to run long-running transactions** — A
> database transaction is a very expensive resource, and should never be left
> idle waiting for some event to occur. If an application is waiting for a user
> to push a button, or a result to come off of a long running job queue, **or is
> holding a persistent connection open to a browser, don't keep a database
> transaction open for the whole time.** As the application needs to work with
> the database and interact with an event, open a short-lived transaction at
> that point and then close it."
> — https://docs.sqlalchemy.org/en/20/errors.html#error-3o7r

Three things make this concrete rather than theoretical:

1. **Today the code is accidentally safe, not safe by design.** Every frame path
   that touches the DB ends in `session.commit()`, and commit releases the DBAPI
   connection back to the pool and expires every object (§1, §2). So between
   frames the session holds no pool slot and no server connection. That
   invariant is *un-enforced* and already has one hole: `touch_agent_last_seen`
   returns early when `session.get(Agent, …)` is `None` **without committing**,
   leaving an open read transaction pinned for the rest of the connection (§5.1).
2. **The pool is 15 connections wide and 30 seconds patient.** SQLAlchemy
   defaults, unset in `get_engine()`: `pool_size=5`, `max_overflow=10`,
   `pool_timeout=30.0` (§2). Fifteen sockets that each leak an open transaction
   take the whole API down, and each such wait happens **on the event loop
   thread** (§5.1) — the sync DB calls in `handle_agent_frame` are not offloaded
   to a threadpool, so a 30 s pool wait freezes every WS connection and every
   `async` route in the single replica.
3. **DMI-64 turns the identity map into an authorization hazard.**
   `Session.get()` "provides direct access to the identity map… the object is
   returned directly from this collection and **no SQL is emitted**, unless the
   object has been marked fully expired" (§3). A state-machine guard read from a
   cached `commands` row that an HTTP request has since mutated is
   check-against-stale-state — CWE-367 / CWE-841 (§5.2). Expiry-on-commit
   currently masks this; it stops masking it the moment a frame reads without
   committing, or reads twice inside one transaction.

**Recommendation: per-frame transaction scope, and separately, a DB-level
compare-and-set for the DMI-64 transition guard.** Concrete options, costs and
the cheapest surgical variant are in "Recommendation for this repo" at the end.

---

## Findings

### 1. What SQLAlchemy documents about session lifetime

**The tl;dr in "When do I construct a Session, when do I commit it, and when do
I close it?" is unusually direct:**

> "As a general rule, keep the lifecycle of the session separate and external
> from functions and objects that access and/or manipulate database data. …
> Make sure you have a clear notion of where transactions begin and end, and
> **keep transactions short, meaning, they end at the series of a sequence of
> operations, instead of being held open indefinitely.**"
> — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#when-do-i-construct-a-session-when-do-i-commit-it-and-when-do-i-close-it

The same section enumerates sample scopes — web request, forked job, CLI script,
GUI event. Note the GUI entry, which is the closest analogue to a socket loop:
"the scope of the `Session` may best be within the scope of a user-generated
event, such as a button push." Not "the lifetime of the window". **There is no
WebSocket entry.** SQLAlchemy's docs never name WebSockets; the only place the
pattern appears is the errors page quote in the TL;DR ("holding a persistent
connection open to a browser").

**Session ≠ transaction, and both are scoped.** Same section:

> "A `Session` is typically constructed at the beginning of a logical operation
> where database access is potentially anticipated. The `Session`, whenever it is
> used to talk to the database, begins a database transaction as soon as it
> starts communicating. This transaction remains in progress until the `Session`
> is rolled back, committed, or closed. The `Session` will begin a new
> transaction if it is used again, subsequent to the previous transaction
> ending; from this it follows that **the `Session` is capable of having a
> lifespan across many transactions, though only one at a time.**"

That last clause is why the current code is *survivable*: a long-lived `Session`
that commits after every frame is a sequence of short transactions, not one long
one. The danger is entirely in whether every path really ends its transaction.

**Autobegin — when the transaction actually starts.**

> "When the `Session` is first constructed, there's no transactional state
> present. The transactional state is begun automatically, when a method such as
> `Session.add()` or `Session.execute()` is invoked, or similarly if a `Query` is
> executed to return results…"
> — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#auto-begin

So the FastAPI-resolved `Session` costs nothing until the first frame does DB
work. `Session(autobegin=False)` exists (2.0+) and raises `InvalidRequestError`
on implicit use — a possible tripwire, see the recommendation.

**Commit and rollback both end the transaction and release the connection.**

> "After the commit, the `Connection` object associated with that transaction is
> closed, causing its underlying DBAPI connection to be **released back to the
> connection pool** … Finally, **all objects within the `Session` are expired** as
> the transaction is closed out."
> — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#committing

> "**Database connections are released.** … `Connection` objects obtained from
> `Engine` objects are closed, causing the DBAPI connections to be released to the
> connection pool within the `Engine`. New connections are checked out from the
> `Engine` if and when a new transaction begins. … **All objects not expunged are
> fully expired — this is regardless of the `Session.expire_on_commit` setting.**"
> — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#rolling-back

This is load-bearing for the cheap fix: a `session.rollback()` in a per-frame
`finally` gives you *both* per-frame connection release *and* unconditional
identity-map expiry, with no change to any function signature.

**Concurrency.** The Session "is a mutable, stateful object that represents a
single database transaction… cannot be shared among concurrent threads or
asyncio tasks without careful synchronization… The concurrency model for
SQLAlchemy's `Session` and `AsyncSession` is therefore **Session per thread,
AsyncSession per task**."
— https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks

For Dmitri this is satisfied today only by accident of single-threadedness: the
WS handler runs on the event loop and calls the sync session inline, so there is
exactly one user at a time. It would be violated the moment anyone offloads two
frame handlers concurrently, or hands the connection's session to a background
task (a natural thing to want when DMI-64 adds command dispatch).

### 2. Pool behaviour and the exhaustion numbers

`get_engine()` sets neither `pool_size` nor `max_overflow`, so the documented
`QueuePool` defaults apply:

| Parameter | Default | Source |
|---|---|---|
| `pool_size` | **5** ("The size of the pool to be maintained, defaults to 5") | https://docs.sqlalchemy.org/en/20/core/pooling.html |
| `max_overflow` | **10** | https://docs.sqlalchemy.org/en/20/core/pooling.html |
| `pool_timeout` | **30.0** seconds | https://docs.sqlalchemy.org/en/20/core/pooling.html |
| `pool_recycle` | -1 (disabled) | https://docs.sqlalchemy.org/en/20/core/pooling.html |

**What happens at exhaustion — it blocks, then raises.**

> "The above `Engine` will allow at most 30 connections to be in play at any
> time… **If a request for a new connection arrives and 30 connections are
> already in use by other parts of the application, the connection pool will
> block for a fixed period of time, before timing out and raising this error
> message.**"
> — https://docs.sqlalchemy.org/en/20/errors.html#error-3o7r
> (error text: `QueuePool limit of size <x> overflow <y> reached, connection
> timed out, timeout <z>` → `sqlalchemy.exc.TimeoutError`)

With Dmitri's unset defaults the number is **5 + 10 = 15 concurrent connections
per process**, and the 16th waits **30 s** before failing.

The same page frames the pool as a security control, which is the right lens
here:

> "the connection pool can be looked at as a **safety valve** for connection use,
> providing a critical layer of protection against a rogue application causing
> the entire database to become unavailable to all other applications."

and names the two failure modes that apply to a socket loop:

> "**The application is not returning connections to the pool** … A common reason
> this can occur is that the application uses ORM sessions and does not call
> `Session.close()` upon them once the work involving that session is complete."

> "**The application's worker threads are not yielding control** … threads that
> hold checked-out connections may monopolize CPU time, preventing the
> connection pool from serving other threads that are blocked waiting for
> connections."

**Not verified:** SQLAlchemy documents no per-tenant or per-connection sub-quota
mechanism. There is no primary-source way to say "agents may use at most N of
the 15 slots" other than running agents on a separate `Engine`/process. The
`max_overflow=-1` unlimited setting is explicitly discouraged on the same page.

### 3. Identity map and expiry — the stale-read mechanics

**`Session.get()` can return a cached row with no SQL at all.**

> "`Session.get()` is special in that it provides direct access to the identity
> map of the `Session`. **If the given primary key identifier is present in the
> local identity map, the object is returned directly from this collection and
> no SQL is emitted, unless the object has been marked fully expired.** If not
> present, a SELECT is performed in order to locate the object. `Session.get()`
> also will perform a check if the object is present in the identity map and
> marked as expired — a SELECT is emitted to refresh the object as well as to
> ensure that the row is still present. If not, `ObjectDeletedError` is raised."
> — https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get

`session.get(...)` is exactly what `touch_agent_last_seen` uses and exactly what
a DMI-64 "load the command row, check the transition" step would use.

**What keeps it fresh: expire-on-commit.**

> "`expire_on_commit` … **Defaults to `True`.** When `True`, all instances will be
> fully expired after each `commit()`, so that all attribute/object access
> subsequent to a completed transaction will load from the most recent database
> state."
> — https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit

Note that the "web applications" guidance in Session Basics recommends setting
`expire_on_commit=False` for request-scoped sessions (so the view layer can read
committed objects without new SQL). **That recommendation must not be copied
onto this WebSocket route** — it is safe only *because* the session dies at the
end of the request. On a connection-scoped session it would remove the only
thing currently preventing stale reads.

**`expire_all()` is not a fix by itself.**

> "`Session.expire_all()` — Expires all persistent instances within this
> `Session`. When any attributes on a persistent instance is next accessed, a
> query will be issued using the `Session` object's **current transactional
> context**… **Note that a highly isolated transaction will return the same
> values as were previously read in that same transaction, regardless of changes
> in database state outside of that transaction.** … calling
> `Session.expire_all()` is not usually needed, assuming the transaction is
> isolated."
> — https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.expire_all

Postgres's default isolation level is Read Committed —

> "*Read Committed* is the default isolation level in PostgreSQL." … "two
> successive `SELECT` commands can see different data, even though they are
> within a single transaction, if other transactions commit changes after the
> first `SELECT` starts and before the second `SELECT` starts."
> — https://www.postgresql.org/docs/current/transaction-iso.html

— so under Dmitri's actual isolation level, `expire_all()` *does* buy fresh
reads within an open transaction. It is still the weaker mitigation: it depends
on an isolation level nobody has pinned in code, it does nothing about the
connection being pinned, and any future move to `REPEATABLE READ` silently
re-introduces the stale read. Ending the transaction gets you the same freshness
plus the released connection.

**The Session is explicitly not a cache you should trust:**

> "Is the Session a cache? Yeee…no. It's somewhat used as a cache, in that it
> implements the identity map pattern… The `Session` is not designed to be a
> global object from which everyone consults as a 'registry' of objects."
> — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-a-cache

### 4. When does FastAPI actually tear down a `yield` dependency on a WebSocket?

**At the end of the connection.** FastAPI's public docs say only:

> "Normally the exit code of dependencies with `yield` is executed **after the
> response** is sent to the client."
> — https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/

and, for WebSockets, only that `Depends` "work[s] the same way as for other
FastAPI endpoints/*path operations*"
— https://fastapi.tiangolo.com/advanced/websockets/. **Neither page states the
WebSocket teardown point.** Verified from source instead (FastAPI 0.139.0,
`fastapi/routing.py`, `websocket_session()` — a vendored copy of Starlette's,
"modified to include the dependencies' AsyncExitStack"):

```python
async def app(scope, receive, send):
    async with AsyncExitStack() as request_stack:
        scope["fastapi_inner_astack"] = request_stack
        async with AsyncExitStack() as function_stack:
            scope["fastapi_function_astack"] = function_stack
            await func(session)          # <- the entire WS handler
```

`get_websocket_app()` resolves dependencies into `fastapi_inner_astack`. Both
stacks close only after `await func(session)` returns, i.e. **after the
`iter_text()` loop ends**. So `get_session`'s `with Session(...)` context — and
therefore `Session.close()` — runs once, when the socket dies. On a Pi that
holds the socket for days, that is a days-long session object. (The newer
`Depends(scope="function")` knob does not help here: on a WS route the function
stack wraps the same `await func(session)` call.)

Two related mechanics, also from source:

- **The auth dependency and the route share one `Session` instance.**
  `require_agent_ws` also takes `session: Session = Depends(get_session)`, and
  FastAPI caches a dependency's result per request by default
  (https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times).
  So the `Agent` row loaded during signature verification is in the identity map
  for the entire connection.
- **The session is created and closed in a worker thread, but used on the event
  loop.** A sync generator dependency is wrapped in
  `contextmanager_in_threadpool` (`fastapi/concurrency.py`), whose `__exit__`
  deliberately runs under its own `CapacityLimiter(1)` — the comment says this
  is to avoid "race conditions/deadlocks if the context manager itself has its
  own internal pool (e.g. a database connection pool)". The `Session` object
  itself is then used inline from the event loop thread by
  `handle_agent_frame`. Sequential handoff across threads is legal per §1's
  "one thread at a time" rule, but the inline sync call on the loop thread is
  its own problem (§5.1).

### 5. Security ranking

#### 5.1 Rank 1 — Resource exhaustion / DoS: pinned pool slot × blocked event loop

**CWE-400 Uncontrolled Resource Consumption; CWE-770 "Allocation of Resources
Without Limits or Throttling" — "The product allocates a reusable resource or
group of resources on behalf of an actor without imposing any intended
restrictions on the size or number of resources that can be allocated"**
(https://cwe.mitre.org/data/definitions/770.html).

Two multiplying factors, both present in the current code:

**(a) A frame path that reads without committing pins a connection forever.**
In `agent_ws.touch_agent_last_seen`:

```python
agent = session.get(Agent, agent_id)
if agent is None:
    return                 # <-- autobegun transaction left open, no commit/rollback
agent.last_seen_at = now
session.commit()
```

`session.get()` autobegins and checks out a pool connection (§1). The early
return leaves it checked out and **idle in transaction** for the remaining life
of the socket. Reachable if the `agents` row is deleted while a socket is live
(auth loaded the row at connect time; nothing re-reads it). More importantly it
is the *template* the DMI-64 work will copy: any `return` or `raise` on a
validation-failure path between a read and the commit does the same thing. 15
such sockets exhaust `pool_size + max_overflow` (§2) and every HTTP request in
the API then blocks 30 s and fails.

**(b) The blocking DB call is on the event loop thread.** `handle_agent_frame`
is `async def` and calls `touch_agent_last_seen(session, …)` directly — no
`run_in_threadpool`. Under ADR-011's single replica, one 30 s `pool_timeout`
wait therefore stalls the event loop, i.e. **all** WebSocket connections and all
`async` routes, not just the offending one. This directly contradicts Caveat 2
of `docs/research/sync-vs-async-db-stack.md` ("it must call the sync DB code via
`run_in_threadpool`… Do not hold a DB session across a long-lived WS loop —
check out a session per message/command inside the threadpool call"). That
caveat was written and then not implemented.

**Attacker model.** Opening the socket requires a valid device signature
(`require_agent_ws`), so this is an *authenticated* actor — a stolen Pi key, or
far more likely a buggy agent in a reconnect loop. Two existing controls limit
the blast radius and are worth crediting:

- `agent_connections.register()` closes the previous socket for the same
  `agent_id`, so one key cannot hold many sockets *steadily*. But the displaced
  handler's `finally`/dependency teardown runs later (see
  `docs/research/ws-connection-registry-reconnect-race.md`), so a fast reconnect
  loop **transiently stacks sessions** — the exact window in which a leaked
  transaction from each of them accumulates.
- Nonce replay protection means each reconnect costs the attacker a fresh signed
  envelope, not free.

Neither control bounds *concurrent overlapping handlers*, and nothing bounds
concurrent agents. There is no per-actor pool quota available (§2, unverified).

#### 5.2 Rank 2 — Stale identity-map read bypassing a state-machine guard (latent, lands with DMI-64)

**CWE-367 Time-of-check Time-of-use** — "The product checks the state of a
resource before using that resource, but the resource's state can change between
the check and the use in a way that invalidates the results of the check"
(https://cwe.mitre.org/data/definitions/367.html) — and **CWE-841 Improper
Enforcement of Behavioral Workflow** — "The product supports a session in which
more than one behavior must be performed by an actor, but it does not properly
ensure that the actor performs the behaviors in the required sequence"
(https://cwe.mitre.org/data/definitions/841.html).

The scenario the task asks about — an HTTP request mutates a `commands` row, then
a WS frame applies a transition against a cached copy — **is real but is
currently blocked by expire-on-commit**, not by design. Trace it:

1. Frame N: `session.get(Command, id)` → SELECT, row cached; `session.commit()`
   → connection released **and every object expired** (§1).
2. HTTP request elsewhere sets `status = 'cancelled'`.
3. Frame N+1: `session.get(Command, id)` → object is fully expired, so per §3 a
   SELECT is emitted in a **new** Read Committed transaction → fresh row.
   Guard holds.

It breaks in three ways, all plausible in a DMI-64 implementation:

- **Two reads inside one transaction.** "Load command, validate transition, load
  it again / touch a relationship" without an intervening commit: the second
  `Session.get()` hits the identity map and emits no SQL (§3). Under Read
  Committed the *row* would have been fresh — the ORM cache, not the DB
  isolation level, is what serves stale state.
- **Someone sets `expire_on_commit=False`**, copying the "web applications"
  advice from Session Basics (§3) without noticing it is request-scoped advice.
  Every read for the rest of the connection then serves the cached row.
- **A read on a path that returns before committing** (the §5.1(a) shape): the
  transaction stays open, and any later read of the same PK in that transaction
  returns the pre-mutation object.

Consequence in Dmitri's domain: a command the operator cancelled (or that
another agent already claimed) is validated against its stale prior status and
transitioned anyway — a workflow-guard bypass, and depending on the transition
table, a way to make a terminal command executable again.

**Session lifetime is a mitigation, not the fix.** Even with a fresh session per
frame, read-then-write across two statements is a TOCTOU window: another writer
can commit between the SELECT and the UPDATE. CWE-367's own mitigation guidance
is to "perform operations atomically, use locking mechanisms before checks
occur, or recheck resources after use" (https://cwe.mitre.org/data/definitions/367.html).
For DMI-64 that means the guard belongs in the write: a conditional
`UPDATE commands SET status = :new WHERE id = :id AND status = :expected` and a
check on rowcount, or `Session.get(..., with_for_update=True)`
(https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get),
or a version counter. Session-per-frame shrinks the window; the compare-and-set
closes it.

#### 5.3 Rank 3 — Long-running transactions: locks, bloat, and the transaction-mode pooler

An idle-in-transaction session is a Postgres-level cost independent of the pool:

> "`idle_in_transaction_session_timeout` … Terminate any session that has been
> idle (that is, waiting for a client query) within an open transaction for
> longer than the specified amount of time. … **A value of zero (the default)
> disables the timeout.** This option can be used to ensure that idle sessions do
> not hold locks for an unreasonable amount of time. **Even when no significant
> locks are held, an open transaction prevents vacuuming away recently-dead
> tuples that may be visible only to this transaction; so remaining idle for a
> long time can contribute to table bloat.**"
> — https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-IDLE-IN-TRANSACTION-SESSION-TIMEOUT

`transaction_timeout` (Postgres 17+) is likewise `0`/disabled by default, and
`idle_session_timeout` (non-transactional idle) is documented as much less
important — plus it carries an explicit warning: "Be wary of enforcing this
timeout on connections made through connection-pooling software or other
middleware, as such a layer may not react well to unexpected connection
closure." (same page).

**Why this bites harder on 6543.** PgBouncer defines transaction pooling as: "A
server connection is assigned to a client only during a transaction. When
PgBouncer notices that the transaction is over, the server will be put back into
the pool." — https://www.pgbouncer.org/features.html. Supabase's Supavisor
behaves the same way: server connections in transaction mode are "assigned and
released on a per-transaction basis", and the docs steer persistent backends
away from it — "This is ideal for serverless or edge functions, which require
many transient connections", with session mode / direct connections recommended
for session-level features and long-lived sessions
(https://supabase.com/docs/guides/database/connecting-to-postgres; also
"Transaction mode does not support prepared statements. To avoid errors, turn
off prepared statements for your connection library." — already handled by
`prepare_threshold: None` in `get_engine()`).

The consequence: a client that keeps a transaction open **defeats the entire
point of transaction mode** — it pins a Supavisor server connection for the
duration, so the leak is charged against the pooler's per-user pool as well as
against SQLAlchemy's 15. Supavisor's own description of the mechanism: "In
transaction mode, the pooler will only add connections if there are not enough
connections to service all pending queries simultaneously" and "once a direct
connection is established, the pooler will keep it available for reuse for
another client"
(https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI).
Sizing guidance, for context: "if you are heavily using the PostgREST database
API, you should be conscientious about raising your pool size past 40% of the
Database Max Connections. Otherwise, you can commit 80% to the pool."
(https://supabase.com/docs/guides/database/connection-management).

Conversely — and this is the good news for the *current* code — a long-lived
`Session` that is **not** in a transaction costs Postgres and Supavisor nothing
at all, because it holds no connection (§1). The entire risk is transaction
lifetime, not session-object lifetime.

**Verified against the live project, 2026-07-31 — there is no platform backstop.**

```
SHOW idle_in_transaction_session_timeout;  →  0   (disabled)
```

Role-level overrides (`pg_db_role_setting`) confirm it is not set anywhere that matters:

| Role | Relevant setting |
|------|------------------|
| `postgres` (the role this app connects as) | `search_path` only — **no** idle-in-transaction timeout, **no** `statement_timeout` |
| `supabase_auth_admin` | `idle_in_transaction_session_timeout=60000` — Supabase's internal auth service, not this app |
| `anon` / `authenticated` / `authenticator` | `statement_timeout` 3s/8s — PostgREST roles, not the SQLAlchemy path |

So a transaction leaked by the WebSocket handler is reaped by **nothing**: it persists until the
API process exits. This closes the open question as worst-case and removes the "maybe the
platform saves us" argument for leaving the session connection-scoped.

Still unverified: whether Supavisor applies its own client-idle or idle-transaction timeout at
the pooler layer, independent of Postgres. Not documented in the Supabase pages read above.

#### 5.4 Adjacent, out of scope but worth logging — revocation is checked only at connect

`require_agent_ws` runs once, at upgrade. `agent.revoked_at` is never re-checked
for the life of the socket, so revoking a compromised Pi does not close its
existing connection. Independent of session lifetime, but it is the other
"decision made once, then trusted for days" in this handler, and a session-per-
frame refactor is the natural place to also re-read the agent's revocation state.

### 6. What the primary sources say the pattern should be

No official source addresses "WebSocket handler that writes" by name. The
closest statements, in descending order of directness:

1. SQLAlchemy errors page — "**or is holding a persistent connection open to a
   browser, don't keep a database transaction open for the whole time. As the
   application needs to work with the database and interact with an event, open
   a short-lived transaction at that point and then close it.**"
   — https://docs.sqlalchemy.org/en/20/errors.html#error-3o7r
   This is a per-event transaction scope, i.e. session-per-frame.
2. Session Basics tl;dr — "keep transactions short… instead of being held open
   indefinitely", and the GUI scope example: "within the scope of a
   user-generated event, such as a button push."
   — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#when-do-i-construct-a-session-when-do-i-commit-it-and-when-do-i-close-it
3. Session Basics closing — "It's recommended that the scope of a `Session` be
   limited by a call to `Session.close()` at the end… The `Session` may be used as
   a context manager to ensure that `Session.close()` is called."
   — https://docs.sqlalchemy.org/en/20/orm/session_basics.html#closing
4. Dmitri's own prior note, `docs/research/sync-vs-async-db-stack.md` §5: "Do not
   hold a DB session across a long-lived WS loop — check out a session per
   message/command inside the threadpool call." (Secondary — internal, but
   derived from the same primary sources.)

**FastAPI documents nothing on this.** Its WebSocket page shows `Depends` only
for auth-shaped dependencies (a cookie/token), never a DB session, and says
nothing about session scope in a socket loop. Absence of guidance, not guidance.

---

## Decision inputs (concrete numbers)

| Input | Value | Source |
|---|---|---|
| `QueuePool` defaults in `get_engine()` (unset → defaults) | `pool_size=5`, `max_overflow=10` → **15 conns/process**; `pool_timeout=30.0 s` | docs.sqlalchemy.org/en/20/core/pooling.html |
| Exhaustion behaviour | **blocks** `pool_timeout` seconds, then raises `sqlalchemy.exc.TimeoutError` | errors.html#error-3o7r |
| Connections needed to DoS the API | **15** leaked-transaction sockets | derived from the two above |
| Session with no transaction | holds **no** pool connection (autobegin is lazy) | session_basics#auto-begin |
| `commit()` / `rollback()` | release the DBAPI connection **and** fully expire all objects (rollback does so regardless of `expire_on_commit`) | session_basics#committing, #rolling-back |
| `expire_on_commit` | default **True** | session_api.html#…params.expire_on_commit |
| `Session.get()` | returns from identity map with **no SQL** unless fully expired | session_api.html#…Session.get |
| Postgres default isolation | **Read Committed**; each statement takes a new snapshot | postgresql.org/docs/current/transaction-iso.html |
| `idle_in_transaction_session_timeout` | default **0 = disabled**; open txn blocks vacuum → bloat | postgresql.org/docs/current/runtime-config-client.html |
| Supavisor 6543 transaction mode | server conn assigned/released **per transaction**; for "serverless or edge functions… many transient connections"; session mode/direct for long-lived sessions | supabase connecting-to-postgres; pgbouncer features.html |
| FastAPI WS dependency teardown | **once, at end of connection** (both exit stacks wrap `await func(session)`) | fastapi 0.139.0 `routing.py::websocket_session` (source; undocumented) |
| Sync generator dependency | entered/exited via `contextmanager_in_threadpool`; `__exit__` gets its own `CapacityLimiter(1)` | fastapi 0.139.0 `concurrency.py` |
| Current frame handling | sync DB call inline on the **event loop thread** (no `run_in_threadpool`) | `backend/src/api/services/agent_ws.py` |

---

## Recommendation for this repo

**Verdict: move to per-frame transaction scope. Do not leave as-is; do not rely
on `expire_all()`.**

Ranked, with cost:

### Option A (recommended) — session per frame, opened inside the loop

`run_agent_channel` stops taking a `Session` and takes a session factory (or
nothing, and calls `get_engine()` itself); `handle_agent_frame` opens
`with Session(get_engine()) as session:` for the duration of one frame, inside a
`run_in_threadpool` call so the blocking DB work leaves the event loop.

- Fixes §5.1(a) structurally: a leaked early-return can pin a connection for one
  frame, not for days — the `with` block closes it.
- Fixes §5.1(b): the 30 s pool wait no longer freezes the replica.
- Removes the §5.2 identity map entirely between frames — no cached `commands`
  row can survive to the next frame under any `expire_on_commit` setting.
- Matches the errors-page instruction verbatim ("open a short-lived transaction
  at that point and then close it") and this repo's own prior research note.
- Drops the WS route's `session: Session = Depends(get_session)` parameter
  (auth's own `Depends(get_session)` still resolves per connection, but that
  session commits inside `remember_nonce`/`prune_expired_nonces` and then sits
  transaction-less and harmless — or can be closed explicitly after accept).

**Cost:** edits DMI-62's already-merged `run_agent_channel(websocket, session, *,
agent_id)` signature and `handle_agent_frame`'s, plus `backend/tests/test_agent_ws.py`
(184 lines; ~6 tests pass `administrative_session` or a `MagicMock` positionally
into `_handle` / `run_agent_channel`). The tests all inject the session
explicitly, so a factory parameter keeps them injectable — `session_factory=lambda:
administrative_session` — but every call site in that file changes. Also touches
`backend/src/api/routers/agents.py` (drop the dependency, adjust the
`touch_agent_last_seen` call at connect time). Backend gate:
`uv run ruff check src tests` + `uv run pytest`, no `ruff format`
(.claude/CLAUDE.md).

### Option B (cheap 80%) — keep the signature, end the transaction every frame

Leave the connection-scoped `Session`, but wrap each frame:

```python
try:
    ...existing frame handling...
finally:
    session.rollback()   # no-op if a commit already ended the transaction
```

Per §1, `rollback()` on an already-committed session "passes silently", releases
any checked-out connection, and fully expires all objects **regardless of
`expire_on_commit`**. That closes §5.1(a) and the §5.2 cross-frame staleness with
a three-line change and **zero signature churn** — no test edits beyond adding
one. Optionally add `Session(get_engine(), autobegin=False)` as a tripwire so an
un-begun implicit transaction raises instead of silently leaking.

What it does **not** fix: the blocking call on the event loop (§5.1(b)), the
within-one-frame double-read staleness, and the "one Session shared with
whatever DMI-64 might hand to a background task" concurrency rule (§1).

**Use B if DMI-64 is imminent and A cannot be sequenced first; A is still the
destination.**

### Option C — leave as-is

Not defensible. It is safe today only because every DB-touching branch happens to
commit, and one branch already doesn't (§5.1(a)). DMI-64 adds branch-heavy
read-validate-write logic to exactly this function, which is the shape most
likely to add more non-committing returns.

### Independent of session lifetime — do this for DMI-64 regardless

Put the state-transition guard in the write, not in a prior read: conditional
`UPDATE … WHERE id = :id AND status = :expected` with a rowcount check, or
`Session.get(Command, id, with_for_update=True)`, or a version column. Session
scope shrinks the CWE-367 window; only an atomic compare-and-set closes it
(https://cwe.mitre.org/data/definitions/367.html).

### Worth doing whichever option is picked

- Set `pool_size` / `max_overflow` explicitly in `get_engine()` rather than
  inheriting 5/10 silently, so the DoS ceiling is a decision with a number
  attached rather than a default.
- Confirm `SHOW idle_in_transaction_session_timeout;` on the actual Supabase
  project (§5.3, unverified) — and if it is `0`, consider setting it per-role as
  a platform-level backstop against exactly this class of leak.
- Re-check `agent.revoked_at` periodically inside the loop (§5.4).

---

## Sources

Primary:

- SQLAlchemy 2.0 — Session Basics (construct/commit/close FAQ, autobegin, committing, rolling back, closing, "Is the Session a cache?", thread-safety FAQ): https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy 2.0 — Session API (`Session.get`, `expire_on_commit`, `expire_all`, `with_for_update`): https://docs.sqlalchemy.org/en/20/orm/session_api.html
- SQLAlchemy 2.0 — State Management / Refreshing–Expiring: https://docs.sqlalchemy.org/en/20/orm/session_state_management.html
- SQLAlchemy 2.0 — Connection Pooling (`pool_size`, `max_overflow`, `pool_timeout`): https://docs.sqlalchemy.org/en/20/core/pooling.html
- SQLAlchemy 2.0 — Error Messages, "QueuePool limit of size <x> overflow <y> reached": https://docs.sqlalchemy.org/en/20/errors.html#error-3o7r
- PostgreSQL — Client Connection Defaults (`idle_in_transaction_session_timeout`, `transaction_timeout`, `idle_session_timeout`): https://www.postgresql.org/docs/current/runtime-config-client.html
- PostgreSQL — Transaction Isolation (Read Committed default): https://www.postgresql.org/docs/current/transaction-iso.html
- PgBouncer — Features / pooling modes: https://www.pgbouncer.org/features.html
- Supabase — Connecting to Postgres (Shared Pooler 6543, transaction mode, prepared statements): https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase — Connection Management (pool sizing): https://supabase.com/docs/guides/database/connection-management
- Supabase — Supavisor FAQ (pool size, client connections, transaction-mode assignment): https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI
- FastAPI — Dependencies with yield: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- FastAPI — WebSockets (`Depends` in WS endpoints): https://fastapi.tiangolo.com/advanced/websockets/
- FastAPI — Sub-dependencies / dependency caching: https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times
- FastAPI 0.139.0 source — `fastapi/routing.py` (`websocket_session`, `get_websocket_app`) and `fastapi/concurrency.py` (`contextmanager_in_threadpool`): https://github.com/fastapi/fastapi/blob/master/fastapi/routing.py
- CWE-770 Allocation of Resources Without Limits or Throttling: https://cwe.mitre.org/data/definitions/770.html
- CWE-400 Uncontrolled Resource Consumption: https://cwe.mitre.org/data/definitions/400.html
- CWE-367 Time-of-check Time-of-use (TOCTOU) Race Condition: https://cwe.mitre.org/data/definitions/367.html
- CWE-841 Improper Enforcement of Behavioral Workflow: https://cwe.mitre.org/data/definitions/841.html

Internal (secondary, this repo):

- `docs/research/sync-vs-async-db-stack.md` — §5 "Do not hold a DB session across a long-lived WS loop"
- `docs/research/ws-connection-registry-reconnect-race.md` — displaced-handler teardown lag
- `docs/adr/ADR-011-pi-command-channel.md`; `docs/roadmap/BACKEND.md` B4+B5
- `backend/src/api/db/session.py`, `routers/agents.py`, `services/agent_ws.py`, `dependencies/agent_auth.py`

## Explicitly not verified from a primary source

- Whether Supabase sets a non-zero `idle_in_transaction_session_timeout` (or any
  Supavisor-side idle-transaction / client-idle timeout) on managed projects. Not
  in any Supabase doc read here. Check the live project before relying on it.
- Any per-actor or per-tenant sub-quota within a SQLAlchemy pool. SQLAlchemy
  documents no such mechanism; isolation would require a separate `Engine`.
- FastAPI/Starlette **documentation** for WebSocket `yield`-dependency teardown
  timing. The per-connection claim in §4 comes from reading FastAPI 0.139.0
  source, not from the docs.
- The exact reachability of the `agent is None` early return in
  `touch_agent_last_seen` in production (it depends on whether an `agents` row
  can be deleted while a socket is live). The code path exists; the operational
  likelihood was not established.
- CWE-400's exact description text was not fetched (only 770/367/841 were);
  CWE-400 is cited by name/number only.
