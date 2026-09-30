# ADR-014: Host identity resolution — MAC-when-present, else IP

> **Status:** Accepted (2026-07-22). Defines how per-scan observations resolve to a durable
> **Host** ([`CONTEXT.md`](../../CONTEXT.md)). Consumed by the read-path feature
> (`specs/015-read-path/`).

## Context

A **Host** is a machine tracked across scans, with a stable `host_id` and a `first_seen_at` that
never moves. Each scan produces a per-scan **ScanHost** observation. Nothing in the domain glossary
or the contract said *how* two observations are judged to be the same Host — yet `host_id`
assignment, `first_seen_at`, and the "new device on your network" signal (contract ask C6) all
depend entirely on that rule.

The only stable hardware identifier available is the **MAC address**, which the scanner obtains via
ARP ([`ADR-004`](ADR-004-scan-methodology.md)). ARP resolves MAC only on the Pi's **local segment**;
a host on a routed/remote subnet, or one ARP misses, arrives with `mac = null`. IP is always present
but is reassigned by DHCP.

## Decision

Resolve host identity, **within an `org`**, by:

- **MAC when the scan observed one** — identity key `mac:<MAC>`.
- **IP when it did not** — identity key `ip:<IP>`.

**Collision exception (2026-09-29):** when a scan observes the same MAC on multiple IPs, those
observations represent separate Hosts and use `ip:<IP>` keys. Once a MAC has been split this way,
later observations for it remain IP-keyed so the records do not merge again. A normal MAC moving
between IPs across scans still follows the original MAC-keyed rule until a simultaneous collision
is observed.

Uniqueness is `(org_id, identity_key)`. The durable Host's `first_seen_at` is the earliest observing
scan's timestamp and never increases; `last_seen_at` and the mutable attributes track the most recent
observation.

This is the **simple rule**, chosen over a reconciliation-based one (e.g. matching a MAC-less
observation to an existing Host by its most-recent IP). The deployment is LAN-primary — the Pi
scans its own segment, where MAC is present for essentially every live host — so the failure modes
below are edge cases in practice, and CLAUDE.md's simplicity-first bias applies.

The collision exception handles virtual machines and locally administered addresses that can
share a reported MAC. Existing affected observations can be relinked with the backend maintenance
command `backend-repair-host-identities`; it previews affected scan/MAC/IP groups by default. Pass
`--apply` to relink scan history and rebuild the affected host inventory projections. The repair is
idempotent.

## Consequences

- **Accepted limitations (v1):**
  - *MAC-less DHCP churn* — a routed/remote host with no MAC is IP-keyed; a new lease looks like a
    new Host and re-fires the new-device signal.
  - *Intermittent MAC* — the same machine seen with MAC in one scan and without in another splits
    into two Hosts. Rare when a machine is consistently local (always MAC) or remote (never MAC).
  - *MAC randomisation* — a device rotating its MAC (phones) appears as several Hosts.
- **Hard to reverse:** identity is resolved and `host_id` + `first_seen_at` are written at **ingest
  time** (`persist_scan` upserts the Host). Changing the rule later requires a re-materialisation /
  backfill migration over stored Hosts — not just new read code. That cost is why this is an ADR.
- If the product later targets routed subnets at scale, revisit with a reconciliation strategy
  (match MAC-less observations by last-known IP) or a composite key; this ADR is the v1 baseline, not
  a permanent ceiling.

## Out of scope

- Cross-org identity (Hosts never merge across `org`).
- Fingerprint-based identity (hostname/OS/open-port heuristics) — not used for identity in v1.

## References

- [`CONTEXT.md`](../../CONTEXT.md) — Host / ScanHost glossary and the identity summary.
- [`ADR-004`](ADR-004-scan-methodology.md) — ARP-based discovery (why MAC is local-segment-only).
- [`ADR-013`](ADR-013-ingest-host-vocabulary-unification.md) — the host vocabulary this builds on.
- `specs/015-read-path/` — the feature that implements the durable Host and this rule.
