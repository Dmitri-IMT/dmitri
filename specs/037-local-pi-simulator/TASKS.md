# Tasks — Local Pi simulator (`037-local-pi-simulator`)

9 tasks. **Unblocked now: #5b**

Source of truth is [PLAN.md](./PLAN.md), not a TRUTH/ARCHITECTURE/DESIGN set — this feature
adds no route, no schema, no screen and no cross-layer contract.

## Batching

The stack is not independently testable in slices: `compose.yaml` cannot come up without the
images, and `seed.sh` cannot run without `api`. A finer split would produce tasks whose
success criteria nobody can verify, so work is grouped to the largest unit that still reviews
cleanly. Task 5 is the feature's real gate — it executes the runbook the earlier tasks build.

## Agents and gate — read this before spawning

**Tasks 1–5 have no layer.** Their target files are `docker/`, `simulator.sh` and
`.dockerignore`. There is no pytest suite for compose YAML and no `npm run lint` for bash, so
the orchestrator's layer table does not apply.

- **Step 1** is `agent-developer`, as always.
- **Step 2, the test engineer, is skipped on tasks 1–5** — deliberately, not by omission.
  Writing pytest against a Dockerfile would be exactly the speculative scaffolding CLAUDE.md
  §2 forbids. **Task 5 is this feature's test step**: the T1–T8 runbook, executed rather than
  written as unit tests.
- **Step 3 is `code-reviewer`** on every task. It reviews shell and YAML against the success
  criteria, and it runs the Python gates where a task actually touches Python (tasks 6 and 7).

**Tasks 5b and 6 take the full trio** — `agent-developer` → `test-engineer` →
`code-reviewer` — because they are permitted to touch `hardware-agent/src/`.

```
cd hardware-agent && uv run pytest && uv run ruff check src tests
./database.sh --test                       # backend; a non-zero skip count is not green
```

**Never run `uv run ruff format`** — `backend/` is hand-formatted (CLAUDE.md §Formatting).

## The T0 baseline is not `main`

Found during task 1. `feat/dmi-111` also carries **DMI-108** — spec `036-email-deliverability`
was committed onto this same branch (`2b8c714` … `522a835`), and it really did change
application code: `backend/src/api/services/mailer.py` and
`backend/src/api/session_response.py`.

So `git diff --stat main -- backend/src hardware-agent/src` is **already non-empty**, before
this feature writes a line. PLAN.md §T0 and §T9 both name `main`; that is wrong for this
branch and would fail T0 for reasons that have nothing to do with the simulator.

**The baseline for every T0/T9 check is `522a835`** — the last DMI-108 commit, and the parent
of DMI-111's first (`7876763`):

```bash
DMI111_BASE=522a835
git diff --stat $DMI111_BASE -- backend/src hardware-agent/src   # expect: empty
```

**For the operator, not for a coder:** the PR will carry both issues' work. `Fixes DMI-111`
on a branch that also ships DMI-108's email fix is a packaging decision — splitting the
branches, or naming both issues in the PR body. Task 7 must not resolve this alone.

## Two decisions the plan leaves open

Both were found while writing this file. They are recorded here so a coder does not discover
them mid-task and a reviewer does not reject good work over them.

1. **`uv` is not in `python:3.12-slim`.** PLAN.md §The stack says "stock `python:3.12-slim`
   … with `uv run uvicorn` as the command", but that image ships no `uv`, and installing it
   at every boot means a network round-trip per container start.

   **Use `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`** for `migrate`, `api`, `worker` and
   `seed`. This keeps the plan's actual constraint — *no `backend/Dockerfile`*, no parallel
   build definition to hand-keep in step with RAILPACK — because it is still a stock image
   with `./backend` bind-mounted, just one that already carries the tool. It adds no new trust
   relationship either: `install.sh:72` already installs uv from `https://astral.sh/uv/install.sh`,
   so Astral is a vendor this repo depends on today. Its bookworm base also matches the
   `debian:12-slim` used by `agent` and `target`.

   Python stays 3.12: `hardware-agent/pyproject.toml:10` is `>=3.11,<3.13`, and
   `backend/pyproject.toml:10` is `>=3.11` with no upper bound.

2. **That image has no `curl` and no `wget`** for the `api` healthcheck. Use the interpreter
   that is already there:

   ```yaml
   test: ["CMD", "python", "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
   ```

   `/api/v1/health` (`backend/src/api/main.py:131`) depends on a DB session, so it is a real
   readiness probe — it stays unhealthy until `db` is actually serving, which is what gates
   `seed`.

---

## Task 1: Build context and the two container images
- **Description**: The bottom of the stack — everything that can be built and run before any
  compose file exists.

  `.dockerignore` at the repo root, keeping `node_modules/`, `.venv/`, `Artigo/`, `.git/` and
  build caches out of the context. Both bind mounts are small; the ignore file exists so the
  two `docker build` contexts stay small.

  `docker/pi-simulator/target.Dockerfile`: `debian:12-slim` + `samba`, with
  `docker/pi-simulator/smb.conf` defining one share. Built from the Debian base rather than
  pulled from `dperson/samba` — PLAN.md §The stack: a third-party image is a supply-chain
  dependency inside a security product's test harness, and its arm64 availability is not
  something to bet on. The target must listen on **445 and 139**; it is the thing under test.

  `docker/pi-simulator/agent.Dockerfile`: `debian:12-slim` + `nmap` + `uv` + the
  hardware-agent. Install `nmap` proper, **not** a minimal variant — a package without its
  scripts directory produces `NSE: failed to initialize the script engine` and breaks T7.

  `docker/pi-simulator/agent-entrypoint.sh`, exactly as PLAN.md §Startup order specifies:

  ```sh
  install -m600 /shared/agent.env /etc/dmitri/agent.env
  set -a; . /etc/dmitri/agent.env; set +a
  exec dmitri agent
  ```

  The agent reads process environment only (`transport/ingest.py:127`). Do **not** add a file
  loader to `src/agent/` — that would be an application code change, which this feature does
  not make.

  No `platform:` pin anywhere (PLAN.md §Known risk).
- **Dependencies**: —
- **Target Files**: [`.dockerignore`, `docker/pi-simulator/target.Dockerfile`,
  `docker/pi-simulator/smb.conf`, `docker/pi-simulator/agent.Dockerfile`,
  `docker/pi-simulator/agent-entrypoint.sh`]
- **Success Criteria**:
  - Both images build with no `--platform` flag and no error.
  - `docker run` of the target shows `smbd` listening on **both** 445 and 139.
  - In the agent image, `nmap --version` succeeds and `nmap --script-help vulners` resolves —
    proof the scripts directory shipped.
  - In the agent image, the `dmitri` console script resolves and prints its usage line.
    (**Not** `dmitri --help` — the product's CLI has no such flag; `agent/cli.py` prints
    usage and exits 2 on any unknown argv. Exit 2 here is correct application behaviour.)
  - The entrypoint, given a hand-written `/shared/agent.env`, installs it `0600` at
    `/etc/dmitri/agent.env`, exports its three variables, and `exec`s (PID 1 is the agent, not
    a shell).
  - `git diff --stat $DMI111_BASE -- backend/src hardware-agent/src` is empty (see
    **The T0 baseline is not `main`** above).

## What task 1 fixed in place, for task 2

- **The build context for both images is the repo root.** The Dockerfiles `COPY hardware-agent`
  and `COPY docker/pi-simulator/…`, so `compose.yaml` must set `context: ../..` with an
  explicit `dockerfile:` path.
- **The agent image bakes the hardware-agent in as a normal, non-editable install** at
  `/opt/agent`. Editing agent source therefore needs an image rebuild, not a container
  restart. That is the right default here — the simulator runs the shipped product, not a live
  checkout — but if task 6 has to iterate on `hardware-agent/src`, rebuild rather than expect
  a bind mount to take effect.

## Task 2: The compose stack and seeding
- **Description**: `docker/pi-simulator/compose.yaml` per PLAN.md §The stack, §Networking and
  §Startup order. Seven services: `db`, `migrate`, `api`, `worker`, `seed`, `agent`, `target`.
  See the two open decisions above for the image and healthcheck details.

  One user-defined bridge with the subnet pinned to **`172.31.7.0/24`**, so the subnet the
  agent detects and the subnet `scan` passes are known in advance. `target` publishes 445/139
  **on the bridge only** — never to the host, which on macOS may already hold 445. `agent`
  runs as root with `cap_add: [NET_RAW, NET_ADMIN]`: `-sn -PE`
  (`discovery/network_discovery.py:18`) and `-O` (`discovery/port_discovery.py:10`) both need
  raw sockets. **The API publishes 8000** — `frontend/.env` pins
  `VITE_API_URL=http://localhost:8000` and `vite.config.ts` throws if it is unset.

  `docker/pi-simulator/seed.sh`, the four steps in order, the last three of which need `api`
  healthy:

  1. `backend-bootstrap-org --org-name sim --email dev@example.invalid` → parse `org_id=` and
     `invite_token=`
  2. `POST /api/v1/invites/accept` with that token and `$SIM_ADMIN_PASSWORD` → **201**
  3. `backend-provision-agent --org-id <org_id> --display-name sim-pi --generate` → parse
     `private_key=` and `agent_id=`
  4. Write `/shared/agent.env` (named volume) with `BACKEND_URL`, `DEVICE_ID`,
     `DEVICE_PRIVATE_KEY`

  No idempotency guard and no seed marker: a cold start always begins with an empty volume
  (PLAN.md §Interface, "the state is ephemeral"). `backend-bootstrap-org` exits 1 on "org
  already exists", so a re-seed against a populated database would fail loudly anyway.

  `docker/pi-simulator/.env.example` carrying every variable in PLAN.md §Configuration:
  `NVD_API_KEY` (blank, operator pastes their own — with a key NVD allows ~50 req/30s against
  ~5 unauthenticated), `HIBP_ENABLED=false` (invite acceptance otherwise calls Have I Been
  Pwned over the network and rejects a fixed dev password), `REFRESH_COOKIE_SECURE=false`
  (plain HTTP), `CORS_ALLOWED_ORIGINS=http://localhost:5173` (the field fails closed when
  unset — `core/config.py:58`), `DATABASE_URL`, `JWT_SIGNING_SECRET`, `SIM_ADMIN_EMAIL` and
  `SIM_ADMIN_PASSWORD`.

  The password is fixed and committed **in `.env.example` only**, and must be ≥ 12 characters
  (`api/services/passwords.py:12`). PLAN.md §Configuration argues why it is not a secret;
  reproduce that reasoning as a comment in the file so nobody "fixes" it later.

  `docker/pi-simulator/.env` is gitignored already — verified: `.gitignore:138` matches it at
  any depth, and `.env.example` is not matched. **No `.gitignore` edit is needed**; do not add
  one.

  The simulator gets its **own** Postgres, database `dmitri_sim`. `./database.sh` owns
  `dmitri_test`, which CLAUDE.md reserves for the backend suite — simulated scans must never
  land there. Supabase local holds 54321–54329, so pick a port outside that range.
- **Dependencies**: Task 1
- **Target Files**: [`docker/pi-simulator/compose.yaml`, `docker/pi-simulator/seed.sh`,
  `docker/pi-simulator/.env.example`]
- **Success Criteria**:
  - `docker compose -f docker/pi-simulator/compose.yaml config` parses with a `.env` copied
    from `.env.example`.
  - The stack reaches a state where `db` and `api` are healthy and `migrate` and `seed` have
    exited **0**.
  - `alembic upgrade head` ran against `dmitri_sim`; `dmitri_test` is untouched.
  - `seed.sh` wrote `/shared/agent.env` with all three variables, and the `agents` row's
    public key matches the private key handed to the container.
  - The bridge is `172.31.7.0/24`; `target` has no host port binding; `agent` carries
    `NET_RAW` and `NET_ADMIN`.
  - No `platform:` key anywhere in the file.
  - `git diff --stat $DMI111_BASE -- backend/src hardware-agent/src` is empty (see
    **The T0 baseline is not `main`** above).

## What task 2 fixed in place, for tasks 3 and 5

- **`DATABASE_URL_DIRECT` is required and PLAN.md's variable table omits it.**
  `backend/alembic/env.py:24` raises `RuntimeError("DATABASE_URL_DIRECT is required for
  migrations.")` — `DATABASE_URL` alone will not migrate. compose derives it from
  `DATABASE_URL` rather than adding an operator-facing variable that would only ever hold the
  same value.
- **`UV_PROJECT_ENVIRONMENT=/opt/venv` is load-bearing, not decoration.** `./backend` is
  bind-mounted, so a bare `uv run` in the container would overwrite the developer's host
  `backend/.venv` — a macOS-aarch64 venv replaced by a Linux one. Do not remove it.
  `--frozen` on every `uv run` keeps `uv.lock` from churning.
- **The seeded password must not contain the org name or any ≥3-character part of the admin
  email.** `validate_policy` rejects both, so `simulator-dev-password` failed on `sim` *and*
  `dev`. It is now `Quiet-Harbour-Lantern`. If task 3 or a reviewer changes the password, the
  same rule applies.
- **`db` publishes 55432**, outside Supabase local's 54321–54329.

## What is load-bearing in `compose.yaml` — do not "simplify" these

From the task 2 approval. Two reviews already cut this file down; what survives survives for a
reason, and each of these looks removable but is not.

- **`networks.default.ipam`** is the only thing pinning `172.31.7.0/24`. Delete it and Docker
  picks a random subnet, breaking the known-subnet contract `scan` and the whole runbook rest on.
- **The `venv` named volume and `UV_PROJECT_ENVIRONMENT` are one mechanism, not two.**
  `./backend` is bind-mounted; without the redirect a container `uv run` overwrites the
  developer's host `backend/.venv` with a Linux one.
- **`seed`'s `volumes:` block repeats the anchor's two entries deliberately.** YAML merge keys
  **replace** lists rather than appending — dropping the repeat unmounts `/app` and the venv.
- **`BACKEND_URL: http://api:8000`** is read twice: by `seed.sh`'s invite POST, and written
  verbatim into `agent.env`.
- **In `seed.sh`, both the `HTTPError` catch and the `!= 201` check are needed.** `urlopen`
  raises on 4xx/5xx but returns quietly on 200, which is not the 201 the spec names.
- **`db`'s 55432 publish** is outside Supabase local's 54321–54329 and is the only host path
  into `dmitri_sim` for the runbook's `psql` calls.

## Task 3: `simulator.sh` and the `nspi` override
- **Description**: The root entry point, PLAN.md §Interface, plus
  `docker/pi-simulator/compose.nspi.yaml`. They ship together because `--nspi` cannot be
  verified without the override file.

  | Command | Behaviour |
  |---|---|
  | `./simulator.sh` | Start. **No-op with a message if already running.** A cold start wipes volumes, brings the stack up and seeds. |
  | `./simulator.sh scan [mode] [subnet]` | Log in as the seeded admin, enqueue a command, print the command id. Defaults `nspi` / `172.31.7.0/24`. |
  | `./simulator.sh stop` | `docker compose down -v`. |
  | `./simulator.sh logs [service]` | Passthrough. |
  | `./simulator.sh --nspi` | Connect-only against the deployed environment. `scan` is **refused**. |

  The no-op-if-running rule is load-bearing: it is what stops `./simulator.sh` typed out of
  habit from destroying a session's scans. `scan` logs in via `POST /api/v1/auth/login`
  (`routers/auth.py:36`) — `require_admin` → `require_user` → bearer JWT, and no CLI mints
  that token.

  **`--nspi` must refuse `scan`.** The agent still runs on the developer's laptop, so a scan
  in that mode records a Docker bridge as though it were a customer network and writes those
  rows into the one deployed environment that exists. `compose.nspi.yaml` drops `db`,
  `migrate`, `api`, `worker` and `seed`, leaving `agent` and `target`, with `BACKEND_URL`,
  `DEVICE_ID` and `DEVICE_PRIVATE_KEY` read from the operator's `.env`. It carries **no
  seeding at all**, so it can never provision against a deployed database.

  **No `simulator.ps1`.** Every other root script has a PowerShell twin and this one
  deliberately does not — an untested `.ps1` implies a promise we are not keeping. Say so in
  the script header, so the next reader and the `docs-sync` mirror-pair rule both know it is
  intentional.
- **Dependencies**: Task 2
- **Target Files**: [`simulator.sh`, `docker/pi-simulator/compose.nspi.yaml`]
- **Success Criteria**:
  - `./simulator.sh` on a clean machine brings the stack up and seeds; the agent reports
    `online`.
  - `./simulator.sh` a second time prints a message and **changes nothing** — scan count
    before equals scan count after. This is the criterion that protects a session's work.
  - `./simulator.sh scan` prints a command id and the row appears in `commands`.
  - `./simulator.sh stop` removes volumes; a following start comes back empty and re-seeded.
  - `./simulator.sh logs agent` streams the agent's logs.
  - `./simulator.sh --nspi scan` **exits non-zero with an explanation** and enqueues nothing.
  - `compose.nspi.yaml` defines only `agent` and `target`, and contains no `bootstrap-org` or
    `provision-agent` invocation.
  - The header states why there is no `.ps1`.
  - `git diff --stat $DMI111_BASE -- backend/src hardware-agent/src` is empty (see
    **The T0 baseline is not `main`** above).

## Task 3b: The agent emits no logs — fix it

**Operator decision, 2026-08-23: fix this inside DMI-111.** Offered the alternatives of
re-witnessing the tests on database state, or filing it and shipping a partial runbook, the
operator chose the fix. Consistent with the standing call on this issue: do the most in one
issue, and comment on it when scope grows.

**The defect.** `hardware-agent/src` configures no logging handler anywhere. Four modules call
`logging.getLogger(...)` (`daemon.py:24` among them) and there is **no** `basicConfig`,
`dictConfig`, `addHandler` or `setLevel` in the whole source tree — verified by grep over
`hardware-agent/src`. Python's last-resort handler drops everything below WARNING, so
`docker logs dmitri-sim-agent-1` returns **0 bytes**, before and after a scan, while the agent
demonstrably works: it connects, and commands reach `running`.

This is a **product** defect, not a simulator one. A Pi in the field is undebuggable today —
the harder version of the same problem, and the reason this is worth fixing rather than
routing around.

**Why it blocked tasks 4 and 5.** Five of the ten runbook tests take their witness from the
agent log: PLAN.md:287 (T1 fail mode), :321 (T3), :388 (T5), :428 (T7), and T6, whose entire
pass condition is "the agent log carries nmap's own stderr".

- **Description**: Configure logging once, at the daemon entry point, so the agent writes to
  stdout at a sensible level — the container runtime collects stdout, so that is the whole
  delivery mechanism. Do **not** add a handler per module, and do not log inside library code
  that has no entry point of its own.

  **Log no secrets.** `DEVICE_PRIVATE_KEY` and any bearer token must never reach a log record.
  `backend/tests/test_mailer.py` has the precedent worth copying: a test asserting no emitted
  record contains the sensitive value, on the success path *and* the failure paths.

  Level and format are yours to choose, but the five tests above must have a witness
  afterwards: an ingest failure, a `403`, a scan upload, a reconnect, the invoked `--script`
  CSV, and nmap's stderr on a failed unit.
- **Dependencies**: Task 3
- **Target Files**: [`hardware-agent/src/agent/`, `hardware-agent/tests/`]
- **Success Criteria**:
  - `docker logs` on the agent container is **non-empty** during a normal scan.
  - Each of the five witnesses above is present in the log of a real run.
  - A test asserts no log record contains `DEVICE_PRIVATE_KEY`'s value or a bearer token.
  - `cd hardware-agent && uv run pytest && uv run ruff check src tests` is green.
  - The diff touches **only** `hardware-agent/src/agent/` and `hardware-agent/tests/`.
  - A comment is posted on DMI-111 recording the defect and why scope grew.

**This task takes the full trio** — `agent-developer` → `test-engineer` → `code-reviewer` —
because it is `hardware-agent/` layer code.

**T0's fence widens to three scoped exceptions.** The permitted application-code diff is this
logging fix, Task 5b's host-scoped SMB normalization fix, plus Task 6's fix if T6's defect
proves real. Task 3b and Task 5b must be justified in the PR body; Task 6 requires a Linear
comment only if its defect is real. Everything else under `backend/src` and
`hardware-agent/src` must still be untouched.

## Task 4: The runbook README and registration
- **What `--nspi` requires — from the task 3 approval, quote this in the README.**
  `--nspi` reads three variables from `docker/pi-simulator/.env` that the committed
  `.env.example` **does not contain**: `BACKEND_URL`, `DEVICE_ID`, `DEVICE_PRIVATE_KEY`. The
  local `.env` deliberately lacks all three, so **`--nspi` fails today by design**.
  `compose.nspi.yaml` guards each with `${VAR:?set VAR in docker/pi-simulator/.env}`, so a
  missing one aborts `up` with that exact message before anything starts — quote that failure
  as the expected first experience. Also state: the agent must already be registered **manually**
  (the override carries no seeding at all), `scan` is refused in this mode, `DEVICE_ID` must
  belong to a throwaway org and **never** the pilot org, and the mode starts no local API or
  database — nothing listens on 8000 or 55432.

- **Also record, found in task 3 review:** `simulator.sh:60-61` tells the operator to copy
  `.env.example` to `.env`, but `.env.example` carries none of `BACKEND_URL`, `DEVICE_ID` or
  `DEVICE_PRIVATE_KEY` — the three variables `--nspi` needs. The failure is legible
  (`compose.nspi.yaml`'s `${VAR:?…}` names each missing variable), but the README must say
  plainly that `--nspi` needs three variables added by hand, and that provisioning them against
  a deployed environment is a deliberate manual act.

- **Description**: Two documentation jobs that cannot conflict.

  **`docker/pi-simulator/README.md`** — write T1–T8 from PLAN.md §Verification into it as the
  verification runbook, each tagged `[auto]` or `[manual]`, because this is the file DMI-112
  inherits when it turns them into a CI gate. `[auto]` means it runs headless on an amd64 CI
  runner with no deployed credentials; `[manual]` means it cannot. **T0 and T9 do not go in**
  — they are review gates for this PR, not reusable tests. After this PR merges the README is
  authoritative and PLAN.md is history; the two must not both be maintained.

  The README must also carry: both modes; the **pilot-org fence** (PLAN.md §`nspi` alternate
  mode — before any `nspi` run, confirm the `DEVICE_ID` belongs to a dedicated throwaway org;
  see `docs/cloud/railway/SETUP.md` and DMI-52); "stop your hand-run backend first, the API
  takes 8000"; and PLAN.md §Known risk, that a green run here proves **nothing** about the Pi
  (DMI-109 owns RSS, sweep time and the USB ceiling) and is **not** the arm64 wheel check
  either — that is a separate `docker run --platform linux/arm64`, deliberately fenced out.

  **Registration**, three narrow edits and no more (PLAN.md §Deliverables):
  - `.claude/skills/docs-sync/SKILL.md` — add `simulator.sh` to the root-script list in the
    frontmatter description, the ownership table and step 4. It must also record that this
    script is the **exception** to that section's "every root script is a `.sh`/`.ps1` mirror
    pair: never patch one without the other" rule, or a future docs-sync run will try to
    create the twin task 3 deliberately omitted.
  - Root `README.md` — one line, beside the existing `install.sh` / `database.sh` block
    (around `README.md:135–151`).
  - `.claude/docs/infra/deployment.md`, whose scope is already "dev-environment installers",
    plus the one-line description in `.claude/docs/infra/index.md`.

  Do not let this expand into rewriting the local-dev docs.
- **Dependencies**: Task 3
- **Target Files**: [`docker/pi-simulator/README.md`, `.claude/skills/docs-sync/SKILL.md`,
  `README.md`, `.claude/docs/infra/deployment.md`, `.claude/docs/infra/index.md`]
- **Success Criteria**:
  - T1–T8 are present with their tags and their pass/fail modes; T0 and T9 are absent.
  - The pilot-org fence, the port-8000 collision and both §Known risk paragraphs are all in
    the README.
  - `docs-sync`'s script list includes `simulator.sh` **and** its no-`.ps1` exception.
  - The root README change is a single line; `.claude/docs/infra` gains the simulator without
    a rewrite.
  - Every command quoted in the README was actually run and its output matches.

## Two T1 assertions in PLAN.md are wrong — corrected here

Found in task 2, then verified directly against `backend/src`.

**`online` is real, but it is not a database column.** `schemas/agents.py:17` exposes it and
`services/agents.py:22` computes it per request from `agent_connections.is_online()`, which is
an **in-process registry** (`services/agent_connections.py:53` — `agent_id in _registry`), as
are `connected_at` and `last_seen_at`. So PLAN.md T1's `curl … | jq '.agents[0].online'` is
**correct** and must stay; what must not happen is looking for an `online` column in SQL. The
task-2 coder read the absent column as an absent feature — half right, and the half that
matters for T1 is fine.

Consequence worth knowing: because the registry is per-process, `online` is only meaningful
while a **single** `api` container serves the request. That holds in this stack. If T1 ever
reports flapping, this is why — not a product bug.

**The agents list envelope is `data`, not `agents`.** `AgentListResponse`
(`schemas/agents.py:35`) wraps the list in `data`, so PLAN.md T1's
`jq '.agents[0].online'` is **wrong** and must be `jq '.data[0].online'`. Verified against the
schema and the live API.

**`target_subnet` being null is expected, not a defect.** It is **operator-set**, through
`routers/agents.py:72` → `set_target_subnet`. The agent does not report it on connect. The
agent *does* send its detected subnets (`command_channel.py:207`), which is a different thing
that PLAN.md §What already exists conflates. **Nobody should chase a null `target_subnet` as a
bug** in T1 or T5.

## Task 5: Run the automated runbook — T1, T2, T3, T4, T7, T8
- **Description**: This is the feature's gate and it stands in for the test-engineer step. Run
  the six `[auto]` tests from PLAN.md §Verification against the built stack, and record real
  output. Do not paraphrase — a test that was not run does not pass.

  - **T1** — one `agents` row, `display_name = sim-pi`, 64-hex public key matching the
    container's, and `online` is `true`. `online` false means the WebSocket never
    established: read the agent log for an `IngestConfigError` (malformed `agent.env`) or a
    `403` (public key mismatch).
  - **T2** — the command walks `queued → delivered → running → uploading → done`. Polling may
    miss a transition, so also assert `created_at`, `delivered_at`, `started_at` are non-null
    and monotonic. Stuck at `queued` means delivery never reached the socket: ADR-011 as
    amended 2026-08-13 makes delivery a **single attempt with no retry**.
  - **T3** — `POST /api/v1/scans` returned **202**; one `scans` row in `nspi` mode;
    `scan_hosts` non-zero; every `scan_hosts.host_id` resolves to a `hosts` row; the orphan
    query returns **0**. The schema joins through `scan_hosts`, and `ports` hang off
    `scan_host_id`, not `hosts.id`. **Then the negative half**: re-run the daemon with a
    corrupted `DEVICE_PRIVATE_KEY` and confirm **401**. A 2xx there is a security defect, not
    a simulator bug — stop and report it.
  - **T4** — the target's bridge address appears with 445 and 139 both `open`. 445/139 are in
    `NSPI_PORTS` (`agent/config.py`), so an empty result points at Samba, not at the profile.
    No host at all is the shape a silent privilege failure takes — see task 6.
  - **T7** — **The witness is decided, not open. Read this before running T7.**
    `smb-enum-shares` returns **nothing** against this target, and that is correct behaviour,
    not a defect. Cause, established in task 1 review: the target is **SMB2-only**. Samba 4.17
    defaults to `server min protocol = SMB2_02`, so `smb-protocols` reports dialects
    `202, 210, 300, 302, 311` and no `NT1`; `smb-enum-shares` and `smb-os-discovery` are
    SMB1/MSRPC-over-SMB1 scripts and so stay silent.

    Adding `server min protocol = NT1` to `smb.conf` makes it enumerate immediately — this was
    proven — and it was **rejected deliberately**. A simulator pinned to SMB1 would hide from
    the product what real customer networks actually return, and `NSPI_NSE_SCRIPTS`
    (`agent/config.py:57-61`) ships `smb-enum-shares` against those networks. Making the
    harness lie to satisfy an assertion is worse than fixing the assertion.

    **So expect `source_script` to carry `smb-protocols` and `smb2-security-mode`** — both
    confirmed to produce output against this target — and expect `smb-enum-shares` **silent**,
    recording the reason. If the team later wants the SMB1 path exercised on purpose, that is a
    decision about what the simulator represents and belongs in PLAN.md before `smb.conf`.

    Beyond the witness: `vulners` must appear in the invoked `--script` CSV and the run must
    complete with no NSE load error. **A zero CVE count is not a failure** — a bare Samba
    container may genuinely have none, which is exactly why `source_script` carries the proof
    instead.
  - **T8** — two scans accumulate; a repeat start preserves them; stop-then-start returns 1
    org, 1 agent, **0** scans. The dangerous failure is the third check returning 0, meaning
    a repeat start wipes a running stack.
- **Dependencies**: Task 4
- **Target Files**: none — verification only; any diff it forces belongs to the task that
  owns the file
- **Success Criteria**:
  - All six tests reported with the actual commands and their actual output.
  - T3's negative half ran and returned 401.
  - Any failure is diagnosed to a file and handed back to the owning task rather than
    patched here.

## Task 5b: Preserve actionable host-scoped SMB NSE findings
- **Description**: Nmap emits `smb2-security-mode` and `smb-protocols` under `<hostscript>`.
  Parsing correctly puts them in `HostInfo.host_scripts`, but normalization calls their
  extractors with `port=None`; both extractors immediately return `None`. Support host-scoped
  SMB signing and SMBv1 findings without inventing a port. Keep benign SMB2-only
  `smb-protocols` informational: it must not create a fake finding merely to act as execution
  evidence. Correct T7 documentation so direct nmap output witnesses benign `smb-protocols`,
  while persisted `source_script` witnesses the actionable `smb2-security-mode` result.
- **Dependencies**: Task 5
- **Target Files**: [`hardware-agent/src/agent/normalize/findings.py`,
  `hardware-agent/tests/test_findings.py`, `docker/pi-simulator/README.md`]
- **Success Criteria**:
  - A real `<hostscript>` `smb2-security-mode` result saying signing is not required produces
    one medium finding with `source_script="smb2-security-mode"` and `port=None`.
  - A real host-scoped `smb-protocols` result containing SMBv1 produces the existing SMBv1
    finding with `port=None`.
  - Benign SMB2-only `smb-protocols` produces no finding.
  - `cd hardware-agent && uv run pytest && uv run ruff check src tests` passes.
  - After rebuilding the agent, live T7 shows `smb2-security-mode` in persisted
    `source_script`, direct nmap still emits both SMB scripts, `vulners` remains in the invoked
    CSV, and no NSE load error occurs.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: T6 — a missing `NET_RAW` must fail legibly
- **Description**: *The test most likely to find something.* Start the stack, then run a
  second agent container **without** `--cap-add`, on the same network, with the same
  `agent.env`, and enqueue a scan against it.

  **Pass**: the command reaches `failed` with a populated `error_code`, and the agent log
  carries nmap's own stderr — *"You requested a scan type which requires root privileges"*.
  The path that should produce this is `_classify_nonzero` (`agent/scanner/nmap.py:38`),
  which raises `UnitScanError` carrying nmap's stderr text.

  **Fail mode, and the one to watch**: the command reaches `done` with zero hosts.
  `AgentSettings.unit_failure_threshold` defaults to `0.5` (`agent/config.py`), so a failure
  rate below that is absorbed into a partial result. A whole-scan privilege failure reported
  as a successful empty scan is a **product defect**, not a simulator defect — it would look
  identical on a real Pi with a broken capability set.

  **If the defect is real, fix it here.** Repair it in `hardware-agent/src/agent/`, add a
  regression test under `hardware-agent/tests/` so the fix does not depend on anyone re-running
  this harness, and post a comment on DMI-111 recording what was found and why the scope grew.
  The comment is written **only if the defect is real** — one written beforehand describes a
  bug that may not exist. This is the sole sanctioned exception to T0, and the operator
  authorised it explicitly (2026-08-23) over filing a separate issue.

  If the failure is already legible, this task changes no code and says so.
- **Dependencies**: Task 5b
- **Target Files**: [`hardware-agent/src/agent/scanner/nmap.py`,
  `hardware-agent/src/agent/config.py`, `hardware-agent/tests/`] — **conditional**; empty if
  the failure is already legible
- **Success Criteria**:
  - The uncapped run was actually performed and its terminal command status is reported.
  - If it reached `failed` with an `error_code` and nmap's stderr: no code change, and that
    is stated.
  - If it reached `done` with zero hosts: a fix, a regression test that fails without it, a
    green `uv run pytest` + `uv run ruff check src tests` in `hardware-agent/`, and a DMI-111
    comment.
  - No change under `backend/src`, and no change under `hardware-agent/src` unless the defect
    was confirmed.

## Task 7: Manual gates — T5, T0, T9 — OPS
- **Description**: The three tests an agent cannot complete alone. **Operator involvement
  required.**

  **T5 `[manual]` — WSS survives Railway's proxy. Throwaway org only. Connect-only: do not
  scan.** Pre-flight is non-negotiable: assert the `DEVICE_ID`'s org is **not** the pilot org
  before anything connects. Then `./simulator.sh --nspi`, wait five minutes, and count
  reconnects. Pass: the org is the throwaway org, one successful connect, `wss://` (not
  `ws://`) in the URL, **zero** reconnects, and `./simulator.sh scan` refuses. A reconnect
  loop means Railway's proxy is closing an idle WebSocket — a real finding for DMI-67 and a
  **new issue**, not a patch here.

  **T0 `[manual]` — application-code fence.** Against the DMI-111 baseline `522a835`, the only
  permitted `hardware-agent/src` diffs are Task 3b's logging fix, Task 5b's host-scoped SMB
  normalization fix, and Task 6's fix if its defect is confirmed. `backend/src` remains
  untouched by DMI-111. Both suites must be green with the backend reporting **0 skips**; a
  non-zero skip count means the database was down and the run proves nothing (CLAUDE.md).

  **T9 `[manual]` — the fence holds.** A review assertion before the PR: `git diff main --stat`
  touches only `simulator.sh`, `docker/`, `specs/037-*`, `docs/`, `.claude/`, the root
  `README.md` and `.dockerignore` — plus the approved Task 3b, Task 5b and conditional Task 6
  files under `hardware-agent/`. No CI workflow file
  (that is DMI-112). No Modbus, OPC-UA or EtherNet/IP emulator. No change under `frontend/`
  (DMI-88 and DMI-89 consume this). No `--platform linux/arm64` pin.
- **Dependencies**: Tasks 5b, 6
- **Target Files**: none
- **Success Criteria**:
  - T5's pre-flight org check ran and named a throwaway org, or T5 is explicitly deferred.
  - T0's DMI-111 diff is empty except Tasks 3b, 5b and Task 6's conditional permitted files,
    and the backend suite reports **0** skips.
  - Every T9 bullet is confirmed against a real `git diff main --stat`.
  - The PR body says `Fixes DMI-111`, notes the board in hand is a **Pi 3** — the one ADR-001
    rejected — and does not offer this run as evidence for DMI-109.

---

## Dependency graph

```
1 ──> 2 ──> 3 ──> 3b ──> 4 ──> 5 ──> 5b ──> 6 ──> 7
```

Fully sequential. Nothing here parallelises: each layer of the stack is the next one's
precondition.

## Status

| # | Task | Layer | Depends on | Status |
|---|---|---|---|---|
| 1 | Build context + the two images | infra | — | COMPLETED |
| 2 | Compose stack + seeding | infra | 1 | COMPLETED |
| 3 | `simulator.sh` + `nspi` override | infra | 2 | COMPLETED |
| 3b | Agent logging fix | hardware-agent | 3 | COMPLETED |
| 4 | Runbook README + registration | docs | 3b | COMPLETED |
| 5 | Run the automated runbook | verification | 4 | COMPLETED |
| 5b | Host-scoped SMB NSE findings | hardware-agent + docs | 5 | COMPLETED |
| 6 | T6 privilege-failure probe | hardware-agent (conditional) | 5b | COMPLETED |
| 7 | Manual gates T5/T0/T9 | ops | 5b, 6 | COMPLETED |

## Review Rejections

| Task | Count | Rejection |
|---|---|---|
| 1 | 1 | 2026-08-23 — every functional criterion passed and was independently re-run; rejected only for dead config. Seven lines restate a compiled Samba default or duplicate another mechanism (`.dockerignore:3,2,11`; `smb.conf:2,7,8,13,14`; `log file = /dev/stdout` vs `--debug-stdout` in `target.Dockerfile:12`). CLAUDE.md §2/§3. Fix is deletion only. |
| 2 | 1 | 2026-08-23 — every functional criterion passed and was independently re-verified against a real stack; rejected only for config simplification. (a) `compose.yaml:93-97` + `:15,:32,:85,:91` — a hand-named `sim` network doing what Compose's `default` already does; rename to `default:` keeping the `ipam` block and delete four `networks: [sim]` lines. (b) `seed.sh:4` — `cd /app` duplicates `working_dir: /app` (`compose.yaml:6`), inherited via the anchor. CLAUDE.md §2. |
| 3 | 1 | 2026-08-23 — all nine criteria passed on real output; rejected for one false message. `simulator.sh:73-75` prints "Up. API on http://localhost:8000, Postgres on 55432" unconditionally, but `--nspi` renders `agent`+`target` only — no api, no db, nothing on either port. In the one mode whose purpose is not confusing local with deployed, it points the operator at the wrong backend. |
