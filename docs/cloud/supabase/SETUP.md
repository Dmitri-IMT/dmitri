# Supabase — setup (DMI-52, updated for DMI-56)

> **Scope:** create the Supabase project, pick the region, capture connection details, wire
> the env-var split, and provision the backend's dedicated runtime role. The backend app
> shell and Alembic ([DMI-56](../../../specs/013-backend-app-shell-rebuild/)) now exist and
> own the schema — this doc documents both the one-time project setup and the provisioning
> runbook a fresh `nspi`-equivalent environment (or a rebuild of the current one) follows.
>
> **Locked decisions:** [`roadmap/BACKEND.md`](../../roadmap/BACKEND.md) B4/B5 · stack detail
> in [`adr/ADR-009-database-stack.md`](../../adr/ADR-009-database-stack.md) (superseded on the
> async-vs-sync driver point by the DMI-56 architecture — see below).
>
> **Out of scope:** AWS staging, Railway service setup (see
> [`docs/cloud/railway/SETUP.md`](../railway/SETUP.md)), frontend hosting.

---

## Locked constraints (from BACKEND.md B4/B5)

| Topic | Decision |
|-------|----------|
| Provider | **Supabase** (managed Postgres) |
| Runtime (API + worker) | Pooler **6543** — transaction mode (Supavisor), connecting as the dedicated `dmitri_runtime` login (not `postgres`) |
| Migrations (Alembic only) | Direct **5432**, or the **Session pooler on 5432** from an IPv4-only network (direct is IPv6-only — see the gotcha below), connecting as the administrative `postgres` login |
| Plan | **Free** is fine while the DB stays small; before real, hard-to-regenerate scan data accumulates, either add a weekly keep-alive or upgrade to Pro (see Step 3) |
| Environments | Single **`nspi`** environment |
| Region | `us-east-1` (N. Virginia), matching Railway `us-east4` — see Step 2 |
| SSL | Required on every connection (`?sslmode=require`) |

---

## Current state of the repo (honest inventory)

| Thing | Status |
|-------|--------|
| Backend app shell (`main.py`, DB session, config) | DMI-56 shell: minimal FastAPI app, health-only route, sync SQLModel session over psycopg3. No business routes, no auth. |
| Alembic | Sole owner of the schema. `backend/alembic.ini`, `backend/alembic/env.py`, one baseline revision (`backend/alembic/versions/20260715_01_baseline.py`). |
| Driver | **psycopg3** everywhere — API, worker, and Alembic. `asyncpg` is not a dependency; sync `Session` only, no async engine. |
| `DATABASE_URL` | Required `SecretStr` in `api.core.config.Settings`; no SQLite default, no fallback. |
| Toolchain | `uv` (`backend/pyproject.toml`, `backend/uv.lock`) |

**DB-access style (human-approved, binding):** sync everywhere. This supersedes ADR-009's
"Driver assíncrono: asyncpg" section and its `connect_args={"timeout": 10}` example (the
psycopg3 equivalent used by the shipped code is `connect_timeout`); the ADR itself is left
unedited by instruction.

---

## Connection methods — what each port is for

Supabase exposes three endpoints. All three reach the same database; they differ in how
connections are managed.

| Method | Host / port | Network | Use for | Prepared statements |
|--------|-------------|---------|---------|---------------------|
| **Transaction pooler** (Supavisor) | `aws-0-<region>.pooler.supabase.com:6543` | IPv4 (all tiers) | **API + worker runtime**, as `dmitri_runtime` — many short-lived connections | **Not supported** — the shipped engine sets `prepare_threshold=None` to disable them |
| **Session pooler** (Supavisor) | `aws-0-<region>.pooler.supabase.com:5432` | IPv4 (all tiers) | **The working IPv4 path for `DATABASE_URL_DIRECT`** — migrations, `psql`, admin tools, from any IPv4-only network | Supported |
| **Direct connection** | `db.<ref>.supabase.co:5432` | **IPv6-only** — confirmed: this host does not resolve on an IPv4-only network, no add-on toggle observed to change that | Admin tools, only from an IPv6-capable network | Supported |

### Why migrations need 5432, not 6543

The transaction pooler (Supavisor in transaction mode) hands each transaction a *different*
physical backend connection. DDL and Alembic's migration transactions assume a stable
session — that does not hold through a transaction pooler. So:

- **Runtime → 6543 (transaction mode):** the API and worker open/close many transient
  connections; the pooler multiplexes them onto a small backend pool.
- **Migrations → 5432, `DATABASE_URL_DIRECT`:** Alembic runs DDL in a real session. Use the
  **Session pooler on 5432** unless you have a confirmed IPv6 path to
  `db.<ref>.supabase.co:5432` — in practice, for this project's network, the Session pooler
  is the working option.

---

## Step-by-step: project setup (one-time)

### 1. Create the organization and project

1. Sign in at <https://supabase.com/dashboard>.
2. Create (or reuse) an **organization** for the team.
3. **New project** → name it for the environment, e.g. `nspi`.
4. Set a strong **database password** for the `postgres` (administrative) role and store it
   in the team secret manager immediately — the dashboard shows it once.
5. Pick the **region** (Step 2) before clicking create.
6. Under **Data API Configuration** (advanced), set the toggles below.

#### Data API settings

The app never uses Supabase's REST layer — the FastAPI backend connects directly to
Postgres. The public auto-REST API is attack surface we do not want.

| Setting | Choose | Why |
|---------|--------|-----|
| **Data API** | **Disabled** | Auto-generates a public PostgREST API over every table; unused exposure. |
| **Automatically expose new tables** | **Off** | Moot once Data API is disabled. |
| **Automatic RLS on new tables** | **Enabled** | Defense-in-depth. The DMI-56 baseline migration also explicitly enables RLS (without policies) and revokes `anon`/`authenticated` privileges on every application table as migration DDL — this dashboard default is a backstop, not the source of truth. |

### 2. Pick the region

**Chosen region:** `us-east-1` (N. Virginia) — mirrors Railway `us-east4`. The
compute↔DB round trip is paid on every query, so co-locating Supabase with Railway compute
dominates the decision. Recorded in [`docs/cloud/README.md`](../README.md).

### 3. Set the plan

- **Free** is fine while the DB is small. The one catch: the project **pauses after 7 days
  of inactivity** — harmless while idle, but a paused DB is a dead API once the deployment is
  live/demoed.
- **Before that matters, pick one:** a weekly keep-alive (`SELECT 1` via a scheduled job) to
  reset the idle timer, **or** upgrade to Pro ($25/mo — no auto-pause, daily backups).

### 4. Grab the administrative connection string

Dashboard → **Connect** → **Session pooler** (5432). This is the `postgres` administrative
login used only for `DATABASE_URL_DIRECT`; it is never wired into Railway.

---

## Provisioning `dmitri_runtime` and applying the baseline (per environment)

This is the human runbook `ARCHITECTURE.md` marks `HUMAN_INFRA_REQUIRED`: confirming the
hosted Postgres major version, applying the baseline migration with the administrative
credential, assigning the runtime role's password interactively, and handing Railway only
the restricted pooled URL. Do this once per environment (or again after a full rollback).

### 1. Pre-flight

Connect with `psql` using the Session pooler string (username `postgres.<project-ref>`,
port 5432) and check three things before running any migration:

```sql
SHOW server_version;                                            -- must start with 17
SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user;  -- must be true
SELECT 1 FROM pg_roles WHERE rolname = 'dmitri_runtime';         -- must return no rows
```

- **PG17 check:** the baseline assumes Postgres 17 behavior.
- **BYPASSRLS check:** PG16+ only allows `CREATE ROLE ... BYPASSRLS` from a superuser or a
  role that itself holds `BYPASSRLS`. Supabase's `postgres` is not a true superuser but does
  carry `BYPASSRLS` on a healthy project; if this returns `false`, the migration's
  `CREATE ROLE dmitri_runtime ... BYPASSRLS` will be refused by Supabase's `supautils`
  extension — treat that as a spec amendment situation (fall back to explicit permissive
  policies for `dmitri_runtime`), not something to route around locally.
- **Absent-role check:** the baseline creates `dmitri_runtime` unconditionally and fails
  rather than adopt a pre-existing role of that name. A non-empty result here means unexpected
  drift; resolve it before migrating.

### 2. Apply the baseline

Export `DATABASE_URL_DIRECT` in the shell only — never write it to `.env` or a Railway
variable — run the migration, then unset it:

```bash
cd backend
export DATABASE_URL_DIRECT=postgresql+psycopg://postgres.<project-ref>:<ADMIN-PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
uv run alembic upgrade head
unset DATABASE_URL_DIRECT
```

The hosted database is empty before this feature, so this is a plain `alembic upgrade head`
— no stamping of pre-existing tables. This creates the 14 application tables with RLS
enabled and no policies, revokes `anon`/`authenticated` privileges, and creates
`dmitri_runtime LOGIN PASSWORD NULL BYPASSRLS` with only `CONNECT` + `USAGE` + table
`SELECT`/`INSERT`/`UPDATE` + sequence `USAGE`/`SELECT` — no ownership, no admin attributes.

### 3. Assign the runtime password interactively

Never assign the password with an `ALTER ROLE ... PASSWORD '...'` SQL literal — it would sit
in shell/SQL history and in any pasted transcript. Use `psql`'s interactive prompt instead:

```bash
psql "postgresql://postgres.<project-ref>:<ADMIN-PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
```

then, at the `psql` prompt:

```
\password dmitri_runtime
```

Enter and confirm a freshly generated high-entropy password at the two interactive prompts.
Neither prompt echoes the value, and no SQL statement carrying the password is ever typed,
logged, or scrolled back through.

### 4. URL-encode the password and build the sealed runtime URL

Pooler DSNs are URLs — a generated password containing `@`, `:`, `/`, `%`, or similar must be
percent-encoded before it goes in the connection string, or the URL parses wrong. Use Python
rather than hand-encoding:

```bash
python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" '<raw-generated-password>'
```

Build the final runtime URL with the encoded password, the `dmitri_runtime.<project-ref>`
username, the **6543 transaction pooler**, and `sslmode=require`:

```
postgresql+psycopg://dmitri_runtime.<project-ref>:<URL-ENCODED-PASSWORD>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

This is the only value that goes into Railway's `DATABASE_URL` (sealed, both services) — see
[`docs/cloud/railway/SETUP.md`](../railway/SETUP.md) for the exact `railway variable set`
commands. The plaintext password itself never appears in a migration, command example, test,
shell/SQL history entry, or tracked file; only the already-encoded value travels into the
sealed Railway variable.

---

## Rollback: stop / drain / downgrade / verify

Hosted rollback is also a human operation, and it is quiescent by design — the API and worker
must never run while their tables and login are being dropped.

1. **Stop** both Railway services (`api` and `worker`) — see
   [`docs/cloud/railway/SETUP.md`](../railway/SETUP.md#rollback) for the exact CLI commands.
2. **Drain** — wait for their pooled sessions on the Supabase side to close (a short pause
   after both services report stopped is normally enough; the Supabase dashboard's
   connection-pool view can confirm no `dmitri_runtime` sessions remain).
3. **Downgrade** — export the locally held administrative `DATABASE_URL_DIRECT` (Session
   pooler, 5432, `postgres` login — never the runtime credential, which cannot alter schema),
   run the reversal, then unset the variable:

   ```bash
   cd backend
   export DATABASE_URL_DIRECT=postgresql+psycopg://postgres.<project-ref>:<ADMIN-PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
   uv run alembic downgrade base
   unset DATABASE_URL_DIRECT
   ```

4. **Verify** — confirm the 14 application tables and `dmitri_runtime` are gone (only
   Alembic's own `alembic_version` bookkeeping table may remain):

   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname = 'public';
   SELECT 1 FROM pg_roles WHERE rolname = 'dmitri_runtime';  -- must return no rows
   ```

Only restart the Railway services once a compatible schema (a fresh `alembic upgrade head`)
is in place — they must never run against a dropped or partially-migrated schema.

This exact sequence — pre-flight, `alembic upgrade head`, interactive `\password`, and
`stop`/`drain`/`downgrade`/`verify` — is rehearsed against the local `supabase start` stack
(`postgresql://postgres:postgres@127.0.0.1:54322/postgres`, scratch database) as part of the
DMI-56 Task 9 verification; see `specs/013-backend-app-shell-rebuild/POOP.md` for that run's
evidence.

---

## Gotchas & remediation

| Gotcha | Why it bites this project | Remediation |
|--------|---------------------------|--------------|
| **Free-tier pausing** (7 days idle) | A paused DB is a dead API once live/demoed | Add a weekly keep-alive (`SELECT 1`), or upgrade to Pro. |
| **Prepared statements on 6543** | Transaction-mode pooling reassigns physical connections mid-session, breaking server-side prepared statements | The shipped engine (`api.db.session.get_engine`) always sets `connect_args={"prepare_threshold": None, "connect_timeout": 10}` — this is not optional/tunable per deployment. |
| **Migrations run on the pooler (6543)** | DDL needs a stable session; transaction mode can't hold one | `alembic/env.py` reads only `DATABASE_URL_DIRECT` from `os.environ` and never falls back to `DATABASE_URL` — there is no path for migrations to accidentally hit 6543. |
| **Direct 5432 is IPv6-only** | `db.<ref>.supabase.co` does not resolve on an IPv4-only network — confirmed against this project; no free add-on flips it to IPv4 | Use the **Session pooler** on 5432 (`aws-0-<region>.pooler.supabase.com`, username `postgres.<project-ref>`) for `DATABASE_URL_DIRECT` instead. |
| **`sslmode` in the URL** | psycopg3 reads `?sslmode=require` from the URL itself (not `connect_args`) | Always append `?sslmode=require` to both `DATABASE_URL` and `DATABASE_URL_DIRECT`. |
| **Wrong username per endpoint** | Pooler endpoints need `<role>.<project-ref>` (e.g. `dmitri_runtime.<project-ref>`); the direct/session-pooler admin login is bare `postgres` unless using the pooler form `postgres.<project-ref>` | Copy usernames exactly per the shapes documented above; don't mix a pooler username with the direct host or vice versa. |
| **Password in a `.env` or Railway `DATABASE_URL_DIRECT` variable** | `DATABASE_URL_DIRECT` must never be configured on, referenced by, or exposed to either long-running Railway service | It is exported transiently from the operator's gitignored local `.env` for a single Alembic command, then unset. Grep hosted `railway variable list --json` output for `DATABASE_URL_DIRECT` after any provisioning pass — it must show nothing. |
| **Password-bearing SQL in history** | An `ALTER ROLE dmitri_runtime PASSWORD '...'` statement lands in shell/SQL history and any pasted transcript | Always use the interactive `\password dmitri_runtime` prompt (Step 3 above), never an `ALTER ROLE` literal. |
| **Connection-limit exhaustion** | Small instance = small max connections, shared with Supabase Auth/Storage | Keep SQLAlchemy pool sizes small; leave the Supavisor pool comfortably under the Database Max Connections limit. |

---

## Integrations (accurate scope)

| Integration | Reality for this project |
|-------------|--------------------------|
| **GitHub / Supabase Branching** | This project uses **Alembic**, not the Supabase CLI, so native branching does not run our migrations. Keep DB provisioning manual and migrations Alembic-driven. |
| **Claude Code / Cursor (MCP)** | Supabase ships an official MCP server (read-only mode recommended) — useful for inspecting schema/data during development. Optional. |
| **Railway** | Consumes the sealed `DATABASE_URL` (6543, `dmitri_runtime`) as an env var; never `DATABASE_URL_DIRECT`. See [`docs/cloud/railway/SETUP.md`](../railway/SETUP.md). |

---

## References

- Connecting to Postgres (direct / pooler / session, ports, IPv4/IPv6): <https://supabase.com/docs/guides/database/connecting-to-postgres>
- Connection management & pool sizing: <https://supabase.com/docs/guides/database/connection-management>
- Pricing / plans / pausing: <https://supabase.com/pricing>
- Internal: [`roadmap/BACKEND.md`](../../roadmap/BACKEND.md) B4/B5 · [`adr/ADR-009-database-stack.md`](../../adr/ADR-009-database-stack.md) · [`cloud/README.md`](../README.md) · [`specs/013-backend-app-shell-rebuild/ARCHITECTURE.md`](../../../specs/013-backend-app-shell-rebuild/ARCHITECTURE.md)
