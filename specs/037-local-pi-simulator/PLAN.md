# PLAN — Local Pi simulator: containerized agent producing real scan data (DMI-111)

**Issue:** [DMI-111](https://linear.app/dmitri-imt/issue/DMI-111) ·
**Branch:** `feat/dmi-111` (kept deliberately; not Linear's suggested name) ·
**Research:** `docs/research/pi-simulator-and-integration-test-harness.md`

A plan, not a full spec. There is no new API route, no schema change, no screen and no
cross-layer contract, so `TRUTH.md` would restate the issue and `ARCHITECTURE.md` /
`DESIGN.md` would each be empty.

Refined with the operator on 2026-08-23 over four rounds. Decisions are recorded inline as
**Decided:**.

## Goal

`./simulator.sh` starts a "Pi". The **real** `dmitri agent` daemon registers, connects,
scans a real target and uploads real results, so DMI-89 and DMI-88 can be built against
live API responses instead of handwritten MSW mocks.

## What already exists

The audit below is why this is a plan and not a spec: **no application code changes are
required.** Every Expected item maps to code that is already shipped.

| Requirement | Where it already lives |
|---|---|
| `BACKEND_URL` / `DEVICE_ID` / `DEVICE_PRIVATE_KEY` from env | `hardware-agent/src/agent/transport/ingest.py:127` (`load_ingest_config`) |
| Daemon entrypoint | `dmitri agent` with no arguments → `run_daemon()`, `hardware-agent/src/agent/cli.py:61` |
| `wss://` derived from an `https://` backend | `_websocket_origin`, `transport/command_channel.py:83` |
| Subnet reporting on connect | `detect_available_subnets` (psutil), `utils/network.py`; sent at `command_channel.py:207` |
| `nspi` mode already includes `vulners` | `NSPI_NSE_SCRIPTS`, `agent/config.py` — last entry |
| Ed25519 keypair generation + registration | `backend-provision-agent --generate` (`backend/src/api/management/provision_agent.py`) |
| Signed upload | `ScanIngestClient` → `POST /api/v1/scans` → `202` |
| Org + admin invite seeding | `backend-bootstrap-org` (`backend/src/api/management/bootstrap_org.py`) |

So `hardware-agent/src/agent/` and `backend/src/` are **not touched**. If the build starts
editing either, stop — that is a signal the container is being made a special case instead
of running the product. The one sanctioned exception is T6; see **Known risk**.

## Interface

**Decided: a root `simulator.sh` wrapping `docker/pi-simulator/compose.yaml`.** The repo
already pairs its entry points this way — `install.sh`, `database.sh`, `lint.sh` — and the
mental model is "start a Pi", not "run a compose file".

| Command | Behaviour |
|---|---|
| `./simulator.sh` | Start. **No-op with a message if already running.** A cold start wipes volumes, brings the stack up, and seeds. |
| `./simulator.sh scan [mode] [subnet]` | Log in as the seeded admin, enqueue a command, print the command id. Defaults to `nspi` on `172.31.7.0/24`. |
| `./simulator.sh stop` | `docker compose down -v`. Everything goes. |
| `./simulator.sh logs [service]` | Passthrough to compose. |
| `./simulator.sh --nspi` | Start in alternate mode against the deployed environment. Connect-only — `scan` is refused. |

**Decided: no `simulator.ps1`.** Every other root script has a PowerShell twin, and this one
deliberately breaks the pattern. The simulator is a Linux-container harness whose Windows
path neither the operator nor the agent will exercise; an untested `.ps1` implies a promise
we are not keeping. Say so in the script header. A twin is a small follow-up if a Windows
developer appears.

**Decided: the state is ephemeral.** Scans accumulate within a session; nothing survives a
stop. This removes two things an earlier draft carried: the seed marker guard (there is
never a populated database to re-seed against) and a `reset` verb (stop-then-start *is*
reset). The no-op-if-running rule exists so that `./simulator.sh` typed out of habit cannot
destroy the session's scans.

**Decided: `--nspi` refuses `scan`.** The agent still runs on the developer's laptop, so a
scan in that mode would record a Docker bridge as though it were a customer network, and
write those rows into the **one** deployed environment that exists. A throwaway org limits
the blast radius but does not make the data useful. T5 — the only test using this mode —
needs the WebSocket, not a scan.

## The stack

**Decided: bind-mounted stock images, no `backend/Dockerfile`.** Railway builds the backend
with RAILPACK (`backend/railway.api.toml`) and that does not change. `docker compose` cannot
invoke RAILPACK, but it does not need to: a stock `python:3.12-slim` with `./backend` mounted
in and `uv run uvicorn` as the command is a dev runner, not a second way to build the
product. A `Dockerfile` would be a parallel build definition that nobody deploys and that
must be hand-kept in step with RAILPACK — what CLAUDE.md's "No temporary code" rule exists
to prevent.

Python is pinned to **3.12**: `hardware-agent/pyproject.toml` declares
`requires-python = ">=3.11,<3.13"`.

| Service | Image | Role |
|---|---|---|
| `db` | `postgres:16-alpine` | Simulator database, `dmitri_sim`. Healthcheck `pg_isready`. |
| `migrate` | `python:3.12-slim` + `./backend` | One-shot `uv run alembic upgrade head`. |
| `api` | `python:3.12-slim` + `./backend` | `uv run uvicorn api.main:app`. Healthcheck `/api/v1/health`. |
| `worker` | `python:3.12-slim` + `./backend` | `uv run backend-worker`. Enrichment + stale-command sweep. |
| `seed` | `python:3.12-slim` + `./backend` | One-shot. Org, admin user, agent, `agent.env`. |
| `agent` | `debian:12-slim` + `./hardware-agent` | nmap + uv + `dmitri agent`. `NET_RAW`, `NET_ADMIN`, root. |
| `target` | `debian:12-slim` + `samba` | Scan target on 445/139. |

**Decided: the simulator gets its own Postgres.** `./database.sh` already runs a local
Postgres, but it owns `dmitri_test`, which CLAUDE.md reserves for the backend suite.
Simulated scans, hosts and findings must not land there. Supabase local occupies 54321–54329,
so there is no port conflict.

**Decided: build the Samba target from `debian:12-slim`.** A third-party image such as
`dperson/samba` adds a supply-chain dependency to a security product's test harness, and its
arm64 availability is not something to bet the stack on. Installing `samba` over the Debian
base is about fifteen lines, builds natively on any architecture, and keeps us in control of
which ports the target opens — the target is the thing under test.

**Decided: `worker` is in the stack.** `run_worker_loop` does *not* deliver commands — that
is the API's WebSocket — but it enriches findings from KEV, EPSS and NVD. Feeding the Scans
and Hosts screens unenriched findings would reproduce exactly the "mocks encode our
assumptions" problem this issue exists to end. It needs outbound internet.

**Decided: no frontend service.** The developer runs `npm run dev` as they already do.
`frontend/Dockerfile` produces a production bundle with no hot reload — wrong for someone
actively editing DMI-88 and DMI-89 — and running Vite's watcher across a macOS bind mount is
the classic slow-and-flaky path.

**Decided: `platform` stays unpinned.** It builds native arm64 on Apple Silicon, which is
closer to the real aarch64 Pi than an emulated amd64 image, and leaves DMI-112's amd64 CI
runners fast. See **Known risk** for what this does *not* prove.

## Networking

- One user-defined bridge with an **explicit** subnet, `172.31.7.0/24`, so the subnet the
  agent detects and the subnet `scan` passes are known in advance rather than whatever
  Docker picks.
- `target` publishes 445/139 **on the bridge only**, never to the host — macOS may already
  hold 445.
- `agent` runs as root with `cap_add: [NET_RAW, NET_ADMIN]`. `-sn -PE`
  (`discovery/network_discovery.py:18`) and `-O` (`discovery/port_discovery.py:10`) both
  need raw sockets.
- Docker on macOS cannot reach the host LAN. Container mode scans the bridge and nothing
  else. Scanning a real network from a laptop is the native-install path, out of scope here.

**The API takes port 8000.** `frontend/.env` already pins `VITE_API_URL=http://localhost:8000`
and `vite.config.ts` throws if it is unset, so the existing frontend works untouched. The
consequence is that the simulator collides with a hand-run `uvicorn` — correct behaviour,
not a bug. The README says plainly: stop your local backend first.

## Startup order

```
db  →  migrate  →  api  →  seed  →  agent
                     ↘  worker
target (no dependencies)
```

`seed` runs after `api` is healthy because one of its four steps needs HTTP:

1. `backend-bootstrap-org --org-name sim --email dev@example.invalid`
   → prints `org_id=…` and `invite_token=…`
2. `POST /api/v1/invites/accept` with that token and the fixed dev password → `201`
3. `backend-provision-agent --org-id <org_id> --display-name sim-pi --generate`
   → prints `private_key=…` and `agent_id=…`
4. Write `/shared/agent.env` (named volume) with `BACKEND_URL`, `DEVICE_ID`,
   `DEVICE_PRIVATE_KEY`

No idempotency guard is needed: a cold start always begins with an empty volume.

**Decided: `/etc/dmitri/agent.env` is sourced by the entrypoint, not parsed by the agent.**
The agent reads process environment only. The entrypoint does
`install -m600 /shared/agent.env /etc/dmitri/agent.env; set -a; . /etc/dmitri/agent.env; set +a; exec dmitri agent`.
Adding a file loader to `src/agent/` would be a code change that buys nothing.

## Configuration

**Decided: a gitignored `docker/pi-simulator/.env` with a committed `.env.example`.**
`.env` is already gitignored repo-wide, and `backend/` and `frontend/` both document their
variables through a tracked `.env.example`. Reusing `backend/.env` is rejected: it is the
hand-run backend's config pointed at Supabase local, and the simulator needs a different
`DATABASE_URL`, `CORS_ALLOWED_ORIGINS` and `REFRESH_COOKIE_SECURE`. One file cannot serve
two contradictory setups.

| Variable | Value | Why |
|---|---|---|
| `NVD_API_KEY` | operator's key, copied in once | Unauthenticated NVD allows ~5 requests/30s; with a key ~50. There is no slowness to accept — just use the key. |
| `HIBP_ENABLED` | `false` | Invite acceptance otherwise calls Have I Been Pwned over the network, failing offline and rejecting a fixed dev password. |
| `REFRESH_COOKIE_SECURE` | `false` | The local stack is plain HTTP. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | The field fails closed when unset, so Vite gets no browser access without it. |
| `DATABASE_URL`, `JWT_SIGNING_SECRET` | simulator-local | Required by `backend/src/api/core/config.py`. |
| `SIM_ADMIN_EMAIL` / `SIM_ADMIN_PASSWORD` | fixed, in `.env.example` | See below. |

**Decided: a fixed, committed dev password.** A password is genuinely required — `require_admin`
→ `require_user` → bearer JWT, and the only way to mint that token is `POST /api/v1/auth/login`;
no CLI issues one. The operator types it into the login form while building two screens, and
`./simulator.sh scan` uses it to enqueue. It must be ≥ 12 characters
(`api/services/passwords.py:12`). It lives visibly in `.env.example` so nobody mistakes it for
a secret: the account is local-only, in an org named `sim`, in a throwaway database on a local
bridge, with no relationship to `nspi` or any real account. `compose.nspi.yaml` carries no
seeding at all, so it can never reach a deployed environment.

## Deliverables

| Path | Purpose |
|---|---|
| `simulator.sh` | Root entry point. Verb table above. No `.ps1` twin — say why in the header. |
| `docker/pi-simulator/compose.yaml` | The stack |
| `docker/pi-simulator/compose.nspi.yaml` | Connect-only override: `agent` + `target` only |
| `docker/pi-simulator/agent.Dockerfile` | `debian:12-slim` + nmap + uv + hardware-agent |
| `docker/pi-simulator/target.Dockerfile` | `debian:12-slim` + samba |
| `docker/pi-simulator/agent-entrypoint.sh` | Source `agent.env`, `exec dmitri agent` |
| `docker/pi-simulator/seed.sh` | The four seeding steps |
| `docker/pi-simulator/smb.conf` | Samba share for the target |
| `docker/pi-simulator/.env.example` | Every variable in the table above |
| `docker/pi-simulator/README.md` | Both modes, the pilot-org fence, and the verification runbook |
| `.dockerignore` | Keep `node_modules/`, `.venv/`, `Artigo/` out of the build context |

**Decided: register the script where people look.** Three narrow edits, no more: the root
script list in the `docs-sync` skill, one line in the root `README.md`, and the `.claude/docs`
entry covering local development. A fourth root script that no doc mentions is how the next
person fails to find it. Keep the edits to registration; do not let this expand into
rewriting the local-dev docs.

## `nspi` alternate mode

`compose.nspi.yaml` drops `db`, `migrate`, `api`, `worker` and `seed`, leaving `agent` and
`target`, with `BACKEND_URL`, `DEVICE_ID` and `DEVICE_PRIVATE_KEY` read from the operator's
`.env`. Provisioning against `nspi` is **manual and documented, not automated** — it writes
to a deployed database, so it stays a deliberate human act.

**Fence: never the pilot org.** Before any `nspi` run, confirm the `DEVICE_ID` belongs to a
dedicated throwaway org. See `docs/cloud/railway/SETUP.md` and DMI-52.

---

# Verification

**Where these live.** T1–T8 are written into `docker/pi-simulator/README.md` as the
verification runbook, tagged `[auto]` or `[manual]`, because that is the file DMI-112 inherits
when it turns them into a CI gate. This section is their *source*; after the PR merges the
README is authoritative, and the two must not both be maintained. **T0 and T9 stay here
only** — they are review gates for this PR, not reusable tests.

The tags: `[auto]` means it can run headless on an amd64 CI runner with no deployed
credentials. `[manual]` means it cannot.

| Test | Tag | What it covers |
|---|---|---|
| T0 | `[manual]` | No application code changed (this PR only) |
| T1 | `[auto]` | Stack up, agent online |
| T2 | `[auto]` | Command lifecycle |
| T3 | `[auto]` | Upload accepted, signed, associated |
| T4 | `[auto]` | Samba discovered on 445/139 |
| T5 | `[manual]` | WSS survives Railway's proxy |
| T6 | `[manual]` | Missing `NET_RAW` fails legibly |
| T7 | `[auto]` | `vulners` and the SMB scripts really run |
| T8 | `[auto]` | Session accumulates; stop wipes |
| T9 | `[manual]` | The fence holds (this PR only) |

Shorthand:

```bash
C="docker compose -f docker/pi-simulator/compose.yaml"
PSQL="$C exec -T db psql -U postgres -d dmitri_sim -tA -c"
API=http://localhost:8000
```

### T0 `[manual]` — no application code changed

**Intent:** prove the simulator did not quietly become a special case in the product.

```bash
git diff --stat main -- backend/src hardware-agent/src     # expect: empty
cd hardware-agent && uv run pytest && uv run ruff check src tests
cd .. && ./database.sh --test
```

**Pass:** the `git diff --stat` output is empty, and both suites are green with the backend
run reporting **0 skips**. A non-zero skip count means the database was not up and the run
proves nothing (CLAUDE.md).
**Fail mode:** a diff under `hardware-agent/src` — except the one permitted by T6, which must
then be justified in the PR body and in a Linear comment.

### T1 `[auto]` — the stack comes up and the agent is online

*Issue test case 1.*

```bash
./simulator.sh
$PSQL "select display_name, encode(public_key,'hex') from agents;"
curl -s $API/api/v1/agents -H "Authorization: Bearer $TOKEN" | jq '.agents[0].online'
```

`$TOKEN` comes from `POST /api/v1/auth/login` with the seeded admin credentials.

**Pass:** exactly one `agents` row, `display_name = sim-pi`, a 64-hex-character public key
matching the container's key; and `online` is `true`.
**Fail mode:** `online` false means the WebSocket did not establish — read
`./simulator.sh logs agent` for an `IngestConfigError` (a malformed `agent.env`) or a `403`
(public key mismatch between `provision_agent` and what the entrypoint sourced).

### T2 `[auto]` — the command walks the full lifecycle

*Issue test case 2.*

```bash
CMD=$(./simulator.sh scan nspi 172.31.7.0/24 | awk -F= '/command_id/{print $2}')

while :; do
  curl -s $API/api/v1/commands/$CMD -H "Authorization: Bearer $TOKEN" | jq -r .status
  sleep 2
done
```

**Pass:** the observed statuses are a prefix-ordered walk of
`queued → delivered → running → uploading → done`. Polling may miss a transition, so also
assert the timestamp columns are non-null and monotonically ordered:

```bash
$PSQL "select status, created_at, delivered_at, started_at from commands where id='$CMD';"
```

**Fail mode:** stuck at `queued` means delivery never reached the socket — ADR-011 as amended
2026-08-13 makes delivery a **single attempt**, with no retry, so a daemon that was briefly
disconnected simply never gets it. `failed` with an `error_code` is a real scan failure; read
it before re-running.

### T3 `[auto]` — upload is accepted, signed, and lands as related rows

*Issue test case 3.*

```bash
./simulator.sh logs agent | grep -E 'POST /api/v1/scans|202'
$PSQL "select s.scan_id, s.scan_mode, s.status,
              count(distinct sh.id) as scan_hosts,
              count(distinct sh.host_id) as hosts,
              count(distinct f.id) as findings
       from scans s
       left join scan_hosts sh on sh.scan_id = s.scan_id
       left join findings f on f.scan_id = s.scan_id
       group by s.scan_id, s.scan_mode, s.status;"

# no orphans: every finding must hang off a scan_host of its own scan
$PSQL "select count(*) from findings f
       left join scan_hosts sh on sh.id = f.scan_host_id
       where f.scan_host_id is not null and sh.scan_id <> f.scan_id;"
```

The schema associates through a join table: `scans.scan_id` ← `scan_hosts.scan_id`, and
`scan_hosts.host_id` → `hosts.id` (the org-scoped identity row, per ADR-014). `ports` hang
off `scan_hosts.id`, not off `hosts.id`. Findings carry both `scan_id` and `scan_host_id`.

**Pass:** `POST /api/v1/scans` returned **202** (`ScanIngestAcceptedResponse`); one `scans`
row in `nspi` mode; `scan_hosts` non-zero; every `scan_hosts.host_id` resolved to a `hosts`
row; and the orphan query returns **0**.

**Negative half — the signature is actually checked.** A 202 only proves the signature
verified if a bad one is refused. Run the daemon once with a corrupted key:

```bash
$C run --rm -e DEVICE_PRIVATE_KEY=$(python -c "print('00'*32)") agent
```

**Pass:** the upload is refused with **401** (`AgentUnauthenticated`).
**Fail mode:** a 2xx here means agent auth is not enforcing — stop and treat it as a security
defect, not a simulator bug.

### T4 `[auto]` — the Samba target is discovered on 445/139

*Issue test case 4.*

```bash
$PSQL "select sh.ip, p.port, p.protocol, p.state
       from scan_hosts sh join ports p on p.scan_host_id = sh.id
       where p.port in (445,139) order by p.port;"
```

**Pass:** the `target` container's bridge address appears, with 445 and 139 both `open`.
**Fail mode:** the host is discovered but the ports are missing → the `nspi` port list is
`502,4840,44818,445,139,3389,5985` (`agent/config.py:NSPI_PORTS`), so 445/139 *are* in scope;
an empty result points at Samba not listening, not at the scan profile. No host at all → see
T6, this is the shape a silent privilege failure takes.

### T5 `[manual]` — WSS survives Railway's proxy

*Issue test case 5.* **Throwaway org only. Connect-only: do not scan.**

Pre-flight, non-negotiable:

```bash
# assert the target org is NOT the pilot org before anything connects
echo "$DEVICE_ID → $(psql "$NSPI_DATABASE_URL" -tA -c \
  "select o.name from agents a join orgs o on o.id=a.org_id where a.id='$DEVICE_ID';")"
```

Then:

```bash
./simulator.sh --nspi
sleep 300 && ./simulator.sh logs agent | grep -ci 'reconnect'
```

**Pass:** the org name is the throwaway org; the log shows one successful connect, `wss://`
(not `ws://`) in the URL, and **zero** reconnects over five minutes. `./simulator.sh scan`
refuses to run in this mode.
**Fail mode:** a reconnect loop indicates Railway's proxy is closing an idle WebSocket — a
real finding for DMI-67, and a new issue rather than a patch here.

### T6 `[manual]` — a missing `NET_RAW` fails legibly

*Issue test case 6. This is the test most likely to find something.*

Start the stack, then run a second agent container **without** `--cap-add`, on the same
network, using the same `agent.env`, and enqueue a scan against it.

**Pass:** the command reaches `failed` with a populated `error_code`, and the agent log
carries nmap's own stderr — something like *"You requested a scan type which requires root
privileges"*. The path that should produce this is `_classify_nonzero`
(`agent/scanner/nmap.py:38`), which raises `UnitScanError` carrying nmap's stderr text.

**Fail mode — and the one worth watching:** the command reaches `done` with zero hosts.
`AgentSettings.unit_failure_threshold` defaults to `0.5` (`agent/config.py`), so a failure
rate below that is absorbed into a partial result. A whole-scan privilege failure reported as
a successful empty scan is a **product defect**, not a simulator defect — it would look
identical on a real Pi with a broken capability set.

**Decided: fix it inside this issue if it happens.** Repair it in
`hardware-agent/src/agent/`, add a regression test under `hardware-agent/tests/` so the fix
does not depend on anyone re-running this harness, and post a comment on DMI-111 recording
what was found and why the scope grew. The comment is written only if the defect is real —
one written beforehand describes a bug that may not exist. This is the sole sanctioned
exception to T0.

### T7 `[auto]` — `vulners` and the SMB scripts really run

The issue requires no divergence from the production script set, and a silently skipped NSE
script would make every finding count wrong.

```bash
./simulator.sh logs agent | grep -o 'vulners'
$PSQL "select count(*) from findings where cve_id is not null;"
$PSQL "select distinct source_script from findings;"
```

**Pass:** `vulners` appears in the invoked `--script` CSV and the run completes without an NSE
load error. A zero CVE count is **not** a failure — a bare Samba container may genuinely have
none. The `source_script` column is the better witness: the SMB scripts in `NSPI_NSE_SCRIPTS`
(`smb-protocols`, `smb2-security-mode`, `smb-enum-shares`) should appear against the target
even when `vulners` yields nothing.
**Fail mode:** `NSE: failed to initialize the script engine` means the nmap package ships
without its scripts directory. Install `nmap` proper, not a minimal variant.

### T8 `[auto]` — a session accumulates, a stop wipes

The state contract: scans pile up while the simulator runs, and nothing survives a stop.

```bash
./simulator.sh
./simulator.sh scan && ./simulator.sh scan
$PSQL "select count(*) from scans;"       # expect 2

./simulator.sh                            # already running
$PSQL "select count(*) from scans;"       # expect 2 — start must NOT wipe a running stack

./simulator.sh stop && ./simulator.sh
$PSQL "select count(*) from orgs;"        # expect 1
$PSQL "select count(*) from agents;"      # expect 1
$PSQL "select count(*) from scans;"       # expect 0
```

**Pass:** all five counts as annotated.
**Fail mode:** the third check returning 0 is the dangerous one — it means `./simulator.sh`
wipes a running stack, and a developer loses a session's work by typing the start command
twice.

### T9 `[manual]` — the fence holds

Not a runtime test; a review assertion before the PR is opened.

- `git diff main --stat` touches only `simulator.sh`, `docker/`, `specs/037-*`, `docs/`,
  `.claude/docs`, the root `README.md` and `.dockerignore` — plus, if T6 forced it, files
  under `hardware-agent/src/agent/` and `hardware-agent/tests/`.
- No CI workflow file was added — that is DMI-112.
- No Modbus, OPC-UA or EtherNet/IP emulator was added.
- No change under `frontend/` — DMI-88 and DMI-89 consume this.
- No `--platform linux/arm64` pin was added.

## Known risk

**A green run here says nothing about the Pi.** DMI-109 owns peak RSS under 1 GB, subnet
sweep wall-time and the USB 2.0 ceiling. A container on a developer laptop cannot speak to
any of them. Do not report this stack passing as evidence for DMI-109, and note in the PR
that the board in hand is a Pi 3 — the one ADR-001 rejected.

**A green run on Apple Silicon is not the arm64 wheel check either.** It happens to build
aarch64 wheels for `pydantic-core` and `cryptography`, but DMI-111 fences that check out
deliberately: it is a separate `docker run --platform linux/arm64`, re-run when those deps
bump. Say so in the README so nobody reads the coincidence as coverage.

## Definition of done

T0–T9 pass, or T6's defect is fixed with a regression test and a Linear comment. T1–T8 are
written into `docker/pi-simulator/README.md` with their tags. `simulator.sh` is registered in
the `docs-sync` script list, the root README and `.claude/docs`. The PR body says
`Fixes DMI-111`.
