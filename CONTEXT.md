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

### Host

A **machine discovered on the network by a scan** — the thing the product *reports on*. Has an
`ip`, `mac`, `hostname`, `vendor`, open ports and findings. Identified by `host_id`.

### Device — deprecated, ingest-only

**"Device" is not a domain term. Do not use it in new work.** It survives in exactly one place: the
**ingest payload the Pi sends** (`POST /api/v1/scans` → `devices[]`, `DevicePayload`,
`devices_received`), whose field names are frozen by [`ADR-011` §5](docs/adr/ADR-011-pi-command-channel.md).

Everywhere else — paths, read models, filters, the UI — the word is **host**.

> **The rename boundary is the ingest endpoint: the Pi reports *devices*; the backend stores and
> serves *hosts*.** Decided 2026-07-13 (contract ask C11, [`BACKEND.md` B7](docs/roadmap/BACKEND.md)).

Historically "device" was overloaded to mean *both* the Pi and the machines it found — which is why
`X-Device-Id` identifies an **agent**, not a host. That header name is frozen by ADR-005 and is the
one permanent scar from the old vocabulary.

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

### Org

One customer company. The tenancy boundary: `org_id` scopes agents, commands, scans and users.
Multi-user, single-org per customer in September ([`BACKEND.md` B1](docs/roadmap/BACKEND.md)).

### Roles — admin, viewer

The two September roles. **`admin`** may trigger scans and invite users; **`viewer`** may only read.
Neither provisions Pi secrets — that is the installer's job.
