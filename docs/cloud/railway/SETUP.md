# Railway — setup (API, worker + frontend)

> **Scope:** DMI-52 stood up the Railway project for `nspi` with the backend services
> (`api` and `worker`); [DMI-56](../../../specs/013-backend-app-shell-rebuild/) wired both to
> their real shell entry points. DMI-91 adds the hosted frontend static service and its
> browser-to-API configuration. **No AWS** here — see
> [`BACKEND.md` B4/B5](../../roadmap/BACKEND.md#b4--b5--hosted-stack-).
>
> **Locked decisions honored:** three services `api` + `worker` + `frontend`; single `nspi`
> environment; region matches Supabase; Postgres lives on **Supabase**, not Railway (Railway
> connects via env vars, restricted `dmitri_runtime` login, transaction pooler **6543** at
> runtime).
>
> **Current state of the repo:** `api` and `worker` build and deploy from `backend/` (Root
> Directory `/backend`) and start through their real entry points. The `frontend` service
> builds the Vite SPA from `/frontend` and publishes `dist/` as a Railway static site. See
> [`specs/013-backend-app-shell-rebuild/ARCHITECTURE.md`](../../../specs/013-backend-app-shell-rebuild/ARCHITECTURE.md)
> for the backend shell contract.

## What this doc delivers

| Deliverable | Status |
|-------------|--------|
| Railway project + `nspi` environment | Created |
| `api` service (web/HTTP), Root Directory `/backend`, config `backend/railway.api.toml` | Deployed, real entry point |
| `worker` service (background job runner), Root Directory `/backend`, config `backend/railway.worker.toml` | Deployed, real entry point |
| `frontend` service (Railway static site), Root Directory `/frontend`, output `dist/` | Required by DMI-91 |
| Region selected (matches Supabase) | Set |
| Restricted pooled `DATABASE_URL` (`dmitri_runtime`, 6543 transaction pooler) wired into both backend services | Documented below — apply with the CLI commands in [Provisioning the runtime variables](#provisioning-the-runtime-variables) |
| `DATABASE_URL_DIRECT` on either backend service | **Forbidden** — see [Provisioning the runtime variables](#provisioning-the-runtime-variables) |

## The services

| Service | Role | Public domain? | Health check? | Replicas |
|---------|------|----------------|---------------|----------|
| `api` | FastAPI web service. Serves the contracted health route `GET /api/v1/health` (`uvicorn api.main:app --host 0.0.0.0 --port $PORT`). No business routes in this shell. | **Yes** — needed for the public URL | **Yes** — `/api/v1/health` | **1** (ADR-011: single API replica for NSPi) |
| `worker` | Background job runner (`python -m api.worker_main` → `api.services.worker`; enrichment poll loop, `FOR UPDATE SKIP LOCKED` against Supabase). No inbound traffic. | **No** | **No** — nothing to probe over HTTP | 1 |
| `frontend` | Railway static site serving the Vite build from `dist/`; every route must fall back to `index.html`. | **Yes** — generated Railway domain | **No** — static hosting | N/A |

The `api` and `worker` services deploy from the **same repo**, Root Directory `/backend`; they
differ only by config file (`railway.api.toml` / `railway.worker.toml`) and therefore start
command. The `frontend` service uses Root Directory `/frontend` and the Vite build output.

## Prerequisites

1. A Railway account with access to project `Dmitri` (`2b6b51c6-f5b7-4979-87f9-296e36a55896`),
   environment `nspi`.
2. The Railway CLI installed and authenticated (`railway login`, then `railway whoami`).
3. The Supabase project's `dmitri_runtime` runtime password, already assigned via the
   interactive `\password` flow in
   [`docs/cloud/supabase/SETUP.md`](../supabase/SETUP.md#3-assign-the-runtime-password-interactively)
   and URL-encoded per that doc's Step 4. This doc never repeats or stores that password —
   every command below uses the placeholder `<DMITRI_RUNTIME_PASSWORD>`.

## Region

**`us-east4` (Virginia)** — co-located with Supabase `us-east-1` (N. Virginia). Set once per
service in **Settings → Region**; both `api` and `worker` already use it.

## Build system

The `api` and `worker` services build with **Railpack** (Railway's default builder) reading
`backend/pyproject.toml` + `backend/uv.lock` — no Dockerfile, no build command. Root Directory
`/backend` on both services makes this the build context; Config Path is set absolute from the
repo root (`/backend/railway.api.toml`, `/backend/railway.worker.toml` — the config path does
**not** follow Root Directory).

## Frontend static service (DMI-91)

Configure the `frontend` service in the `nspi` environment with:

| Setting | Value |
|---------|-------|
| Source | Same repository as `api` and `worker` |
| Root Directory | `/frontend` |
| Builder | Dockerfile |
| Dockerfile path | `/frontend/Dockerfile` |
| Build stage | `npm ci --legacy-peer-deps && npm run build` |
| Build output | `dist` |
| Runtime server | Caddy, listening on Railway's `$PORT` |
| SPA fallback | `try_files {path} /index.html` |
| `VITE_API_URL` | Public `api` service URL, without `/api/v1` |

`frontend/Dockerfile` builds the Vite bundle and copies `dist/` into Caddy. `frontend/Caddyfile`
serves static assets and falls back to `index.html` for React Router deep links.
The Dockerfile declares `VITE_API_URL` as a build argument and exports it during the Vite build;
Railway service variables are available to the Docker build when declared this way.

Set the API service's `CORS_ALLOWED_ORIGINS` to the local development origin plus the
generated public `frontend` origin. Do not use `*`:

```text
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<frontend-service-domain>
```

`VITE_API_URL` is required at build time. The Vite config and frontend API client fail when it
is missing instead of defaulting to localhost.

## Config-as-code (`railway.*.toml`)

`backend/railway.api.toml`:

```toml
[build]
builder = "RAILPACK"
watchPatterns = ["backend/**"]

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 300
restartPolicyType = "ALWAYS"
```

`backend/railway.worker.toml`:

```toml
[build]
builder = "RAILPACK"
watchPatterns = ["backend/**"]

[deploy]
startCommand = "python -m api.worker_main"
restartPolicyType = "ALWAYS"
```

`api` binds `0.0.0.0:$PORT` (Railway injects `$PORT`; the health check uses it too) and Railway
probes the contracted `/api/v1/health` route — it returns `200` only after a live
`SELECT 1` round-trip through the configured `DATABASE_URL`, and `503` if the database is
unreachable. `worker` has no `healthcheckPath` and binds no port by design — it is an
independently runnable background process with no inbound traffic.

## Provisioning the runtime variables

`api` and `worker` receive **only** the restricted pooled runtime credential. Railway never
holds the administrative direct credential: `DATABASE_URL_DIRECT` is exported transiently from
the operator's gitignored local `.env` for a single `alembic` command (see
[`docs/cloud/supabase/SETUP.md`](../supabase/SETUP.md)) and is never configured on, referenced
by, or exposed to either Railway service. If a service ever carries `DATABASE_URL_DIRECT`, that
is drift and must be removed.

The runtime URL shape (`ARCHITECTURE.md` § Connection targets, matching what
`api.core.config.Settings` and `api.db.session.get_engine` accept): psycopg scheme, the pooler
username `dmitri_runtime.<project-ref>`, the **6543 transaction pooler**, and
`?sslmode=require` in the URL —

```
postgresql+psycopg://dmitri_runtime.<project-ref>:<URL-ENCODED-PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

For the current `nspi` Supabase project (`pxxcojewkivbadvktsrp`, region `us-east-1`):

```
postgresql+psycopg://dmitri_runtime.pxxcojewkivbadvktsrp:<DMITRI_RUNTIME_PASSWORD>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

`<DMITRI_RUNTIME_PASSWORD>` is the already URL-encoded password from the Supabase runbook's
Step 4 — never the raw password, and never typed into a command that lands in shared shell
history.

### Exact operator commands

Run from a shell authenticated with `railway login` (`railway whoami` to confirm). These set
the sealed runtime `DATABASE_URL` on both services, remove any `DATABASE_URL_DIRECT`, confirm
the result, then redeploy both services so the new credential takes effect:

```bash
PROJECT=2b6b51c6-f5b7-4979-87f9-296e36a55896
ENV=nspi

# 1. Set the restricted pooled runtime DATABASE_URL on both services
railway variable set DATABASE_URL="postgresql+psycopg://dmitri_runtime.pxxcojewkivbadvktsrp:<DMITRI_RUNTIME_PASSWORD>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" --service api --environment "$ENV" --project "$PROJECT" --skip-deploys
railway variable set DATABASE_URL="postgresql+psycopg://dmitri_runtime.pxxcojewkivbadvktsrp:<DMITRI_RUNTIME_PASSWORD>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" --service worker --environment "$ENV" --project "$PROJECT" --skip-deploys

# 2. Remove DATABASE_URL_DIRECT from both — it must never reach a long-running service
railway variable delete DATABASE_URL_DIRECT --service api --environment "$ENV" --project "$PROJECT"
railway variable delete DATABASE_URL_DIRECT --service worker --environment "$ENV" --project "$PROJECT"

# 3. Confirm: DATABASE_URL is the sealed runtime URL, DATABASE_URL_DIRECT is absent
railway variable list --service api --environment "$ENV" --project "$PROJECT" --json
railway variable list --service worker --environment "$ENV" --project "$PROJECT" --json

# 4. Redeploy both so the new credential takes effect
railway up --detach --service api --environment "$ENV" --project "$PROJECT"
railway up --detach --service worker --environment "$ENV" --project "$PROJECT"

# 5. Poll to a terminal state and confirm the health probe / worker boot
railway deployment list --service api --environment "$ENV" --project "$PROJECT" --json
railway deployment list --service worker --environment "$ENV" --project "$PROJECT" --json
railway logs --service api --environment "$ENV" --project "$PROJECT"
railway logs --service worker --environment "$ENV" --project "$PROJECT"
```

`railway logs --service api` should show Uvicorn bound to `0.0.0.0:$PORT` and
`"GET /api/v1/health HTTP/1.1" 200 OK`; `railway logs --service worker` should show the poll
loop starting without the previous `psycopg` authentication/undefined-table errors once the
hosted schema is migrated (see the Supabase runbook).

### Optional: sealing the NVD API key

If an `NVD_API_KEY` is configured, seal it the same way on both services — the API and worker
both call the NVD client during enrichment:

```bash
railway variable set NVD_API_KEY="<NVD_API_KEY>" --service api --environment "$ENV" --project "$PROJECT" --skip-deploys
railway variable set NVD_API_KEY="<NVD_API_KEY>" --service worker --environment "$ENV" --project "$PROJECT" --skip-deploys
railway up --detach --service api --environment "$ENV" --project "$PROJECT"
railway up --detach --service worker --environment "$ENV" --project "$PROJECT"
```

### Required: `JWT_SIGNING_SECRET`

`api.core.config.Settings` requires `JWT_SIGNING_SECRET` with no default — both `api` and
`worker` call `get_settings()` at startup (`worker.py`'s poll loop does so immediately), so a
missing value fails Pydantic validation before either process finishes starting. On `api` this
surfaces as a failed healthcheck; on `worker` there is no healthcheck to catch it, so it silently
crash-loops instead. Seal a strong random secret on both services:

```bash
railway variable set JWT_SIGNING_SECRET="$(openssl rand -hex 32)" --service api --environment "$ENV" --project "$PROJECT" --skip-deploys
railway variable set JWT_SIGNING_SECRET="$(openssl rand -hex 32)" --service worker --environment "$ENV" --project "$PROJECT" --skip-deploys
```

Generate the secret once and reuse the same value for both `variable set` calls — the two
invocations above each generate their own, which is wrong. Then redeploy so the running
containers pick it up. Use `railway redeploy` (restart the existing build), not `railway up` —
`up` re-uploads and rebuilds, and Railway will report `SKIPPED` / "No changes to watched files"
when only an env var changed, not a rebuild:

```bash
railway redeploy --service api --environment "$ENV" --project "$PROJECT" --yes
railway redeploy --service worker --environment "$ENV" --project "$PROJECT" --yes
```

Note that device auth is **Ed25519 signatures** (ADR-005 amended 2026-07-24): the backend stores
only each device's public key, so there is **no** `AGENT_HMAC_SECRET` or device-secret encryption
key to provision.

## Rollback

Hosted rollback is quiescent by design: the API and worker must never run while
[`docs/cloud/supabase/SETUP.md`](../supabase/SETUP.md#rollback-stop--drain--downgrade--verify)'s
`alembic downgrade base` drops their tables and login. **Stop both services first:**

```bash
PROJECT=2b6b51c6-f5b7-4979-87f9-296e36a55896
ENV=nspi

railway down --service api --environment "$ENV" --project "$PROJECT" --yes
railway down --service worker --environment "$ENV" --project "$PROJECT" --yes
```

Confirm both are stopped (`railway status`), then follow the Supabase runbook's drain →
downgrade → verify steps. Only after a fresh `alembic upgrade head` reapplies a compatible
schema, bring both services back:

```bash
railway redeploy --service api --environment "$ENV" --project "$PROJECT" --yes
railway redeploy --service worker --environment "$ENV" --project "$PROJECT" --yes
```

Neither service may restart against a dropped or partially-migrated schema.

## Gotchas & Remediation

| # | Gotcha | Impact on this stack | Remediation |
|---|--------|----------------------|-------------|
| 1 | **Free trial pauses services** ($5 credit / 30 days, whichever first) | `api` + `worker` would silently stop when trial credit runs out | Move to the **Hobby plan ($5/mo)** before nspi needs to run 24/7. |
| 2 | **Usage-based billing on always-on containers** | `api` and `worker` run 24/7 and accrue usage even at zero traffic | Set a **usage/spend alert** in the billing dashboard. Keep to two small services; do not scale `api` replicas (ADR-011). |
| 3 | **Cold starts / serverless sleep** | A sleeping `api` would drop any persistent connection | Do **not** enable app-sleep/serverless on `api` or `worker`. Keep both always-on. |
| 4 | **Config file does not follow Root Directory** | A relative Config Path silently uses defaults | Always use the **absolute-from-repo-root** path: `/backend/railway.api.toml`, `/backend/railway.worker.toml`. |
| 5 | **Two services, one build → cross-triggered rebuilds** | A worker-only change rebuilds `api` and vice-versa | `watchPatterns = ["backend/**"]` is already set in both configs; narrow it if the code is later split into subpackages. |
| 6 | **`$PORT` binding** | `api`'s health check fails and traffic never routes if it binds `127.0.0.1` or a hardcoded port | `api` must listen on **`0.0.0.0:$PORT`** (already the shipped `startCommand`). `worker` must **not** bind a port or define a health check. |
| 7 | **`DATABASE_URL_DIRECT` on a Railway service** | The administrative credential would be reachable by a long-running, network-exposed process | Never set it on `api` or `worker`; it lives only in the operator's local shell for a single `alembic` command. Re-run `railway variable list --json` after any provisioning pass to confirm it is absent. |
| 8 | **Transaction pooler (6543) and prepared statements** | Prepared-statement errors under load | The shipped engine (`api.db.session.get_engine`) always sets `connect_args={"prepare_threshold": None, "connect_timeout": 10}` — not tunable per deployment. Migrations always use `DATABASE_URL_DIRECT` (5432/Session pooler), never 6543. |
| 9 | **Build cache staleness after dependency changes** | Old wheels served after a `backend/uv.lock` bump | Trigger a **redeploy without cache** from the deployment's menu when dependencies change and a build looks stale. |
| 10 | **Egress cost / cross-region latency** | `api`/`worker` ↔ Supabase and NVD/KEV/EPSS clients cross regions | Region is matched to Supabase (see [Region](#region)). External enrichment egress is small but watch it in the usage dashboard. |

## Integrations

| Tool | Fit |
|------|-----|
| **GitHub** (primary) | Railway GitHub App → auto-deploy on push to `main`; per-service Root Directory (`/backend`) + Config Path drive the monorepo split. |
| **Railway CLI** | Manual deploys (`railway up --detach --service <name>`), variable management (`railway variable set/delete/list`), logs (`railway logs`), stop/redeploy (`railway down` / `railway redeploy`). |
| **Claude Code / Cursor** | Edit code and the committed `railway.*.toml` in-repo like any file; deploys still flow through GitHub or the CLI. |

## References

- Monorepo: <https://docs.railway.com/guides/monorepo>
- Build configuration: <https://docs.railway.com/builds/build-configuration>
- Railpack (default builder): <https://docs.railway.com/builds/railpack> · Python/uv: <https://railpack.com/languages/python/>
- Config as code reference: <https://docs.railway.com/config-as-code/reference>
- Health checks: <https://docs.railway.com/guides/healthchecks>
- Using variables / reference variables: <https://docs.railway.com/variables>
- Private networking: <https://docs.railway.com/networking/private-networking> · Public networking: <https://docs.railway.com/public-networking>
- Pricing / plans: <https://docs.railway.com/pricing/plans>
- CLI: <https://docs.railway.com/guides/cli>
- Backend shell contract: [`specs/013-backend-app-shell-rebuild/ARCHITECTURE.md`](../../../specs/013-backend-app-shell-rebuild/ARCHITECTURE.md)
- Supabase runbook (runtime role, password, rollback): [`docs/cloud/supabase/SETUP.md`](../supabase/SETUP.md)
