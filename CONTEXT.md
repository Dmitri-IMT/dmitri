# Context — Dmitri

The domain language of the vulnerability-scanner product. Terms here are the ones that mean
something to a domain expert; implementation detail lives in [`docs/adr/`](docs/adr/) and
[`docs/roadmap/`](docs/roadmap/).

## Glossary

### Agent

A **Raspberry Pi appliance** running `dmitri agent`, deployed on a customer's network by an
installer. It is the thing that *performs* scans. Identified by `agent_id` — a **UUID**, minted by
the backend at provisioning, and the same value the Pi signs HMAC requests with (`X-Device-Id`).
Humans read the agent's `display_name`, never its id. An agent belongs to exactly one `org`.

**Not** a piece of software the customer installs themselves — Pi provisioning is the installer's
job, never the org admin's ([`AUTH.md`](docs/roadmap/AUTH.md), B2B model).

**Revoke ≠ rotate.** *Revoking* an agent is a soft, timestamped tombstone (`revoked_at`) that kills it
for good — every future HMAC verify returns `403`, but its history is kept. *Rotating* an agent's secret
just re-issues the HMAC secret (ADR-005) and leaves the agent active. Secret storage is encrypted at
rest, not hashed ([`ADR-015`](docs/adr/ADR-015-agent-secret-storage-at-rest.md)). `online` is never
stored — it is derived from the live WS registry; `last_seen_at` is a persisted heartbeat for the UI,
never an auth input.

### Host

A **machine tracked on the network across scans** — the thing the product *reports on*. Has an
`ip`, `mac`, `hostname`, `vendor`, open ports and findings. Identified by `host_id` (a UUID), which
is **stable across scans**: the same physical machine seen in two scans is one Host.

**Identity resolution** (how two observations are judged the same Host): by **MAC when the scan
observed one, otherwise by IP**, within an `org`. MAC comes from ARP and is present for hosts on the
Pi's local segment; a MAC-less host (routed/remote subnet) is identified by IP and so can fracture
under DHCP churn — an accepted v1 limitation ([`ADR-014`](docs/adr/ADR-014-host-identity-resolution.md)).

A Host carries a **`first_seen_at`** (earliest observing scan; never moves) and **`last_seen_at`**
(most recent). Its mutable attributes — shown `ip`/`mac`/`hostname`/`vendor`, open ports, highest
severity — reflect its **most recent** observation, not a union across history.

### ScanHost

**One Host as observed in a single scan** — what that scan saw at that machine (`ip`/`mac`/`hostname`
/`vendor` at scan time, its ports), linked to its durable `Host` by `host_id`. Findings hang off the
ScanHost. This is the per-scan row; the durable machine is the **Host**. (In storage this is the
record formerly named `DeviceRecord`.)

### Device — retired

**"Device" is not a domain term and no longer appears on the wire.** As of
[`ADR-013`](docs/adr/ADR-013-ingest-host-vocabulary-unification.md) the ingest payload the Pi sends
also speaks **host** (`POST /api/v1/scans` → `hosts[]`, `HostPayload`, `hosts_received`); the earlier
"ingest stays `devices`" boundary ([`ADR-011` §5–§6](docs/adr/ADR-011-pi-command-channel.md)) is
superseded. The scanner and backend speak one vocabulary end to end.

The **one** surviving scar is `X-Device-Id` — an HMAC-signed header that identifies the **agent** (the
Pi itself), *not* a discovered host. Its name is frozen by ADR-005 and is unrelated to the retired
host/device vocabulary; historically "device" was overloaded to mean both the Pi and the machines it
found, which is why that header still reads "device".

### Command

One **"Scan now"** — an operator's request for an agent to run a scan. Carries its own lifecycle
(`queued → delivered → running → uploading → done | failed | expired`) and is the audit record of
who asked for what.

**A command's terminal state splits on whether the Pi ever took the job** (decided 2026-07-13):

| The Pi… | State |
|---------|-------|
| never took the command (delivery gave up) | `expired` |
| took the command, then broke | `failed` |

### Scan

The **result** of a command: what was found, when. Created as a **stub** (`status: pending`, empty
`hosts` / `findings`) the moment a command is enqueued, and filled in when the agent uploads. So a
scan always exists before it has any content — the UI can link to it immediately.

A Scan's `status` is a **projection of its Command's status**, never set independently — one lifecycle,
two faces:

| Command | Scan |
|---------|------|
| `queued`, `delivered` | `pending` |
| `running` | `accepted` |
| `uploading` | `processing` |
| `done` | `completed` |
| `failed`, `expired` | `failed` |

### Org

One customer company. The tenancy boundary: `org_id` scopes agents, commands, scans and users.
Multi-user, single-org per customer in September ([`BACKEND.md` B1](docs/roadmap/BACKEND.md)).

### Roles — admin, viewer

The two September roles. **`admin`** may trigger scans and invite users; **`viewer`** may only read.
Neither provisions Pi secrets — that is the installer's job.

## Relationships

- An **Org** owns many **Agents**, **Commands**, **Scans** and **Users**; `org_id` is the tenancy
  boundary on all of them.
- An **Agent** executes many **Commands** over its life; each **Command** targets exactly one Agent.
- A **Command** produces **exactly one Scan** — born together at enqueue (the Scan as a `pending`
  stub). A re-scan is a *new* Command, never a reused one; idempotent re-delivery of the same
  `command_id` reuses the same Scan.
- A **Scan** contains many **ScanHosts**; each **ScanHost** resolves to one durable **Host**.
