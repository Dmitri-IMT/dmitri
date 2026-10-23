# DESIGN — Devices screens

> **Status:** approved by the owner on 2026-10-23.
> **Visual source:** [Dmitri scan visual cues canvas](https://claude.ai/artifact/UVnbjzroi7jkG1Xz6BsWFf),
> tab **Devices page** (boards "Devices · box list" and "Devices · one box").
> **Shared rules:** tokens and the "For your IT person" pattern come from
> [`../052-ai-assistant-upgrade/DESIGN.md`](../052-ai-assistant-upgrade/DESIGN.md) (§3, §14.2).
> **Binding look:** [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md).
> **Vocabulary:** a *device* or *box* is a Dmitri box (the agent); a *machine* is a host on
> the customer network. Never mix them.
> **Depends on 052:** no. This redesign uses only data the API has today, except where
> noted in §3.

Today's sources: `pages/Devices.tsx` (`ListSurface` with `deviceListColumns`),
`pages/DeviceDetail.tsx` and `pages/agents/*` (`AgentIdentity`, `AgentPresence`,
`TargetSubnetSection`, `ScanTypeTabs`, `ScanControl`, `AgentUpdateSection`,
`DeviceScanHistory`, `DeviceRevoke`, `DeviceRestore`, `WatchedNetworkReadOnly`).

Same shell as 052 §14: top bar with the active nav item in bold `--ink` (no background),
the `AI assistant` button in the top bar, content padding 32px / 80px / 64px, 32px
between sections.

## 1. Box list (board "Devices · box list")

Replaces today's table (Box, Network, Status, Last report).

1. **Header:** title `Devices` (`title-lg`); line `The Dmitri boxes that check your
   network. {n} boxes · {k} online.` (`body-md`, `--ink-muted`). No actions.
2. **Cards:** grid `repeat(auto-fill, minmax(320px, 1fr))`, gap 16px, so any number of
   boxes fits and wraps.
   - **The whole card is one link** to the box page (`/devices/{agent_id}`). No buttons
     inside the card: no `Start a scan`, no `Open`, no nested links (owner decision). The
     link's accessible name is today's `devices.open` copy (`Open {name}`).
   - Card: `--card`, 1px `--rule` for every state (no dashed or thick borders), radius
     12px, padding 20px 24px, gap 8px. Hover: border `--edge`. Focus: 2px `--accent` ring.
   - Row 1: box name (`title-xs`, 16px 600) and, right-aligned, an 18px **arrow (→)**
     icon (`aria-hidden`). Not a chevron: a chevron reads as "opens in place" (owner
     decision).
   - Row 2: status word in 600 (`Online` / `Offline` / `Revoked`) + ` · reported {time}` or
     ` · last report {time}` in `--ink-muted` (today's `AgentPresence` + `Timestamp`).
   - Row 3 (`caption-md`, `--ink-muted`):
     - online: `Watches {subnet in mono} · last scan {date}`; without a watched network:
       `No network chosen yet`;
     - offline: `Check its power and network cable. It reconnects by itself.`;
     - revoked: `Revoked on {date}.`
   - Order: online first, then offline, then revoked; by name inside each group.
3. **Empty state:** today's copy and note (`devices.emptyHeading`, `devices.emptyBody`,
   `devices.emptyNote`), unchanged.

## 2. One box (board "Devices · one box")

Order, top to bottom:

1. **Header:** `← Devices` (today's `BackLink`). Meta line `Dmitri box · **{Online}** ·
   reported {time}` (`caption-md`). Title = box name (`title-lg`). Replaces the
   `AgentIdentity` layout; same data.
2. **About this box** (card, title `title-xs`, 4-column definition list as 052 §4):

   | Label | Value (`title-sm`) | Line under (`body-sm`, `--ink-muted`) |
   |-------|--------------------|---------------------------------------|
   | `Watches` | `Your network` | subnet in mono |
   | `Last scan` | date | `{mode} · {n} problems` (link to the scan) |
   | `Software` | `Up to date` / `Update waiting` | `Version {x}` |
   | `Connected since` | date | `{n} scans so far` |

3. **Start a scan** (card) — replaces `ScanTypeTabs` + `ScanControl` visually; the
   behaviour of `ScanControl` stays (command status, NSPi submode select, stale-subnet
   handling, admin-only rules, read-only mode for members).
   - Title `Start a scan` (`title-sm`) + line `A scan only looks at your network. It does
     not change anything on your machines.` (`body-sm`, `--ink-muted`).
   - A radio group (`<fieldset>`, visually hidden legend `Type of scan`) of five cards in a
     5-column grid, gap 12px, in `SCAN_MODE_ORDER`. Each card is the `<label>`: radio +
     mode name (`body-md` 600), time (`caption-md`), one plain sentence (`body-sm`,
     `--ink-muted`).
   - **Radio buttons use `--accent`** (`accent-color: #600BB5`; owner decision). The
     selected card has a 2px `--ink` border (padding 15px); others 1px `--rule`.
   - Standard is the default and shows `· recommended` after its time.
   - Card copy (shortened from `SCAN_MODE_DESCRIPTION`):

     | Mode | Time | Sentence |
     |------|------|----------|
     | Quick | `2–5 minutes` | `Finds your machines and the most common problems.` |
     | Standard | `5–10 minutes` | `Also checks file sharing, remote login and web pages for weak settings.` |
     | Extensive | `Can take over an hour` | `More doors, encryption checks, and smaller problems too.` |
     | Max | `45 minutes or more` | `Every door on every machine, and everything it finds.` |
     | NSPi | `20–30 minutes` | `For networks with industrial equipment.` |

   - Primary button `Start a {Mode} scan` (`--accent`, 40px). The NSPi submode select
     appears under the cards when NSPi is selected, as today.
   - Members (not admins) see today's read-only scan type instead of the radio group.
   - Hidden while the watched-network chooser is open, as today.
4. **Scans by this box** (card, title `title-sm`): today's `DeviceScanHistory` data in
   the 052 table style. Columns: Date (link to the scan) | Type | Result (`{n} problems ·
   **{k} Critical**`, or `Partial results` in `--ink-muted`) | Took | Status (`Completed`,
   `Stopped by you`, …).
5. **Agent update** (card): **today's `AgentUpdateSection`, unchanged in content and
   behaviour** — package version, observed version, local outcome, requested by and when,
   completion and confirmation times, last contact, and the update history. Shown open,
   not collapsed (owner decision). Only the card shell follows the new style.
6. **For your IT person** (052 §14.2 pattern, collapsed cards):
   - `Watched network · change which network this box checks` → today's
     `TargetSubnetSection` (chooser, admin-only `Change`). When an admin has not chosen a
     network yet, this section opens by itself and moves above "Start a scan", as today.
   - `Box details · ID, address, hardware` → agent ID (mono), box address, hardware model.
7. **Remove this box** (no card; top 1px `--rule`, padding-top 24px): title `title-xs`,
   line `It stops reporting at once. Its past scans stay. Only admins see this.`, outline
   button `Remove box…`. Opens today's `DeviceRevoke` confirmation. Absent (not disabled)
   for members.

**Revoked box:** sections 3, 5 and 6 are replaced by today's revoked layout
(`WatchedNetworkReadOnly`, `DeviceRestore`), plus "Scans by this box". Section 7 is absent.

## 3. Data

All fields exist today on `AgentSummary` / `AgentDetail`, scan history and update
operations, except:

1. `Connected since` and `{n} scans so far` (enrolment date and scan count per agent) —
   check before building; drop the item if the API has neither.
2. Hardware model in "Box details" — check what the agent reports.
3. `Last scan` problem count on the box page — from the latest scan of this agent.

## 4. Keyboard and accessibility

- Box cards: one tab stop each (the link); Enter opens the box page.
- Scan type: arrow keys move inside the radio group; Space selects.
- Collapsed IT cards: `<button aria-expanded>`.
- `Remove box…` opens today's dialog; focus returns to the button on cancel.

## 5. Test selectors

| Element | `data-testid` |
|---------|---------------|
| Box card link | `device-card-{agent_id}` |
| About strip | `device-about` |
| Scan type group / card | `device-scan-modes`, `device-scan-mode-{mode}` |
| Start button | keep today's `ScanControl` id |
| Scans by this box | keep today's `DeviceScanHistory` id |
| Agent update | keep today's `AgentUpdateSection` id |
| IT cards | `device-it-network`, `device-it-details` |
| Remove | keep today's `DeviceRevoke` id |
