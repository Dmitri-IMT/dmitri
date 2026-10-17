# Development setup

This guide covers every layer of the repo. Each part is independent — run only what you
need:

| Part | Layer | You need it when |
|------|-------|------------------|
| [1](#part-1--hardware-agent--tui) | `hardware-agent/` + Textual TUI | Working on scanning, discovery, or the terminal UI |
| [2](#part-2--local-database) | Local Postgres (Supabase CLI + Docker) | Anything that touches the backend or its tests |
| [3](#part-3--backend-api) | `backend/` FastAPI + worker | Working on the API, or serving data to the frontend |
| [4](#part-4--frontend) | `frontend/` React SPA | Working on the web UI |

**Working on the web UI end to end?** You need parts 2 → 3 → 4, in that order, and the
[full-stack walkthrough](#running-the-whole-stack) chains them into one sequence.

**Deployment context:** o agente **Dmitri** está orientado ao laboratório **NSPi** (robótica industrial na universidade). Equipamentos típicos (CLPs em Ethernet, Pi em Wi‑Fi) e o foco só-TUI estão descritos no [README](../README.md) (secções *Foco atual do desenvolvimento* e *Ambiente de implantação: laboratório NSPi*).

**Still not in scope:** Docker Compose for the app itself. The backend and frontend run as
plain local processes; only Postgres runs in Docker, via the Supabase CLI.

---

## Quick install (recommended)

From the **repo root** after cloning:

```bash
# macOS / Linux / Pi — full dev bootstrap (agent + backend + local Supabase when Docker is available)
./install.sh

# Agent-only (Pi, no Docker)
./install.sh --agent-only

# Skip post-install pytest
./install.sh --skip-verify

# Also install pre-commit pre-push hooks
./install.sh --hooks
```

Windows (PowerShell):

```powershell
.\install.ps1
.\install.ps1 -AgentOnly
.\install.ps1 -SkipVerify
.\install.ps1 -Hooks
```

The root installer auto-installs **uv** and **nmap**, runs `uv sync --extra dev` in both packages (required for `uv run pytest`), seeds `backend/.env` when missing, runs `npm install` and seeds `frontend/.env`, and — if the Supabase CLI is present — starts local Postgres and runs Alembic migrations. Docker only has to be *installed*: if the daemon is down the installer starts it (Docker Desktop on macOS/Windows, `systemctl` on Linux) and waits up to 180s. It also installs a `dmitri` launcher in `~/.local/bin` (and adds that directory to your shell `PATH` on macOS/Linux when missing).

**What the installer does not do:** it never installs **Node.js** — without a `node` on
`PATH` it prints instructions and skips the frontend entirely — and the `backend/.env` it
seeds is a verbatim copy of the example, so you still have to set `JWT_SIGNING_SECRET` and
`REFRESH_COOKIE_SECURE` yourself before the API is usable. `--agent-only` skips the
frontend along with the backend. See [part 3](#part-3--backend-api) and
[part 4](#part-4--frontend).

After `./install.sh`, run the TUI from anywhere:

```bash
dmitri
```

`hardware-agent/install.sh` is a thin wrapper that runs `./install.sh --agent-only`.
On Raspberry Pi armhf/arm64, that mode installs and verifies the service-targeted
tools and DIRB wordlist. It exits with an error if provisioning fails, so a
successful install means those scan capabilities are available.

The appliance installer `sudo sh hardware-agent/scripts/provision-pi.sh` also installs
and verifies those prerequisites before reporting the Pi ready. If the Python agent
was installed manually or as a package alone, run this from a repository checkout
on the Pi to install the missing external tools and wordlist:

```bash
sudo bash hardware-agent/scripts/provision-targeted-tools.sh
sudo bash hardware-agent/scripts/provision-targeted-tools.sh --verify-only
```

The second command only checks local versions, capabilities and the wordlist; it
does not scan targets. Successful provisioning removes missing-tool gaps, while
real target failures and timeouts still make a scan partial.

Manual steps below remain valid if you prefer not to use the scripts.

---

## Prerequisites

Always:

- **Git**
- **Python 3.11+** (matches `requires-python` in `hardware-agent/pyproject.toml` and `backend/pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — required for syncing dependencies (supported path; `pip` is an unsupported escape hatch per product specs)

For the agent / TUI (part 1):

- **Nmap** — install on the host yourself. It must be available for **real** scans when you run the TUI. Verify with `nmap --version`. Automated **tests** mock nmap; CI does not install it — see `[specs/001-agent-tui/tech-stack/testing-tooling.md](../specs/001-agent-tui/tech-stack/testing-tooling.md)`.

For the database and backend (parts 2–3):

- **Docker** — [Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) on macOS/Windows, [Engine](https://docs.docker.com/engine/install/) on Linux. Only Postgres runs in it.
- **Supabase CLI** — `brew install supabase/tap/supabase` (macOS), `scoop install supabase` (Windows), or the [Linux instructions](https://supabase.com/docs/guides/local-development/cli/getting-started).

For the frontend (part 4):

- **Node.js 22.x** — pinned by `engines` in `frontend/package.json`. Verify with `node --version`.

### Nmap (local runs)

- **Windows**: [Nmap download](https://nmap.org/download.html) or a package manager (e.g. Chocolatey: `choco install nmap`).
- **macOS**: `brew install nmap` or the upstream installer.
- **Debian / Ubuntu**: `sudo apt install nmap`
- **Fedora**: `sudo dnf install nmap`

---

## Part 1 — hardware-agent & TUI

### Install dependencies (**uv**)

From `**hardware-agent/**`:

```bash
cd hardware-agent
uv sync --extra dev
```

This installs runtime and dev dependencies (including **pytest**). Plain `uv sync` omits dev extras and `uv run pytest` will fail. It does **not** install Nmap; if `nmap` is missing from `PATH`, install it using the section above (or use `./install.sh` from the repo root).

**Advanced (unsupported):** `pip install -e .` inside `hardware-agent/` may work in some environments (e.g. air-gapped mirrors), but it is **not** the supported install path — prefer **uv** — `[specs/001-agent-tui/tech-stack/package-and-distribution.md](../specs/001-agent-tui/tech-stack/package-and-distribution.md)`.

#### Persisted prefs (TUI)

When saving app config (e.g. under `%LOCALAPPDATA%\Dmitri\`, XDG `~/.config/dmitri/`, etc.), use **write a `*.tmp`next to the real file → flush →`os.replace`/`Path.replace`** so a crash never leaves a half-written config. Details:` [specs/001-agent-tui/tech-stack/persistence-and-io.md](../specs/001-agent-tui/tech-stack/persistence-and-io.md) `(**Atomic save**). Default scan output for **Use default** is under `**…/Dmitri/results`** —` [specs/001-agent-tui/ui/screens.md](../specs/001-agent-tui/ui/screens.md)`.

---

### Run the TUI

From `**hardware-agent/`** (after `uv sync`):

```bash
cd hardware-agent
uv run dmitri
# or
uv run dmitri start
```

The `**dmitri**` console script is declared in `hardware-agent/pyproject.toml` (`[project.scripts]`). If your environment cannot see the script entrypoint, use:

```bash
uv run python -m agent.cli
```

---

## Part 2 — local database

Postgres runs in Docker through the Supabase CLI. **Alembic owns the schema** — never
`supabase db reset|push|migration`.

The repo ships `./database.sh`, which starts Docker if needed, brings the stack up, creates
the dedicated **test** database, and tidies unused Docker images:

```bash
./database.sh              # start + create dmitri_test
./database.sh --test       # ... then run the backend suite against it
./database.sh --no-clean   # skip the Docker image cleanup
./database.sh --help
```

Windows (PowerShell) — `.\database.ps1` is the same script with switch-style flags:

```powershell
.\database.ps1             # start + create dmitri_test
.\database.ps1 -Test       # ... then run the backend suite against it
.\database.ps1 -NoClean    # skip the Docker image cleanup
.\database.ps1 -Help
```

It is idempotent and never deletes volumes, so your local data survives re-runs. If you
only want the stack up, plain `supabase start` from the repo root is enough.

Two databases live on the same server, and they are not interchangeable:

| Database | URL | Used by |
|----------|-----|---------|
| `postgres` | `postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres` | the running API and worker (`DATABASE_URL`) |
| `dmitri_test` | `postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test` | `uv run pytest` (`DATABASE_URL_TEST`) |

`conftest.py` refuses to run against a database not named exactly `dmitri_test`, so the
suite can never touch your dev data. Ports come from `supabase/config.toml` (API `54321`,
db `54322`) — read them from there rather than hardcoding if you change them.

Stop the stack with `supabase stop` (add `--no-backup` only if you want the data gone).

---

## Part 3 — backend API

### Install and configure

```bash
cd backend
uv sync --extra dev
cp .env.example .env          # ./install.sh does this for you
```

Then edit `backend/.env`. Four values in the example are **not** usable as shipped:

```bash
# Ships EMPTY, and an empty value boots without complaint — generate a real one:
#   openssl rand -hex 32
JWT_SIGNING_SECRET=<64 hex chars>

# Must be false for local http:// development. See Gotchas.
REFRESH_COOKIE_SECURE=false

# Ships EMPTY so browser access fails closed. Trust only the local Vite origin:
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Email links must return to the local SPA rather than the hosted deployment:
APP_BASE_URL=http://localhost:5173

# Optional AI overview (Groq). Off by default. Needs a key on the worker to run jobs,
# and the same pair on the API or Scan Detail returns unavailable.
# AI_ENABLED=true
# AI_AUTO_ANALYSIS=false
# AI_API_KEY=
# AI_MODEL=openai/gpt-oss-120b
# AI_POLL_INTERVAL_SECONDS=5
# AI_MAX_FINDINGS=10
# AI_TIMEOUT_SECONDS=30
# AI_MAX_OUTPUT_TOKENS=4096
# AI_REASONING_EFFORT=low
# AI_MAX_ATTEMPTS=2
# AI_RETRY_DELAY_SECONDS=30
# ENRICHMENT_POLL_INTERVAL_SECONDS=5
# ENRICHMENT_BATCH_SIZE=10
# ENRICHMENT_MAX_ATTEMPTS=3
# ENRICHMENT_RETRY_DELAY_SECONDS=30
# ENRICHMENT_STALE_AFTER_SECONDS=120
# NVD_MIN_REQUEST_INTERVAL_SECONDS=6
```

`DATABASE_URL` already points at the local `postgres` database. CORS has no trusted origin by
default, so keep the explicit localhost allowlist above or the browser will block frontend API
calls even though the backend boots.

> `Settings` reads `.env` automatically, and **`.env` beats variables exported in your
> shell** — including during tests. If something behaves unexpectedly, suspect a stale
> value in that file first.

### Migrate (required before the first boot)

The app never creates tables at boot. Alembic runs against `DATABASE_URL_DIRECT`, a
**shell-only** variable — never put it in `.env`:

```bash
cd backend
export DATABASE_URL_DIRECT=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
uv run alembic upgrade head
unset DATABASE_URL_DIRECT
```

### Run

```bash
cd backend
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Serving on `http://127.0.0.1:8000`. Check it:

```bash
curl http://127.0.0.1:8000/api/v1/health
# {"status":"ok","version":"0.1.0"}
```

That endpoint does a real `SELECT 1`, so a `503` means the database, not the API.
`/docs`, `/redoc` and `/openapi.json` are **disabled by design** — the published contract
is `contracts/openapi/openapi.yaml`.

The enrichment worker is a separate process. It is optional for UI-only work, but scans will
not get NVD/KEV/EPSS scores without it, and **Explain this scan** will stay pending:

```bash
cd backend
uv run python -m api.worker_main
```

When `AI_ENABLED=true` and `AI_API_KEY` is set, this same process starts an AI poll loop in a
daemon thread. Completing a scan does not call Groq. A member presses **Explain this scan**
(`POST /api/v1/scans/{id}/analysis`). The worker will not claim that job while the scan still
has `pending` or `running` enrichment jobs. Put the same `AI_ENABLED` + `AI_API_KEY` on the
API process or Scan Detail returns `unavailable`.

### Create the first user

A fresh database has no accounts, and the SPA has no sign-up screen — bootstrapping is a
CLI plus one HTTP call. First, create the org and an admin invite:

```bash
cd backend
uv run backend-bootstrap-org --org-name "NSPi Lab" --email you@example.com
# org_id=...
# invite_token=<TOKEN>
# expires_at=...
```

Then redeem the token to set a password (**minimum 12 characters**). The token goes in the
**body**, not the path, and the request carries **no email** — the invite already knows the
address:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/invites/accept" \
  -H 'Content-Type: application/json' \
  -d '{"token":"<TOKEN>","password":"correct-horse-battery"}'
```

A `201` returns tokens and confirms the account exists. The email from
`backend-bootstrap-org` plus this password are the credentials you type into the login
screen. Re-running `backend-bootstrap-org` with the same org name exits `1` rather than
creating a duplicate.

> **The route takes no other shape.** `POST /api/v1/invites/<TOKEN>/accept` is the pre-DMI-77
> path form and now 404s; sending `email` in the body fails `extra="forbid"`. The live
> contract is `backend/src/api/routers/invites.py` and `docs/ui/SCREENS.md`.

> Password checks call **HaveIBeenPwned** by default. Offline, set `HIBP_ENABLED=false` in
> `.env` or the accept call fails.
>
> The policy also rejects a password **containing your own email**, matching any
> `>= 3`-character part of it (`test@dmitri.local` bans `test`, `dmitri`, `local`). A
> `400 password_policy_violation` names the rule you hit.

### Tests

```bash
cd backend
uv run ruff check src tests
DATABASE_URL_TEST=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/dmitri_test uv run pytest
```

Without `DATABASE_URL_TEST` collection aborts with pytest exit code 4. There is no skip
and no opt-out. `./database.sh --test` starts Postgres, sets the URL, and runs the suite.

Industrial observations are retained **180 days** from ingest (`INDUSTRIAL_OBSERVATION_RETENTION_DAYS`).
No pruning job enforces that yet.

On the Pi, OT policy is `DMITRI_OT_POLICY_PATH` or `~/.config/dmitri/ot-policy.json`.
The org digest key is `DMITRI_OT_DIGEST_KEY` (64 hex) or `~/.config/dmitri/ot-digest-key`
(mode 0600). `backend-provision-agent` prints `ot_digest_key=` once per org.

**Never run `ruff format`** (or `black`, or `./lint.sh` from the root) over `backend/`.
Formatters are scoped to `hardware-agent/`; `ruff check` is the backend's only gate. See
`AGENTS.md` § Formatting and lint gates.

---

## Part 4 — frontend

```bash
cd frontend
npm install
cp .env.example .env          # sets VITE_API_URL=http://localhost:8000
npm run dev
```

`./install.sh` already did the `npm install` and the `.env` copy — the manual steps above
are for a machine where Node arrived after the installer ran.

Vite serves on `http://localhost:5173`. That exact origin must be present in the backend's
deployment-supplied `CORS_ALLOWED_ORIGINS` allowlist.

The dev server proxies nothing — it calls the backend directly at `VITE_API_URL`, so the
API from part 3 must be running or every request fails.

Other scripts:

| Command | Does |
|---------|------|
| `npm run dev` | Vite dev server with HMR on `:5173` |
| `npm test` | Vitest suite (MSW-mocked; **no** backend needed) |
| `npm run lint` | ESLint |
| `npm run format:check` | Prettier check (CI gate) |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run build` | Type-check then production build |
| `npm run gen:types` | Regenerate `src/types/openapi.d.ts` from `contracts/openapi/openapi.yaml` |

Run `gen:types` and commit the result whenever a route contract changes — API types are
never hand-written.

---

## Running the whole stack

Four terminals, in order:

```bash
# 1 — database (once; leave Docker running)
./database.sh

# 2 — migrate (once per schema change)
cd backend
export DATABASE_URL_DIRECT=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
uv run alembic upgrade head && unset DATABASE_URL_DIRECT

# 3 — API
cd backend && uv run uvicorn api.main:app --port 8000 --reload

# 4 — frontend
cd frontend && npm run dev
```

Then open `http://localhost:5173` and log in with the account from
[Create the first user](#create-the-first-user).

**A fresh database has no scans**, so Home renders its blank state. That is correct
behaviour, not a bug — ingest a scan through the agent to see populated data.

---

## Gotchas

Each of these has cost someone an afternoon:

- **`REFRESH_COOKIE_SECURE=true` over `http://`.** The default is `true` (correct for
  production). Browsers silently discard a `Secure` cookie sent over plain http, so login
  appears to work and then every refresh logs you out. Set it to `false` locally.
- **Missing `frontend/.env`.** Only `.env.example` is committed. Without the copy,
  `VITE_API_URL` is `undefined` and every request goes to `undefined/api/v1` — a 404 with
  no obvious cause.
- **`backend/.env` overrides your shell.** Exported variables lose to the file, including
  under pytest.
- **Empty `JWT_SIGNING_SECRET`.** A fresh copy of `.env.example` boots *successfully* with
  an **empty** signing key — nothing warns you, and every token is signed with `""`.
  Generate one with `openssl rand -hex 32`. Under 32 bytes you also get
  `InsecureKeyLengthWarning` from PyJWT.
- **Starting the API from the repo root.** `Settings` resolves `env_file=".env"` relative to
  the **current working directory**, and there is no `.env` at the root. Run
  `uv run uvicorn …` from the root and it dies with
  `JWT_SIGNING_SECRET Field required [type=missing]` — which reads like a broken `.env`
  when the real problem is that no `.env` was found at all. Always `cd backend` first.
- **Forgetting `alembic upgrade head`.** The app never creates tables, so the first request
  fails against an empty database rather than self-healing.
- **`DATABASE_URL_DIRECT` in `.env`.** It is shell-only. The pooled `DATABASE_URL` cannot
  run DDL in transaction mode.
- **Running a formatter.** `uv run ruff format` rewrites ~32 backend files that have
  nothing to do with your change.
- **PDF report download fails on macOS.** The report renderer looks for a Unicode font only
  at fixed paths: Windows Arial, or DejaVu Sans / Liberation Sans under
  `/usr/share/fonts/truetype/` on Linux. macOS has none of these, so a report download
  raises `A Unicode font is required to render scan reports` and returns a 500. The rest of
  the app works. On Linux, install `fonts-dejavu-core` (Debian/Ubuntu) to fix it.

---

## Optional: pre-commit (repo-wide)

If the repository configures **pre-commit** at the root:

```bash
pip install pre-commit
pre-commit install --hook-type pre-push
```

Or with uv: `uv tool install pre-commit` then run the same `pre-commit install --hook-type pre-push`.

The pre-push hook runs the repo lint hooks plus the full pytest suite before `git push`
(including pushes triggered from the VS Code Git UI). Lint checks always run against
`hardware-agent/` even if no files are staged.

Do not commit real secrets. For hardware-agent–only work, hooks may still touch other trees if configured globally — adjust or skip as needed.

---

## Spec pointers

- CLI contract: `[specs/001-agent-tui/contracts/cli.md](../specs/001-agent-tui/contracts/cli.md)`
- Tech stack (uv, lockfile, CI intent): `[specs/001-agent-tui/tech-stack/](../specs/001-agent-tui/tech-stack/)`

