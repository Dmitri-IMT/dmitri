# Local Pi simulator

The simulator runs the real `dmitri agent` daemon, a local backend and database, and
isolated targets for the targeted-scan demonstration. The vulnerable targets are attached
only to the internal Docker network `172.31.13.0/28`; their service ports are not published
on the host. The scan covers `172.31.13.0/29`, containing the five targets; agent `.13` and
gateway `.14` are outside it. The agent is dual-homed to reach the API and targets.
State is deliberately ephemeral: the matching `stop` command removes that simulator's
volumes.
The local backend image includes DejaVu Sans so API-generated PDF reports support Unicode.

## Local mode

Stop any hand-run backend first: the simulator API takes host port **8000** (and its
Postgres is exposed on 55432). From the repository root, create the local configuration and
start the stack:

```bash
test -f docker/pi-simulator/.env || cp docker/pi-simulator/.env.example docker/pi-simulator/.env
./simulator.sh
```

A second start is a no-op. Use `./simulator.sh scan` to enqueue the default `nspi` scan of
`172.31.7.0/24`, `./simulator.sh logs agent` to follow the daemon, and
`./simulator.sh stop` to wipe the session. See `./simulator.sh --help` for optional scan
mode and subnet arguments.

### Targeted-scan demonstration

The local profile includes HTTP/HTTPS, SSH, anonymous read-only FTP, guest SMB and Telnet
targets. They expose only synthetic data and intentionally weak configurations. The
`extensive` profile runs the seven service-targeted tools and NSE scripts for HTTP methods,
TLS, FTP anonymous access, SSH authentication, SMB protocol/signing and `vulners`. Vulners
uses the agent's outbound connection to correlate detected CPEs/versions with CVEs; a
correlation is reported as version evidence, not as proof of exploitation.

Start the lab as its own Compose project. Every start reconciles and rebuilds changed lab
services while retaining its database volume and the older local simulator data:

```bash
./simulator.sh lab-start
```

Use one full Dmitri scan for the presentation result:

```bash
./simulator.sh lab-scan
```

The command prints a `command_id` and `scan_id`. After that scan finishes, inspect and
validate the same persisted scan, replacing the placeholder with the returned scan ID:

```bash
./simulator.sh lab-verify <scan-id>
```

The verifier requires all five target hosts, the expected seven-tool unit coverage, the
expected evidence from each targeted tool, the configured NSE findings, and at least one
structured positive Vulners CPE/CVE correlation. Nikto is deliberately reported as
inconclusive by the current production adapter, so the verifier confirms its recorded
evidence without labeling it a confirmed vulnerability. It prints every persisted finding
and its available evidence, then returns a
non-zero exit status if any required evidence is missing. Review its full report before
using the scan as the presentation result. `./simulator.sh lab-stop` removes only the lab
database, containers and volumes after the demonstration.

### Recorded rehearsal (2026-10-21)

The [Nikto/testssl remediation record](../../specs/053-targeted-scan-lab/WEB-TOOLS-REMEDIATION.md), dated 2026-10-22, documents the implementation and measurements. Automatic selection in `nspi`/`extensive`, other tools and current evidence policies remain unchanged. Nikto retains the broad `2345789acf` tuning and now uses `-Pause 0.05`, `-maxtime 700s` and an 800 s unit timeout. Direct HTTP/HTTPS runs completed in 565/582 s (5,920 requests each). testssl's command, parser and unit limit are unchanged; its failure diagnostic now includes sanitized, bounded captured problem lines.

The single persisted integrated scan is `8d1fa696-6da0-4289-a959-400fe47fe848`; its raw API payload is saved at `../../scan-results/targeted-lab-2026-10-21.json`. It completed with 7 discovered hosts and 83 findings. It demonstrated ffuf exposures, TLS/NSE signals, SSH algorithm/authentication evidence, SMB enumeration and NSE evidence, Telnet cleartext, and structured Vulners version/CVE correlations. Vulners results are CPE/version matches with applicability unverified; distro backports may affect applicability.

The diagnostic replay on 2026-10-22 (`45039520-8e46-4f92-806f-89c729c63c40`) persisted 80 findings across five hosts and failed acceptance because both Nikto units hit the old 250 s cap. It is not the presentation result and must not be combined with another run. The final integrated scan (`b1dd4b7b-865a-4962-b2e4-df111a4e4a0f`) passed `./simulator.sh lab-verify`: completed, five hosts, 90 findings. Single-scan JSON: `../../scan-results/targeted-lab-2026-10-22.json`. Both Nikto units completed and persisted evidence, which remains inconclusive under current policy.

The agent needs outbound DNS/HTTPS for Vulners lookups. Target containers stay on the
internal network and have no published host ports. The `smb-vuln-ms17-010` script is not in
the `extensive` script list; do not attribute that Windows vulnerability to the Samba target.

## Deployed `nspi` mode

This is connect-only verification against the deployed environment. It starts only the
agent and target: there is no local API or database, and nothing listens on 8000 or 55432.
The override contains no seeding or provisioning.

Before connecting, register the agent **manually** against a dedicated throwaway org and
confirm that org is **never the pilot org**. Follow
[`docs/cloud/railway/SETUP.md`](../../docs/cloud/railway/SETUP.md) and DMI-52 for deployed
environment access. Then add these three values by hand to `docker/pi-simulator/.env`; the
committed `.env.example` deliberately does not contain them:

```text
BACKEND_URL=https://<deployed-api>
DEVICE_ID=<manually-provisioned-agent-id>
DEVICE_PRIVATE_KEY=<manually-provisioned-private-key>
```

Without them, `./simulator.sh --nspi` fails before starting anything. The expected first
failure with the normal local `.env` is:

```text
error while interpolating services.agent.environment.BACKEND_URL: required variable BACKEND_URL is missing a value: set BACKEND_URL in docker/pi-simulator/.env
```

After the manual variables and org check are complete, run `./simulator.sh --nspi`.
`./simulator.sh --nspi scan` is always refused so a laptop Docker bridge cannot be recorded
as a customer network in the deployed database.

## Verification runbook

`[auto]` means the check can run headlessly on an amd64 CI runner without deployed
credentials. `[manual]` means it cannot. Run the checks in order from the repository root.
The commands below were exercised against the current stack on 2026-08-23.

For API checks, load the simulator settings and obtain an admin token without printing it:

```bash
set -a; source docker/pi-simulator/.env; set +a
TOKEN=$(curl -fsS -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' --data "{\"email\":\"$SIM_ADMIN_EMAIL\",\"password\":\"$SIM_ADMIN_PASSWORD\"}" | jq -r .access_token)
```

### T1 `[auto]` — stack up and agent online

```bash
docker compose -f docker/pi-simulator/compose.yaml ps -a
curl -fsS http://localhost:8000/api/v1/agents -H "Authorization: Bearer $TOKEN" | jq '{count:(.data|length), agent:.data[0]}'
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select display_name, length(encode(public_key,'hex')) from agents;"
derived=$(docker compose -f docker/pi-simulator/compose.yaml exec -T agent sh -c '. /etc/dmitri/agent.env; export DEVICE_PRIVATE_KEY; python -c "import os; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; print(Ed25519PrivateKey.from_private_bytes(bytes.fromhex(os.environ[\"DEVICE_PRIVATE_KEY\"])).public_key().public_bytes_raw().hex())"')
stored=$(docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select encode(public_key,'hex') from agents;")
test "$derived" = "$stored" && echo 'public_key_matches=true'
```

Pass: `db` and `api` are healthy; `migrate` and `seed` exited 0; the API's `.data` envelope
contains exactly one `sim-pi` with `online: true`; the stored public key is 64 hex
characters and matches the private key installed in the container. A null `target_subnet`
is expected because that field is operator-set, not reported on connect.

Fail: `online: false` means the WebSocket did not establish. Inspect agent logs for malformed
configuration, a public-key mismatch, or a 403. Do not look for an `online` database column:
online state is an in-process API registry.

### T2 `[auto]` — command lifecycle

```bash
./simulator.sh scan
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -x -c "select status, error_code, created_at, delivered_at, started_at, completed_at from commands order by created_at desc limit 1;"
```

Poll the query while the scan runs. Pass: observed states form an ordered prefix of
`queued -> delivered -> running -> uploading -> done`; fast transitions may be missed, so
`created_at`, `delivered_at`, `started_at`, and `completed_at` must all be non-null and
monotonic at completion.

Fail: a command stuck at `queued` missed the WebSocket's single delivery attempt. A terminal
`failed` is a real scan failure; read `error_code` and the agent log before retrying.

### T3 `[auto]` — signed upload and relational integrity

```bash
docker compose -f docker/pi-simulator/compose.yaml logs agent | grep 'POST http://api:8000/api/v1/scans' | tail -1
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -x -c "select s.scan_id, s.scan_mode, s.status, count(distinct sh.id) as scan_hosts, count(distinct sh.host_id) as hosts, count(distinct f.id) as findings from scans s left join scan_hosts sh on sh.scan_id=s.scan_id left join findings f on f.scan_id=s.scan_id group by s.scan_id,s.scan_mode,s.status;"
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select count(*) from scan_hosts sh left join hosts h on h.id=sh.host_id where h.id is null;"
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select count(*) from findings f left join scan_hosts sh on sh.id=f.scan_host_id where f.scan_host_id is not null and sh.scan_id<>f.scan_id;"
```

Pass: the upload log says `202 Accepted`; one completed `nspi` scan has non-zero
`scan_hosts`; every `scan_hosts.host_id` resolves to `hosts.id`; and both orphan queries
return 0. The schema joins scans through `scan_hosts`; ports hang off `scan_hosts.id`, not
`hosts.id`.

Prove the negative half with a signed but deliberately wrong private key (the key value is
never printed):

```bash
docker compose -f docker/pi-simulator/compose.yaml exec -T agent sh -c '. /etc/dmitri/agent.env; export DEVICE_ID; python - <<'"'"'PY'"'"'
import os
import httpx
from agent.transport.signing import build_device_signature_headers

body = b"{}"
headers = build_device_signature_headers(
    "POST", "/api/v1/scans", body, os.environ["DEVICE_ID"], bytes(32)
)
response = httpx.post(
    "http://api:8000/api/v1/scans",
    content=body,
    headers={**headers, "Content-Type": "application/json"},
)
print(response.status_code, response.text)
PY'
```

Pass: the negative request returns 401 with `signature verification failed`. Fail: any 2xx
is a security defect; stop and report it rather than treating it as a harness failure.

### T4 `[auto]` — Samba target on 445 and 139

```bash
TARGET_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dmitri-sim-target-1); echo "target_ip=$TARGET_IP"
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select sh.ip,p.port,p.protocol,p.state from scan_hosts sh join ports p on p.scan_host_id=sh.id where sh.ip='$TARGET_IP' and p.port in (445,139) order by p.port;"
```

Pass: the target bridge address appears twice, with TCP 139 and 445 both `open`. Fail: if
the host exists but the ports do not, inspect Samba because both ports are in `NSPI_PORTS`.
No target host at all has the same shape as a privilege failure; continue to T6.

### T5 `[manual]` — deployed WSS survives Railway's proxy

Use only the manually provisioned throwaway-org agent described above. Before connecting,
query the deployed database for the configured `DEVICE_ID`, name its org aloud, and abort if
it is the pilot org. Start deployed mode, confirm the log's successful connection URL begins
with `wss://`, observe it for five minutes, and count reconnect messages. Also confirm the
scan verb is refused.

Pass: the named org is the throwaway org, there is one successful WSS connection, zero
reconnects over five minutes, and scan remains refused. Fail: any pilot-org association is a
hard stop. A reconnect loop is a Railway proxy finding for DMI-67 and a new issue, not a
simulator patch.

### T6 `[manual]` — missing raw-socket capability fails legibly

Start a second agent container on the simulator bridge using the same installed agent file,
but remove `NET_RAW` and `NET_ADMIN`; ensure the normal agent is not competing for that
device slot. Enqueue a scan for the uncapped daemon and follow both its log and the latest
command row.

Pass: the command reaches `failed`, `error_code` is populated, and the log contains nmap's
own root-privilege stderr. Fail: `done` with zero hosts is a product defect; repair the agent
with a regression test rather than changing this harness. This check deliberately stays
manual because it coordinates a second daemon and validates a failure path.

### T7 `[auto]` — production NSE scripts execute

```bash
docker compose -p dmitri-targeted-lab-demo -f docker/pi-simulator/compose.yaml -f docker/pi-simulator/compose.lab.yaml logs agent | grep 'invoking nmap:' | tail -6
docker compose -p dmitri-targeted-lab-demo -f docker/pi-simulator/compose.yaml -f docker/pi-simulator/compose.lab.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select count(*) from findings where cve_id is not null;"
docker compose -p dmitri-targeted-lab-demo -f docker/pi-simulator/compose.yaml -f docker/pi-simulator/compose.lab.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c "select distinct source_script from findings where source_script is not null order by source_script;"
```

Pass: the invoked script CSV contains `vulners` and the run has no NSE load error. The
targeted-lab profile intentionally enables SMBv1 and disables required SMB signing on the
isolated Samba target; `smb-protocols` and `smb2-security-mode` should therefore produce
their supported findings in the lab scan. The separate `compose.nspi.yaml` target retains
its original SMB2-only configuration. Use `lab-verify` to check the NSE evidence; do not
launch a second scan for the presentation result.

Fail: `NSE: failed to initialize the script engine` means the agent image lacks the full
nmap script directory. Silence from `smb-enum-shares` alone is not a failure.

### T8 `[auto]` — session accumulation and wipe

```bash
./simulator.sh scan
./simulator.sh scan
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c 'select count(*) from scans;'
./simulator.sh
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c 'select count(*) from scans;'
./simulator.sh stop && ./simulator.sh
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c 'select count(*) from orgs;'
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c 'select count(*) from agents;'
docker compose -f docker/pi-simulator/compose.yaml exec -T db psql -U postgres -d dmitri_sim -tA -c 'select count(*) from scans;'
```

Wait for each command to finish before counting. Pass: the first two counts are 2 and 2;
the repeat start says it is leaving the stack alone; after stop and cold start, the org,
agent, and scan counts are 1, 1, and 0. Fail: the count falling to 0 on the repeat start means
a harmless-looking start destroyed the active session.

## Scope and known risks

A green run here proves **nothing about Raspberry Pi performance or compatibility**. DMI-109
owns peak RSS under 1 GB, subnet sweep wall-time, and the USB 2.0 ceiling. The board in hand
is a Pi 3, the model ADR-001 rejected; do not cite a laptop-container run as DMI-109 evidence.

A green Apple Silicon run is **not the arm64 wheel check** either. It may happen to build
aarch64 wheels for `pydantic-core` and `cryptography`, but that check is a separate
`docker run --platform linux/arm64` performed when those dependencies change and is
deliberately outside this simulator runbook.
