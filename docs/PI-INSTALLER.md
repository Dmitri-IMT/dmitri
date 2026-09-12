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

The agent lives in `/opt/dmitri-agent`, owned by root. `contracts/` must sit beside it
at `/opt/contracts`, because the agent resolves the OpenAPI contract one level above its
own directory.

```bash
sudo mkdir -p /opt/dmitri-agent /opt/contracts
# copy hardware-agent/ -> /opt/dmitri-agent, contracts/ -> /opt/contracts
sudo chown -R root:root /opt/dmitri-agent /opt/contracts
# verification pass, with dev tooling
sudo env HOME=/root ~/.local/bin/uv sync --project /opt/dmitri-agent --extra dev
```

Verify on the device before going further:

```bash
sudo /opt/dmitri-agent/.venv/bin/python -V     # expect 3.12.x
cd /opt/dmitri-agent && sudo env HOME=/root ~/.local/bin/uv run pytest -q
```

The suite must be fully green. A failure in `tests/test_contract_models.py` means
`/opt/contracts` is missing or misplaced.

**Then strip the dev tooling.** `pytest` and `ruff` have no place on a customer
appliance; they exist only for the verification above.

```bash
sudo env HOME=/root UV_PYTHON_INSTALL_DIR=/opt/uv-python \
  ~/.local/bin/uv sync --project /opt/dmitri-agent
```

This removes `pytest`, `pytest-asyncio`, `ruff` and `pyyaml`, leaving only the runtime
dependencies. Re-run a scan afterwards to confirm the agent still starts.

> **`UV_PYTHON_INSTALL_DIR` is not optional.** By default `uv` puts its interpreter under
> `/root/.local/share/uv/`, and the venv's `bin/python` becomes a symlink into `/root`.
> The service runs with `ProtectHome=true`, which hides `/root` — so systemd fails with
> `203/EXEC "No such file or directory"` even though the executable is plainly there.
> Installing the interpreter under `/opt/uv-python` keeps the whole runtime in one place
> that the hardened unit can reach. Use the same variable on every later `uv sync`.

> **What ships to the Pi:** only `hardware-agent/` — the daemon (outbound WebSocket
> command channel), the scanner, the ingest client and the local TUI. The backend and
> the frontend never go on the device.

## 5. Generate the device keypair **on the Pi**

The private key is created on the device and never leaves it. Only the public key is
transmitted, and that channel needs integrity, not confidentiality.

```bash
sudo mkdir -p /etc/dmitri && sudo chmod 700 /etc/dmitri

/opt/dmitri-agent/.venv/bin/python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
k = Ed25519PrivateKey.generate()
priv = k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()).hex()
pub  = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
open('/tmp/.dk','w').write(priv)
print('PUBLIC_KEY=' + pub)
"

sudo sh -c "mv /tmp/.dk /etc/dmitri/device.key; chmod 600 /etc/dmitri/device.key; chown root:root /etc/dmitri/device.key"
```

Carry the printed `PUBLIC_KEY` to step 6. The private key stays in
`/etc/dmitri/device.key`, `root:root`, mode `0600`.

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

## 7. Write `/etc/dmitri/agent.env`

Three variables, validated by `agent/transport/ingest.py`:

| Variable | Format |
|---|---|
| `BACKEND_URL` | http/https origin, no credentials |
| `DEVICE_ID` | UUID — the `agent_id` from step 6 |
| `DEVICE_PRIVATE_KEY` | 64 hex characters — contents of `/etc/dmitri/device.key` |

```bash
sudo sh -c 'umask 077; cat > /etc/dmitri/agent.env <<ENV
BACKEND_URL=<backend origin>
DEVICE_ID=<agent_id>
DEVICE_PRIVATE_KEY=<contents of /etc/dmitri/device.key>
ENV'
sudo chmod 600 /etc/dmitri/agent.env
```

## 8. Enable the service

```bash
sudo mkdir -p /var/lib/dmitri
sudo cp /opt/dmitri-agent/deploy/dmitri-agent.service /etc/systemd/system/
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
| `test_contract_models.py` fails | `/opt/contracts/openapi/openapi.yaml` missing |
| `IngestConfigError` on start | `agent.env` malformed — check the `DEVICE_ID` is a UUID and the key is 64 hex characters |
| Under-voltage or throttling | Check `vcgencmd get_throttled`; `0x0` means healthy |

## Not covered

- **Agent updates.** No mechanism is defined yet. Today an update means copying a new
  tree to `/opt/dmitri-agent`, re-running `uv sync` and restarting the unit, by hand,
  per device. This does not scale past a handful of appliances and needs its own
  decision record.
- Self-service pairing and device-key rotation (Phase 2).
- Wi-Fi capture via the ALFA adapter.
