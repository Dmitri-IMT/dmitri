# DESIGN — Agents: the scan trigger, the network chooser and the status pill

React web screens. Copy and interaction, not pixels.

**`docs/ui/SCREENS.md` § AGENTS is the source of truth for this screen, and it is already fully
designed.** Its epicenter, its state list, its layouts and — above all — its copy table stand as
written. This document **honours and completes** it: it reproduces the fixed copy verbatim, draws
the states SCREENS.md names but never drew (loading, the terminal rows, the chooser in flight and
refused), and settles the things it left as prose (focus movement, the control cell's anatomy, the
role split on three other screens). §Foundations — two faces, six neutrals, purple accent, light
only, the nine permitted spacing steps, the eleven consistency rules — is inherited and never
re-decided.

Behaviour: [`TRUTH.md`](TRUTH.md). Flow: [`FLOWS.md`](../../docs/ui/FLOWS.md) B4 and the first-run
step of B2. Contract: [`ADR-011`](../../docs/adr/ADR-011-pi-command-channel.md) and
`contracts/openapi/openapi.yaml`. Where this document and `SCREENS.md` disagree, `SCREENS.md` wins
**except** at the two divergences in §11, which are argued there and are the shape that ships.

## Rendered preview — the approvable artefact

**<https://claude.ai/code/artifact/763cd953-6d40-46f9-a64b-b498bc5518c9>**

Fifteen plates at the 1120px frame, drawn with the product's own tokens from
`frontend/src/index.css` and its two real faces, IM Fell English and IBM Plex Mono. The ASCII below
is structural notes and does not constitute an approvable design — it cannot express proportion,
type size or affordance. **Look at the plates, not the boxes.**

**The human performs the visual check and it closes this feature** (`TRUTH.md` business rule 13).
No agent signs off on how this looks. Plate 15 lists the six calls worth a deliberate look; they
are repeated as §13.

Plate numbers below match the section numbers here.

---

## 0. What is new

One screen grows from a single-state explainer into the product's only place a human causes
something to happen, and three blank states elsewhere get the button they were specified to gain.

| Thing | State |
|---|---|
| `/agents` | Twelve designed states where it has one today |
| `EmptyState` | Gains an **action slot** and a **note slot**; neither has an outer margin |
| `StatusPill` | Height matched to the trigger — **ripples to the scan list and scan detail** |
| `Toast` | Four new call sites — the chooser's two refusals and the trigger's two |
| Home, Scans, Hosts blank states | `[Run first scan]` for an admin, one sentence for a viewer; the stand-in Pi sentence retires |
| Polling | The product's first. It exists on this screen and nowhere else |

Nothing here is blocked on a contract. C1, C2 and C12 are resolved and every endpoint is shipped.

---

## 1. Screen flow

```
Home (blank) ──[Run first scan]──┐
Scans (blank) ─[Run first scan]──┼──> /agents
Hosts (blank) ─[Run first scan]──┘
Home ──review item "coverage stale" ──[Check the Pi]──> /agents      (already built)

/agents  on mount / return / reload
    GET /agents ─────────> no agent ........................> BLANK (no action, either role)
                  └──────> agent ─> GET /agents/{agent_id}
                                      target_subnet == null ─> CHOOSER  (admin)
                                                            └─> read-only row (viewer)
                                      active_command_id != null ─> adopt that run, poll it
                                      otherwise ..................> READY

CHOOSER ──[Set this Network]──> PATCH /agents/{agent_id}
              200 ..............> READY, focus on [Scan now]
              409 ..............> toast; chooser stays open; stored choice unchanged
              422 ..............> toast; chooser stays open; agent re-read

READY ──[Scan now]──> POST /agents/{agent_id}/commands
              201 ..............> pill: Queued → Sent to the Pi → Scanning… → Uploading results…
              503 device_offline > toast; re-read the agent; stay READY
              409 device_busy ...> toast; re-read the agent; adopt active_command_id
              422 subnet_not_reported > toast; re-read the agent; back to CHOOSER

polling GET /commands/{command_id} every 5s while non-terminal
              done .............> [View scan] ──> /scans/{scan_id}
                                  invalidate scans, hosts, findings, agents
              failed ...........> reason sentence + [Retry]
              expired ..........> "never picked up" sentence + [Retry]
              (terminal) .......> polling stops

READY ──[Change]──> CHOOSER (with the current network preselected)
```

`/agents` is readable by **both roles**; only the trigger and the chooser are admin. There is no new
route, no route guard and no `RequireAdmin` here — this screen stays reachable by a viewer, which is
why the affordances are omitted inside it rather than the page being refused.

---

## 2. The card, and the one thing that moves — Plate 6

Every admin state after the chooser is the same card with the same three caption lines and a
different **control cell**. That is the whole design, and it is what `TRUTH.md` rule 22 asks for.

```text
+----------------------------------------------------------------+
|  DMITRI-NSPI-01                                        <- IM Fell, title-sm
|  Online · last seen 2 min ago                          <- body-md muted, Timestamp
|                                                        <- step 6
|  Scanning: Ethernet · 192.168.0.0/24     [Change]      <- body-md + quiet button
|                                                        <- step 6
|                              +--------------------+    |
|                              | ▓    Scan now      |    |  <- the control cell
|                              +--------------------+    |
|                                    (empty until terminal) |  <- the status line
+----------------------------------------------------------------+
```

**Anatomy of the control cell.** Bottom-right of the card, right-aligned, two rows:

| Row | Holds |
|---|---|
| Control row | An optional `StatusPill`, then an optional button. Never more than one of each. |
| Status line | The terminal state's words, when there are any. **Empty in every non-terminal state.** |

The cell is present in every admin state and is the **only** part of the card that differs between
them. It is why the card does not change height across a ten-minute run, and why an operator
returning to the tab reads the same three lines they left.

**One owner, two exclusive lower modes.** `AgentCard` owns the card's lower interactive mode. In
**control/status mode**, the lower slot contains `[Scan now]`, `Starting…`, or the followed-command
status and terminal control. In **choosing mode**, the chooser form replaces that entire slot.
The two modes never render together: while the chooser is open, `agents-scan-now` and the complete
`ScanControl` slot — including an old terminal action or a currently followed status — are absent.
If a command is already being followed, its polling continues in data state and the latest status
returns when the chooser closes.

**Where the existing sentence went.** *"Scanning is set up on the Pi itself."* is today the page's
IM Fell `text-title-lg` epicenter. The row and the trigger are now the epicenter, so the sentence
demotes to a closing caption below the card — **verbatim**, at `text-body-md`, keeping its
`agents-note` testid. `TRUTH.md` rule 27 requires it to survive; the method requires it not to
outrank the trigger. Demotion satisfies both.

---

## 3. Loading — Plate 1

```text
|   AGENTS                                                          |
|   The Dmitri box on your network.                       (muted)   |
|   ------------------------------------------------------------   |
|                                                                   |
|   +-------------------------------------------------------+       |
|   |  ██████████████████                                    |      |
|   |  ████████████████████████                              |      |
|   |                                                        |      |
|   |  ██████████████████████████████                        |      |
|   +-------------------------------------------------------+       |
```

The skeleton is the **shape of the row it becomes** — three bars at the identity, presence and
network heights, inside the real card, at the real padding. No control cell: a trigger drawn before
the device is known is a button that does not yet know what it would talk to. The page header
renders immediately; only the card is skeletal.

This is a screen-specific, inert loading card, **not** the shared table-body `LoadingSkeleton`. The
real bordered `bg-card` surface renders at step-6 padding and step-6 inter-group rhythm. It contains
exactly three `aria-hidden="true"` bars: one at title-line height for identity and two at body-line
height for presence and network. The identity/presence pair uses step-2 rhythm, and all three bars
have visibly different widths. There is no button, link, radio, pill or other focusable placeholder.
The shared table skeleton remains unchanged.

First load only — never on the 5s command poll, which must not make the card flicker, and never on a
background agent re-read. The page header and permanent closing note remain real and readable
during loading.

---

## 4. Blank — no device at all — Plate 2

```text
|                     NO PI CONNECTED YET.                          |
|                                                                   |
|        Dmitri scans your network from a small box installed        |
|        on site. Your installer sets it up — once it's online,      |
|        it shows up here and you can run your first scan.           |
|                                                                    |
|        Contact whoever installed Dmitri if you were expecting       |
|        to see one.                                       (muted)   |
|                                                                    |
|                     ~ engraving ornament ~                         |
```

**The one blank state in the product with no action, on purpose.** The admin cannot provision a
device — that is the installer's job — so a call to action here would name something the product
cannot honour. Both roles see this identical screen; there is nothing to gate.

This is the state that requires `EmptyState` to grow a **note slot**: a second muted line after the
body, before the ornament. The same component's **action slot** (§10) is not passed here.

Step 16 above and below the block. Told nothing, an implementer packs it to the top and the calm is
lost.

---

## 5. Needs a network — Plates 3, 4, 5

### 5.1 The chooser — Plate 3

```text
|   +---------------------------------------------------------+     |
|   |  DMITRI-NSPI-01                                          |    |
|   |  Online · last seen 12 s ago                             |    |
|   |  - - - - - - - - - - - - - - - - - - - - - - - - - - -   |    |
|   |  Which network should Dmitri scan?                       |    |
|   |  This box is connected to more than one network. Pick    |    |
|   |  the one you want scanned; usually the office network,   |    |
|   |  not the internet connection.                   (muted)  |    |
|   |                                                          |    |
|   |    (•) Ethernet · 192.168.0.0/24                         |    |
|   |    ( ) Wi-Fi · 10.12.0.0/16  (internet connection)       |    |
|   |                                                          |    |
|   |                          [ ▓ Set this Network ]         |    |
|   +---------------------------------------------------------+     |
```

The device is **online and unscannable** — a designed state, not an error. `[Scan now]` is not drawn
at all; the choice is. The dashed hairline under the identity block is the only rule inside the card
and appears in **this state only**: the chooser is a different kind of thing from the caption lines
above it, and 8px of space cannot say that on its own.

**Options read as words.** `AvailableSubnet` gives `interface`, `cidr` and `is_default_route`. The
label is `<human interface> · <cidr>`, with `(internet connection)` appended when
`is_default_route` is true — that network is almost never the right answer, and the label exists so
a non-technical admin can tell the two apart. Interface mapping: `eth*` / `en*` → **Ethernet**,
`wl*` → **Wi-Fi**, anything else renders the raw interface name. **No free-text field for a network
address exists anywhere on this screen**, in any state.

Reached from `[Change]` the chooser is identical. Opening it begins a new chooser session whose
draft is initialized from the **latest successfully read** `agent.target_subnet`, not the value from
the card's first mount. That target is preselected only if it still appears in the latest
`available_subnets`; otherwise no option is checked and confirm is disabled.

Once open, the operator owns the draft. A background agent read may update the displayed stored
target and option list, but it never silently replaces the current draft. Draft validity is checked
against the latest options on every render: if a refetch removes the selected CIDR, the selection
may remain visible for explanation but confirm is disabled until a currently reported option is
selected. Closing after success destroys the draft; every later opening starts a new session from
the then-current server state.

### 5.2 In flight — Plate 4

The confirm button becomes its own progress copy — `Saving…` — and the radios go inert. This is the
**progress** carve-out of consistency rule 3, not the permission rule: the admin may choose, they
are simply choosing right now. Nothing else in the card changes, so it does not resize under the
cursor.

### 5.3 Refused — Plate 5

```text
|   |                          [ ▓ Set this Network ]         |    |
+----------------------------------------------------------------+
                                                     (toast, bottom right)
                        +----------------------------------------+
                        | Couldn't reach the Pi; nothing changed. |
                        +----------------------------------------+
```

**Both refusals are toasts, and the chooser stays exactly as it was** — open, with the operator's
selection still made and focus retained on `[Set this Network]`. *Decided 2026-08-28 at the visual
review, reversing this document's original inline treatment.* An inline error block sits in the
card as permanent dead space reserved for a message that is almost never there, and it moves the
confirm button down the moment it appears; a toast carries the same sentence without either cost.
It is also what `TRUTH.md` rule 30 asks for — a refused action reports itself as a message naming
what failed, and does not discard what is on screen. The form surviving is what matters, and the
toast leaves it untouched by construction.

The toast is the **only visible** refusal. For announcement without focus theft, the chooser also
retains the identical sentence in a visually hidden node with a stable id, `role="status"`, and
`aria-live="polite"`; `agents-chooser-confirm` references it with `aria-describedby`. Choosing a
different option clears both the stale hidden description and that relationship. This local string
exists only for accessibility announcement and is not a second business-state authority.

The agent is re-read after a refusal so the option list is the Pi's current one. The refetch may
invalidate the draft and disable confirm without closing the form; an invalid draft cannot issue a
second PATCH.

| Refusal | Means | Toast |
|---|---|---|
| `409 device_offline` | The Pi is holding no connection, so it is reporting no networks | "Couldn't reach the Pi; nothing changed." **invented** |
| `422 subnet_not_reported` | The chosen network is not one the Pi currently reports | "The Pi doesn't report that network any more; nothing changed." **invented** |

Both name what failed, both say the stored choice is untouched, and neither carries a code.

### 5.4 A viewer, with no network chosen

No chooser, no `[Change]`. The network line reads *"No network chosen yet. Ask your admin to choose
one."* — the same shape as the blank-state viewer line: state the fact, name the person who can act.

---

## 6. Ready — Plates 6, 7

**Admin, online (plate 6).** `[Scan now]` alone in the control cell. The button is the only purple
on the page after the active nav item.

**No hint under the trigger.** `SCREENS.md` gives it *"A scan usually takes about 10 minutes."*;
**it is removed** (decided 2026-08-28 at the visual review). A fixed duration printed under a button
is a promise the product cannot keep — the run's length depends on the subnet — and it is the wrong
answer to the question the operator actually has once they press, which is *where is it now*. That
question is answered by the pill, and answered better by the progress bar tracked as a follow-up
(§18). The status line is therefore empty until a run reaches a terminal state.

**Admin, offline (plate 7).** *Identical, but for the presence line.* The trigger **stays visible and
enabled** — SCREENS.md open question 1, settled there and not reopened here. `online` is derived
from a socket registry and can be momentarily stale; the server makes exactly one delivery attempt
and never retries, so the operator pressing the button again **is** the only retry the system has.
Hiding it on a flag that may be wrong denies a scan that would have worked. This is not consistency
rule 3, which governs what a *role* may do.

The honest failure is the refusal that follows: a toast reading *"Pi seems to be offline."*, then a
re-read of the device. The card never blanks.

---

## 7. Scanning — Plate 8

```text
|   |  DMITRI-NSPI-01                                          |    |
|   |  Online · last seen 4 s ago                              |    |
|   |  Scanning: Ethernet · 192.168.0.0/24      [Change]       |    |
|   |                                                          |    |
|   |                                    [ Scanning… ]         |    |
```

The pill takes the trigger's place. The status line remains empty while the command is
non-terminal. Four labels walk through the same box:

| `CommandStatus` | Pill | Tone |
|---|---|---|
| `queued` | "Queued" | running |
| `delivered` | "Sent to the Pi" | running |
| `running` | "Scanning…" | running |
| `uploading` | "Uploading results…" | running |

`[Change]` stays available during a run: it edits a stored property of the device, not the run in
flight, and the next scan is the one it affects. Opening it places the card in choosing mode and
temporarily replaces the entire status/control slot; polling continues, and the latest status
returns when the chooser closes. `[Scan now]` is gone — not because a role forbids it but because
there is nothing to start.

**The run survives navigation and reload** because the screen never remembers what it started: every
arrival reads `active_command_id` from the device and follows whatever is there, including a run
this browser never triggered. Polling is `GET /commands/{command_id}` every 5s, and it **stops the
moment a terminal state arrives**.

---

## 8. The three terminal states — Plates 9, 10, 11

### 8.1 Done — Plate 9

```text
|   |                       [ Done ]  [ ▓ View scan ]          |    |
|   |                              Finished just now.          |    |
```

`[View scan]` navigates to `/scans/{scan_id}` from `CommandDetail.scan_id`. It is offered **only at
completion**, though the scan has existed since the command was accepted: sending an operator to an
empty scan is worse than making them wait.

On arrival at `done`, everything the product knows about scans, hosts and findings is invalidated,
so the run log and the inventory are already right when the operator gets there.

### 8.2 Failed — Plate 10

```text
|   |                  [ Scan failed ]  [ ▓  Retry  ]          |    |
|   |   The Pi stopped responding while the scan was running.  |    |
|   |   Check that it's powered on and online, then try again. |    |
```

The Pi **took the command** and it broke — the scan failed, the upload failed, or the box went dark
mid-run. The pill is `failed` tone; the sentence comes from the approved deck in
`frontend/src/lib/scanFailureReasons.ts`, keyed by `CommandDetail.error_code` (§11 divergence 1).

### 8.3 Expired — Plate 11

```text
|   |               [ Not picked up ]  [ ▓  Retry  ]           |    |
|   |   The Pi never picked up the scan. Check that it's       |    |
|   |   powered on and connected to the network.               |    |
```

The Pi **never took the command** — there was no open socket, or the one delivery attempt threw. A
different event, so different words and a different next step: look at the box first, try again
second. **Failed and expired are never given the same words**, which is why the sentence is the
load-bearing part of both plates and the pill is only its label.

Both terminal failures offer the way to try again as **`[Retry]`**, exactly as `SCREENS.md`
specifies. It posts the identical command, but it reads as continuing the run that just failed
rather than starting something unrelated, and it keeps the screen spec authoritative.
*Decided 2026-08-28 at the refine gate, against this document's original proposal.*

---

## 9. Viewer — Plate 12

Sees the card, the identity, the presence line, the network line and any run in progress — reading
the device is available to both roles. **Absent from the DOM**, not disabled: `[Scan now]`, the
hint, `[Change]`, the chooser, `[Retry]`, and the `Users` nav item. A viewer is never informed of an
action they cannot take, and a test of this asserts absence rather than sweeping for `[disabled]`.

**`[View scan]` is the one control a viewer keeps.** When a run reaches `done` the viewer sees the
same pill and the same link, because it navigates to a scan they already have full read access to.
It is a destination, not an action on the device — consistency rule 3 hides what a role *may not
do*, and reading a scan is not that.

The blank (no device) and error states are identical for both roles.

---

## 10. The three blank states get their call to action — Plate 14

`TRUTH.md` rule 26, and the promise `SCREENS.md` recorded in three copy tables: *the `[Run first
scan]` admin CTA and the viewer line return together when this trigger exists.* It exists now.

`EmptyState` gains two optional slots, both rendered inside its own box with the component's
existing step-6 internal rhythm and **no outer margin** — the pages that place it own the space
around it:

| Slot | Holds | Rendered |
|---|---|---|
| `action` | The `[Run first scan]` button | After the body, before the ornament |
| `note` | One muted line | Same position; the two are mutually exclusive in this feature |

| Screen | Admin | Viewer |
|---|---|---|
| Home (`HomeBlank`) | `[Run first scan]` replaces the `home-blank-note` line | "Ask your admin to run the first scan." in that line's place |
| Scans (`scans-blank`) | `[Run first scan]` in the action slot | The same sentence in the note slot |
| Hosts (`hosts-blank`) | `[Run first scan]` in the action slot | The same sentence in the note slot |

All three buttons navigate to `/agents`. The admin's button renders inside `AdminOnly`; the viewer's
line renders on the complementary condition. Neither role ever sees both.

**The stand-in sentence goes.** Spec 039 appended *"Scanning is set up on the Pi itself."* to the
Scans and Hosts blank bodies **explicitly in place of the removed CTA** (039 §8, §12).
The CTA is back, so the stand-in comes out and those two bodies return to their `SCREENS.md` wording
verbatim. On Home the same sentence occupied `home-blank-note`; the CTA takes that slot, per the
issue brief. The sentence keeps its permanent home on `/agents` (§2), which is what
SCREENS.md-039 open question 5 settled it as.

---

## 11. Two deliberate divergences from `SCREENS.md`

> **Withdrawn — the retry after a bad run.** This document originally proposed shipping `[Scan now]`
> in place of `SCREENS.md`'s `[Retry]`, on the grounds that it says what it does and avoids a third
> meaning of *Retry* on one page. **Rejected at the refine gate, 2026-08-28:** `[Retry]` ships as
> specified. It reads as continuing the run that just failed rather than starting an unrelated one,
> and `SCREENS.md` stays authoritative. The `ErrorRetry` overlap is accepted knowingly. Recorded
> here rather than deleted so the argument is not made again.

### Divergence 1 — the failure reason replaces the error code

`SCREENS.md` gives the failed pill *"Scan failed — `<error_code>`"*. **No code reaches the screen.**
The pill reads `Scan failed` and the status line carries the sentence from
`scanFailureReasons.ts` — the deck approved in DMI-75, which names what happened and ends with the
operator's next action. The org admin is non-technical (zero training); `agent_disconnected` teaches
them nothing. The precedent is set and shipped: spec 039 made the same call for the failed scan
page, and this reuses that single source rather than adding a second vocabulary for the same codes.

### Divergence 2 — the terminal pills gain two short labels

`SCREENS.md` writes the done pill as *"View scan"* and the expired pill as *"The Pi never picked up
the scan."* Under the control-cell anatomy (§2) the affordance and the words are different
elements — so `[View scan]` ships **exactly as specified, as the button**, the expired **sentence
ships verbatim on the status line**, and the pills take two short labels beside them: `Done` and
`Not picked up`. Both are invented and flagged in §12. A pill is a state badge; a sentence in a
badge wraps to three lines and stops reading as one.

---

## 12. Copy

`SCREENS.md` § AGENTS is reproduced verbatim below wherever it exists. **Invented** marks copy this
document wrote because SCREENS.md has none — written in the same voice: name the thing, say what
happened, give the next action, no error codes.

### The screen

| Element | Copy | Source |
|---|---|---|
| Page title | "Agents" | verbatim |
| Subtitle | "The Dmitri box on your network." | verbatim |
| Row — online | "Online · last seen 2 min ago" | verbatim |
| Row — offline | "Offline · last seen Tuesday 14:10" | verbatim |
| Row — network | "Scanning: Ethernet · 192.168.0.0/24" · [Change] | verbatim |
| Row — no network, viewer | "No network chosen yet. Ask your admin to choose one." | **invented** |
| Trigger | "Scan now" | verbatim |
| ~~Hint under trigger~~ | ~~"A scan usually takes about 10 minutes."~~ | **removed** 2026-08-28 (§6) — SCREENS.md amendment |
| Closing note | "Scanning is set up on the Pi itself." | verbatim (built; `TRUTH.md` rule 27) |
| Closing note — body | "The Dmitri box is installed and configured on site. It scans the network chosen above and uploads what it finds here." | adapted from the built page (was "the network it is connected to") |
| Closing note — links | "Every scan it runs appears under Scans, and every device it finds appears under Hosts." | verbatim (built) |

### The chooser

| Element | Copy | Source |
|---|---|---|
| Heading | "Which network should Dmitri scan?" | verbatim |
| Body | "This box is connected to more than one network. Pick the one you want scanned; usually the office network, not the internet connection." | verbatim **but for the em dash → semicolon**, decided 2026-08-28 — SCREENS.md amendment |
| Options | "Ethernet · 192.168.0.0/24" / "Wi-Fi · 10.12.0.0/16 (internet connection)" | verbatim |
| Confirm | "Set this Network" | verbatim |
| Confirm — in flight | "Saving…" | **invented** |
| Refused — `409 device_offline` | "Couldn't reach the Pi; nothing changed." | **invented**; approved 2026-08-29 |
| Refused — `422 subnet_not_reported` | "The Pi doesn't report that network any more; nothing changed." | **invented**; approved 2026-08-29 |

### The pill and its status line

| State | Pill | Status line | Source |
|---|---|---|---|
| `queued` | "Queued" | empty | verbatim pill; hint removed |
| `delivered` | "Sent to the Pi" | empty | verbatim pill; hint removed |
| `running` | "Scanning…" | empty | verbatim pill; hint removed |
| `uploading` | "Uploading results…" | empty | verbatim pill; hint removed |
| `done` | "Done" | "Finished just now." (`Timestamp` on `completed_at`) | **invented**; the `[View scan]` button is verbatim |
| `failed` | "Scan failed" | `scanFailureReason(error_code)` | pill verbatim less the code; sentence from the DMI-75 deck (§11 divergence 1) |
| `expired` | "Not picked up" | "The Pi never picked up the scan. Check that it's powered on and connected to the network." | pill **invented**; first sentence verbatim, second **invented** (`TRUTH.md` rule 16 — expired points at the box) |

### Toasts, blank and error

| Element | Copy | Source |
|---|---|---|
| Toast — `503 device_offline` | "Pi seems to be offline." | verbatim |
| Toast — `409 device_busy` | "That Pi is already scanning. Showing the scan in progress." | verbatim — this adopts SCREENS.md's proposed wording and closes FLOWS open decision #2 |
| Toast — `422 subnet_not_reported` | "The Pi doesn't report that network any more. Pick the network to scan again." | **invented** |
| Blank — heading | "No Pi connected yet." | verbatim |
| Blank — body | "Dmitri scans your network from a small box installed on site. Your installer sets it up — once it's online, it shows up here and you can run your first scan." | verbatim |
| Blank — note | "Contact whoever installed Dmitri if you were expecting to see one." | verbatim |
| Error | "Couldn't load the agents." · [Retry] | verbatim |

### The three blank states elsewhere

| Element | Copy | Source |
|---|---|---|
| Home blank — heading / body | unchanged from the built screen | built |
| Home blank — CTA (admin) | "Run first scan" | verbatim (§ HOME) |
| Home blank — viewer line | "Ask your admin to run the first scan." | verbatim (§ HOME) |
| Scans blank — body | "Dmitri scans your network for devices and known vulnerabilities. Every scan you run shows up here." | verbatim (§ SCAN LIST — the 039 stand-in sentence is removed) |
| Scans blank — CTA / viewer line | as Home | verbatim |
| Hosts blank — body | "Once a scan runs, every device Dmitri finds on your network shows up here." | verbatim (§ HOST INVENTORY — stand-in removed) |
| Hosts blank — CTA / viewer line | as Home | verbatim |

Every time on this screen goes through `Timestamp`: relative inside 7 days, absolute beyond, exact
value always in `title`.

---

## 13. Layout, spacing and rhythm

The screen holds `--container-frame`, like the bar above it. `--container-form` appears nowhere.

**Vertical rhythm — three steps, and no fourth:**

| Step | Used between |
|---|---|
| **2** — intra-group | The identity name ↔ presence line; radio ↔ radio; the control row ↔ its status line |
| **6** — inter-group | The card's internal padding, and between the card's three groups (identity, network, control cell); chooser heading ↔ body ↔ radios ↔ confirm |
| **12** — inter-section | `PageHeader` ↔ card, card ↔ closing note, closing note ↔ ornament |

**Step 16 around the epicenter on the near-empty states**: the blank (no device) block and the error
block each get step 16 above and below, as `EmptyState` and `ErrorRetry` already do.

**Space groups; it does not decorate.** The card is the only box on the page and the dashed rule
inside it appears in the chooser state only (§5.1). Nothing else on this screen is separated by a
line — the closing note is set apart by step 12 of paper, not by a rule.

**The pill matches the trigger's height.** `StatusPill` is sized to the same height as the
`Scan now` button — same vertical padding, same type size — so the control cell keeps one height
whether it holds a button, a pill, or a pill and a button. It is wider than the button whenever its
label is longer (*"Uploading results…"*), and that is fine: the cell is right-aligned, so the pill
grows leftward into the card's empty middle and nothing else moves. *Decided 2026-08-28 at the
visual review.* This is the one change to `StatusPill`'s appearance; its tones are untouched, and
the taller pill applies at every call site, including the scan list and scan detail.

**Normative authored type scale.** These three ordinary read lines use exactly the following
tokens; compact-body, caption, title and raw Tailwind type utilities fail this contract:

| Element | Token | Notes |
|---|---|---|
| `agents-presence` | `text-body-md` | Muted device value, not compact helper copy |
| `agents-network` | `text-body-md` | Both chosen and viewer no-target forms; muted colour remains |
| `agents-note` | `text-body-md` | Permanent Pi sentence, demoted from title treatment |

**Components carry no outer margin.** `StatusPill`, `EmptyState` (including its new slots),
`ErrorRetry`, the screen-specific loading card and `Toast` all render flush to their own boxes;
every gap around them is set by the page, in one place.

Horizontal padding inside the card is step 6 and never less. Prose is held to about 65 characters
however wide the frame gets.

---

## 14. Keyboard and focus

Tab order is DOM order. Focus starts on the document body at route change. Programmatic movement is
keyed to an accepted operator action whose control is replaced, never merely to the boolean presence
of a followed command.

| Moment | Behaviour |
|---|---|
| Ready (admin) | Top bar → `[Change]` → `[Scan now]` → the closing note's Scans and Hosts links |
| Terminal failure (admin) | Top bar → `[Change]` → `[Retry]` → the closing note's links |
| Chooser | Top bar → the radio group (**one** tab stop) → `[Set this Network]` → the note's links |
| Inside the radio group | Native radios: **↑ ↓ ← →** move and select, and the group is one stop. No roving tabindex is hand-rolled |
| Enter inside the chooser | Submits — it is a real `<form>` with a real submit button |
| While saving | Radios and confirm are inert and out of the tab order (progress carve-out) |
| **After a successful choice** | **Focus moves to `[Scan now]`** — the operator's next action, and the button they were standing on has unmounted |
| After a refused choice | Focus **stays** on `[Set this Network]`. The hidden refusal description is a polite status region referenced by `aria-describedby`; the toast is the only visible copy and is not focused |
| **After successful `[Scan now]`** | The accepted command replaces the trigger and focus moves once to `agents-command-status`, including while its first GET still reads `Starting…` |
| **After successful terminal `[Retry]`** | The replacement command takes ownership and focus moves once to `agents-command-status`, even though the transition is old command id → new command id |
| **After user-triggered busy adoption** | If the refusal re-read yields an active command id, focus moves once to `agents-command-status`, because the acted-on control is replaced by that status |
| Passive adoption | Mount, reload, focus refetch and background adoption never move focus |
| Trigger refusal without a followed id | Focus stays on the still-mounted action control |
| Poll advance or terminal arrival | No focus movement. The status region announces lifecycle changes; a terminal control mounts without stealing focus |
| Toasts | Not focused. Polite live region with a `Dismiss` control, per the built `Toast` |
| Error state | `[Retry]` is the only stop on the page below the bar |

Whenever a command id is followed and control/status mode is visible,
`agents-command-status` is the single stable region root from the pending first read through the
terminal state. It has `role="status"`, `aria-live="polite"`, and `tabindex="-1"`; it reads
`Starting…` until command data exists, stays mounted as polling advances, and is not a sequential
Tab stop. `agents-pill` appears only once command data exists.

**Closing-note links.** `agents-scans-link` and `agents-hosts-link` use the shared `Button` primitive
with `asChild` and `variant="link"`, in document order after the card/status action, with no custom
click handler. At rest each has its accessible name, correct `/scans` or `/hosts` href, primary
link colour, and inline `text-body-md` typography. Hover shows a pointer cursor and underline;
focus-visible shows both the visible ring and underline without removing the outline; active uses
the shared pressed downward nudge. Disabled does not apply and no disabled state is authored.

---

## 15. Data — contract names only

| Call | Feeds |
|---|---|
| `GET /api/v1/agents` → `AgentListResponse` | Discovery of `agent_id`; an empty `data` array is the blank state |
| `GET /api/v1/agents/{agent_id}` → `AgentDetail` | The row, the chooser and run adoption. Read on mount, and re-read after every refusal |
| `PATCH /api/v1/agents/{agent_id}` → `AgentDetail` | Body `{ target_subnet }`. The response is the full detail, so no refetch follows a success |
| `POST /api/v1/agents/{agent_id}/commands` → `CommandSummary` | Body `{ scan_mode: "quick", subnet: <target_subnet> }` — **both supplied by the system, neither typed** |
| `GET /api/v1/commands/{command_id}` → `CommandDetail` | Polled every 5s while non-terminal |

Fields consumed:

- `AgentSummary`: `agent_id` only. The list exists to find the one agent.
- `AgentDetail`: `display_name`, `online`, `last_seen_at`, `available_subnets`, `target_subnet`,
  `active_command_id`.
- `AvailableSubnet`: `interface`, `cidr`, `is_default_route`.
- `CommandSummary`: `command_id`. Its `status` is not rendered — the poll owns the lifecycle from
  the first tick.
- `CommandDetail`: `status`, `error_code`, `scan_id`, `completed_at`.
- `CommandStatus`: `queued | delivered | running | uploading | done | failed | expired` — **all seven
  rendered**.
- `ScanErrorCode` on `error_code` keys the existing `SCAN_FAILURE_REASONS` deck.

Refusal codes are pinned in the contract and switched on by code, never displayed: `503`/`409`
`device_offline`, `409 device_busy`, `422 subnet_not_reported`.

**Invalidated on `done`:** the scans, hosts, findings and agents queries. That is the cache shape's
first and only invalidator, and it is why the run log holds the new scan without a reload.

---

## 16. `data-testid`

Kebab-case, `agents-` prefixed, matching `agents-page` and `agents-note` as built.

**The page**

| Value | On |
|---|---|
| `agents-page` | the route container (existing) |
| `agents-loading` | the skeleton card |
| `agents-blank` · `agents-blank-note` | the no-device `EmptyState` and its note line |
| `agents-error` · `agents-error-retry` | the page-level failure and its button |
| `agents-note` · `agents-scans-link` · `agents-hosts-link` | the closing note (existing) |

**The card**

| Value | On |
|---|---|
| `agents-card` | the card container |
| `agents-identity` | the identity group wrapping `agents-name` and `agents-presence` |
| `agents-name` · `agents-presence` | identity lines |
| `agents-network` | the network line, in every role and state |
| `agents-network-change` | `[Change]` — **absent for a viewer** |

**The chooser**

| Value | On |
|---|---|
| `agents-chooser` | the form — **absent for a viewer** |
| `agents-chooser-option-{interface}` | one radio, e.g. `agents-chooser-option-eth0` |
| `agents-chooser-confirm` | `[Set this Network]` |
| `toast` | the chooser's two refusals, and the trigger's — one shared component |

**The trigger and the run**

| Value | On |
|---|---|
| `agents-scan-now` | `[Scan now]` in the ready state — **absent for a viewer** |
| `agents-retry` | `[Retry]` in the failed and expired states — **absent for a viewer** |
| `agents-pill` | the `StatusPill`, all seven states |
| `agents-command-status` | the one stable `role="status"`, `aria-live="polite"`, `tabindex="-1"` region from `Starting…` through terminal state |
| `agents-view-scan` | `[View scan]`, done only |
| `toast` | the built `Toast` (existing) |

**The three blank states elsewhere**

| Value | On |
|---|---|
| `first-scan-cta` | the admin button, on all three — **one shared id, one shared component** |
| `first-scan-note` | the viewer line, on all three |
| `scans-blank` · `hosts-blank` | existing containers, unchanged |
| `home-blank-note` | **retired** — the sentence it held is removed (`TRUTH.md` rule 28) |

`scans-blank` and `hosts-blank` keep the `${testId}-blank` shape `ListSurface` already produces, so
no existing assertion moves. **The CTA and the note take bare, shared ids rather than
`home-blank-cta` / `scans-blank-cta` / `hosts-blank-cta`:** one component renders in all three
places, so three ids for one thing would make a single component look like three, and every suite
would assert a different name for the same node. This is the shared-component carve-out to the
screen-prefix rule (`ARCHITECTURE.md` §11.4).

### 16.1 Normative presentation and interaction acceptance matrix

Focused frontend tests prove every row below in addition to the existing lifecycle, role-omission,
refusal and cache-invalidation behavior. Pseudo-class assertions may inspect the shared primitive's
rendered class contract because jsdom cannot visually activate those states.

| Contract | Given / action | Required assertion |
|---|---|---|
| Latest target owns opening | Closed chooser; server target changes A→B | Click Change; B checked, A unchecked |
| Missing latest target | Closed chooser; latest target absent from latest options | Open; no radio checked and confirm disabled |
| Draft is session-owned | Open chooser; operator selects C; background read changes stored target | C remains selected while open |
| Refetch revalidates draft | Selected C disappears from refreshed options | Confirm disabled; another activation causes no PATCH |
| Modes are exclusive | Chooser opens from first run, Change, or stale-trigger refusal | Chooser present; `agents-scan-now` and the complete old command-control slot absent |
| Refusal is perceivable | PATCH 409 and 422 | Toast visible; confirm focused; its resolvable `aria-describedby` target has identical copy, `role=status`, and `aria-live=polite` |
| Scan-now focus | Scan now accepts an id; first GET pending | `agents-command-status` reads `Starting…`, has focus, `role=status`, `aria-live=polite`, and `tabindex=-1` |
| Retry focus | Failed and expired old ids; Retry accepts a new id | New id queried; status region focused although a command was already followed |
| Busy-adoption focus | User action gets 409; detail returns active id | Adopted id queried and status region focused |
| Passive adoption | Page mounts with active id | Status renders without programmatically displacing focus |
| Stable status region | Starting resolves to queued and poll advances | Same `agents-command-status` remains and focus is not moved again |
| Body scale | Ready admin and viewer/no-target render | Presence, network and permanent note each contain `text-body-md` and not `text-body-sm` |
| Loading geometry | Initial list/detail read pending | Bordered `agents-loading`; exactly three `aria-hidden` bars, one title-height and two body-height; no interactive descendant |
| Identity contract | Ready state | `agents-identity` wraps `agents-name` and `agents-presence` |
| Closing-link states | Permanent note renders | Named Scans/Hosts links have correct hrefs and the shared rest, hover, focus-visible and active class contract |
| Test-id authority | Every state above | Only the names in this section and the approved tables above identify these screen elements; no aliases |

---

## 17. Out of scope — deliberate, v1

- **No device pairing, provisioning or key handling.** The screen never offers to add a device.
- **No scan-mode picker, no scheduling, no recurring scans, no cancel.** The product asks for the
  quick mode and offers no way to change it or stop a run.
- **No live connection in the browser.** The product asks every 5s; it is never pushed to.
- **No multi-device management.** One card. No grouping, renaming or per-device settings.
- **No history of past commands.** This screen shows the current run; the run log is the history.
- **No polling anywhere else.** Scan detail keeps its manual `Check again`.
- **No rework of the read surfaces** beyond the call to action their blank states were specified to
  gain.
- **No progress percentage, no elapsed timer, no step list.** A fabricated percentage on a run the
  server reports as four coarse states would be a lie.
- **No confirmation dialog before scanning.** The scan changes nothing on the network.
- **No dark-theme variants.**

---

## 18. Open questions

Nothing here is blocked on a missing API contract. Every endpoint is shipped, and C1, C2 and C12 are
resolved.

**For the approval gate — the six calls on plate 15:**

1. **The trigger stays live while the Pi reads offline.** Settled in `SCREENS.md` and not reopened;
   confirm at the visual gate that the toast is a strong enough answer.
2. **The control cell is the only moving part.** Confirm nothing important is lost by refusing to
   grow the card when a run fails, and that the two-line failure sentence reads well at the card's
   width.
3. ~~`[Scan now]` as the retry~~ — **closed 2026-08-28: `[Retry]` ships, as `SCREENS.md` specifies.**
4. **The failure reason replaces the error code** (§11 divergence 1). Confirm no code needs to reach the screen
   for support to work — if it does, the place for it is the scan detail page, not the pill.
5. **"Scanning is set up on the Pi itself." demoted to a caption** (§2). Confirm it still reads as
   true beside a button that starts a scan.
6. **Interface labels** — `eth*`/`en*` → Ethernet, `wl*` → Wi-Fi, anything else raw (§5.1). Confirm
   the raw fallback is acceptable on an unfamiliar box.

**Settled at the visual review, 2026-08-28** — these are decided, not open:

- **The chooser's refusals are toasts**, not inline blocks (§5.3).
- **The ten-minute hint is removed** from every non-terminal state (§6). The status line is empty
  until a run ends.
- **The pill matches the trigger's height** (§13) — which changes `StatusPill` for the scan list and
  scan detail too.
- **The chooser body takes a semicolon**, not an em dash (§12) — a `SCREENS.md` copy amendment.
- **`[Retry]` stands** on the terminal states.

**Settled at the structural re-evaluation approval, 2026-08-29:**

- **The chooser exclusively owns the lower card mode while open**, even during a followed command;
  polling continues and the latest status returns on close.
- **Chooser refusals use the short pair in §§5.3 and 12** for both the visible toast and the
  identical hidden polite description.

**Follow-up issues to file — deliberately not built here:**

1. **A progress bar showing the scan's current stage.** Requested at the review as the better answer
   to *where is it now* than either the removed hint or the pill alone. It is a frontend-only change
   if it reads the existing lifecycle states, and a larger one if it wants real progress from the Pi.
2. **A `Stop scan` control (red) while a run is in flight.** Out of scope for DMI-89 by decision:
   scan cancellation does not exist anywhere in the system yet. It needs a cancel frame on the Pi, a
   new frame type and terminal state in `ADR-011`, a backend endpoint and state-machine edge, and a
   contract change — before the button is worth drawing. Confirmed at the review as a new issue.

**Recorded as closed by this document:**

- **FLOWS.md B4 open decision #2 — the `409 device_busy` copy.** Adopted as SCREENS.md proposed it:
  *"That Pi is already scanning. Showing the scan in progress."* It is not an error; the operator's
  intent is already being satisfied.

## Related specs

- Behaviour: [`TRUTH.md`](TRUTH.md) · Implementation: `ARCHITECTURE.md`
