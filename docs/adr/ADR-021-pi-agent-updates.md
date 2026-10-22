# ADR-021: Pi agent updates

> **Status:** Accepted; implementation is in staged rollout (2026-10-20).
> **Extends:** [ADR-011](ADR-011-pi-command-channel.md) for what the command channel does not carry.
> **Does not cover:** patching Raspberry Pi OS itself.

## Context

The agent needs a recoverable update path that does not ask the agent process to replace itself,
does not carry package bytes over the scan command channel, and does not interrupt an active scan.
The system now uses Debian packages for the agent and its durable updater companion. A signed APT
repository and backend catalog describe releases. The web application can display availability
and request an update, while an administrator explicitly approves the operation.

## Decision

### Signed Debian packages and trust chain

The `hardware-agent` and `hardware-agent-updater` packages are built and published as immutable
Debian artifacts. Repository metadata is signed with the approved release key. The backend worker
verifies the signed catalog with its baked-in public keyring and imports the catalog; the API
serves the persisted read model. The Pi verifies APT metadata and package hashes using its
installed archive key before installation. The package is not sent through the WebSocket.

The canonical public keyring is `backend/agent-release/public-keyring.gpg`. The release workflow
and backend image consume this same tracked file. Its approved primary fingerprint is
`92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A`. Private signing material is kept outside the
repository in protected custody.

Releases are manual. The release workflow builds and publishes a package only when a maintainer
pushes an annotated `agent-vX.Y.Z` tag on a `main` commit whose `hardware-agent/pyproject.toml`
version is `X.Y.Z`. A merge to `main` alone does not publish a release.

The selected static repository base is
`https://dmitri-imt.github.io/dmitri/`. The Pages workflow can publish signed APT metadata and
packages there. A selected hosting URL does not mean that a release has been published or that
production has been configured; those remain gated rollout steps.

### Bootstrap and operator approval

The assisted installer, `hardware-agent/scripts/provision-pi.sh`, accepts both package files,
the HTTPS repository, the approved primary fingerprint, and a public key file. It verifies the
key identity, stages its inputs safely, preserves a recovery baseline, and installs/configures
the agent and updater under the shared scan/update lock. It requires Debian 13 arm64. Older
installations do not acquire update capability just because the backend is upgraded; they need
the companion package installed through the assisted bootstrap.

The device page offers an available compatible release and requires an administrator to confirm
the operation. The backend authorizes the request and the Pi updater performs the transaction.
The daily `dmitri-agent-update.timer` runs a check-only service that verifies/reports repository
metadata. It never runs `apt-get upgrade` or installs packages automatically.

### Scan exclusion, journaling, and recovery

The updater takes the persistent shared scan/update lock before changing packages. A running scan
therefore prevents update admission, and an update prevents a new scan from starting. The durable
supervisor owns update state and recovery across an agent restart. It records operation progress,
preserves a recovery baseline, and keeps a gate when automated recovery cannot safely complete.
Do not delete `/var/lib/dmitri/updates/` or `/var/lib/dmitri/update-gate.json` during recovery.
Use [PI-RECOVERY](../PI-RECOVERY.md#agent-update-recovery) to collect state and escalate
`recovery_required`/`needs_intervention` cases.

## Deployment configuration

The backend API and worker share the `backend/` Railpack build context. Both images need
`ca-certificates`, `dpkg`, `gpgv`, and the canonical keyring at
`/app/agent-release/public-keyring.gpg`. Configure the same non-secret values on both services:

- `AGENT_UPDATE_REPOSITORY_URL=https://dmitri-imt.github.io/dmitri/`
- `AGENT_UPDATE_KEYRING_PATH=/app/agent-release/public-keyring.gpg`
- `AGENT_UPDATE_ORIGIN=Dmitri`
- `AGENT_UPDATE_SUITE=stable`
- `AGENT_UPDATE_REFRESH_INTERVAL_SECONDS=300`

The worker imports the signed release catalog; the API does not fetch it on GET. An unset
repository URL disables refresh, so update availability remains unknown. See
[Railway setup](../cloud/railway/SETUP.md#agent-release-catalog) for the gated production
configuration steps.

## Rollout status and limits

Implementation tasks 1–14 and local O1–O3 code gates are complete.
Protected CI, hosted signing and publication, production migration/configuration, and the
assisted real-Pi bootstrap/canary are separate gates. Until these are completed, this ADR does
not assert that a production repository is live, that Railway has been configured, or that a
production Pi can update itself.

The system updates Dmitri agent packages only; operating-system security updates remain outside
this decision.

## Consequences

- The update channel carries authorization and status, not package bytes.
- Updates are administrator initiated. The periodic Pi timer performs metadata checks only.
- Package installation is serialized with scans and backed by durable recovery state.
- The current legacy/manual install path remains relevant until a device is bootstrapped with
  the updater companion.

## References

- [ADR-011](ADR-011-pi-command-channel.md) — command channel frames and device connection state
- [PI-INSTALLER](../PI-INSTALLER.md) — assisted install and bootstrap
- [PI-RECOVERY](../PI-RECOVERY.md) — device and updater recovery
- [`hardware-agent/scripts/provision-pi.sh`](../../hardware-agent/scripts/provision-pi.sh)
- [`hardware-agent/packaging/updater.py`](../../hardware-agent/packaging/updater.py)
