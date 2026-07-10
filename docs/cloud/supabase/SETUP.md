# Supabase — setup (DMI-52)

> **Scope (DMI-52):** create the Supabase project, pick the region, capture connection
> details, and wire the env-var split. This is greenfield — the backend app shell (DMI-56)
> and Alembic do **not** exist yet. This doc documents the connection contract now so the
> first migration lands cleanly when the app shell arrives.
>
> **Locked decisions:** [`roadmap/BACKEND.md`](../../roadmap/BACKEND.md) B4/B5 · stack detail
> in [`adr/ADR-009-database-stack.md`](../../adr/ADR-009-database-stack.md).
>
> **Out of scope:** AWS staging, Railway service setup, frontend hosting, running the first
> migration.

---

## Locked constraints (from BACKEND.md B4/B5)

| Topic | Decision |
|-------|----------|
| Provider | **Supabase** (managed Postgres) |
| Runtime (API + worker) | Pooler **6543** — transaction mode (Supavisor) |
| Migrations (Alembic only) | Direct **5432** — session protocol required for DDL |
| Plan | **Free now** — nothing connects to the DB until the app shell (DMI-56). Before September, keep the project active (weekly keep-alive) or upgrade to Pro for backups. Free tier pauses after 7 days idle. |
| Environments | Single **`nspi`** environment for September |
| Region | Same broad region as Railway, closest to operators/Pi — record below |
| SSL | Required on every connection |

> BACKEND.md B4/B5 says "Pro **or keep active** before September". We take the "keep active"
> path: **start on Free now** (the DB is empty until DMI-56), then before September either add
> a weekly keep-alive or upgrade to Pro. ADR-009 also starts on Free — consistent.

---

## Current state of the repo (honest inventory)

| Thing | Status |
|-------|--------|
| Backend app shell (`main.py`, DB session, config) | Exists under `backend/`, but is the **legacy scorer** slated for discard (BACKEND.md B8). Not wired to anything. |
| Alembic | **Does not exist** — no `alembic.ini`, no `migrations/`, not a dependency |
| Async driver | `asyncpg` and `psycopg[binary]` are declared in `backend/pyproject.toml` |
| ORM | `sqlmodel` + `sqlalchemy>=2.0` declared |
| `DATABASE_URL` today | `backend/src/api/core/config.py` defaults to **SQLite**; `db/session.py` even rewrites `asyncpg` → sync `psycopg`. This whole shell is being rebuilt (DMI-56). |
| Toolchain | `uv` (repo root `pyproject.toml`, `uv.lock`) |

**Takeaway:** nothing here connects to Postgres yet. DMI-52 only stands up the Supabase
project and hands the app shell a correct env-var contract to consume later.

---

## Connection methods — what each port is for

Supabase exposes three endpoints. All three reach the same database; they differ in how
connections are managed.

| Method | Host / port | Network | Use for | Prepared statements |
|--------|-------------|---------|---------|---------------------|
| **Transaction pooler** (Supavisor) | `aws-0-<region>.pooler.supabase.com:6543` | IPv4 (all tiers) | **API + worker runtime** — many short-lived connections | **Not supported** — must disable |
| **Session pooler** (Supavisor) | `aws-0-<region>.pooler.supabase.com:5432` | IPv4 (all tiers) | IPv4-only fallback for migrations / long-lived backends | Supported |
| **Direct connection** | `db.<ref>.supabase.co:5432` | IPv6 by default (IPv4 = paid add-on) | **Alembic migrations**, `pg_dump`, admin tools | Supported |

### Why migrations need 5432, not 6543

The transaction pooler (Supavisor in transaction mode) hands each transaction a *different*
physical backend connection. DDL and Alembic's migration transactions assume a stable
session, and asyncpg's server-side prepared statements assume the same connection is reused —
neither holds through a transaction pooler. So:

- **Runtime → 6543 (transaction mode):** the API and worker open/close many transient
  connections; the pooler multiplexes them onto a small backend pool. This is exactly what a
  transaction pooler is good at.
- **Migrations → 5432 (direct or session mode):** Alembic runs DDL in real sessions. Use the
  **direct connection**; if your network/CI is IPv4-only (direct is IPv6-only without the
  add-on), use the **session pooler** on 5432 instead — session mode also holds a stable
  session and supports DDL and prepared statements.

---

## Step-by-step

### 1. Create the organization and project

1. Sign in at <https://supabase.com/dashboard>.
2. Create (or reuse) an **organization** for the team.
3. **New project** → name it for the single September environment, e.g. `nspi`.
4. Set a strong **database password** and store it in the team secret manager immediately —
   the dashboard shows it once. It becomes `[YOUR-PASSWORD]` in every string below.
5. Pick the **region** (next step) before clicking create.
6. Under **Data API Configuration** (advanced), set the three toggles as below.

#### Data API settings

The app **never** uses Supabase's REST layer — the FastAPI backend connects directly to
Postgres (pooler 6543, asyncpg) and the frontend talks to that backend, not to Supabase. So
the public auto-REST API is attack surface we do not want (doubly so for a vuln-scanner product).

| Setting | Choose | Why |
|---------|--------|-----|
| **Data API** | **Disabled** | Auto-generates a public PostgREST API at `https://<ref>.supabase.co/rest/v1/` over every table. We have our own backend + direct DB connection, so it is unused exposure. |
| **Automatically expose new tables** | **Off** (moot once Data API is disabled) | If on, every table Alembic creates is silently published to that public REST API. |
| **Automatic RLS on new tables** | **Enabled** | Free defense-in-depth. The backend connects as the `postgres` role, which **bypasses RLS**, so it never interferes; but if the Data API is ever turned on or a table gets exposed, RLS-on-by-default keeps it locked instead of open. |

> Note (not for DMI-52): connecting as `postgres` is high-privilege. When DMI-56 builds the
> app shell, give the app a dedicated, less-privileged DB role — separate hardening step.

### 2. Pick the region

Criteria (BACKEND.md): **same broad region as Railway, closest to operators/Pi.**

| Consideration | Note |
|---------------|------|
| Railway regions are limited | `us-east`, `us-west`, `eu-west`, `ap-southeast` — Railway has **no South America region**. Supabase must sit in the AWS region matching whichever Railway region you deploy to. |
| Latency | The compute↔DB round trip is paid on **every query** (5–20× per request), so co-locating Supabase with Railway compute dominates the decision. The operator/Pi↔stack hop is paid once per request and is negligible for a background scanner. Optimize for *matching* Railway, not for the absolute closest AWS region to operators. |
| Decision | **`us-east-1` (N. Virginia)** — co-located with Railway `us-east4` (Virginia). This is the "same broad region as Railway" lock; the ~120ms Brazil-based operators pay on their once-per-request HTTP hop is imperceptible for this workload. |

**Chosen region:** `us-east-1` (N. Virginia) — mirrors Railway `us-east4`. Recorded in [`docs/cloud/README.md`](../README.md).

### 3. Set the plan — Free now

- **Stay on Free.** DMI-52 only stands up an empty project; nothing connects until the app
  shell (DMI-56). Free covers everything here at no cost.
- **The one Free-tier catch:** the project **pauses after 7 days of inactivity**. That is
  fine while the DB is empty and unused, but a paused DB = dead API once nspi is live/demoed.
- **Before September, pick one** (do not decide now):
  - **Keep-alive on Free** — a weekly scheduled query (GitHub Action / cron running a trivial
    `SELECT 1`) resets the idle timer. $0. No backups.
  - **Upgrade to Pro ($25/mo)** — no auto-pause **and** daily backups (7-day retention),
    8 GB storage, 250 GB egress. Justify it once nspi holds real scan data you can't regenerate.
- **Tie-breaker:** backups. Free + keep-alive is fine until there's data worth protecting;
  after that, Pro pays for itself.

### 4. Grab the connection strings

Dashboard → **Connect** (top bar). It shows all three modes. Copy:

- **Transaction pooler** (6543) → runtime.
- **Direct connection** (5432) → migrations. (Copy the **Session pooler** 5432 string too if
  you may run migrations from an IPv4-only machine or CI.)

Substitute the SQLAlchemy driver prefix yourself — the dashboard prints bare
`postgres://…`; the app needs `postgresql+asyncpg://…` (runtime) and
`postgresql+psycopg://…` (migrations).

### 5. Wire the env-var split

The app shell (DMI-56) will read two separate URLs. Define both now so the contract is fixed.

```
DATABASE_URL=postgresql+asyncpg://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres

MIGRATION_DATABASE_URL=postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.abcdefghijklmnop.supabase.co:5432/postgres
```

IPv4-only fallback for migrations (session pooler instead of direct):

```
MIGRATION_DATABASE_URL=postgresql+psycopg://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

Notes on the shapes:

- **Username differs by endpoint.** Pooler strings use `postgres.<project-ref>`; the direct
  connection uses bare `postgres`. Copy them verbatim from the dashboard — do not hand-edit.
- **`sslmode` vs `ssl`.** psycopg accepts `?sslmode=require` in the URL. **asyncpg does not
  understand `sslmode`** — pass SSL via `connect_args` on the async engine instead (see
  §6), or use `?ssl=require`. Appending `?sslmode=require` to the asyncpg URL will error.
- Keep both URLs out of git. `backend/.env.example` is a template only; real values live in
  Railway/CI env and the team secret manager.

### 6. App-shell contract (for DMI-56, documented now)

When the shell is built, the runtime engine **must disable prepared statements** (transaction
pooler requirement) and set SSL for asyncpg:

```
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "ssl": "require",
        "timeout": 10,
    },
)
```

Alembic (`env.py`) uses a **separate** sync engine off `MIGRATION_DATABASE_URL` (5432,
psycopg) — no `statement_cache_size` gymnastics needed there because it is not on the
transaction pooler.

### 7. Verify the connection (optional, no app shell required)

With `uv`, from `backend/` you can smoke-test the pooler endpoint without building anything:

```
uv run python -c "import asyncio, asyncpg; asyncio.run(asyncpg.connect('postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres', statement_cache_size=0, ssl='require').close())"
```

A clean exit confirms the pooler host, password, region, and SSL are all correct.

---

## Gotchas & remediation

| Gotcha | Why it bites this project | Remediation (Python / uv / Alembic / asyncpg) |
|--------|---------------------------|-----------------------------------------------|
| **Free-tier pausing** (7 days idle) | Harmless while the DB is empty (now); but once `nspi` is live/demoed, a paused DB = dead API | **Now:** stay on Free, no action needed. **Before September:** add a weekly keep-alive (`SELECT 1` via GitHub Action/cron) to reset the idle timer, **or** upgrade to Pro (also gets backups). |
| **Prepared statements on 6543** | asyncpg uses server-side prepared statements by default; the transaction pooler reassigns connections, so you hit `prepared statement "…" does not exist` | Set `statement_cache_size=0` **and** `prepared_statement_cache_size=0` in the async engine `connect_args` (§6). |
| **Migrations run on the pooler** | If someone points Alembic at 6543, DDL fails or behaves oddly (transaction mode can't hold a session) | Keep migrations on `MIGRATION_DATABASE_URL` (5432, direct/session, psycopg). Never let Alembic read `DATABASE_URL`. |
| **Direct 5432 is IPv6-only** | Direct connect (`db.<ref>.supabase.co`) needs IPv6 unless you buy the IPv4 add-on; many CI runners / office networks are IPv4-only → migration can't connect | Use the **Session pooler** on 5432 (`…pooler.supabase.com`, IPv4, session mode) for migrations — it also supports DDL and prepared statements. |
| **`sslmode` on asyncpg** | Copy-pasting `?sslmode=require` (valid for psycopg) onto the asyncpg URL raises a connect error | Pass `connect_args={"ssl": "require"}` on the async engine, or use `?ssl=require`. Reserve `?sslmode=require` for the psycopg migration URL. |
| **Connection-limit exhaustion** | Small instance = small max connections; the pool must share room with Supabase Auth/Storage/PostgREST | Keep SQLAlchemy `pool_size` small (API ~5–10, worker ~2–5 per ADR-009); leave the Supavisor pool ≤ ~80% of Database Max Connections (less if PostgREST is heavily used). |
| **Wrong username per endpoint** | Pooler needs `postgres.<ref>`, direct needs bare `postgres`; mixing them → auth failure | Copy each string verbatim from Dashboard → Connect; don't reuse one host's username with another host. |
| **Password / URL leakage** | Strings hold the DB password in plaintext | Store only in Railway/CI env + secret manager. `.env` stays gitignored. Rotate via Dashboard → Database → Reset password if exposed (then update both URLs). |

---

## Integrations (accurate scope)

| Integration | Reality for this project |
|-------------|--------------------------|
| **GitHub / Supabase Branching** | Supabase can create preview branches on PRs and run migrations it finds in a `supabase/migrations` directory (Supabase CLI format). This project uses **Alembic**, not the Supabase CLI, so native branching does **not** run our migrations. Skip it for now; keep DB provisioning manual and migrations Alembic-driven. Revisit only if we adopt the Supabase CLI. |
| **Claude Code / Cursor (MCP)** | Supabase ships an official **MCP server** that works with Claude Code and Cursor (read-only mode recommended; auth via a Supabase personal access token). Useful for inspecting schema/data during development. Optional, not required for DMI-52. |
| **Railway** | Out of scope here (B5) — Railway consumes `DATABASE_URL` (6543) as an env var. This doc only produces that value. |

---

## References

- Connecting to Postgres (direct / pooler / session, ports, IPv4/IPv6): <https://supabase.com/docs/guides/database/connecting-to-postgres>
- Connection management & pool sizing: <https://supabase.com/docs/guides/database/connection-management>
- Disabling prepared statements (asyncpg + transaction pooler): <https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL>
- Pricing / plans / pausing: <https://supabase.com/pricing>
- Internal: [`roadmap/BACKEND.md`](../../roadmap/BACKEND.md) B4/B5 · [`adr/ADR-009-database-stack.md`](../../adr/ADR-009-database-stack.md) · [`cloud/README.md`](../README.md)
