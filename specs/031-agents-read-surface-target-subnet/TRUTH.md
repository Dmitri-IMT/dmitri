# TRUTH — Agent read surface and the Pi's target network (DMI-78, contract asks C1 + C2)

## Narrative

Dmitri's whole point is that an operator presses one button in the browser and a Raspberry Pi
scans their network. Today nobody can press it, for two reasons.

The first is that **the web app cannot find the Pi.** An agent can be read one at a time, by its
identifier — but that identifier is the one minted at provisioning and stamped into the device,
and the browser has never been told it. There is no way to ask "which scanners does my
organisation have?" So the agents screen has no row to render, and the Pi status line on the home
screen was left unbuilt rather than invented from a fabricated identifier.

The second is that **nobody can say which network to scan.** Triggering a scan requires naming a
network in CIDR notation. The person who owns this product is a non-technical org admin who does
not know their CIDR, and the Pi cannot supply it either: it is deliberately dual-homed — plugged
into the target network by ethernet with no default gateway, and onto the internet by wifi so that
vulnerability enrichment can reach the outside world. It therefore sees two networks and has no
basis for guessing which one it was brought in to scan. Scanning the wrong one — the host site's
own wifi — would be both useless and hostile.

The answer to both is one read surface, built once. The Pi **reports** the networks it can see,
each with the interface it sits on and whether that interface is the one carrying the default
route — which is exactly the fact that lets the screen label the choices honestly, so a human can
tell "the network I plugged you into" from "the internet". A human **chooses one, once**. The
backend **stores** that choice on the agent, where it belongs: it is a property of the box and its
cabling, the same for every admin in the organisation, not a per-person preference. From then on
the scan trigger reads the stored choice and sends it, and no admin ever sees a CIDR field.

## Business rules

- An organisation's scanners can be listed. In the current product that list holds exactly one
  agent, but it is a list, because the product is designed toward many organisations each with
  their own hardware.
- A scanner row carries: who it is, whether it is **online right now**, when it was **last seen**,
  which network it is **pointed at**, and which command it is **currently working on**.
- **Online is not a stored fact.** It is true exactly while the Pi is holding an open connection to
  the backend, and it is always answered from the live connection registry — never read from the
  database, never cached, never inferred from a timestamp. A Pi that disconnects is offline on the
  very next read. (The command lifecycle separately records a connection timestamp of its own, for
  sweeping stale scans. That is not this answer, and this answer never consults it.)
- **The networks a Pi can see are reported, not stored.** They arrive when the Pi connects and are
  replaced wholesale each time it reconnects. They are never persisted. A Pi that is offline
  reports nothing, and the product says so rather than showing a stale list.
- Each reported network names the interface it belongs to, the network itself, and whether that
  interface holds the default route. All three are needed for a human to choose correctly.
- **The chosen network is stored, and it is stored on the agent.** It has no value until a human
  chooses one.
- **A human can only choose a network the Pi actually reported.** A choice that does not match
  something the connected Pi named is refused. Since the report exists only while the Pi is
  connected, the choice can only be made while the Pi is online — which is not a limitation worth
  working around, because an offline Pi cannot be scanned with either.
- Choosing again replaces the previous choice. There is no history and no second slot.
- **The same rule is enforced again at the moment of use, and that is where it really binds.**
  Choosing is a convenience; triggering a scan is the act that points the scanner. A scan naming a
  network the Pi is not currently reporting is refused, whatever the stored choice says and
  whoever asks. Without this, the product would promise "only networks the Pi reported" while the
  operation that matters accepted any network at all.
- **A stored choice can go stale, and staleness is caught when the choice is used.** Re-cabling a
  site, a new address range, or moving the Pi can leave a stored network the Pi no longer sits on.
  The backend never silently corrects the stored choice and never silently scans it: the scan is
  refused, and the person is sent back to the current list to choose again.
- The check is against the networks the Pi is reporting **at that moment**, not the ones it
  reported when the choice was made. A report is only ever a description of now.
- **Only networks the Pi sits on directly can be chosen or scanned.** A network reachable only
  through a gateway is not offered and cannot be named. This matches a product that shows the
  operator a short list of what the box is plugged into. It is a real limit: the day the product
  needs to scan a routed network, this is the rule that has to change, deliberately.
- If the Pi has reported nothing — it is not connected, or has connected but not yet said what it
  can see — a scan is not refused on these grounds. Nothing is known, so nothing is contradicted,
  and the trigger's existing behaviour for an unreachable Pi stands unaltered.
- **Only an admin may choose the network.** Anyone in the organisation may read the scanner list
  and the scanner detail — the home screen shows Pi status to everyone.
- Everything here is scoped to the caller's own organisation. Another organisation's scanner is
  indistinguishable from one that does not exist.
- **The scan trigger keeps its shape, permanently.** It still takes the network in its request, and
  the web app fills that in from the stored choice. This is the settled design, not a step on the
  way to something else. Exactly one refusal is added to it — the reported-network check above —
  and nothing else about triggering, delivering, or tracking a scan changes.
- **A scan cannot be triggered before a network has been chosen.** With no stored choice the web
  app has nothing to send, the trigger's own requirement that a network be named refuses the
  request, and the screen does not offer the button in the first place. No new rule is added to the
  trigger to achieve this.
- The reported networks belong to the detail view only. The list view carries the chosen network,
  not the candidates — a list is for finding the Pi, not for configuring it.

## User stories

1. As an admin, I want to open the agents screen and see my Pi, so that I can work with it without
   knowing the identifier stamped into it at the factory.
2. As any member, I want the home screen to tell me whether the Pi is online, so that I know
   whether the product is working before I ask anyone.
3. As an admin, I want to choose which network to scan from a list of plain-language options, once,
   so that I never have to type or even understand a CIDR.
4. As an admin, I want to be told which of the offered networks is the internet-facing one, so that
   I do not point the scanner at the wrong network.
5. As an admin, I want to correct the choice if I picked wrong or the Pi was re-cabled, so that a
   mistake is not permanent.
6. As an admin returning to the agents screen mid-scan, I want to see that a scan is already in
   flight, so that the progress indicator survives navigating away and back.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| List the org's scanners | one provisioned agent | any member reads the scanner list | exactly one row is returned, carrying online, last-seen, the chosen network and the current command |
| List is org-scoped | two organisations each with an agent | a member of one reads the scanner list | only their own organisation's agent is returned |
| Detail reports both networks | a connected dual-homed Pi that reported two interfaces | any member reads that scanner's detail | both networks are listed, each with its interface name and network, and the internet-facing one is marked as holding the default route |
| Offline Pi reports nothing | a Pi that has never connected, or has disconnected | any member reads its detail | the reported-network list is empty rather than stale |
| Online reflects the live connection | a connected Pi | it disconnects, and the detail is read again | online flips from true to false |
| Online is never stored | any agent | its stored record is inspected | the stored record carries no online column, and the answer given by the API is shown to come from the live registry rather than the database |
| Reported networks are never stored | a Pi that reported two networks | its stored record is inspected | no reported network is persisted; only the chosen one can be |
| Unchosen network reads as absent | a newly provisioned agent | its detail is read | the chosen network has no value |
| Choosing a reported network | a connected Pi reporting two networks, and an admin | the admin chooses one of them | the choice succeeds and both the detail and the list subsequently report it |
| Choosing an unreported network | a connected Pi reporting two networks, and an admin | the admin names a network the Pi did not report | the request is refused and no choice is stored |
| Choosing while the Pi is offline | an offline Pi and an admin | the admin tries to choose a network | the request is refused as the device being offline, and no choice is stored |
| Re-choosing replaces | an agent with a network already chosen | an admin chooses a different reported network | the new choice replaces the old one |
| Viewer may read | a viewer | they read the scanner list and a scanner's detail | both succeed |
| Viewer may not choose | a viewer | they try to choose the network | the request is forbidden and no choice is stored |
| Cross-org choose refused | two organisations | an admin of one tries to choose the network of the other's agent | the other agent is not found, and its choice is unchanged |
| Unknown agent | any member | they read a scanner identifier that does not exist | the request is not found |
| Current command surfaces | an agent with a command in flight | its list row and detail are read | both name that command |
| No command in flight | an agent with no active command | its list row and detail are read | the current command has no value |
| No network chosen blocks the scan | an agent with no chosen network | a scan is triggered without naming a network | the request is refused by the trigger's existing requirement that a network be named |
| Chosen network drives the scan | a connected Pi and an agent whose chosen network the Pi reports | a scan is triggered with that network | the trigger succeeds and the command carries it |
| Unreported network cannot be scanned | a connected Pi reporting two networks | a scan is triggered naming a well-formed network it did not report | the scan is refused, no command is created, and the refusal names the same reason as an unreported choice |
| Stale choice is refused, not scanned | an agent whose stored choice the Pi reported once but no longer does | a scan is triggered with the stored choice | the scan is refused, and the stored choice is left exactly as it was rather than corrected or cleared |
| Silence is not contradiction | an agent whose Pi has reported nothing, whether disconnected or connected but not yet speaking | a scan is triggered | the reported-network rule refuses nothing, and the trigger behaves exactly as it did before this feature |
| Everything else about triggering is untouched | the scan trigger | it is exercised with a network the Pi reports | delivery, the command lifecycle, the busy refusal and the unreachable-Pi refusal all behave exactly as they did |
| Contract published | the feature is complete | the published API contract is inspected | it documents the scanner list, the scanner detail including reported networks and the chosen network, and the operation that sets the choice, with their forbidden, not-found and refusal responses |
| Gates pass | the touched scope | the backend lint and test gates run | both pass with the database up and no database-test skips |

## Out of scope (v1)

- **The command write path, with one deliberate exception.** Delivering a scan, moving it through
  its lifecycle and timing it out belong to DMI-64 and are already delivered; nothing here changes
  them. The one exception, decided 2026-08-11 against this feature's original scope fence: the
  trigger gains the reported-network refusal described in the business rules. It was added here
  rather than deferred because storing a chosen network while leaving the operation that uses it
  unguarded would ship the feature in a shape that does not hold its own promise. No other rule is
  added to the trigger — in particular no "you must choose a network first" rule, because the
  existing requirement that a network be named already does that job.
- **The web screens that consume this.** The agents screen, the network chooser, the Scan-now
  button and the status pill are DMI-89. This feature ships the API only.
- Documentation work on how a dead Pi is classified. That question was settled on 2026-07-13 —
  never delivered is *expired*, delivered then broken is *failed* — and the roadmap already says
  so. The one remaining gap, a missing edge in the lifecycle state machine, belongs to DMI-64.
- Multi-agent management: naming, grouping, or comparing more than one Pi.
- Agent provisioning and pairing. A Pi enters the system through the installer, not through this
  API.
- Key or secret rotation, and revoking an agent.
- Scan-mode selection. The product picks the quick mode and does not offer the choice.
- A CIDR text field, anywhere, ever — including as a fallback when the Pi is offline.
- Any history of past network choices.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Decisions: `docs/adr/ADR-011-pi-command-channel.md` (WS envelope, hello frame, command
  lifecycle), `docs/adr/ADR-005-security-model.md` (agent auth, as amended 2026-07-24)
- Roadmap: `docs/roadmap/BACKEND.md` B6 (API surface 5a, `agents` table 5b, contract asks C1/C2),
  `docs/ui/FLOWS.md` B4 (why the network is chosen here, and once)

## Docs drift (docs-sync, 2026-08-12) — resolved

All items below were raised as needing a human call, then fixed on the operator's instruction the
same day. Decision taken: **a contract ask closes when the contract publishes and the backend
implements it**, not when a screen consumes it; SPA consumption is DMI-89.

- **C1 and C2 marked resolved.** `docs/roadmap/BACKEND.md` (status row, API-surface table, the
  `agents` column list, and both ask rows), `docs/ui/SCREENS.md` (AGENTS data section and its
  open-questions item), `docs/ui/FLOWS.md` (ask table and the single-agent note),
  `docs/roadmap/FRONTEND.md` (single-agent note, C2 pointer, the unimplemented-route note and
  milestone 1) and `docs/roadmap/PI.md` step 2b. The Agents screen is now recorded as unblocked and
  buildable, with the SPA work left to DMI-89.
- **ADR-011 corrected and annotated.** The claim that the backend "caches `available_subnets`
  against the agent" overstated what shipped — replaced with the in-process connection registry,
  no column and no cache table. An implementation note records that DMI-78 delivered the HTTP half
  the ADR deferred, consistently with the decision; the ADR's original scope statement is left as
  the historical record it is.

Root scripts (`install`, `database`, `lint`): no trigger — no new dependency, env var, entrypoint,
service, or gate. Migration `20260811_17` runs through the existing Alembic step.
