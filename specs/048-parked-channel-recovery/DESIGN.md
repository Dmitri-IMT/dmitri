# DESIGN: Revoked devices, revoke and restore (DMI-155)

Spec only. No implementation code. This document changes two existing screens —
**Devices** (`/devices`) and **Device detail** (`/devices/:agentId`) — and adds one confirm
dialog. Every visual value inherits [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md)
and the layouts in [`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) §8–§9
and [`specs/043-scan-box-and-duration/DESIGN.md`](../043-scan-box-and-duration/DESIGN.md).
It does not restyle anything else.

**Behaviour source:** [`TRUTH.md`](TRUTH.md). **Contract owner:** `ARCHITECTURE.md` /
`INTEGRATION.md` (written in parallel). This document names data by domain meaning — *revoked
date*, *revoke*, *restore* — and defines no endpoint.

**Rendered preview:** [Revoked Devices](https://claude.ai/artifact/6y8DfDCBfyrSZYVG64tAfG) — the Devices list with Online, Offline and Revoked rows;
Device detail as admin (connected, revoked, restore pending, restore error), as viewer
(revoked); the revoke confirm dialog at rest, pending and failed. Built from Foundations tokens
and the real typefaces (Inter Variable, Geist Mono for data). The box-drawing renders below are
structural notes only. **The human performs the visual check on the preview, and that check
closes this feature** (project rule: the human visual check closes every frontend feature). No
agent signs off on how it looks.

**Role vocabulary.** The product's roles are **Admin** and **Viewer** (FOUNDATIONS §Vocabulary;
the API role union is `admin | viewer`); `TRUTH.md` uses the same words. The role is read from the session (`useSession().user.role`,
sourced from `GET /users/me`), and role-gated controls use the existing `AdminOnly` wrapper.

---

## 1. Screen flow

No new routes.

```
/devices                              Devices list
  │ whole row (unchanged) ──────────► /devices/:agentId
  │ Status cell now reads Online · Offline · Revoked {time}
  │
/devices/:agentId                     Device detail
  │
  ├─ device NOT revoked
  │    admin:  [Revoke device] (bottom section)
  │              └─► Revoke dialog
  │                    ├─ [Cancel] / Esc / overlay ─► back to detail, nothing changes
  │                    └─ [Revoke device] ─► pending ─┬─ ok ─► toast, detail re-reads ─► revoked state
  │                                                   └─ fail ─► error line in the dialog, stays open
  │    viewer: no section
  │
  └─ device revoked
       admin:  [Restore device] (in place of the scan controls)
                 └─► pending ─┬─ ok ─► toast (reconnects within the hour), re-read ─► offline state
                              └─ fail ─► error line under the button
       viewer: the revoked section, words only, no button
```

After either action succeeds, the device detail **and** the device list re-read, so the list is
correct when the reader goes Back.

---

## 2. Devices (`/devices`)

**Epicenter: the box table** (042 §8, unchanged). This feature changes one cell, the column
shares and the row tone.

**Vertical rhythm (unchanged from 042):** intra-group `2`, inter-group `4`, inter-section `12`.

### 2.1 Regular state — Online, Offline and Revoked rows

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings          gui@ronthocorp.com │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Devices                                                         ← title-lg              │
│  The Dmitri boxes reporting to this organisation.                ← muted                 │
│                                                    ↕ step 12                             │
│  BOX                       NETWORK            STATUS                  LAST REPORT        │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  Rontho HQ                 192.168.1.0/24     Online                  4 min ago          │
│  Warehouse                 10.0.4.0/24        Offline                 yesterday 18:02    │ ← muted row
│  Old office                172.16.0.0/24      Revoked today 09:40     today 09:38        │ ← muted row
│  Reception spare           10.0.9.0/24        Revoked Aug 14, 11:05   Aug 14, 11:04      │ ← muted row
└──────────────────────────────────────────────────────────────────────────────────────────┘
       30%                       25%                 20%                    25%
```

**Walkthrough.**

- **Status cell.** One line. `Online`, `Offline`, or `Revoked` followed by the revoked date
  through the shared `Timestamp` component (relative inside 7 days, absolute beyond, exact value
  in the hover `title`). The word is first, so the column still scans by word. No chip, no icon,
  no colour — the word carries the state (FOUNDATIONS §Color, §Tables silent-machine precedent).
  The cell truncates with the full string in `title` if it ever overflows.
- **Column shares change from 30 / 30 / 15 / 25 to 30 / 25 / 20 / 25.** At 15% the Status cell
  truncates `Revoked yesterday 18:02`. The Network cell holds a mono CIDR of at most 18
  characters and keeps ample room at 25%.
- **Row tone.** A revoked row is muted, exactly like an offline row: it is not connected. The
  word, not the tone, tells Revoked from Offline.
- **Last report** keeps showing the last report time. A revoked device's last report is still
  true and useful ("it stopped reporting when we revoked it").
- **No per-row action.** Revoke and restore live on the detail screen only. The whole row still
  opens the device.

The revoked date is the source of truth for the Revoked state: a device with a revoked date is
Revoked whatever its connection flag says; a device without one is Online or Offline as today.

### 2.2 States

| State | Render |
| --- | --- |
| Regular | §2.1. |
| Loading | Unchanged — `LoadingSkeleton` table body, first load only. |
| Blank | Unchanged (042 §8.1). A revoked device is still listed, so it never causes the blank state. |
| Error | Unchanged — `Couldn't load your devices.` + `Try again`. |

### 2.3 Keyboard and focus

Unchanged: nav → user menu → each row in order; `Enter` opens the device.

---

## 3. Device detail (`/devices/:agentId`)

**Epicenter, unchanged for a connected device: this box's scan controls.** For a **revoked**
device the epicenter becomes *why it cannot scan, and how to bring it back* — the revoked section
takes the place the scan controls held.

**Vertical rhythm (unchanged from 042 §9):** intra-group `2` (heading to body), inter-group `4`
(body to button), inter-section `12`. No rules, no cards between sections — proximity groups.

**Section order.**

| Device | Order, step `12` apart |
| --- | --- |
| Not revoked | Back · identity · Watched network · scan section · Scan history · **Revoke this device** (admin only) |
| Revoked | Back · identity · Watched network (read-only) · **This device is revoked** · Scan history |

Revoke sits last because it is rare and destructive — the Settings "Leave this organisation"
precedent. Restore sits high because on a revoked device it is the only thing to do.

### 3.1 Admin — connected device

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings          gui@ronthocorp.com │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Rontho HQ                                                       ← title-lg              │
│  Online · last report 4 min ago                                  ← muted                 │
│                                                    ↕ step 12                             │
│  Watched network                                                                         │
│  192.168.1.0/24 (eth0)                                        [ Change ]                 │
│                                                    ↕ step 12                             │
│  Scan type                                                                               │
│  ┌───────┬──────────┬───────────┬─────┬──────┐                                           │
│  │ Quick │ Standard │ Extensive │ Max │ NSPi │                                           │
│  └───────┴──────────┴───────────┴─────┴──────┘                                           │
│  Same 1000 connection points, and also inspects …                                        │
│  [ Scan now ]                                                                            │
│                                                    ↕ step 12                             │
│  Scan history                                                                            │
│  … (043 table, unchanged) …                                                              │
│                                                    ↕ step 12                             │
│  Revoke this device                                              ← title-sm              │
│  It disconnects straight away and can't scan or send results     ← muted, max-w-prose    │
│  until an admin restores it.                                                             │
│                                                    ↕ step 4                              │
│  [ Revoke device ]                                               ← outline, self-start   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Walkthrough.** Everything above Scan history is 042 §9.1 and 043, unchanged. One new section
closes the page: a `title-sm` heading, one muted sentence (step `2` below the heading), and an
**outlined** `Revoke device` button step `4` below, left-aligned. It is outlined, never filled:
the filled primary on this screen stays `Scan now`. An **offline** (not revoked) device renders
the same way, with 042 §9.6's offline note under `Scan now`.

### 3.2 Revoke confirm dialog

```
                ┌──────────────────────────────────────────────────────┐
                │  Revoke Rontho HQ?                     ← title-sm     │
                │                                        ↕ step 2      │
                │  It disconnects straight away and can't scan or send  │
                │  results. You can restore it later; it reconnects     │
                │  within an hour of being restored.     ← muted        │
                │                                                        │
                │  (error line — empty at rest)          ← role=alert   │
                │                                                        │
                │                        [ Cancel ]  [ Revoke device ]  │
                └──────────────────────────────────────────────────────┘
                              DialogShell, size md
```

**Walkthrough.** The same shape as the invite `RevokeDialog` in `frontend/src/pages/users/`:
`DialogShell` (size `md`, no close button), `Dialog.Title`, `Dialog.Description`, a
`role="alert"` error paragraph that is empty at rest, and a right-aligned button row (step `2`
between buttons) with outlined `Cancel` and filled `Revoke device`. Gaps inside the dialog follow
the existing dialog primitive; nothing new.

It is a **plain confirm, not confirm-by-typing.** Typing the target is reserved for hard deletes
(`RemoveMemberDialog`, Settings leave). Revocation is undone with one click, like an invite
revoke.

**Pending.** `Cancel` is removed and the dialog is locked (no Esc, no overlay close) — the
`RevokeDialog` precedent. The confirm reads `Revoking…` and is disabled (the progress carve-out
of FOUNDATIONS §Interaction states: reduced opacity, `pointer-events: none`, out of tab order).

```
                │                                   [ Revoking… ]      │   ← Cancel absent, locked
```

**Error.** The dialog stays open and unlocked; the alert line reads
`Couldn't revoke this device. Try again.` in `--ink`, `text-body-sm`. `Cancel` returns and the
confirm reads `Revoke device` again, so trying again is the next step.

```
                │  Couldn't revoke this device. Try again.  ← ink, alert │
                │                        [ Cancel ]  [ Revoke device ]  │
```

**Success.** The dialog closes, the toast reads `Rontho HQ was revoked.`, and the detail re-reads
into §3.3.

### 3.3 Admin — revoked device

```
│  ← Back                                                                                  │
│  Old office                                                      ← title-lg              │
│  Revoked today 09:40 · last report today 09:38                   ← muted                 │
│                                                    ↕ step 12                             │
│  Watched network                                                                         │
│  172.16.0.0/24 (eth0)                                            ← no Change             │
│                                                    ↕ step 12                             │
│  This device is revoked                                          ← title-sm              │
│  It can't connect, scan or send results. Once restored, it       ← muted, max-w-prose    │
│  reconnects on its next hourly attempt, within the hour.                                 │
│                                                    ↕ step 4                              │
│  [ Restore device ]                                              ← filled primary        │
│                                                    ↕ step 12                             │
│  Scan history                                                                            │
│  … (unchanged; past scans stay readable) …                                               │
│                                                    ← no Scan type, no Scan now,          │
│                                                      no command status, no Retry,        │
│                                                      no "Revoke this device" section     │
```

**Walkthrough.**

- **Presence line** reads `Revoked {time} · last report {time}`. Revoked replaces Online/Offline;
  never both.
- **Watched network** shows the kept network, **without `Change`**. A revoked device reports
  nothing, so a save could never succeed; restore keeps the network (TRUTH §Restore). If no
  network was ever chosen, the line reads `No network chosen yet.` and the chooser does **not**
  open on arrival.
- **Scan section is absent** — the tab strip, `Scan now`, the offline note, and any in-flight
  command status with its `Retry` (TRUTH: a revoked device offers no scan trigger; `Retry` is a
  trigger). A scan that was running when the device was revoked still shows its outcome in Scan
  history.
- **The revoked section** holds the heading, one sentence and the **filled primary**
  `Restore device`. It is the one primary action on this screen now that `Scan now` is gone. The
  sentence sets the hourly expectation *before* the click, so the toast after it confirms what the
  admin was already told.
- **No confirm for restore.** It is not destructive, and TRUTH asks for confirmation on revoke
  only.

### 3.4 Admin — restore pending and restore error

```
Pending
│  This device is revoked                                                                  │
│  It can't connect, scan or send results. Once restored, it                               │
│  reconnects on its next hourly attempt, within the hour.                                 │
│  [ Restoring… ]                                                  ← disabled (progress)   │

Error
│  This device is revoked                                                                  │
│  It can't connect, scan or send results. Once restored, it                               │
│  reconnects on its next hourly attempt, within the hour.                                 │
│  [ Restore device ]                                                                      │
│  Couldn't restore this device. Try again.                        ← ink, body-sm, alert   │
```

**Walkthrough.** Pending disables the button and swaps its label; nothing else on the page moves.
On failure the button returns to `Restore device` and a `role="alert"` line appears step `2`
below it. The next click clears the line. **Success:** the toast reads
`Old office was restored. It reconnects on its next hourly attempt, within the hour.`, and the
detail re-reads. The device then shows as **Offline** (it is no longer revoked and not yet
connected) with the §3.1 layout; it turns Online by itself when the Pi's hourly attempt connects.

### 3.5 Viewer — revoked device

```
│  ← Back                                                                                  │
│  Old office                                                                              │
│  Revoked today 09:40 · last report today 09:38                                           │
│                                                    ↕ step 12                             │
│  Watched network                                                                         │
│  172.16.0.0/24 (eth0)                                                                    │
│                                                    ↕ step 12                             │
│  This device is revoked                                                                  │
│  It can't connect, scan or send results. Ask your admin to restore it.                   │
│                                                    ↕ step 12                             │
│  Scan history                                                                            │
```

**Walkthrough.** The viewer learns the same fact in the same place. `Restore device` is **absent
from the DOM**, not disabled, and the sentence names the next step as a person, matching the
existing viewer line `No network chosen yet. Ask your admin to choose one.` A viewer on a
**connected** device sees 042 §9.3 with **no** "Revoke this device" section at all — the section
holds only an action, so it goes with the action.

### 3.6 States summary

| State | Admin | Viewer |
| --- | --- | --- |
| Loading | Unchanged (042 §9.7). | Unchanged. |
| Not found / load error | Unchanged (`That device doesn't exist.` / `Couldn't load this device.` + `Try again`). | Unchanged. |
| Online or offline, not revoked | §3.1 — new Revoke section last. | 042 §9.3 — no Revoke section. |
| Revoke dialog at rest / pending / error | §3.2 | — (never rendered) |
| Revoked | §3.3 | §3.5 |
| Restore pending / error | §3.4 | — (never rendered) |
| Just restored | §3.1 layout, presence `Offline · …`, success toast. | — |

**Idempotence.** A repeat revoke or repeat restore (for example, two admins acting at once)
succeeds on the server, so the UI shows the success toast and re-reads; the screen lands in the
correct state either way. No special copy.

**Refused or vanished.** A revoke or restore that the server refuses — including a device that no
longer exists to the caller, or an admin demoted mid-session — shows the error line of §3.2 or
§3.4. The re-read that follows any later navigation then shows the true state (not found, or the
viewer layout).

### 3.7 Keyboard and focus

**Page, admin, not revoked.** Tab order: nav → user menu → `Back` → `Change` → tab strip (one
stop, ← / → inside) → `Scan now` → Scan history rows and pagination → `Revoke device`.

**Page, admin, revoked.** Tab order: nav → user menu → `Back` → `Restore device` → Scan history.

**Revoke dialog.**

| Moment | Behaviour |
| --- | --- |
| Open | Focus moves to the `Revoke device` confirm button (the `RevokeDialog` precedent, `initialFocusRef`). |
| Tab / Shift+Tab | Cycles `Cancel` ↔ `Revoke device`; focus is trapped in the dialog. |
| `Enter` / `Space` | Activates the focused button. There is no form and no submit-on-enter beyond that. |
| `Esc`, overlay click, `Cancel` | Closes with nothing changed; focus returns to the page's `Revoke device` button (`DialogShell` opener restore). |
| Pending | Locked: `Esc` and overlay do nothing, `Cancel` is absent, the confirm is disabled. |
| Error | Unlocked; focus stays on the confirm button, so `Enter` tries again. The alert line is announced. |
| Success | The dialog closes and the opener disappears in the re-read, so focus moves to the presence line (`agents-presence`, `tabIndex={-1}`), which now reads `Revoked …`. |

**Restore.**

| Moment | Behaviour |
| --- | --- |
| Press | Button disables; focus stays on it. |
| Error | Button re-enables with focus kept on it; the alert line is announced. |
| Success | The button disappears in the re-read, so focus moves to the presence line (`agents-presence`), which now reads `Offline · …`. The toast is announced by the existing toast live region. |

---

## 4. Copy

Every string ships verbatim. `{name}` is the device's display name; `{time}` is the shared
`Timestamp` output.

| Where | String |
| --- | --- |
| List — Status, revoked | `Revoked {time}` (e.g. `Revoked today 09:40`, `Revoked Aug 14, 11:05`) |
| List — Status, others | `Online` · `Offline` (unchanged) |
| Detail — presence, revoked | `Revoked {time} · last report {time}` |
| Detail — presence, revoked, never reported | `Revoked {time} · no report yet` |
| Detail — revoke section heading (admin, not revoked) | `Revoke this device` |
| Detail — revoke section body | `It disconnects straight away and can't scan or send results until an admin restores it.` |
| Detail — revoke button | `Revoke device` |
| Dialog — title | `Revoke {name}?` |
| Dialog — body | `It disconnects straight away and can't scan or send results. You can restore it later; it reconnects within an hour of being restored.` |
| Dialog — cancel | `Cancel` |
| Dialog — confirm | `Revoke device` / pending `Revoking…` |
| Dialog — error | `Couldn't revoke this device. Try again.` |
| Toast — revoked | `{name} was revoked.` |
| Detail — revoked section heading | `This device is revoked` |
| Detail — revoked body, admin | `It can't connect, scan or send results. Once restored, it reconnects on its next hourly attempt, within the hour.` |
| Detail — revoked body, viewer | `It can't connect, scan or send results. Ask your admin to restore it.` |
| Detail — restore button | `Restore device` / pending `Restoring…` |
| Detail — restore error | `Couldn't restore this device. Try again.` |
| Toast — restored | `{name} was restored. It reconnects on its next hourly attempt, within the hour.` |
| Detail — watched network, revoked, none chosen | `No network chosen yet.` |

**Never** say it reconnects "now", "immediately" or "shortly". Button labels are verb + noun
(FOUNDATIONS §Copy rules), so the confirm is `Revoke device`, not the bare `Revoke` the invite
dialog uses.

---

## 5. Data

Consumed by domain name; the field and route names are fixed by `ARCHITECTURE.md` /
`INTEGRATION.md` and the regenerated `frontend/src/types/openapi.d.ts`.

| Need | Where |
| --- | --- |
| **Revoked date** (nullable timestamp) | On the device list item (`AgentSummary`) and the device detail (`AgentDetail`). Present ⇒ Revoked. |
| Connection flag, last report, display name, watched network | Existing `AgentSummary` / `AgentDetail` fields, unchanged. |
| **Revoke** action | Admin-only call on one device; success returns the device (or nothing) — either way the screen re-reads. |
| **Restore** action | Admin-only call on one device; same. |
| Role | `useSession().user.role` (`admin` \| `viewer`), from `GET /users/me`; gated with `AdminOnly`. |

After a successful revoke or restore, invalidate both the device list and this device's detail
query (`queryKeys.agents`).

---

## 6. `data-testid`

All existing ids in 042 §8.5, §9.11 and 043 are **kept**.

| id | Element | Status |
| --- | --- | --- |
| `devices-table-row-{agent_id}` | List row | kept |
| `devices-status-{agent_id}` | List Status cell | **new** |
| `agents-presence` | Detail presence line; now also the focus target after revoke/restore (`tabIndex={-1}`) | kept, changed |
| `device-revoke` | "Revoke this device" section | new |
| `device-revoke-trigger` | `Revoke device` button on the page | new |
| `device-revoke-dialog` | Dialog container (`DialogShell` `testId`) | new |
| `device-revoke-confirm` | Dialog confirm button | new |
| `device-revoke-cancel` | Dialog `Cancel` button | new |
| `device-revoke-error` | Dialog alert line | new |
| `device-revoked` | "This device is revoked" section (both roles) | new |
| `device-revoked-body` | Its sentence | new |
| `device-restore` | `Restore device` button | new |
| `device-restore-error` | Restore alert line | new |

---

## 7. Out of scope

- Showing **why** a non-revoked device is disconnected (replaced, refused, upload refused). Those
  devices read `Offline`, as today — see Q1.
- A persistent "restored, waiting for its next attempt" state after the toast fades — see Q3.
- Revoke or restore from the list row, bulk actions, who revoked, notifications, re-pairing,
  key rotation, delete (TRUTH out of scope).
- Any change to Home, Scans or Network. No scan trigger exists there today, so none needs hiding.
- The recovery guide is documentation, not a screen; no web link to it is designed.

## 8. Open questions for the approval gate

1. ~~TRUTH narrative vs rules.~~ **Resolved:** TRUTH now says the web app shows Revoked vs
   Offline only, and lists the Pi's own park reason as out of scope. A replaced or refused Pi reads
   `Offline`.
2. ~~"Date" vs the house timestamp.~~ **Resolved:** TRUTH now says "when it was revoked (the
   app's standard time display)", so `Timestamp` applies.
3. **After restore, the only reconnect message is a toast** plus the pre-click sentence. With no
   *restored date* field the screen cannot tell "just restored" from "offline". Acceptable for v1?
4. ~~`Change` absent on a revoked device.~~ **Resolved:** ARCHITECTURE D5 and INTEGRATION §1.4
   confirm the save returns `409 device_offline` for a device with no hello.
5. **Vocabulary.** The new copy says *device* (FOUNDATIONS'
   word and the `Remove device` button example) where neighbouring detail copy still says *box*
   (`This box is offline.`). Keep *device* for the new strings?
6. **Drift noted, not fixed:** SCREENS.md §DEVICES says the manual scan trigger moved to Scans, but
   the built app keeps `Scan now` on Device detail (042 §9). This design hides it there.
