---
type: Domain Glossary
title: Domain glossary
description: The core domain terms — agent, host, device, command, scan, org — and their code meanings.
resource: CONTEXT.md
tags: [glossary, domain]
timestamp: 2026-07-21T00:00:00Z
---

# Domain glossary

The authoritative glossary is [`CONTEXT.md`](../../CONTEXT.md). This page summarizes the terms and
points at where each shows up in code.

## Agent

A **Raspberry Pi appliance** running `dmitri agent` — the thing that *performs* scans. Identified by
`agent_id` (a UUID minted by the backend at provisioning) and signs HMAC requests with
`X-Device-Id`. Belongs to exactly one **org**. In code, the agent *is* the
[`hardware-agent`](/hardware-agent/overview.md) package.

## Host

A **machine discovered on the network by a scan** — the thing the product *reports on*. Has `ip`,
`mac`, `hostname`, `vendor`, open ports, and findings. In the agent, an in-memory host is
[`HostInfo`](/hardware-agent/scanner/models.md); persisted, it is a `DeviceRecord`
([backend/models](/backend/models.md)).

## Device — deprecated, ingest-only

**"Device" is not a domain term.** It survives only in the **ingest payload the Pi sends**
(`devices[]`, `DevicePayload`, `devices_received`), whose field names are frozen by
[ADR-011 §5](../../docs/adr/ADR-011-pi-command-channel.md). Everywhere else the word is **host**.

> **The rename boundary is the ingest endpoint: the Pi reports *devices*; the backend stores and
> serves *hosts*.** Historically "device" meant both the Pi and the machines it found — which is why
> `X-Device-Id` identifies an **agent**, not a host. That header name is a permanent scar.

The agent's [`DevicePayload`](/hardware-agent/normalize.md) and the backend's
[`schemas/scan.py`](/backend/schemas.md) `Device` are the two code sites that keep the word.

## Command

One **"Scan now"** — an operator's request for an agent to run a scan. Carries its own lifecycle
(`queued → delivered → running → uploading → done | failed | expired`) and is the audit record of
who asked for what. A command that the Pi never took → `expired`; one it took then broke → `failed`.
Defined in the [contract](/contracts.md); no in-code implementation yet.

## Scan

The **result** of a command: what was found, when. Created as a **stub** (`status: pending`, empty
hosts/findings) the moment a command is enqueued, and filled when the agent uploads — so a scan
always exists before it has content. In the agent, a completed scan is a
[`ScanPayload`](/hardware-agent/normalize.md) written to disk by
[`workspace`](/hardware-agent/scanner/workspace.md); in the backend, a `ScanRecord`.

## Org & roles

An **org** is one customer company — the tenancy boundary (`org_id` scopes agents, commands, scans,
users). Two roles: **`admin`** (trigger scans, invite users) and **`viewer`** (read only). Neither
provisions Pi secrets — that is the installer's job. Backed by the `orgs`/`users`/`invites` tables
in [backend/models](/backend/models.md) (`identity.py`); not yet enforced in code.

# Citations

[1] [CONTEXT.md](../../CONTEXT.md)
[2] [docs/adr/ADR-011-pi-command-channel.md](../../docs/adr/ADR-011-pi-command-channel.md)
[3] [docs/adr/ADR-005-security-model.md](../../docs/adr/ADR-005-security-model.md)
