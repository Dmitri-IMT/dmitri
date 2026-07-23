---
type: Domain Glossary
title: Domain glossary
description: The core domain terms — agent, host, scan_host, command, scan, org — and their code meanings.
resource: CONTEXT.md
tags: [glossary, domain]
timestamp: 2026-07-22T00:00:00Z
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

A **machine tracked on the network across scans** — the thing the product *reports on*. Has `ip`,
`mac`, `hostname`, `vendor`, open ports, and findings. Identified by `host_id` (UUID), **stable
across scans**: the same physical machine seen in two scans is one Host. Identity resolution is by
**MAC when the scan observed one, otherwise IP**, within an org
([ADR-014](../../docs/adr/ADR-014-host-identity-resolution.md)). In the agent, an in-memory host is
[`HostInfo`](/hardware-agent/scanner/models.md); persisted, the durable identity is a `HostRecord`
(table `hosts`) — see [backend/models](/backend/models.md).

## ScanHost

**One Host as observed in a single scan** — the per-scan snapshot (`ip`/`mac`/`hostname`/`vendor` at
scan time, its ports), linked to its durable Host by `host_id`. Findings hang off the ScanHost. In
storage this is `ScanHostRecord` (table `scan_hosts`) — the record formerly named `DeviceRecord`
(table `devices`); see [backend/models](/backend/models.md).

## Device — retired

**"Device" is not a domain term and no longer appears on the wire.** As of
[ADR-013](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md), the ingest payload the Pi
sends also speaks **host** (`POST /api/v1/scans` → `hosts[]`, `HostPayload`, `hosts_received`); the
earlier "ingest stays `devices`" boundary ([ADR-011 §5–§6](../../docs/adr/ADR-011-pi-command-channel.md))
is superseded. The scanner and backend speak one vocabulary end to end — the agent's
[`HostPayload`](/hardware-agent/normalize.md) and the backend's [`schemas/scan.py`](/backend/schemas.md)
`Host` are the same shape.

> The **one** surviving scar is `X-Device-Id` — an HMAC-signed header that identifies the **agent**
> (the Pi itself), *not* a discovered host. Its name is frozen by ADR-005 and is unrelated to the
> retired host/device vocabulary.

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
[4] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[5] [docs/adr/ADR-014-host-identity-resolution.md](../../docs/adr/ADR-014-host-identity-resolution.md)
