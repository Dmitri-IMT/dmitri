# Pi Installer Playbook (vendor)

> **Audience:** the technical installer who deploys a Dmitri appliance on-site.
> **Scope:** flashing, provisioning, registering and enabling one Raspberry Pi.
> Self-service pairing and device-key rotation are Phase 2 — see
> [`roadmap/AUTH.md`](roadmap/AUTH.md).

Every step below was executed against real hardware on 2026-09-11; the commands are
transcribed from that run, not written from memory.

## 0. Hardware

| Item | Value |
|---|---|
| Board | Raspberry Pi 4 Model B (ADR-001 target) |
| Power | USB-C, 3 A. **Not** micro-USB — that is the Pi 3 connector |
| Video (if needed) | micro-HDMI |
| Storage | microSD, 8 GB minimum |
| Network | Ethernet |

**Verify the card before trusting it.** A counterfeit or failing microSD writes
successfully, then silently discards the data — the board simply never boots. Use an
imaging tool that reads back and verifies what it wrote. Do not use bare `dd`, which
reports success without checking.

## 1. Flash the OS

Raspberry Pi OS Lite, 64-bit. Configure in the imager's settings screen before writing:

- hostname
- SSH enabled, password authentication
- the installer account username and password
- locale and timezone

Leave Wi-Fi unset when deploying on Ethernet.

> **Debian release matters.** Trixie ships Python 3.13, and
> `hardware-agent/pyproject.toml` requires `>=3.11,<3.13`. The system interpreter
> therefore cannot run the agent. This is expected and handled: `uv` provisions its own
> Python 3.12 in step 3. Do not "fix" it by installing a system Python.

## 2. First boot and network

Boot with the Ethernet cable connected. Find the device and open a session:

```bash
ping <hostname>.local
ssh <user>@<address>
```

Give the first boot 90 seconds — it resizes the filesystem and reboots once.

Record the address. Assign a **static IP or a DHCP reservation** on the router: the
backend addresses the device by its registered agent, but operators and installers need
a stable address for support.

## 3. Install the runtime

```bash
sudo apt-get update
sudo apt-get install -y nmap
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`nmap` is the scanning engine (ADR-002). `uv` manages the agent's Python.

## 4. Install the agent

The agent lives in `/opt/dmitri-agent`, owned by root.

```bash
sudo mkdir -p /opt/dmitri-agent
# copy hardware-agent/ -> /opt/dmitri-agent
sudo chown -R root:root /opt/dmitri-agent
sudo env HOME=/root UV_PYTHON_INSTALL_DIR=/opt/uv-python \
  ~/.local/bin/uv sync --project /opt/dmitri-agent
```

One sync, production dependencies only. `pytest` and `ruff` never reach a customer appliance.

> **`UV_PYTHON_INSTALL_DIR` is not optional.** By default `uv` puts its interpreter under
> `/root/.local/share/uv/`, and the venv's `bin/python` becomes a symlink into `/root`.
> The service runs with `ProtectHome=true`, which hides `/root` — so systemd fails with
> `203/EXEC "No such file or directory"` even though the executable is plainly there.
> Installing the interpreter under `/opt/uv-python` keeps the whole runtime in one place
> that the hardened unit can reach. Use the same variable on every later `uv sync`.

Verify the runtime on the device:

```bash
sudo /opt/dmitri-agent/.venv/bin/python -V     # expect 3.12.x
```

> **The test suite does not run here.** `tests/test_contract_models.py` resolves
> `contracts/openapi/openapi.yaml` two directories above the agent, which is repository
> layout, not a runtime dependency — `agent.normalize.contracts` is an in-tree Python
> module and nothing at runtime reads that YAML. Prove the suite on the vendor machine
> against the release being shipped; the appliance receives the runtime, the virtualenv
> and the unit, and nothing else.

## 5. Generate the device keypair **on the Pi**

The private key is created on the device and never leaves it. Only the public key is
transmitted, and that channel needs integrity, not confidentiality.

```bash
sudo mkdir -p /etc/dmitri && sudo chmod 700 /etc/dmitri

sudo /opt/dmitri-agent/.venv/bin/python - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s

key = Ed25519PrivateKey.generate()
private_hex = key.private_bytes(
    s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()
).hex()
public_hex = key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()

with open("/etc/dmitri/agent.env", "w") as env:
    env.write("DEVICE_PRIVATE_KEY=" + private_hex + "\n")

print("PUBLIC_KEY=" + public_hex)
PY

sudo chmod 600 /etc/dmitri/agent.env
sudo chown root:root /etc/dmitri/agent.env
```

Carry the printed `PUBLIC_KEY` to step 6.

> **One copy of the private key, in one place.** The daemon reads `DEVICE_PRIVATE_KEY` from
> the environment via `load_ingest_config()` and never opens a key file, so a separate
> `device.key` would be private material on disk with no consumer — surface area for nothing.
> The key is written straight into `agent.env`, and the private hex is never printed, never
> written to `/tmp`, and never leaves the device.

## 6. Register the public key with the backend

Run by the **vendor**, against the target environment. Use `--public-key` with the value
from step 5 — never `--generate`, which would create the private key off-device and
defeat the model.

```bash
cd backend
railway run --service api --environment <env> \
  uv run backend-provision-agent \
  --org-id <ORG_ID> \
  --display-name <device-name> \
  --public-key <PUBLIC_KEY from step 5>
```

It prints `agent_id=<uuid>`. That UUID is the `DEVICE_ID`.

## 7. Complete `/etc/dmitri/agent.env`

Step 5 already wrote `DEVICE_PRIVATE_KEY`. Append the other two — `agent/transport/ingest.py`
validates all three:

| Variable | Format |
|---|---|
| `BACKEND_URL` | http/https origin, no credentials |
| `DEVICE_ID` | UUID — the `agent_id` from step 6 |
| `DEVICE_PRIVATE_KEY` | 64 hex characters — written in step 5 |

```bash
sudo sh -c 'printf "BACKEND_URL=%s\nDEVICE_ID=%s\n" \
  "<backend origin>" "<agent_id>" >> /etc/dmitri/agent.env'
sudo chmod 600 /etc/dmitri/agent.env
```

## 8. Enable the service

```bash
sudo mkdir -p /var/lib/dmitri
sudo cp /opt/dmitri-agent/dmitri-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dmitri-agent
systemctl status dmitri-agent
journalctl -u dmitri-agent -f
```

A healthy start logs:

```
agent.transport.command_channel: command channel connected
```

Confirm it is not restart-looping:

```bash
systemctl show dmitri-agent -p ActiveState,SubState,NRestarts
# ActiveState=active  SubState=running  NRestarts=0
```

Scan results land in `/var/lib/dmitri`, set by `XDG_DATA_HOME` in the unit. Without it the
agent writes under `/root`, which `ProtectHome=true` makes unreachable.

The unit runs as **root** deliberately: `nmap` requires root for TCP/IP fingerprinting.
Without it every scan finishes `partial` (exit 10) with *"TCP/IP fingerprinting (for OS
scan) requires root privileges"*.

`Restart=always` with `StartLimitIntervalSec=0` covers the scheduled-reboot policy — the
daemon reconnects to the command channel by itself after any reboot or backend restart.

## 9. Verify end to end

```bash
curl -s <BACKEND_URL>/api/v1/health          # {"status":"ok",...}
systemctl is-active dmitri-agent             # active
```

Then trigger a scan from the web UI and confirm results arrive on the read path.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Board never appears on the network | Bad microSD. Verify the write; check whether `userconf.txt` is still on the boot partition — the OS deletes it during a successful first boot |
| Scan ends `partial`, exit 10 | `nmap` not running as root |
| `IngestConfigError` on start | `agent.env` malformed — `BACKEND_URL` must be a bare origin, `DEVICE_ID` a UUID, `DEVICE_PRIVATE_KEY` 64 hex characters |
| Under-voltage or throttling | Check `vcgencmd get_throttled`; `0x0` means healthy |

## Not covered

- **Agent updates.** No mechanism is defined yet. Today an update means copying a new
  tree to `/opt/dmitri-agent`, re-running `uv sync` and restarting the unit, by hand,
  per device. This does not scale past a handful of appliances and needs its own
  decision record.
- Self-service pairing and device-key rotation (Phase 2).
- Wi-Fi capture via the ALFA adapter.
