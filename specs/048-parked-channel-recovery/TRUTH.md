# TRUTH — A parked Pi recovers on its own, and admins can revoke and restore devices

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

Source issue: DMI-155 (related: DMI-143, DMI-144; builds on spec 041 — revocation closes the
live connection).

## Narrative

A Pi appliance already recovers from almost every failure without help. It starts at boot, its
service restarts after a crash, and its command connection redials with a short backoff after a
network drop. This was verified on real hardware on 2026-09-11.

The exception is a **parked** Pi. When the backend refuses the device, the agent decides it must
never try again. Its process then ends, the service manager starts it again ten seconds later,
it is refused again, and it parks again. This cycle repeats forever and never reaches a
connected state. The only way out is a person on the customer's site with a terminal.

Today a Pi parks in four situations: the backend refuses the connection because the device is
revoked; the backend closes the connection because the device is revoked; the backend closes the
connection because a newer connection for the same device replaced it; or the backend refuses a
scan upload. In every case, the organization sees only an offline device with no reason.

There is also no way for an admin to revoke a device or to undo a revocation. Revocation is a
manual database change. So a revoked Pi can never come back, even if it retried.

This feature makes three changes:

1. A parked Pi stays running, says why it is parked, and tries again **once every hour**. It
   never enters a restart loop.
2. Admins can **revoke** a device and **restore** a revoked device from the web app. A restored
   device reconnects on its next hourly attempt, with no one touching it.
3. The web app shows when a device is **revoked**, distinct from offline, and a **recovery
   guide** explains what to do for each park reason.

## Glossary

- **Parked** — the Pi has stopped its normal redial because the backend refused it. It waits
  for the next hourly attempt.
- **Revoke** — an admin action that stops a device from connecting, receiving commands, or
  uploading scans.
- **Restore** — an admin action that undoes a revocation. (The issue calls this "unrevoke".)
- **Park reason** — why the Pi parked: *revoked*, *replaced*, *refused by the backend*, or
  *upload refused*.

## Business rules

### Pi behaviour while parked

- Every park reason uses the same retry policy: **one attempt per hour**. No reason parks the Pi
  forever.
- A parked Pi **keeps its process running**. Parking never causes the process to exit, so the
  service manager never restarts it in a loop.
- While parked, the Pi records its park reason and the time of its next attempt in its log. A
  person who reads the log can tell that the Pi is parked, why, and when it tries again.
- A parked Pi **starts** no scan and uploads nothing. A scan that was already running on the Pi
  finishes by itself, but its result is discarded: it is neither reported nor uploaded.
- When an hourly attempt connects, the Pi leaves the parked state and resumes normal behaviour,
  including the normal short redial backoff after later network drops.
- When an hourly attempt is refused again, the Pi parks again for another hour.
- A network failure is **not** a park reason. It keeps the existing short backoff.
- A missing or wrong device credential that the backend reports as *unauthenticated* is **not** a
  park reason. It keeps the existing short backoff (existing behaviour, unchanged).

### Revoke

- Only an **admin** can revoke a device. Viewers can see that a device is revoked but cannot
  change it.
- Revoking asks the admin to confirm before it takes effect.
- Revocation takes effect at once: the live connection closes, and the device is not delivered
  commands and cannot upload scans (spec 041 behaviour, unchanged).
- Revoking an already revoked device changes nothing and is not an error.
- A device that belongs to another organization cannot be revoked; to the caller it does not
  exist.

### Restore

- Only an **admin** can restore a device.
- Restoring clears the revocation. The device's identity, name and chosen scan network are kept.
- A restored device reconnects on its **next hourly attempt**, so within one hour, with no action
  on site.
- Restoring a device that is not revoked changes nothing and is not an error.
- A device that belongs to another organization cannot be restored; to the caller it does not
  exist.

### Why a device is not connected

- The device list and the device detail show a revoked device as **Revoked**, distinct from
  **Offline**, together with when it was revoked (the app's standard time display).
- A device that is not revoked and not connected shows as **Offline**, as today.
- The home page reports a device that has not reported for many days. A **revoked** device is left
  out of that report, because an admin revoked it on purpose.
- A revoked device offers no scan trigger.

### Recovery guide

- A written recovery guide exists for vendors and admins. For each park reason it says how to
  recognise it, what the Pi does by itself, and what a person must do, if anything.
- The guide covers the cases software cannot fix, and says when a site visit is needed.

## User stories

1. As the vendor, I want a refused Pi to try again by itself, so that a temporary refusal does not
   need a visit to the customer's site.
2. As an admin, I want to revoke a device from the web app, so that I can stop a lost, stolen or
   retired Pi without a database change.
3. As an admin, I want to restore a revoked device, so that a device revoked by mistake comes back
   without anyone touching it.
4. As a viewer in an organization, I want to see that a device is revoked rather than just
   offline, so that I know why it does not scan.
5. As a person on site, I want the Pi's log to say that it is parked, why, and when it tries
   again, so that I do not mistake a parked Pi for a broken one.
6. As the vendor or an admin, I want a recovery guide, so that I know what to do for each reason
   a Pi stops connecting.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Revoked, then restored | A connected Pi | An admin revokes it, then restores it | The Pi parks, and on its next hourly attempt it connects again with no action on the device |
| Refused attempt parks again | A parked Pi whose device is still revoked | Its hourly attempt runs | The attempt is refused, and the Pi parks for another hour |
| Retry interval | A Pi that has just parked, for any park reason | Time passes | Its next connection attempt happens one hour after it parked, and not before |
| No restart loop | A parked Pi | One hour passes | The agent process has kept running for the whole hour and was not restarted |
| Park is logged | A Pi that parks | Its log is read | The log shows the park reason and the time of the next attempt |
| Replaced | A Pi whose connection is closed because a newer connection for the same device replaced it | Less than one hour passes | The Pi makes no connection attempt |
| Parked Pi does no work | A parked Pi | Time passes | It starts no scan and uploads nothing; a scan that was already running has its result discarded |
| Upload refused | A Pi whose scan upload is refused by the backend | The refusal arrives | The Pi parks with the reason *upload refused* and follows the hourly retry policy |
| Network drop is not a park | A connected Pi | The network drops and returns | The Pi redials with the existing short backoff and does not park |
| Normal backoff resumes | A Pi that reconnected after being parked | Its network drops later | It redials with the short backoff, not the hourly one |
| Admin revokes | A connected device and an admin | The admin revokes it and confirms | The device shows as Revoked with the revocation time, its connection closes, and it offers no scan trigger |
| Revoke needs confirmation | An admin on a device | The admin starts a revoke and cancels | Nothing changes |
| Admin restores | A revoked device and an admin | The admin restores it | The device no longer shows as Revoked; its name and scan network are unchanged |
| Viewer cannot revoke or restore | A viewer (not an admin) | The viewer views a device, or calls revoke or restore directly | No revoke or restore action is shown, and a direct call is refused as forbidden |
| Foreign device | An admin of organization A | The admin revokes or restores a device of organization B | The call reports the device as not found, and nothing changes |
| Repeat revoke | A revoked device | An admin revokes it again | Nothing changes, and no error is shown |
| Repeat restore | A device that is not revoked | An admin restores it | Nothing changes, and no error is shown |
| Revoked device is not reported as long offline | A revoked device that has not reported for more days than the home page's limit | The home page is read | It reports no "offline for N days" event for that device |
| Revoked vs offline | One revoked device and one disconnected device that is not revoked | A user opens the device list | The first shows Revoked with its revocation time; the second shows Offline |
| Recovery guide | The documentation | A reader opens the recovery guide | It covers each park reason: how to recognise it, what the Pi does itself, what a person must do, and when a site visit is needed |
| Gates | The touched scope | Each layer's gates run | The Pi, backend and frontend gates pass, with the test database up for the backend |

## Out of scope (v1)

- Powering on a Pi that is switched off (a smart plug or Wake-on-LAN question, not software).
- Changing the authentication model or what a refusal means.
- The single-command failures in DMI-143 and DMI-144.
- Rotating a device's key, re-pairing a device, or deleting a device.
- Recording who revoked or restored a device (only the revocation time is shown).
- Showing the Pi's own park reason (for example *replaced*) in the web app. The web app shows only what the backend knows: Revoked, Online or Offline.
- Notifying anyone (email or otherwise) when a device is revoked, restored or parked.
- A home-page event for a revoked device. The home page only stops reporting it as long offline.
- A link to the recovery guide from the web app. The guide serves the vendor and the repository.
- Stopping a scan that is already running on a parked Pi.
- A way to make a parked Pi try again sooner than its next hourly attempt.

## Related specs

- Builds on: `specs/041-revoked-agent-live-socket-close/`
- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
