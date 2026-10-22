# Dmitri physical-Raspberry target lab

This Compose project starts only six vulnerable training targets. It has no Dmitri agent,
backend, worker, or database for scan results. The real Raspberry runs its installed agent
and scans these hosts over the physical LAN.

Targets reuse the checked-in HTTP, SSH, FTP, SMB, and Telnet fixtures. MySQL is pinned to
`mysql:5.7.30`, an upstream release Oracle lists as affected by CVE-2020-14559 and
CVE-2020-14553. The image and server banner must still be observed during the first build and
scan; a Vulners version/CPE match is a correlation, not proof of applicability. Nmap's
current `extensive` profile includes version detection and `vulners`; it does not include
the optional `mysql-info` NSE script.

## Network prerequisites

Run Docker Engine inside a Linux VM whose virtual NIC is bridged to the same wired LAN as
the Raspberry. Docker Desktop for Windows does not support macvlan. The hypervisor's
virtual switch/NIC must pass multiple MAC addresses (promiscuous/forged-transmit mode, as
named by the hypervisor). Reserve six unused addresses outside the DHCP pool and set the
VM interface, subnet and gateway in `.env`. Copy `.env.example` to `.env` and replace the
example values first.

Macvlan containers have distinct LAN IPs and are reachable by other LAN devices. The Linux
VM host itself cannot communicate directly with those macvlan containers by default. No
target ports are published through Docker port forwarding; the deliberately weak services
are visible on the LAN, so connect the VM only to a controlled network where the operator
is authorized to run this assessment.

## Run from the Linux VM

```bash
cp .env.example .env
# Edit .env for the actual bridged interface and reserved LAN addresses.
docker compose config
docker compose up -d --build
docker compose ps
```

From the Raspberry, confirm reachability and run one `extensive` scan against the six-IP
CIDR that contains only the targets. Inspect the persisted scan JSON and verify tool
coverage, evidence, MySQL version/CPE and any CVE correlation. Do not treat version
correlation as confirmed exploitability. After collecting the result:

```bash
docker compose down -v
```

The user-facing AI explained-report download follows the separate backend/Groq path; its
current coverage limits and deferred review are documented in
[`SCAN-JSON-AND-AI.md`](../../specs/053-targeted-scan-lab/SCAN-JSON-AND-AI.md).
