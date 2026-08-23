# PLAN — Local Pi simulator: containerized agent producing real scan data (DMI-111)

**Issue:** [DMI-111](https://linear.app/dmitri-imt/issue/DMI-111) ·
**Branch:** `feat/dmi-111` (kept deliberately; not Linear's suggested name) ·
**Research:** `docs/research/pi-simulator-and-integration-test-harness.md`

A plan, not a full spec. There is no new API route, no schema change, no screen and no
cross-layer contract, so `TRUTH.md` would restate the issue and `ARCHITECTURE.md` /
`DESIGN.md` would each be empty. Decisions are recorded inline as **Decided:**.

## Goal

One command brings up a stack in which the **real** `dmitri agent` daemon registers,
connects, scans a real target and uploads real results, so DMI-89 and DMI-88 can be built
against live API responses instead of handwritten MSW mocks.

## What already exists

The audit below is the reason this is a plan and not a spec: **no application code
changes are required.** Every Expected item maps to code that is already shipped.

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

Two consequences:

1. `hardware-agent/src/agent/` and `backend/src/` are **not touched**. If the build starts
   editing either, stop — that is a signal the container is being made a special case
   instead of running the product.
2. The only exception is T6 below, which may expose a genuine defect. See **Known risk**.

## Approach

### The stack

**Decided: bind-mounted stock images, no `backend/Dockerfile`.** Railway builds the backend
with RAILPACK (`backend/railway.api.toml`) and that does not change. `docker compose` cannot
invoke RAILPACK, but it does not need to: a stock `python:3.12-slim` with `./backend` mounted
in and `uv run uvicorn` as the command is a dev runner, not a second way to build the
product. Writing a `Dockerfile` would create a parallel build definition that nobody deploys
and that must be hand-kept in step with RAILPACK — which is what CLAUDE.md's "No temporary
code" rule exists to prevent.

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
| `target` | `dperson/samba` (or `debian:12-slim` + `samba`) | Scan target on 445/139. |

**Decided: the simulator gets its own Postgres, not the Supabase one.** `./database.sh`
already runs a local Postgres, but it owns `dmitri_test`, which CLAUDE.md reserves for the
backend suite. Simulated scans, hosts and findings must not land there.

**Decided: `worker` is in the stack.** `run_worker_loop` does *not* deliver commands — that
is the API's WebSocket — but it enriches findings from KEV/EPSS/NVD. Since the point of this
issue is to feed the Scans and Hosts screens realistic data, unenriched findings would
undercut it. The worker needs outbound internet; note that in the README.

### Networking

- One user-defined bridge with an **explicit** subnet, `172.31.7.0/24`, so the subnet the
  agent detects and the subnet passed to the enqueue call are known in advance rather than
  whatever Docker picks.
- `target` publishes 445/139 **on the bridge only**, never to the host — macOS may already
  hold 445.
- `agent` runs as root with `cap_add: [NET_RAW, NET_ADMIN]`. `-sn -PE`
  (`discovery/network_discovery.py:18`) and `-O` (`discovery/port_discovery.py:10`) both
  need raw sockets.
- Docker on macOS cannot reach the host LAN. Container mode scans the bridge and nothing
  else. Scanning a real network from a laptop is the native-install path and is out of scope.

### Startup order

`docker compose up` must satisfy test T1 unattended, so seeding lives inside compose:

```
db  →  migrate  →  api  →  seed  →  agent
                     ↘  worker
target (no dependencies)
```

`seed` runs after `api` is healthy because one of its four steps needs HTTP:

1. `backend-bootstrap-org --org-name sim --email dev@example.invalid`
   → prints `org_id=…` and `invite_token=…`
2. `POST /api/v1/invites/accept` with that token and a fixed dev password
   (≥ 12 characters — `api/services/passwords.py:12`) → `201`, admin user exists
3. `backend-provision-agent --org-id <org_id> --display-name sim-pi --generate`
   → prints `private_key=…` and `agent_id=…`
4. Write `/shared/agent.env` (named volume) with `BACKEND_URL`, `DEVICE_ID`,
   `DEVICE_PRIVATE_KEY`

**Decided: `/etc/dmitri/agent.env` is sourced by the entrypoint, not parsed by the agent.**
The agent reads process environment only. The entrypoint does
`install -m600 /shared/agent.env /etc/dmitri/agent.env; set -a; . /etc/dmitri/agent.env; set +a; exec dmitri agent`.
Adding a file loader to `src/agent/` would be a code change that buys nothing.

`seed` writes a marker file into the shared volume and exits early if it is present, so a
second `docker compose up` does not fail on `bootstrap_org`'s "org already exists" (exit 1).

### Backend environment

Required by `backend/src/api/core/config.py`: `DATABASE_URL`, `JWT_SIGNING_SECRET`.
Also set for the simulator:

- `HIBP_ENABLED=false` — invite acceptance otherwise calls Have I Been Pwned over the
  network, making seeding fail offline and rejecting a fixed dev password.
- `REFRESH_COOKIE_SECURE=false` — the local stack is plain HTTP.
- `CORS_ALLOWED_ORIGINS=http://localhost:5173` — the field fails closed when unset, so the
  Vite dev server gets no browser access without this.

### `nspi` alternate mode

An override file, `compose.nspi.yaml`, drops `db`, `migrate`, `api`, `worker` and `seed`,
and leaves only `agent` and `target`, with `BACKEND_URL`, `DEVICE_ID` and
`DEVICE_PRIVATE_KEY` read from an operator-supplied `.env`.

Provisioning against `nspi` is **manual and documented, not automated**. It writes to a
deployed database, so it stays a deliberate human act.

**Fence: never the pilot org.** Before any `nspi` run, confirm the `DEVICE_ID` belongs to a
dedicated throwaway org. See `docs/cloud/railway/SETUP.md` and DMI-52.

## Deliverables

| Path | Purpose |
|---|---|
| `docker/pi-simulator/compose.yaml` | The stack |
| `docker/pi-simulator/compose.nspi.yaml` | Alternate-mode override |
| `docker/pi-simulator/agent.Dockerfile` | `debian:12-slim` + nmap + uv + hardware-agent |
| `docker/pi-simulator/agent-entrypoint.sh` | Source `agent.env`, `exec dmitri agent` |
| `docker/pi-simulator/seed.sh` | The four seeding steps, marker-guarded |
| `docker/pi-simulator/smb.conf` | Samba share for the target |
| `docker/pi-simulator/README.md` | Both modes, the pilot-org fence, worker internet need |
| `.dockerignore` | Keep `node_modules/`, `.venv/`, `Artigo/` out of the build context |

Invocation: `docker compose -f docker/pi-simulator/compose.yaml up`. No root wrapper script
— if one is wanted later it is a two-line follow-up, and `docs-sync` owns the root scripts.

---

# Verification

Run in order. T0 first — it proves the premise that nothing in Python changed. T1–T6 are the
issue's six test cases. T7–T9 guard failure modes this plan introduces.

Shorthand used below:

```bash
C="docker compose -f docker/pi-simulator/compose.yaml"
PSQL="$C exec -T db psql -U postgres -d dmitri_sim -tA -c"
API=http://localhost:8000
```

### T0 — no application code changed

**Intent:** prove the simulator did not quietly become a special case in the product.

```bash
git diff --stat main -- backend/src hardware-agent/src     # expect: empty
cd hardware-agent && uv run pytest && uv run ruff check src tests
cd .. && ./database.sh --test
```

**Pass:** the `git diff --stat` output is empty, and both suites are green with the backend
run reporting **0 skips**. A non-zero skip count means the database was not up and the run
proves nothing (CLAUDE.md).
**Fail mode:** a diff under `hardware-agent/src` — except the one permitted by T6, which
must then be justified in the PR body.

### T1 — the stack comes up and the agent is online

*Issue test case 1.*

```bash
$C up -d --wait
$PSQL "select display_name, encode(public_key,'hex') from agents;"
curl -s $API/api/v1/agents -H "Authorization: Bearer $TOKEN" | jq '.agents[0].online'
```

`$TOKEN` comes from `POST /api/v1/auth/login` with the seeded admin credentials.

**Pass:** exactly one `agents` row, `display_name = sim-pi`, a 64-hex-character public key
matching the container's key; and `online` is `true`.
**Fail mode:** `online` false means the WebSocket did not establish — read
`$C logs agent` for an `IngestConfigError` (a malformed `agent.env`) or a `403`
(public key mismatch between `provision_agent` and what the entrypoint sourced).

### T2 — the command walks the full lifecycle

*Issue test case 2.*

```bash
CMD=$(curl -s -X POST $API/api/v1/agents/$AGENT_ID/commands \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"scan_mode":"nspi","subnet":"172.31.7.0/24"}' | jq -r .command_id)

while :; do
  curl -s $API/api/v1/commands/$CMD -H "Authorization: Bearer $TOKEN" | jq -r .status
  sleep 2
done
```

**Pass:** the observed statuses are a prefix-ordered walk of
`queued → delivered → running → uploading → done`. Polling may miss a transition, so also
assert the timestamp columns are all non-null and monotonically ordered:

```bash
$PSQL "select status, created_at, delivered_at, started_at from commands where id='$CMD';"
```

**Fail mode:** stuck at `queued` means delivery never reached the socket — ADR-011 as
amended 2026-08-13 makes delivery a **single attempt**, with no retry, so a daemon that was
briefly disconnected simply never gets it. `failed` with an `error_code` is a real scan
failure; read it before re-running.

### T3 — upload is accepted, signed, and lands as related rows

*Issue test case 3.*

```bash
$C logs agent | grep -E 'POST /api/v1/scans|202'
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
row (`hosts` count equals `scan_hosts` count); and the orphan query returns **0**.

**Negative half — the signature is actually checked.** A 202 only proves the signature
verified if a bad one is refused. Run the daemon once with a corrupted key:

```bash
$C run --rm -e DEVICE_PRIVATE_KEY=$(python -c "print('00'*32)") agent
```

**Pass:** the upload is refused with **401** (`AgentUnauthenticated`), not accepted.
**Fail mode:** a 2xx here means agent auth is not enforcing — stop and treat it as a
security defect, not a simulator bug.

### T4 — the Samba target is discovered on 445/139

*Issue test case 4.*

```bash
$PSQL "select sh.ip, p.port, p.protocol, p.state
       from scan_hosts sh join ports p on p.scan_host_id = sh.id
       where p.port in (445,139) order by p.port;"
```

**Pass:** the `target` container's bridge address appears, with 445 and 139 both `open`.
**Fail mode:** the host is discovered but the ports are missing → the `nspi` port list is
`502,4840,44818,445,139,3389,5985` (`agent/config.py:NSPI_PORTS`), so 445/139 *are* in
scope; an empty result points at Samba not listening, not at the scan profile.
No host at all → see T6, this is the shape a silent privilege failure takes.

### T5 — WSS survives Railway's proxy

*Issue test case 5.* **Run against the throwaway org only.**

Pre-flight, non-negotiable:

```bash
# assert the target org is NOT the pilot org before anything connects
echo "$DEVICE_ID → $(psql "$NSPI_DATABASE_URL" -tA -c \
  "select o.name from agents a join orgs o on o.id=a.org_id where a.id='$DEVICE_ID';")"
```

Then:

```bash
docker compose -f docker/pi-simulator/compose.yaml -f docker/pi-simulator/compose.nspi.yaml up -d
sleep 300 && $C logs agent | grep -ci 'reconnect'
```

**Pass:** the org name is the throwaway org; the log shows one successful connect, `wss://`
(not `ws://`) in the URL, and **zero** reconnects over five minutes.
**Fail mode:** a reconnect loop indicates Railway's proxy is closing an idle WebSocket —
that is a real finding for DMI-67, and belongs in a new issue rather than being patched here.

### T6 — a missing `NET_RAW` fails legibly

*Issue test case 6. This is the test most likely to find something.*

```bash
$C up -d --no-deps --scale agent=0
docker run --rm --network pi-simulator_default \
  --env-file <(...) pi-simulator-agent   # deliberately WITHOUT --cap-add
```

Then enqueue a scan as in T2.

**Pass:** the command reaches `failed` with a populated `error_code`, and the agent log
carries nmap's own stderr — something like *"You requested a scan type which requires root
privileges"*. The path that should produce this is `_classify_nonzero`
(`agent/scanner/nmap.py:38`), which raises `UnitScanError` carrying nmap's stderr text.

**Fail mode — and the one worth watching:** the command reaches `done` with zero hosts.
`AgentSettings.unit_failure_threshold` defaults to `0.5` (`agent/config.py`), so a failure
rate below that is absorbed into a partial result. If a whole-scan privilege failure is
reported as a successful empty scan, **that is a product defect, not a simulator defect** —
it would look identical on a real Pi with a broken capability set. Fix it in
`hardware-agent/src/agent/`, and say so explicitly in the PR: it is the one sanctioned
exception to T0.

### T7 — `vulners` really runs in `nspi` mode

The issue requires no divergence from the production script set, and a silently skipped NSE
script would make every finding count wrong.

```bash
$C logs agent | grep -o 'vulners'
$PSQL "select count(*) from findings where cve_id is not null;"
$PSQL "select distinct source_script from findings;"
```

**Pass:** `vulners` appears in the invoked `--script` CSV, and the run completes without an
NSE load error. A zero CVE count is **not** a failure — a bare Samba container may genuinely
have none; the assertion is that the script ran, not that it found something. The
`source_script` column is the better witness: the SMB scripts in `NSPI_NSE_SCRIPTS`
(`smb-protocols`, `smb2-security-mode`, `smb-enum-shares`) should appear against the Samba
target even when `vulners` yields nothing.
**Fail mode:** `NSE: failed to initialize the script engine` means the nmap package in the
image ships without the scripts directory. Install `nmap` proper, not a minimal variant.

### T8 — `docker compose up` twice is safe

Guards the seeding idempotency this plan introduces.

```bash
$C down && $C up -d --wait
$PSQL "select count(*) from orgs;"    # expect 1
$PSQL "select count(*) from agents;"  # expect 1
```

**Pass:** counts stay at 1 and `seed` exits 0 on the second run.
**Fail mode:** `seed` exits 1 with "org already exists" — the marker guard is missing or the
marker volume was not persisted.

### T9 — the fence holds

Not a runtime test; a review assertion before the PR is opened.

- `git diff main --stat` touches only `docker/`, `specs/037-*`, `docs/` and `.dockerignore`
  (plus, if T6 forced it, one file under `hardware-agent/src/agent/`).
- No CI workflow file was added — that is DMI-112.
- No Modbus, OPC-UA or EtherNet/IP emulator was added.
- No change under `frontend/` — DMI-88 and DMI-89 consume this.
- No `--platform linux/arm64` build was added.

## Known risk

**A green run here says nothing about the Pi.** DMI-109 owns peak RSS under 1 GB, subnet
sweep wall-time and the USB 2.0 ceiling. A container on a developer laptop cannot speak to
any of them. Do not report this stack passing as evidence for DMI-109, and note in the PR
that the board in hand is a Pi 3 — the one ADR-001 rejected.

## Definition of done

T0–T9 all pass (or T6's failure is fixed and documented), the README covers both modes and
the pilot-org fence, and the PR body says `Fixes DMI-111`.
