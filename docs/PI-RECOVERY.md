# Pi recovery guide

Use this guide when a Dmitri device is offline or its service log says the command channel is
parked. A parked agent stays running, starts no new scan, uploads nothing, and tries to connect
again once per hour.

Read the current log on the Pi:

```bash
sudo journalctl -u dmitri-agent -n 100 --no-pager
```

The park line has this form:

```text
command channel parked (<reason>); next attempt at <UTC time>
```

## Park reasons

### `revoked`

- **How to recognize it:** the web app shows **Revoked**, and the Pi logs `command channel parked
  (revoked)` after the backend closes its live connection.
- **What the Pi does:** it waits until the logged time, then tries again. If it is still revoked,
  the upgrade is refused and later park lines say `refused`.
- **What to do:** an admin opens the device detail and selects **Restore device**. The device keeps
  its name and watched network. It reconnects on its next hourly attempt.
- **Site visit:** not needed unless the Pi is also powered off, offline, or damaged.

### `replaced`

- **How to recognize it:** the log says `command channel parked (replaced)`.
- **What the Pi does:** it waits one hour and tries again. With two running daemons that share one
  device identity, the two copies can continue replacing each other.
- **What to do:** find the duplicate installation or cloned SD card and stop it. Keep only the Pi
  that owns this device identity.
- **Site visit:** needed when the duplicate cannot be reached remotely or its location is unknown.

### `refused`

- **How to recognize it:** the log says `command channel parked (refused)`. This follows an HTTP
  `403` during the WebSocket upgrade or another backend-defined refusal.
- **What the Pi does:** it retries once per hour with a fresh signed request.
- **What to do:** first check whether the web app shows **Revoked** and restore the device if
  appropriate. If it is not revoked, verify that `DEVICE_ID` in `/etc/dmitri/agent.env` is the UUID
  registered for this appliance.
- **Site visit:** needed only when the configuration cannot be corrected through remote access.

### `upload_refused`

- **How to recognize it:** the log says `command channel parked (upload_refused)` after a scan
  upload receives `403`. The command records `ingest_failed`.
- **What the Pi does:** it discards the result, drops the command connection, and retries the
  connection once per hour. It does not retry that upload.
- **What to do:** check whether the device was revoked. If not, verify that its registered
  organization and identity own the scan it was asked to upload.
- **Site visit:** normally not needed; investigate backend provisioning first.

## Problems that parking cannot repair

| Symptom | Action | Site visit |
|---|---|---|
| Pi has no power | Restore power and check the supply. | Yes, unless the power can be controlled remotely. |
| Pi has no network route | Restore Ethernet/Wi-Fi and DNS access to the backend. | Only if remote network management is unavailable. |
| `IngestConfigError` and the process exits | Correct `/etc/dmitri/agent.env`; `BACKEND_URL` must be an origin, `DEVICE_ID` a UUID, and `DEVICE_PRIVATE_KEY` 64 hex characters. | Only without remote access. |
| Repeated upgrade `401` with short reconnect backoff | Correct clock skew, device ID, or the registered public/private key pair. A `401` does not park. | Only without remote access. |
| Read-only filesystem, I/O errors, or an SD card that will not boot | Replace or re-image the SD card, then provision the device key again. | Yes. |

After a repair, use the log to confirm `command channel connected`. For a parked device, wait until
the logged next-attempt time; there is no supported “retry now” action.

## Agent update recovery

The update timer only checks signed repository metadata. A package installation starts only after
an administrator accepts an update from the device page. If an update is reported as failed or
the device remains unavailable afterward, collect the updater state before retrying:

```bash
sudo systemctl status dmitri-agent.service dmitri-agent-update.service \
  dmitri-agent-update.timer --no-pager
sudo journalctl -u dmitri-agent-update.service -n 100 --no-pager
sudo journalctl -u dmitri-agent-update-check.service -n 100 --no-pager
sudo /usr/bin/python3 /usr/lib/dmitri/updater.py --inspect
```

`--inspect` is read-only. Check the journal for the operation phase and failure code, and retain
`/var/lib/dmitri/updates/` plus `/var/lib/dmitri/update-gate.json` for recovery. If inspection
reports `recovery_required` or `needs_intervention`, do not remove the gate or journal and do not
start another update. Keep the device available for an assisted operator recovery. If the
metadata check fails, verify the Pi clock, DNS/HTTPS connectivity, and that the backend release
catalog is refreshing successfully; never bypass signature verification or replace the installed
archive key with an unverified one.

For a backend-side catalog problem, inspect worker logs and confirm that API and worker use the
same repository URL, keyring path, origin, and suite. The keyring is baked into the reviewed
backend image at `/app/agent-release/public-keyring.gpg`; it is not accepted from the request.
