# Research: sync-everywhere DB stack vs asyncpg/async SQLAlchemy

> **Location note:** the repo had no existing convention for research notes
> (no `docs/research/`, `notes/`, or similar existed as of 2026-07-14), so this
> file establishes `docs/research/` as the location for them.

**Question.** Is "sync everywhere" — synchronous SQLModel `Session` + psycopg v3
driver, FastAPI sync `def` routes running in the threadpool — a sound
architectural choice for a low-traffic FastAPI + Postgres MVP, versus
asyncpg/async SQLAlchemy sessions?

**Traffic profile assumed.** One Raspberry Pi agent posting one bulk scan
payload per completed scan (~1 scan/day/site), a handful of dashboard readers,
a background worker polling a jobs table with `FOR UPDATE SKIP LOCKED`,
Postgres on Supabase (runtime via Supavisor transaction-mode pooler on 6543,
Alembic via direct 5432), and a future WebSocket command channel in the same
app. Existing enrichment/scoring domain code is sync SQLModel.

---

## TL;DR verdict

**Yes — sync-everywhere is sound for this profile, with three caveats.**

- The concurrency ceiling of a sync FastAPI app is `min(threadpool tokens,
  SQLAlchemy pool)` = `min(40, 5+10=15)` concurrent DB-touching requests per
  worker process by default. This traffic profile needs low single digits.
  It is also the stack FastAPI's own docs steer you to when unsure ("If you
  just don't know, use normal `def`"), and the SQLAlchemy author's published
  position is that threads beat asyncio for CRUD-style DB work anyway.
- **Caveat 1 (mandatory):** disable psycopg3's automatic prepared statements
  on the 6543 engine (`connect_args={"prepare_threshold": None}`) — Supabase's
  transaction-mode pooler does not support prepared statements.
- **Caveat 2 (design rule):** the future WebSocket endpoint **must** be
  `async def` (Starlette does not threadpool sync WS endpoints), and it must
  call the sync DB code via `run_in_threadpool` / `anyio.to_thread.run_sync`.
  Those calls share the same default 40-token thread limiter as all sync
  routes, so long-blocking work inside WS handlers eats route capacity.
- **Caveat 3 (migration hedge):** going async later is a mechanical but
  nontrivial rewrite — `await` on every session call plus eliminating all
  lazy-loading/implicit-IO points (`MissingGreenlet`). Keeping relationship
  access eager/explicit now keeps that door cheap. The asyncpg-specific
  PgBouncer prepared-statement workarounds (UUID statement names + `NullPool`)
  are a point *against* asyncpg on this Supabase setup, not for it.

---

## Findings

### 1. FastAPI threadpool behavior for sync routes

- **Where the threadpool lives.** Starlette's `run_in_threadpool` is a
  two-line wrapper over `anyio.to_thread.run_sync` with no limiter argument
  and no Starlette-level thread limit — capacity is entirely anyio's default
  limiter. Verified in source:
  `https://github.com/encode/starlette/blob/master/starlette/concurrency.py`
  (`return await anyio.to_thread.run_sync(func)`).
- **Default capacity: 40 tokens.** AnyIO docs, "Adjusting the default maximum
  worker thread count": "The default AnyIO worker thread limiter has a value
  of **40**, meaning that any calls to `to_thread.run_sync()` without an
  explicit `limiter` argument will cause a maximum of 40 threads to be
  spawned." — https://anyio.readthedocs.io/en/stable/threads.html
- **Tunable.** Same page: set
  `anyio.to_thread.current_default_thread_limiter().total_tokens = 60` (from
  async context, e.g. FastAPI lifespan).
- **FastAPI's documented behavior and guidance.** "When you declare a *path
  operation function* with normal `def` instead of `async def`, it is run in
  an external threadpool that is then awaited, instead of being called
  directly (as it would block the server)." And, for blocking libraries
  without `await` support / when unsure: "If you just don't know, use normal
  `def`." — https://fastapi.tiangolo.com/async/

### 2. Concurrency math

- **Per-process request ceiling:** 40 concurrent sync-route executions
  (anyio default limiter, above). Note this limiter is shared by *everything*
  Starlette/FastAPI threadpools: sync routes, sync dependencies, and any
  explicit `run_in_threadpool` calls.
- **Per-process DB ceiling:** SQLAlchemy's default `QueuePool` holds
  `pool_size=5` with `max_overflow=10` ("The size of the pool to be
  maintained, defaults to 5"; overflow "defaults to 10") — i.e. at most 15
  concurrent DB connections per engine/process; the 16th concurrent
  DB-touching request waits (up to `pool_timeout`, default 30 s). —
  https://docs.sqlalchemy.org/en/20/core/pooling.html
- **So the binding constraint** for a sync app is `min(40, 15) = 15`
  concurrent DB transactions per worker process. For ~1 bulk POST/day/site +
  a few dashboard readers + one polling worker, expected concurrency is < 5.
  Headroom is orders of magnitude.
- **Supabase side.** Per compute tier ("recommended values"), Nano/Micro:
  direct `max_connections` 60, pooler max client connections 200 (scaling up
  to 500 direct / 12,000 pooler clients at 16XL). —
  https://supabase.com/docs/guides/platform/compute-and-disk
  Pool-size guidance: "if you are heavily using the PostgREST database API,
  you should be conscientious about raising your pool size past 40% of the
  Database Max Connections. Otherwise, you can commit 80% to the pool." —
  https://supabase.com/docs/guides/database/connection-management
  Pool size and max client connections are adjustable in the dashboard. —
  https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI
  A FastAPI app holding ≤15 client connections against a 200-client pooler
  limit is nowhere near any limit.

### 3. PgBouncer/Supavisor transaction-mode compatibility

- **Supabase's flat rule:** "Transaction mode does not support prepared
  statements. To avoid errors, turn off prepared statements for your
  connection library." Direct 5432 is what they recommend for migrations
  ("client applications like pg_dump, migrations, backup-restore"). —
  https://supabase.com/docs/guides/database/connecting-to-postgres
- **psycopg3 (sync driver chosen here):** auto-prepares "after it is executed
  more than `Connection.prepare_threshold` times on a connection" (default 5);
  "You can disable the use of prepared statements on a connection by setting
  its `prepare_threshold` attribute to `None`." On poolers: "Unless a
  connection pooling middleware explicitly declares otherwise, they are not
  compatible with prepared statements." (psycopg 3.2+ can use prepared
  statements through real PgBouncer ≥ 1.22 with `max_prepared_statements > 0`
  and libpq ≥ 17 — but Supabase's pooler is Supavisor and its docs say turn
  them off, so disable.) —
  https://www.psycopg.org/psycopg3/docs/advanced/prepare.html
  With SQLAlchemy: `create_engine(..., connect_args={"prepare_threshold": None})`
  on the 6543 engine. That single kwarg is the entire psycopg3 story.
- **asyncpg (the alternative):** SQLAlchemy's asyncpg dialect docs carry a
  dedicated "Prepared Statement Name with PgBouncer" section: asyncpg caches
  prepared statements (default cache 100/connection); to run through
  transaction-mode PgBouncer you must set `prepared_statement_cache_size=0`
  and/or supply `prepared_statement_name_func=lambda: f"__asyncpg_{uuid4()}__"`,
  and "When using PgBouncer, to prevent a buildup of useless prepared
  statements in your application, it's important to use the `NullPool` pool
  class, and to configure PgBouncer to use `DISCARD`". —
  https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.asyncpg
  i.e. asyncpg on this exact Supabase setup requires *more* workarounds than
  psycopg3, and loses client-side pooling (`NullPool`) in the documented
  recipe.
- **NullPool vs QueuePool behind an external pooler:** SQLAlchemy's core
  pooling docs contain **no** general "use NullPool behind PgBouncer" rule
  (verified against https://docs.sqlalchemy.org/en/20/core/pooling.html); the
  `NullPool` recommendation is specific to the asyncpg dialect page above.
  With psycopg3 and prepared statements disabled, the default `QueuePool` is
  compatible with transaction-mode pooling; idle client connections merely
  occupy a few of the 200 pooler client slots.

### 4. SQLModel async support maturity

- **Code exists, docs don't.** SQLModel ships
  `sqlmodel.ext.asyncio.session.AsyncSession` — a ~100-line subclass of
  SQLAlchemy's `sqlalchemy.ext.asyncio.AsyncSession` whose sole addition is a
  typed `exec()` (three overloads for `Select`/`SelectOfScalar`/`UpdateBase`)
  plus a deprecation shim on `execute()`. —
  https://github.com/fastapi/sqlmodel/blob/main/sqlmodel/ext/asyncio/session.py
- The official Advanced User Guide documents only Decimal and UUID topics and
  says async is future work: "At some point it will include: How to use
  `async` and `await` with the async session. …" —
  https://sqlmodel.tiangolo.com/advanced/
- So async SQLModel is a thin, undocumented wrapper: usable, but you are
  effectively writing SQLAlchemy-async against SQLAlchemy's docs, not
  SQLModel's. Sync SQLModel is the documented, first-class path — another
  point for lifting the existing sync domain code unchanged.

### 5. WebSockets in the same app

- **Coexistence is fine and by design.** FastAPI runs `async def` endpoints on
  the event loop and `def` endpoints in the threadpool within the same app
  (https://fastapi.tiangolo.com/async/). All WebSocket examples in FastAPI's
  docs are `async def`, and `Depends`/`Cookie`/`Query` etc. work in WS
  endpoints — https://fastapi.tiangolo.com/advanced/websockets/
- **WS endpoints must be async.** Starlette source: HTTP `request_response`
  wraps non-async callables with `functools.partial(run_in_threadpool, func)`,
  but `websocket_session` is typed `Callable[[WebSocket], Awaitable[None]]`
  and does **no** threadpool wrapping (it even carries a commented-out
  `assert asyncio.iscoroutinefunction(func), "WebSocket endpoints must be
  async"`). —
  https://github.com/encode/starlette/blob/master/starlette/routing.py
- **Pattern for sync DB from a WS handler:** offload with
  `starlette.concurrency.run_in_threadpool(sync_fn, ...)` (re-exported as
  `fastapi.concurrency.run_in_threadpool`), which is exactly
  `await anyio.to_thread.run_sync(...)` —
  https://github.com/encode/starlette/blob/master/starlette/concurrency.py,
  https://anyio.readthedocs.io/en/stable/threads.html
  Budget note: these offloaded calls draw from the same default 40-token
  limiter as sync routes. Do not hold a DB session across a long-lived WS
  loop — check out a session per message/command inside the threadpool call.

### 6. Migration cost to async later

- **API surface:** `AsyncSession` mirrors `Session` "with full ORM
  functionality" in 2.0 style; the mechanical change is `await` on
  `execute()`/`commit()`/`refresh()` etc. and `create_async_engine` +
  `async_sessionmaker`. The extension "also depends upon the greenlet
  library." — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **The real cost is implicit IO:** under asyncio "the application needs to
  avoid any points at which IO-on-attribute access may occur." Violations
  raise `MissingGreenlet` ("greenlet_spawn has not been called; can't call
  await_only() here"), which "when using the ORM … is nearly always due to
  the use of lazy loading, which is not directly supported under asyncio
  without additional steps." —
  https://docs.sqlalchemy.org/en/20/errors.html#error-xd2s
  Documented mitigations ("Preventing Implicit IO when Using AsyncSession"):
  eager loading (`selectinload()`), the `AsyncAttrs` mixin /
  `awaitable_attrs`, `AsyncSession.run_sync()`, write-only relationships. —
  https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Estimate for this codebase:** query/commit call sites are a rote
  find-and-await pass; the risk surface is every relationship attribute
  access in the enrichment/scoring engine. If the sync code is written today
  with explicit eager loading, a later async port is days, not weeks. Note
  `run_sync()` also offers a halfway house: an async app can run the whole
  sync engine unchanged inside one awaitable.

### 7. Maintainer guidance: when is sync the right default?

- **FastAPI (tiangolo):** "If you just don't know, use normal `def`" — and the
  framework's whole threadpool design exists so blocking code "won't block
  the server." Sync routes are a supported first-class mode, not a legacy
  one. — https://fastapi.tiangolo.com/async/
- **Mike Bayer (SQLAlchemy author), "Asynchronous Python and Databases":**
  for pooled, low-latency database access, "calls to your database … do not
  typically produce an IO bound effect" — Python interpreter overhead
  dominates; his benchmarks showed threads outperforming asyncio (~22k vs
  8–10k rows/sec) for CRUD work, and he argues correctness under concurrency
  comes from ACID transactions and row locks, not from an event loop. His
  recommendation: use threads for CRUD-style DB work; reserve asyncio for
  genuinely slow/idle connections (chat servers, many long-lived sockets). —
  https://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/
  (2015, but this remains the design rationale behind SQLAlchemy's
  greenlet-bridged asyncio extension.)
- The one workload class in this app that *is* Bayer's "long-lived socket"
  case — the WS command channel — is exactly the part that will be
  `async def` regardless (finding 5). Async where the sockets are, sync where
  the database is.

---

## Decision inputs (concrete numbers)

| Input | Value | Source |
|---|---|---|
| Starlette/FastAPI sync-route threadpool | anyio default limiter, **40 tokens**, tunable via `current_default_thread_limiter().total_tokens` | anyio docs (threads.html); starlette/concurrency.py |
| SQLAlchemy QueuePool defaults | `pool_size=5`, `max_overflow=10` → **15 conns/process max**, `pool_timeout` 30 s | docs.sqlalchemy.org/en/20/core/pooling.html |
| Effective sync concurrency ceiling | `min(40, 15)` = **15** DB-touching requests/process | derived from the two above |
| Supabase Nano/Micro limits | 60 direct `max_connections`; **200** pooler client connections; pool size configurable (~40–80% of max conns guidance) | supabase compute-and-disk; connection-management |
| Supavisor transaction mode (6543) | **No prepared statements** — "turn off prepared statements for your connection library"; migrations via direct 5432 | supabase connecting-to-postgres |
| psycopg3 fix | `connect_args={"prepare_threshold": None}` (auto-prepare default threshold: 5) | psycopg3 advanced/prepare.html |
| asyncpg on same pooler | needs `prepared_statement_cache_size=0` + UUID `prepared_statement_name_func` + `NullPool` per SQLAlchemy dialect docs | sqlalchemy asyncpg dialect docs |
| SQLModel async | `sqlmodel.ext.asyncio.session.AsyncSession` exists (~100-line typed wrapper) but is **undocumented**; docs list async as future work | sqlmodel repo; sqlmodel.tiangolo.com/advanced/ |
| WebSocket endpoints | must be `async def` (Starlette does not threadpool WS endpoints); call sync DB via `run_in_threadpool` (shares the 40-token limiter) | starlette/routing.py; fastapi advanced/websockets |
| Async port cost driver | `MissingGreenlet` on any lazy load; mitigate now with explicit eager loading | sqlalchemy errors.html#error-xd2s; orm/extensions/asyncio.html |
