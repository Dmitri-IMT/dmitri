# TRUTH — Agents screen, the scan trigger, and the status pill

Domain language and verifiable behaviour only. No file paths, no endpoints, no code.

Issue: **DMI-89**. Screen spec: `docs/ui/SCREENS.md` § AGENTS, plus the blank-state rows of
§§ HOME, SCAN LIST, HOST INVENTORY and § Foundations — the source of truth for all copy and
layout. Flow: `docs/ui/FLOWS.md` B4, and the first-run step of B2. Contract:
`docs/adr/ADR-011-pi-command-channel.md`. Roadmap: `docs/roadmap/FRONTEND.md` milestone 6.

## Narrative

Everything the product shows today arrived on its own. A scan happened somewhere, results were
uploaded, and the screens read them. This is the one place a human causes a scan to happen, and it
is the September demo: the Control scenario is exactly this button working end to end.

It carries the two hardest pieces of interaction in the MVP. The first is choosing the target
network. The scanning device is deliberately dual-homed — wired onto the network it is meant to
scan, wireless for internet so it can enrich findings while it works — so it sees two networks and
has no basis for guessing which one is the target. Scanning the wrong one would be useless and
hostile. A human must choose, once, in plain language, never by typing a network address.

The second is telling the truth for ten minutes. A scan takes about that long, and the operator
will navigate away, come back, and reload during it. The state of the run lives on the device and
the server, not in the screen, so the screen must ask what is happening rather than remember what
it started. It must also be able to show a run it did not start, because the device may already be
scanning when the operator arrives.

This feature also closes three things the read surfaces deliberately left open. Those screens have
empty states that explain and offer nothing, because the action that would fill them did not
exist. Nothing in the product refreshes itself. And the query cache has a shape designed for
invalidation but nothing that ever invalidates it, because the only event that should is a scan
completing — which happens here.

The backend is complete. Every endpoint this screen needs is shipped and unblocked.

## Definitions

| Term | Meaning |
|------|---------|
| **Agent** | The scanning device installed on site. The MVP has exactly one; it is discovered rather than configured. |
| **Online** | The device currently holds an open connection to the server. It is derived from that connection and may be briefly stale. |
| **Available networks** | The networks the device reports it can currently see, each with the interface it sits on, its address range, and whether it carries the internet route. Reported by the device, never stored. |
| **Target network** | The one available network a human has chosen for scanning. It is a property of the device, not a preference of the person — one box, pointed at one network, the same for every admin. |
| **Command** | One request for the device to run one scan. It has a lifecycle and, once results arrive, a scan. |
| **Active command** | A command belonging to the device that has not reached a terminal state. The device has at most one at a time. |
| **Lifecycle** | The seven states a command passes through or ends in: queued, delivered, running, uploading, done, failed, expired. |
| **Expired** | The device **never took the command** — there was no open connection, or the single delivery attempt failed. The operator's next step is to check the device. |
| **Failed** | The device **took the command** and it broke — the scan failed, the upload failed, or the device went dark mid-run. The operator's next step is to try again. |
| **Scan mode** | How thorough a scan is. The product has several and surfaces none; it always asks for the quick one. |

## Business rules

**Roles**

1. Reading the device — its name, whether it is online, when it was last seen, its target network,
   and any run in progress — is available to **both** roles.
2. Triggering a scan and choosing the target network are **admin only**, and are **omitted from
   the page entirely** for a viewer rather than shown unavailable. A viewer is never informed of
   an action they cannot take.
3. Role governs permission, not progress. An action an admin may take but cannot take *yet* is a
   different case and is not governed by rule 2.

**Choosing the target network**

4. A device with no target network is **online but unscannable**. This is a correct, designed
   state, not an error, and the screen says so in words rather than presenting a broken trigger.
5. The choice is made from the networks the device is currently reporting, presented as human
   labels naming the interface. The operator never types a network address, anywhere, ever.
6. The network carrying the internet route is labelled as such. It is almost never the right
   answer, and the labelling exists so a non-technical admin can tell the two apart.
7. A chosen network is persisted on the device and survives reloads and other admins.
8. An admin may change an already-chosen network.
9. Choosing may be refused: the device may be reporting nothing, or the chosen network may no
   longer be one it reports. Each refusal is stated plainly and leaves the previous choice intact.

**Triggering a scan**

10. The trigger is available once a target network is chosen. The operator supplies nothing: the
    product asks for the quick mode and sends the stored target network on their behalf.
11. Scan thoroughness is **not** offered as a choice.
12. The trigger **remains available while the device reads as offline**. Online is derived from a
    connection that can be momentarily stale, and the server makes exactly one delivery attempt
    with no retry — so the operator pressing the button again is the only retry the system has.
    Hiding it on a flag that may be wrong denies a scan that would have worked; the honest failure
    is the refusal that follows.
13. A trigger refused because the device is unreachable tells the operator the device seems to be
    offline, and re-reads the device's state.
14. A trigger refused because the device is **already scanning** does not read as an error. The
    product adopts the run already in progress and shows it, because the operator's intent —
    "show me a scan of this network" — is already being satisfied.
15. A trigger refused because the target network is no longer one the device reports states that
    the network is no longer available and returns the operator to choosing one.

**Reporting the run**

16. All seven lifecycle states are rendered. Each terminal state is given words matching what the
    operator should do next; expired and failed are **never** given the same words, because they
    call for different actions.
17. While a run is not in a terminal state, the product asks the server for its state on a fixed
    short interval. It stops asking the moment the run reaches a terminal state.
18. On arriving at the screen — first visit, return, or reload — the product reads whether the
    device has an active command and, if so, shows and follows that run. The pill therefore
    survives navigation and reload, and can show a run this screen never started.
19. A completed run offers a way to open the scan it produced. That way is offered **only** on
    completion, even though the scan exists from the moment the command is accepted: sending an
    operator to an empty scan is worse than making them wait.
20. A failed or expired run offers a way to try again.
21. When a run completes, everything the product knows about scans, hosts and findings is treated
    as stale, so those screens show the new result without the operator refreshing anything.
22. The run's state is the only thing on the row that changes. The rest of the row stays readable
    and still.
23. A run being followed is **held until the next one is started**, whoever started it. Once the
    product is showing a run it does not stop showing it because the server stopped calling it
    active — a run reaching its end is the moment the operator most needs to see it, and rules 19
    and 20 are what they need it for. Holding a followed run does not allow an unchanged cached
    `active_command_id` from that run to overwrite a newer command accepted in the same screen
    session.
24. A momentary failure to re-read the device does **not** discard a run in progress. The operator
    who starts a scan, looks at something else and comes back is the ordinary case, not the edge
    one; losing their run to one failed background read would break the promise rule 18 makes.
    Only a device that has never loaded produces a page-level error.

**When there is no device**

25. An installation with no device shows a blank state that **explains and offers no action**. The
    admin cannot provision a device themselves — that is the installer's job — so a call to action
    here would name something the product cannot honor. This is the one blank state in the product
    with no action, deliberately.

**The screens that were waiting on this**

26. The empty states of the home screen, the run log and the inventory gain a call to action that
    takes an admin to the device, now that there is something there to do. A viewer sees a line
    directing them to their admin instead — omitted, not disabled, per rule 2.
27. The device destination keeps its existing statement that scanning is configured on the device.
    That sentence was written to survive the trigger's arrival; the screen grows around it rather
    than replacing it.
28. **On the other three screens that carried it, the same statement retires.** It stood in for the
    call to action that did not exist yet. Beside a button that starts a scan it says the opposite
    of what the button does, so it goes when the button arrives. The guarantee in rule 27 is about
    the device's own destination, not about every screen that once pointed at it.

**Everywhere**

29. Three states, no exceptions: a designed regular state, a designed blank state, and a designed
    error state with a retry.
30. A refused action reports itself as a message naming what failed, not as a page-level error
    that discards what is on screen.
31. Times are relative within a week and absolute beyond it, with the exact value always
    available.

## User stories

1. As an admin on first run, I want to pick which of the device's networks to scan, once, in words
   I understand, so that I never have to know what a network address is.
2. As an admin, I want to press one button and watch the scan progress to done, so that I know it
   is working without going to look at the device.
3. As an admin who walked away mid-scan, I want the screen to still be right when I come back, so
   that I can trust what it tells me.
4. As an admin who arrives while the device is already scanning, I want to see that run rather than
   be told I cannot start one, so that the product answers what I actually wanted.
5. As an admin whose scan failed, I want to know whether the device took the job or never got it,
   so that I know whether to try again or go check the box.
6. As an admin on an empty product, I want the blank screens to lead me to the first scan, so that
   I am not left guessing what to do first.
7. As a viewer, I want to see whether the device is online and what it scans, without being shown
   buttons I cannot press.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Unscannable until chosen | An online device with no target network | The screen renders for an admin | The device reads as online, the trigger is not offered, and the screen explains that a network must be chosen first |
| Choosing enables the trigger | An online device with no target network | The admin chooses one of the reported networks | The choice is persisted, the screen shows it as the scanned network, and the trigger becomes available |
| Networks read as words | A device reporting two networks, one carrying the internet route | The chooser renders | Each option names its interface and range, the internet-carrying one is labelled as such, and no free-text field for a network address exists anywhere on the screen |
| Choice can be changed | A device with a target network already chosen | The admin changes it | The new choice is persisted and shown |
| Choice refused | A device that no longer reports the chosen network | The admin submits that choice | The refusal is stated plainly and the previously stored choice is unchanged |
| Latest target starts a chooser session | A device target was A and a later agent read reports B | The admin opens Change after that read | B is preselected; the stale A value is not |
| Refetch revalidates a chooser draft | A selected chooser CIDR is removed from the newly reported networks | The agent read completes while the chooser remains open | The draft is not submitted again; confirm is disabled until a currently reported network is selected |
| Trigger sends nothing typed | An admin-ready device | The admin triggers a scan | The request carries the quick mode and the stored target network, neither of which the operator supplied |
| Pill walks the lifecycle | A triggered scan | The run's state advances on the server | The pill shows each state in turn with its own words, without the operator acting |
| Terminal states stop the asking | A triggered scan | The run reaches a terminal state | The product stops asking the server for its state |
| Run survives navigation | A scan in progress, started on this screen | The operator navigates away and returns, or reloads | The pill shows the correct current state, read from the device's active run |
| Adopting a run never started here | A device already scanning, and an operator who did not start it | The screen is opened | The run in progress is shown |
| An adopted run reaches its end | A run in progress that this operator did not start, being watched to completion | It completes, and the device stops calling it active | The completed state stays on screen and the way into the scan is offered — the run is not dropped at the moment it finishes |
| A momentary read failure keeps the run | A run in progress | One background re-read of the device fails | The run stays on screen and no page-level error replaces it; the next successful read resolves it silently |
| Unreachable device | An offline device | The admin triggers a scan | The screen says the device seems to be offline and the device's state is re-read |
| Trigger stays put when offline | A device reading as offline | The screen renders for an admin | The trigger is still offered |
| Already scanning | A device with a run already in progress | The admin triggers a scan | No error is presented; the run already in progress is adopted and shown |
| Stale network refused | A stored target network the device no longer reports | The admin triggers a scan | The screen says the network is no longer available and offers the choice again |
| Completion opens the scan | A run that completes | The pill reaches completion | A way to open the produced scan is offered, and it was not offered at any earlier state |
| Completion refreshes the product | A run that completes while the run log holds older results | The operator opens the run log | The new scan is present without the operator refreshing anything |
| Expired is not failed | A run the device never took, and a run the device took and broke | Each is rendered | Each carries its own words, and the two are not interchangeable |
| Retry after a bad run | A failed or expired run | The screen renders | A way to try again is offered |
| Retry owns its replacement run | A followed failed or expired command and agent cache that still names it | Retry accepts a new command | The new command is followed; unchanged cached old state cannot restore the prior command |
| Retry focus follows the action | Focus is on Retry for a terminal command | Retry accepts a replacement command | Focus moves to the status region for that replacement command |
| Viewer sees state, not actions | A signed-in viewer | The screen renders | The device, its state and its network are shown; no trigger and no chooser exist on the page, and the admin-only navigation destination is likewise absent |
| No device at all | An installation with no device | The screen renders | It explains that a device is installed on site by an installer, and offers no action to either role |
| Read failure | The device cannot be read | The screen renders | Plain copy names what could not be loaded and offers a retry |
| Blank screens lead to the scan | An installation where no scan has ever run, signed in as admin | The home screen, the run log and the inventory render | Each offers a call to action leading to the device |
| Blank screens for a viewer | The same installation, signed in as a viewer | Those screens render | Each directs them to their admin, and no call to action is present |
| Existing sentence survives | The device destination | It renders | Its existing statement that scanning is configured on the device is still present |

## Out of scope (v1)

- **No device pairing, provisioning, or key handling.** Installing and enrolling a device is the
  installer's job for September. The screen never offers to add one.
- **No scan-mode picker**, no scheduling, no recurring scans, and no way to cancel a running scan.
- **No live connection in the browser.** The product asks repeatedly; it is not pushed to. The
  device's live channel is between the device and the server only.
- **No multi-device management** beyond a list that happens to contain one. No grouping, no
  per-device settings, no naming.
- **No history of past commands.** The screen shows the current run, not a log of runs — the run
  log already exists for that.
- **No self-refreshing anywhere else.** The run log and scan detail keep their static reads and
  their manual re-check. Polling belongs on the screen where someone is watching a scan they just
  started.
- **No rework of the read surfaces** beyond adding the call to action their empty states were
  specified to gain.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`

## Docs drift (2026-08-29 docs-sync)

* **Patched in this run:** `.claude/docs/frontend/*` (full OKF update); `docs/roadmap/FRONTEND.md`,
  `docs/roadmap/README.md`, `docs/ui/SCREENS.md` (factual DMI-89 shipped items), `docs/ui/FLOWS.md`
  (409 toast copy settled).
* **Resolved 2026-08-29:** Home blank body aligned to `docs/ui/SCREENS.md` (shorter copy in
  `HomeBlank.tsx`; spec 020 `DESIGN.md` updated).
* **Resolved 2026-08-29:** Home Pi-status footer built (`HomeFooter` + `useHomeReview` agent read);
  `FRONTEND.md` stale C1/C2 blockers corrected; `ADR-008` §Papéis amended to `GET /users/me`.
* **Root scripts:** no change — no new deps, env vars, entrypoints or lint gates.
