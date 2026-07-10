# Railway — setup (API + worker)

> **Scope:** DMI-52 — stand up the Railway project for NSPi with **two services (`api`, `worker`)**,
> pick the region, and wire Supabase env vars. **No frontend service, no AWS** here (both are later
> work — see [`BACKEND.md` B4/B5](../../roadmap/BACKEND.md#b4--b5--hosted-stack-)).
>
> **Locked decisions honored:** two services `api` + `worker`; single `nspi` environment; region
> matches Supabase and is closest to operators/Pi; Postgres lives on **Supabase**, not Railway
> (Railway connects via env vars, pooler **6543** at runtime).
>
> **Honest state of the repo:** the FastAPI **app shell for these two services does not exist yet**.
> `backend/` today is a legacy standalone scorer whose app shell is explicitly discarded
> ([`BACKEND.md` B8](../../roadmap/BACKEND.md#reuse-from-backend-code-)); the real `api`/`worker`
> entrypoints land with **DMI-56**. Every start command below is a **placeholder** marked as such —
> the services are created empty and will not build successfully until DMI-56 ships. That is expected
> for DMI-52.

## What this doc delivers

| Deliverable | Status after DMI-52 |
|-------------|---------------------|
| Railway project + `nspi` environment | Created |
| `api` service (web/HTTP + WSS) connected to GitHub | Created, empty, no successful build yet |
| `worker` service (background job runner) connected to GitHub | Created, empty, no successful build yet |
| Region selected (matches Supabase) | Set |
| Supabase `DATABASE_URL` (6543 pooler) wired into both services | Set as shared variable |
| Config-as-code (`railway.*.toml`) committed with placeholder start commands | Committed |

## The two services

| Service | Role | Public domain? | Health check? | Replicas |
|---------|------|----------------|---------------|----------|
| `api` | FastAPI web service. Serves HTTP (`/api/v1/...`) **and** the Pi WSS endpoint `/api/v1/agents/{agent_id}/commands`. Holds the in-memory WebSocket connection registry (the Pi dials **in**; the socket is outbound only from the Pi's side — [`PI.md`](../../roadmap/PI.md)). | **Yes** — WSS/HTTPS need a public URL | **Yes** — `/health` | **1** (ADR-011: single API replica for NSPi — the WS registry is in-memory, so do not scale horizontally) |
| `worker` | Background job runner (enrichment + risk scoring poll loop, `FOR UPDATE SKIP LOCKED` against Supabase — [`BACKEND.md` B8](../../roadmap/BACKEND.md#reuse-from-backend-code-)). No inbound traffic. | **No** — background worker, no domain | **No** — nothing to probe over HTTP | 1 |

Both services deploy from the **same repo and same build** (identical dependencies); they differ only
by **start command**. This is Railway's "shared monorepo" shape.

## Prerequisites

1. A Railway account. **Start on the free trial** ($5 one-time credit) for DMI-52 — creating empty services costs nothing. Move to the **Hobby plan ($5/mo)** before nspi runs 24/7 (see [Gotchas](#gotchas--remediation) — the trial pauses services once the $5 credit / 30 days is exhausted).
2. The Supabase project already created, and its **region** decided (Railway region must mirror it).
3. GitHub access to `vulnerability-scanner-device` with permission to install the Railway GitHub App.
4. (Optional but recommended) the Railway CLI installed locally.

---

## Step 1 — Create the project and the `nspi` environment

1. Railway dashboard → **New Project** → **Empty Project**.
2. Name it `vulnerability-scanner-nspi` (or per team convention).
3. Rename the default environment to **`nspi`**: project → **Settings → Environments** → rename `production` to `nspi`. Keep a single environment for September (no PR/branch environments yet — [Gotchas](#gotchas--remediation)).

Verify: project canvas shows one environment named `nspi`.

## Step 2 — Pick the region

Railway sets region **per service**, not per project, so you set it in Steps 3–4. Decide it now.

| Fact | Detail |
|------|--------|
| Railway regions | `us-east4` (Virginia), `us-west2` (Oregon/California), `europe-west4` (Amsterdam), `asia-southeast1` (Singapore) |
| No South America region | Railway has **no SA region** today. |
| Decision | **`us-east4` (Virginia)** — co-located with Supabase `us-east-1` (N. Virginia). The compute↔DB round trip is paid on every query, so co-locating with Supabase dominates; the ~120ms Brazil-based operators pay on their once-per-request HTTP hop is negligible for this workload. |

Set the region on **each** service in Settings → **Region** (change before the first deploy — moving a
service later re-provisions it).

## Step 3 — Create the `api` service

1. Project canvas → **New → GitHub Repo** → select `vulnerability-scanner-device`. Install/authorize the Railway GitHub App if prompted.
2. Rename the service to **`api`**.
3. **Settings → Source:**
   - **Branch:** `main` (auto-deploy on push).
   - **Root Directory:** `/backend` (build context is the backend package once DMI-56 lands there).
   - **Config Path:** `/backend/railway.api.toml` (absolute from repo root — the config path **does not** follow Root Directory; see [monorepo docs](#references)).
4. **Settings → Region:** set per Step 2.
5. **Settings → Networking → Public Networking:** generate a domain (needed for HTTPS + WSS). Note the `*.up.railway.app` URL — the Pi's `BACKEND_URL` and the frontend will point at it.
6. **Settings → Deploy → Replicas:** leave at **1** (do not increase — ADR-011).
7. Add the `watchPatterns` in the config (Step 7) so worker-only changes don't rebuild `api`.

Verify: the `api` service card shows the GitHub repo, branch `main`, root `/backend`, and a public domain.

## Step 4 — Create the `worker` service

1. Project canvas → **New → GitHub Repo** → same repo `vulnerability-scanner-device`.
2. Rename the service to **`worker`**.
3. **Settings → Source:**
   - **Branch:** `main`.
   - **Root Directory:** `/backend`.
   - **Config Path:** `/backend/railway.worker.toml`.
4. **Settings → Region:** same region as `api`.
5. **Settings → Networking:** do **not** generate a public domain. A background worker needs no inbound port and no health check. If it ever needs to reach `api` internally, use **Private Networking** (`api.railway.internal`) rather than the public domain.

Verify: the `worker` service card shows the repo and root `/backend`, and **no** public domain.

## Step 5 — Build system: Railpack + uv

**Recommendation: use Railpack (Railway's default builder) — do not add a Dockerfile.**

| Fact | Detail |
|------|--------|
| Default builder | **Railpack** (successor to Nixpacks). Zero-config; smaller Python images. |
| uv support | Railpack **auto-detects** `pyproject.toml` + `uv.lock` and installs deps with `uv`. This matches this repo's toolchain (`uv` everywhere). |
| Requirement | The backend package must ship its **own `uv.lock`**. `backend/` has `pyproject.toml` but **no `uv.lock` today** — DMI-56 must add one (`cd backend && uv lock`). Until then Railpack cannot pin deps. |
| Escape hatch | If Railpack ever mis-detects, set `builder = "NIXPACKS"` (and `NIXPACKS_PYTHON_PACKAGE_MANAGER=uv`) or `builder = "DOCKERFILE"` in the service's config. Not needed for a standard uv project. |

No build command is required for a uv project — Railpack handles install. You only override the
**start command** (Step 7).

## Step 6 — Wire Supabase env vars

Postgres is **on Supabase**. Both services need the connection string. Use a **project-level shared
variable** referenced by each service so there is one source of truth.

1. Project → **Settings → Shared Variables** → environment `nspi` → add:

| Variable | Value (placeholder) | Used by | Notes |
|----------|---------------------|---------|-------|
| `DATABASE_URL` | `postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:6543/postgres` | `api`, `worker` | **Runtime** connection via the **6543 transaction pooler** ([`BACKEND.md` B4/B5](../../roadmap/BACKEND.md#b4--b5--hosted-stack-)). |
| `DATABASE_URL_DIRECT` | `postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-us-east-1.pooler.supabase.com:5432/postgres` | `api` (migrations only, later) | **Direct 5432** for Alembic only. Wire now; consumed by a `preDeployCommand` when migrations land (DMI-56+). |

2. **Share** each variable to both `api` and `worker` (Shared Variables → Share → select services). This creates a reference variable in each service.
3. Alternatively, reference explicitly inside a service's Variables tab:

```
DATABASE_URL=${{shared.DATABASE_URL}}
```

4. Add any app config (JWT secret, HMAC pepper, NVD/KEV/EPSS URLs + TTLs) as they are defined by DMI-56. Keep secrets in Railway variables — never commit them.

Verify: both `api` and `worker` → Variables tab show `DATABASE_URL` resolving from `shared`.

> **Transaction-pooler caveat:** the 6543 pooler is PgBouncer in transaction mode — **server-side
> prepared statements must be disabled**. For SQLAlchemy + asyncpg use `?prepared_statement_cache_size=0`
> (or the psycopg equivalent) on `DATABASE_URL`, or connections will error under load. Confirm the exact
> driver flag when DMI-56 picks the DB driver.

## Step 7 — Config-as-code (`railway.*.toml`)

Commit one config file per service under `backend/`. **The start commands are placeholders** — replace
the marked lines when DMI-56 defines the real entrypoints. No `[build]` command is needed (Railpack + uv).

`backend/railway.api.toml`:

```toml
[build]
builder = "RAILPACK"
watchPatterns = ["backend/**"]

[deploy]
startCommand = "PLACEHOLDER_DMI56 uvicorn api.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ALWAYS"
```

`backend/railway.worker.toml`:

```toml
[build]
builder = "RAILPACK"
watchPatterns = ["backend/**"]

[deploy]
startCommand = "PLACEHOLDER_DMI56 python -m api.worker_main"
restartPolicyType = "ALWAYS"
```

Placeholder rules for DMI-56:
- `api`: must bind **`0.0.0.0:$PORT`** (Railway injects `$PORT`; the health check uses it too). Keep `--host 0.0.0.0 --port $PORT`. Remove the `PLACEHOLDER_DMI56` token.
- `worker`: has **no** `healthcheckPath` and **no** `$PORT` binding by design. Point the command at the real worker entrypoint (today's legacy loop is `api.worker_main` — reconcile the module path in DMI-56).
- Both `watchPatterns` are scoped so a change under `backend/**` rebuilds both; narrow them further if the api/worker code is later split into subpackages.

## Step 8 — Railway CLI (optional, for local ops and CI)

```
curl -fsSL agents.railway.com | sh
railway login
railway link
railway variables --service api
railway up --service api
railway logs --service worker
```

- `railway link` connects your local checkout to the project/environment.
- `railway up --service <name>` deploys a specific service manually (GitHub push auto-deploy remains the primary path).
- `railway variables --service <name>` inspects resolved env vars per service.

---

## Gotchas & Remediation

| # | Gotcha | Impact on this stack | Remediation |
|---|--------|----------------------|-------------|
| 1 | **Free trial pauses services** ($5 credit / 30 days, whichever first) | Harmless now (empty services); but once nspi runs, `api` + `worker` would silently stop when the trial credit runs out | **Now:** trial is fine for creating the empty services. **Before nspi goes 24/7:** move to **Hobby ($5/mo)**. Mirrors the Supabase "start cheap, commit before September" decision. |
| 2 | **Usage-based billing on always-on containers** | On Hobby, `api` (persistent WS) and `worker` (poll loop) run 24/7 and accrue usage even at zero traffic | Set a **usage/spend alert** in the billing dashboard. Keep to two small services; do not scale `api` replicas (also required by ADR-011). Delete any stray preview/test services. Hobby includes $5/mo of usage before overage. |
| 3 | **Cold starts / serverless sleep** | The Pi's persistent WSS would drop if `api` slept | Do **not** enable app-sleep/serverless on `api` (or `worker`). Keep both always-on; the WS registry must stay resident. |
| 4 | **Config file does not follow Root Directory** | Setting Config Path to `railway.api.toml` (relative) silently uses defaults | Always give the **absolute-from-repo-root** path: `/backend/railway.api.toml`, `/backend/railway.worker.toml`. |
| 5 | **Two services, one build → cross-triggered rebuilds** | A worker-only change rebuilds `api` and vice-versa (wasted build minutes) | Set `watchPatterns` in each config. Once code is split, narrow to the owning subpaths. |
| 6 | **`$PORT` binding** | `api` health check fails and traffic never routes if it binds `127.0.0.1` or a hardcoded port | `api` must listen on **`0.0.0.0:$PORT`**. The `worker` must **not** bind a port or define a health check. |
| 7 | **Missing `uv.lock` in `backend/`** | Railpack can't pin deps; builds are unreproducible or fail | DMI-56 runs `cd backend && uv lock` and commits `backend/uv.lock`. |
| 8 | **PgBouncer transaction pooler (6543)** | Prepared-statement errors under load | Disable prepared statements on `DATABASE_URL` (`prepared_statement_cache_size=0` for asyncpg). Use **5432 direct** only for Alembic via `DATABASE_URL_DIRECT`. |
| 9 | **Build cache staleness after dep changes** | Old wheels served after a `uv.lock` bump | Trigger a **redeploy without cache** from the deployment's menu when dependencies change and a build looks stale. |
| 10 | **Egress cost / cross-region latency** | `api`/`worker` ↔ Supabase and NVD/KEV/EPSS clients cross regions | Keep Railway region matched to Supabase (Step 2). External enrichment egress is unavoidable but small; watch it in the usage dashboard. |
| 11 | **Empty services can't build pre-DMI-56** | First deploys will fail until the app shell exists | Expected. Leave services created and connected; do not chase red builds until DMI-56 lands the entrypoints and `uv.lock`. |

## Integrations

| Tool | Fit |
|------|-----|
| **GitHub** (primary) | Railway GitHub App → auto-deploy on push to `main`; per-service Root Directory + Config Path drive the monorepo split. |
| **Railway CLI** | Local deploys (`railway up --service`), variable inspection, logs. Usable from CI later. |
| **Claude Code / Cursor** | Edit code and the committed `railway.*.toml` in-repo like any file; deploys still flow through GitHub or the CLI. Railway has no special editor plugin — no integration claim beyond "edit config-as-code, push to deploy." |

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
