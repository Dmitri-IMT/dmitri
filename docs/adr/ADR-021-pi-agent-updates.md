# ADR-021: Pi agent updates

> **Status:** Accepted (2026-09-23).
> **Extends:** [ADR-011](ADR-011-pi-command-channel.md) for what the command channel does not carry.
> **Does not cover:** patching Raspberry Pi OS itself.

## Context

There is no agent update mechanism. [PI-INSTALLER](../PI-INSTALLER.md) tells the installer to copy `hardware-agent/` to `/opt/dmitri-agent`, run `uv sync`, and restart `dmitri-agent.service` by hand. That matches the one appliance provisioned on 2026-09-11. It has no rollback, and it does not survive a second customer.

`hardware-agent/pyproject.toml` says `0.1.4`. That string is a leftover from TUI work. The same literal is copied in `hardware-agent/src/agent/tui/widgets.py` (`APP_VERSION`) and `hardware-agent/src/agent/scanner/nmap.py` (`AGENT_VERSION`). Nothing in production treats it as a release. The WebSocket `hello` frame already sends `importlib.metadata.version("hardware-agent")`. [ADR-011](ADR-011-pi-command-channel.md) keeps that value in the API process connection registry for the life of the socket, the same way it keeps `available_subnets`. The `agents` row has no version column, and the device page does not show one.

The command channel carries `hello`, `command`, `status`, and `error`. A `command` frame is a scan. The Pi keeps the scan ledger in the process. A restart drops the ledger. The backend does not redeliver the command. If the device reconnects inside the disconnect grace, the command stays non-terminal and the next scan returns `device_busy` until the mode duration limit.

The unit runs as root from `/opt/dmitri-agent/.venv/bin/dmitri`. `requires-python` is `>=3.11,<3.13`. The playbook installs Python 3.12 under `/opt/uv-python` because the image Python on Debian 13 is 3.13. Railway publishes the API, the worker, and the frontend. CI tests the tree. Nothing publishes a wheel, a `.deb`, or a container image for the agent.

## Decision

### 1. Update with a signed Debian package

The agent is a signed `.deb` named `hardware-agent`, installed and upgraded with `apt`. The `dmitri` process does not download or replace itself.

The package installs the tree the unit already starts. `ExecStart` stays `/opt/dmitri-agent/.venv/bin/dmitri`. The package bundles Python 3.12, or it keeps `/opt/uv-python`. It does not depend on the image Python. It does not replace `/etc/dmitri/agent.env`.

Where the repository is hosted is still open. The `.deb` itself is built by `hardware-agent/packaging/build-deb.sh`.

### 2. Prepare the Pi once

Provisioning leaves three things on the device before any later update can run on its own.

- The apt repository line.
- The vendor signing key. The Pi installs only packages that key signed.
- A systemd timer that runs as root, outside the agent process.

The timer runs `apt-get update` and `apt-get install --only-upgrade hardware-agent` while the Pi is on and can reach the repository. The backend does not push the bits.

The appliance provisioned on 2026-09-11 does not have the timer. That device needs one SSH session to install the `.deb`. Every later appliance gets the package from `hardware-agent/scripts/provision-pi.sh`.

The first packages are installed with `dpkg -i`. The timer's `apt` upgrade does nothing useful until an apt repository exists. That repository is not part of this decision's implementation.

### 3. Do not upgrade during a scan

The timer does not upgrade `hardware-agent` while that device has a scan in progress. An upgrade restarts the unit, and a restart kills the scan.

The package owns `/usr/lib/dmitri/scan-lock-path`, which names the shared appliance
lock independently of results directories and XDG settings. The timer and provision
script take it exclusively before changing the installation. Scans take it shared
and non-blocking: they refuse to start while an update owns it. The daemon acquires
it before reporting `running`, holds it through result upload, and retains it while
a terminal status awaits replay. TUI and headless entrypoints use the same contract.
The package creates the lock file; source checkouts without the package have no updater.

If the process does exit during a scan, the follow-up marks that command failed. Otherwise the backend can hold the command open and return `device_busy` after the device is back.

### 4. Version starts at 1.0.0

The first published package is `1.0.0`. `0.1.4` is not a release.

The version is `MAJOR.MINOR.PATCH` from `hardware-agent/pyproject.toml`, and that file is the only copy.

- The first number changes for a major break.
- The second number changes for a substantial update.
- The third number changes for a small change, a feature, or a fix.

`APP_VERSION` and `AGENT_VERSION` go away. The TUI header, scan metadata, and the `hello` frame all read the installed package version.

A pull request that changes `hardware-agent/` must set a version greater than the version on `main`. CI fails the pull request when it does not. A pull request that does not change `hardware-agent/` does not bump the version. Once the apt repository exists, CI compares against the published package version instead of `main`.

### 5. Report the running version, and roll back from it

After an upgrade the process connects and sends `hello` with the installed version. The follow-up stores that version on the device and shows it in the device page. The connection registry alone is not enough, because it disappears when the socket drops.

Move from `1.0.0` to `1.0.1` by publishing the new `.deb`. The timer upgrades the package and restarts `dmitri-agent` when no scan is in progress. The next `hello` reports `1.0.1`.

The upgrade failed when the unit is not active afterward, or when `hello` does not report `1.0.1`. Roll back with the previous package, which the repository must still serve.

```bash
sudo flock -n -x "$(cat /usr/lib/dmitri/scan-lock-path)" \
  apt-get install --allow-downgrades hardware-agent=1.0.0
```

The package restarts the unit while the lock is held. `/etc/dmitri/agent.env`
stays as it was. If the lock is busy, retry after the current command finishes.

## Consequences

- [PI-INSTALLER](../PI-INSTALLER.md) leads with `hardware-agent/scripts/provision-pi.sh`. The manual steps stay as the troubleshooting path.
- The command channel stays a scan channel. An "update now" control, if it is built later, only runs the same `apt` command sooner. It does not carry the package.
- The `.deb`, the timer, the single version source, and the CI version check are in the tree. Still open: the apt repository, package signing, and storing `hello`'s version on the device page.
- OS updates for Raspberry Pi OS stay out of this decision.

## Rejected alternatives

- **Container.** The local simulator image uses `/opt/agent` and is not the appliance. A container adds a runtime and a registry the Pi does not have, and `nmap` still needs the host network.
- **A WebSocket command that pulls and restarts.** The channel has no such frame. A bad write under `/opt/dmitri-agent`, plus `Restart=always`, boots the broken tree. The updater would be the process being replaced.
- **Stay manual, and revisit later.** Manual install has no rollback and requires a visit per device. It remains only as the bridge until the package ships.

## References

- [DMI-147](https://linear.app/dmitri-imt/issue/DMI-147/decide-how-the-pi-agent-gets-updated-write-the-adr)
- [ADR-011](ADR-011-pi-command-channel.md) — command channel frames and the in-memory `hello` registry
- [PI-INSTALLER](../PI-INSTALLER.md) — current install, and the manual update that this ADR replaces
- `hardware-agent/dmitri-agent.service` — the unit the package must keep starting
- `hardware-agent/pyproject.toml` — the version source, today still `0.1.4`
