# TRUTH — Revocation takes effect on the live agent connection

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

Source issue: DMI-97 (parent DMI-47, milestone MVP — Control).

## Narrative

Revoking a device is the operator's answer to a Pi that was stolen, compromised, or
decommissioned. Today it only stops the *next* connection. Revocation is checked once, when
the agent opens its socket. A Pi holds that socket open for days, so a device revoked at
10:00 keeps receiving scan commands and keeps reporting status until it happens to
disconnect on its own. A security control that takes effect at an unpredictable future time
is a control in name only.

This feature makes revocation effective **from the moment it is recorded**, on the connection
the device already holds. It does not build the operator-facing way to *trigger* revocation —
today that is a manual database update, and the surface for it is separate work.

## Business rules

- A revoked agent must not hold a live command connection. The connection is **closed**, not
  merely refused at its next upgrade.
- Revocation is re-checked on every inbound frame from the agent. A frame from a revoked
  agent is rejected and its connection closed.
- A revoked agent must not be **delivered** a command, even when its socket is still open and
  it has sent nothing since being revoked.
- The close carries a **distinct, documented close code** that means *permanently revoked*, so
  the daemon knows to stay down rather than redial forever. A revoked device redialling in a
  loop is noise against the API.
- Closing the connection clears the agent's connected projection, so a revoked agent reads as
  offline and is not eligible for command delivery.
- The existing upgrade-time refusal is correct and stays exactly as it is.
- **The check fails closed.** If the system cannot determine whether an agent is revoked, it
  treats the frame as unprocessable and the command as undeliverable. A lookup that fails is
  never read as "not revoked" — that is how revocation checking silently stops working.

## User stories

1. As an operator who has lost physical control of a Pi, I want revocation to stop the backend
   talking to it immediately, so that a stolen device cannot be told to scan our network.
2. As an operator decommissioning a device, I want a revoked Pi to be unable to trigger or
   report scans, so that retired hardware cannot write into our scan history.
3. As the Pi daemon, I want a close code that distinguishes *revoked* from *replaced* or
   *restarting*, so that I stop redialling instead of hammering an API that will never accept
   me.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Frame from revoked agent | A connected agent whose revocation has been recorded | It sends any frame | The frame is rejected without effect, and the socket closes with the revoked close code |
| Status frame does not land | A connected agent revoked mid-scan | It sends a `status` frame | No command lifecycle transition is written and no scan status changes |
| Connected projection cleared | A revoked agent whose socket has been closed | The agent record is read | Its connected projection is empty and the agent reads as offline |
| Delivery refused to revoked agent | A revoked agent whose socket is still registered and which has sent no frame | An operator triggers a scan on it | The command is not delivered; the operator gets the offline outcome and the command reaches its terminal non-delivered state |
| Reconnect still refused | A revoked agent | It attempts a fresh connection | The upgrade is refused `403` (existing behaviour — regression guard) |
| Healthy agent unaffected | A connected agent that is not revoked | It sends frames and is sent commands | Everything behaves exactly as before |
| Lookup failure fails closed | A connected agent | The revocation lookup raises | The frame is not processed and no command is delivered; the failure surfaces rather than being read as "not revoked" |
| Close code documented | The published API contract | The close-code table is read | The revoked code appears beside the existing codes, with "stay down" as the client action |
| Gates | The touched scope | The backend gates run | `uv run ruff check src tests` and `uv run pytest` pass with the test database up |

## Out of scope (v1)

- **No revoke endpoint and no admin UI.** Recording a revocation stays a manual database
  update; the operator-facing surface is separate work.
- **No device key rotation** (AUTH.md Phase 2).
- **No change to the upgrade-time check**, which already works.
- **No revocation of user browser sessions** — an unrelated path.
- **No proactive disconnect at the instant of revocation.** Revocation takes effect on the
  connection at the next inbound frame or the next delivery attempt — whichever comes first —
  and both are closed here. A revoked, idle agent that is never sent a command may hold a
  dead-weight socket until it speaks; it cannot act through it, which is what the control
  requires.

  This is **pull-based revocation** (on-demand validation), the dominant deployed class, not a
  shortcut. `sshd` cannot terminate a live session on key revocation either; EMQX shipped client
  banning without kicking live sessions and added the kick later. Deployed push systems are
  slower than they sound — AWS IoT promises only "within a few minutes" after deactivating a
  certificate, and Entra's continuous access evaluation admits up to 15 minutes. On every path
  this feature checks, our window is smaller than any of them. See
  `docs/research/revocation-on-live-connections.md`.

- **No bounded window for the idle case.** A revoked agent that never speaks and is never sent a
  command holds its socket for an unbounded time in v1. Every system that takes revocation
  seriously eventually bounds this with a number. Dmitri already runs periodic sweeps, so a
  future sweep could bound it at one sweep interval — that is follow-up work, not this issue.

## Settled decisions

- **Revoked close code — `4001 revoked`. Confirmed by the operator 2026-09-01.** Existing codes
  are `1012` (restarting, redial), `1000` (normal, redial), `4000 replaced` (stay down). `4001`
  is the next code in the private range and carries `4000`'s "stay down" semantics. The daemon
  (DMI-66) keys its reconnect behaviour on this value, so it is a contract value: changing it
  later is a coordinated change across both ends.

  Research found no argument against it — a distinct code carrying *why* an authenticated session
  was torn down matches MQTT 5.0's use of a separate reason code for the same case.

No open questions remain.

## Related specs

- Implementation: `ARCHITECTURE.md`
- No `DESIGN.md` — backend and contract only, no screen changes.
- Contract: ADR-011 §2, §3, §4 (Pi command channel); ADR-005 §1 (agent auth, Ed25519).
- Related issues: DMI-66 (daemon reconnect behaviour), DMI-101 (supersession/replacement).

## Docs drift (from `/docs-sync`, 2026-09-01)

Reported, not applied — each needs a human call:

- `docs/roadmap/AUTH.md:78` hedges "`revoked_at` column **may** exist". It does exist, and as of
  this feature it is enforced on live connections, not only at the upgrade. The substantive claim
  on that line — no rotate/revoke UX in September — remains true and is unaffected by this work, so
  the line was left alone. `docs/roadmap/BACKEND.md:212` already lists `revoked_at` definitively.
  Roadmap files are owned by the `roadmap-sync` skill; re-word there if the hedge is worth removing.
