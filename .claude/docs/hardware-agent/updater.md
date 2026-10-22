---
type: Module
title: packaging updater — durable remote update companion
description: The root-owned update companion validates signed APT metadata and package identity, serializes updates against scans, journals recovery, and replays signed operation events.
resource: hardware-agent/packaging/updater.py
tags: [hardware-agent, updater, apt, recovery, systemd, security]
timestamp: 2026-10-20T00:00:00Z
---

# packaging updater — durable remote update companion

## Purpose

`hardware-agent/packaging/updater.py` is the long-lived, root-owned companion behind the local
`dmitri-agent-update.service`. It exposes a restricted Unix socket to the unprivileged daemon,
keeps operation and event state in a durable SQLite journal, checks the signed APT source and exact
package digest/version before installation, excludes concurrent scans, and recovers interrupted
updates using a retained package/filesystem snapshot. It does not publish releases or update the Pi
OS.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `Updater` | Owns companion startup, journal, readiness, package check/request, event reporting and recovery. | `packaging/updater.py:72` |
| `initialize()` / `serve()` | Validates durable state, restores update gate/recovery state, then serves the restricted local socket. | `:101`, `:324` |
| `_readiness_handshake()` / `inspect()` | Checks systemd/package identity and local update state; returns only the bounded readiness and operation context consumed by daemon hello. | `:522`, `:598` |
| `check()` | Refreshes signed package metadata only when the update/scan gate is idle. | `:656` |
| `accept_update()` / `_apply_claimed_update()` | Validates the request/deadline, claims the backend operation idempotently, verifies and caches the exact package, installs it, and performs local health confirmation. | `:690`, `:766` |
| `_resume_interrupted_update()` / `_recover_update()` | Reconciles claim/install state after restart and restores the previous installation or retains the gate for intervention. | `:1040`, `:1312` |
| `_emit()` / `_flush_events()` | Persists sequenced events before posting them; retries pending events after restart or a lost acknowledgement without creating a second journal event. | `:1399`, `:1453` |
| `_verify_apt_origin_suite()` / `_verify_dedicated_apt_source()` / `_verify_apt_metadata_dates()` | Enforce the HTTPS stable suite, root-owned Signed-By keyring, valid metadata window, expected package version and catalog digest. | `:1726`, `:1840`, `:1976` |
| `_preflight()` / `_check_package_manager_idle()` | Confirm platform, package-manager state, free space and snapshot feasibility before mutation. | `:2080`, `:2192` |
| `request()` / `main()` | Local socket client and executable entry point used by the daemon and installed helper. | `:1593`, `:2331` |

## How it connects

- The companion executable and systemd service/timer ship in the separate
  `hardware-agent-updater` Debian package, which is required by `hardware-agent`; see
  [provisioning](./provisioning.md) and [deployment](../infra/deployment.md).
- The [daemon](./daemon.md) requests readiness and forwards signed backend update authorization
  over the restricted socket. The [command channel](./command-channel.md) negotiates capability
  only when both backend protocol and local companion readiness allow it.
- Uses the appliance shared scan lock, package cache and state directory; the daemon and TUI
  acquire the complementary scan lock for their work.
- Reports operation claims and sequenced events to backend agent-update routes; UI reads them through
  [frontend API](../frontend/api.md).

## Notes / gotchas

- Readiness is capability evidence, not proof of a real deployed Pi. The production systemd,
  package/repository signing key, hosting and canary still require human infrastructure gates.
- The companion does not accept arbitrary shell commands. Its local request vocabulary is closed,
  the socket checks peer identity, and process calls use fixed argument arrays.
- A local install/health result is distinct from backend confirmation; durable events and a later
  hello reconcile that boundary. A pending gate remains held until the state is safe to release.

# Citations

[1] [ADR-021 — Pi agent updates](../../../docs/adr/ADR-021-pi-agent-updates.md)
