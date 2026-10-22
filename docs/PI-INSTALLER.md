# Pi installer playbook

Audience: the technical installer who prepares and registers a Dmitri Raspberry Pi.
This describes the current assisted package bootstrap. The original manual installation
was exercised on hardware on 2026-09-11; the later signed-package bootstrap has only
been validated on a disposable Debian 13 arm64 VM so far. It has not been run on the
production Pi. Do not interpret the historical hardware date as validation of this new
procedure.

## Requirements

- Raspberry Pi OS based on Debian 13 (Trixie), `arm64`.
- A reviewed checkout containing `hardware-agent/scripts/provision-pi.sh` and the
  canonical public keyring at `backend/agent-release/public-keyring.gpg`.
- The agent and updater `.deb` files from a published signed APT snapshot. Their bytes
  must match the package hashes and control fields in its signed `Packages` index.
- The repository fingerprint confirmed out of band:
  `92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A`.
- A backend on the reviewed migration head and an admin account for device registration.

The selected repository URL is `https://dmitri-imt.github.io/dmitri/`, but a selected
URL alone does not prove that a signed release has been published or that production is
configured. Confirm the publication and production configuration before scheduling a
production installation.

## 1. Flash and connect

Flash Raspberry Pi OS Lite 64-bit, configure the installer account, enable SSH, and
connect the device to the authorized network. After first boot, SSH to the device and
confirm its platform:

```bash
cat /etc/os-release
dpkg --print-architecture  # must be arm64
```

The bootstrap refuses other architectures and Debian versions. For a new device, clone
the reviewed repository checkout. On an existing device, keep its current checkout and
identity; do not replace `/etc/dmitri/agent.env`, its results, or the persistent lock.

Before registering a Pi, confirm the backend has been migrated to the reviewed Alembic
head. The current source head is `20261019_43`; use the deployment runbook to verify the
actual deployed head and backup before applying any production migration.

## 2. Prepare OS tools and the pinned runtime

Install the packages used for scanning, TLS, and the bootstrap's OpenPGP fingerprint
check. Install the pinned `uv` release and Python runtime required by the agent package:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates gnupg nmap

UV_VERSION=0.11.20
curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | \
  sudo env HOME=/root UV_INSTALL_DIR=/usr/local/bin sh
sudo /usr/local/bin/uv --version  # must report uv 0.11.20

sudo env UV_PYTHON_INSTALL_DIR=/opt/uv-python \
  UV_PYTHON_BIN_DIR=/opt/uv-python/bin \
  /usr/local/bin/uv python install --default 3.12.15
sudo /opt/uv-python/bin/python -V  # must report Python 3.12.15
```

The agent package's `postinst` uses `/usr/local/bin/uv` 0.11.20 and
`/opt/uv-python/bin/python` 3.12 to create its virtual environment from the bundled,
hash-checked wheelhouse. Do not use an unpinned `uv` installation, run `uv sync`, or
install the agent's Python dependencies from the network on the Pi.

The bootstrap takes the persistent scan/update lock before modifying packages. The lock
file must already exist. On a **new, otherwise unprovisioned** Pi only, create it once,
and create the agent runtime directory before the bootstrap starts the supervisor:

```bash
sudo install -d -o root -g root -m 0755 /var/lib/dmitri
sudo install -o root -g root -m 0644 /dev/null /var/lib/dmitri/scan.lock
sudo install -d -o root -g root -m 0755 /opt/dmitri-agent
```

The supervisor systemd unit uses `/opt/dmitri-agent` in `ReadWritePaths` and the
provisioning script starts it before installing the agent package, so this directory must
exist on a new Pi first. Do not run these commands on an existing installation: replacing
its lock file can split the inode shared by scans and updates, and changing the agent tree
can damage its runtime. The bootstrap refuses to proceed if an existing scan or update
owns the lock.

For an **existing Pi**, wait until the scan is terminal in the UI and result upload or
finalization has completed. Then stop the agent before bootstrap; the script rejects an
active `dmitri-agent.service`, even when it is idle, and restarts it after installation:

```bash
sudo systemctl stop dmitri-agent.service
sudo systemctl is-active dmitri-agent.service || true  # should report inactive
```

Do not stop the service during a scan or while results are still being finalized. Do not
create or replace `/var/lib/dmitri/scan.lock` or `/opt/dmitri-agent` on an existing device.

## 3. Verify the trust anchor and obtain packages

From the reviewed checkout, inspect the key fingerprint and compare it out of band with
the approved value above:

```bash
gpg --batch --show-keys --fingerprint \
  ./backend/agent-release/public-keyring.gpg
```

Obtain both package files from the published repository. The repository stores packages
by content hash, so local filenames may differ. The bootstrap refreshes signed metadata
and verifies each package's identity, version, architecture, and hash before installation.
It will reject mismatched bytes. Do not install either package manually with `dpkg -i`.

## 4. Run the assisted bootstrap

Run from the repository checkout on the Pi. Use package file paths whose bytes came from
the release being verified:

```bash
sudo hardware-agent/scripts/provision-pi.sh \
  --repository https://dmitri-imt.github.io/dmitri/ \
  --fingerprint 92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A \
  --public-key ./backend/agent-release/public-keyring.gpg \
  -- /path/to/hardware-agent-package.deb /path/to/hardware-agent-updater-package.deb
```

The script requires Debian 13 arm64, the prepared runtime above, and both package files.
It verifies the public key, stages the inputs safely, configures the signed HTTPS APT
source, verifies signed metadata and package hashes, preserves a recovery baseline, and
installs both packages while holding the scan/update lock. It then runs `dmitri provision`
to collect the deployed HTTPS backend URL, an admin email and password, and the device
name. Provisioning generates the device key on the Pi, registers it, writes
`/etc/dmitri/agent.env`, and starts the agent. The private device key stays on the Pi.

The agent package installs `dmitri-agent.service`. The companion package installs the
durable updater supervisor and `dmitri-agent-update.timer`. During bootstrap,
`provision-pi.sh` installs the approved APT keyring and configures the signed APT source;
these are not installed by the companion `.deb`. The daily timer invokes a **metadata
check only**; it never installs packages. Each package update must be requested from the
device page and explicitly approved by an admin.

For service-targeted scans, install and verify their additional tools after bootstrap:

```bash
sudo hardware-agent/scripts/provision-targeted-tools.sh
sudo hardware-agent/scripts/provision-targeted-tools.sh --verify-only
```

That tool script supports Raspberry Pi OS Bookworm and Trixie on armhf or arm64. Its
broader platform support does not change the updater bootstrap's Debian 13 arm64 limit.

## 5. Verify without starting a scan

```bash
sudo systemctl status dmitri-agent.service dmitri-agent-update.service \
  dmitri-agent-update.timer --no-pager
sudo journalctl -u dmitri-agent.service -n 100 --no-pager
sudo /usr/bin/python3 /usr/lib/dmitri/updater.py --inspect
```

Confirm that the agent and updater supervisor are active, the timer is enabled, inspection
reports a healthy/unblocked state, and the device page shows the same registered device.
The agent log should report `command channel connected`. Do not run a scan solely to test
the installer. If a functional scan test is needed, schedule it on an authorized test
subnet and confirm the uploaded result in the UI.

Legacy devices that do not yet have `hardware-agent-updater` need this assisted bootstrap
before they can use the update UI. A backend deployment alone does not install the Pi
companion.

## Troubleshooting and recovery

| Symptom | Action |
|---|---|
| Bootstrap says the persistent scan lock is missing | For a new Pi, initialize it once as shown in section 2. For an existing device, do not replace the lock; inspect its installation history and escalate. |
| Bootstrap says a scan or update is in progress | Wait for it to finish. Do not remove or recreate the lock. |
| Bootstrap rejects the public-key fingerprint or package bytes | Stop. Confirm the key fingerprint out of band and obtain packages from the same signed repository snapshot. Never bypass signature verification. |
| `postinst` says the runtime is missing or has the wrong version | Check `/usr/local/bin/uv` is 0.11.20 and `/opt/uv-python/bin/python` is Python 3.12.15. Prepare the runtime before retrying. |
| Agent does not connect | Check `/etc/dmitri/agent.env`, network reachability, and `journalctl -u dmitri-agent.service`. Keep the private key and device identity intact. |
| Update fails or inspection reports recovery needed | Follow [PI-RECOVERY](PI-RECOVERY.md), preserve the journal and update gate, and do not retry until an operator reviews the recovery state. |

The updater's daily timer only checks signed metadata. For package failures, retain
`/var/lib/dmitri/updates/` and `/var/lib/dmitri/update-gate.json`; see the
[agent update recovery procedure](PI-RECOVERY.md#agent-update-recovery).

## Not covered

- Self-service pairing and device-key rotation (Phase 2; see
  [`roadmap/AUTH.md`](roadmap/AUTH.md)).
- Raspberry Pi OS upgrades or general OS patch management.
- Wi-Fi capture via the ALFA adapter.
