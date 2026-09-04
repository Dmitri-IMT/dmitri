# DESIGN — Design system v2 and the restyle onto it

Spec only. No implementation code. Every value comes from
[`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md); this document owns layout, copy, states
and `data-testid`s.

**Rendered preview:** https://claude.ai/code/artifact/47ec803b-591f-46e1-b209-cd9426be3680

The preview is built from the Foundations tokens and the real typefaces (Inter Variable, Geist
Mono for data). The box-drawing renders below are structural notes only — arrangement and
proportion. **The human performs the visual check on the preview, and that check closes this
feature** (TRUTH business rule 13). No agent signs off on how it looks.

---

## 0. Corrections this work makes to `FOUNDATIONS.md`

These are owner decisions, recorded here so the edit is not lost.

| § | Sentence today | Correction |
| --- | --- | --- |
| Scan settings | "It sits below the scans table on the Scans page." | **The scan-type control and the watched network are per box.** Both live on **Device detail** (`/devices/:agentId`). The Scans page carries no settings block. `FOUNDATIONS.md` §Scan settings must be edited to say so. |
| Scan settings | The section names a "Use this scan type" button, its confirm dialog and a "Daily scan uses:" line. | Out of scope here (DMI-133). Not drawn, and **not drawn as a placeholder**. The five tabs, the verbatim descriptions, "Scan now", preview-only selection and revert-on-leave all ship. |
| Vocabulary | "A *device* is the Dmitri box running inside a network" — contradicted by the exemplar, which heads the Network table `DEVICE` for customer machines. | **Owner ruling 2026-09-02: Foundations is right.** A **device** is the Dmitri box (`Devices`). A thing on the customer's network is a **machine** (`Network`). §Tables' "Silent devices" wording is corrected to "Silent machines" in the same edit. |
| Chrome | "User identity — **the user's name.**" | `UserProfileResponse` has no name field. **Owner ruling: ship the email**, truncated with an ellipsis when it would crowd the bar, its full value in `title`. Amend §Chrome to say email. |
| Vocabulary | *Open ports* — "🔓 Exact wording open" | **Resolved: "Services running on this device."** |
| Vocabulary | *Seen in these scans* — "🔓 Wording open" | **Resolved: "Scan history."** |

### Where the exemplar and Foundations disagree

`docs/ui/mockups/dmi-131-mockups-v4.html` is the visual exemplar. Where it and `FOUNDATIONS.md`
disagree, Foundations wins. Found, and how each is settled:

| # | Disagreement | Settled |
| --- | --- | --- |
| 1 | The exemplar's five scan-type descriptions are worded differently from the §Scan settings table. | **Foundations' table ships verbatim.** The exemplar's wording is dropped. |
| 2 | The exemplar draws Duration and Result on Scans, Type-and-vendor and Open-vulnerabilities on Network, First-seen on the vulnerability table, Last-seen on the services table, and Events/Activity on Home. | No API field feeds any of them. **Not drawn, and not drawn as placeholders** (TRUTH: nothing renders without data). |
| 3 | The exemplar draws a search box and an "All devices" filter above the Network table. | Search and filters are "Later, not MVP" in `docs/ui/status.md`. **Not drawn.** |
| 4 | The exemplar mutes the severity word to weight 500 inside a quiet-device row. | Foundations §Color: severity is **always weight 600**. Inside a muted row the word inherits `--ink-muted` with the whole row, but keeps its weight. |
| 5 | §Chrome says the top-bar identity is "the user's name". `UserProfileResponse` has `email` and `role` — there is no name field. | The bar shows the **email**. Raised as open question **Q3**. |

---

## 1. Screen flow

```
  PUBLIC                                    SIGNED IN (AppShell: top bar + frame)
  ────────────────────────                  ────────────────────────────────────────────
  /login ───── sign in ───────────────────► /                    Home
    │  forgot link                              │ row (a vulnerability)
    ▼                                           └──────────────► /scans/:scanId?finding=:findingId
  /forgot-password ── sent ──► back ──┐
    │                                 │     /scans               Scans log
  /reset-password?token= ── set ──────┤         │ row
    │                                 │         └──────────────► /scans/:scanId
  /invite?token= ── create account ───┼──►                            │ devices-seen row
                                      │                               └──► /network/:hostId
                          (all land on /login or /)
                                          /network              Network (devices found)
                                              │ row
                                              └──────────────► /network/:hostId
                                                                     │ scan-history row
                                                                     └──► /scans/:scanId

                                          /devices              Devices (Dmitri boxes)
                                              │ row
                                              └──────────────► /devices/:agentId
                                                                     │ command done
                                                                     └──► /scans/:scanId

                                          /users   (admin only — RequireAdmin)
                                          /settings ── leave organisation ──► /login
```

**Route changes.** `/hosts` → `/network`, `/hosts/:hostId` → `/network/:hostId`,
`/agents` → `/devices`, plus the new `/devices/:agentId`. Per TRUTH, `/hosts` and `/agents` are
**no longer routes** — no redirect is registered; they fall through to `NotFound`.

**Back links.** Every detail screen carries one back link, a Lucide `arrow-left` + the word
**"Back"**, above the page title (Foundations §Chrome). `/scans/:scanId` → `/scans`,
`/network/:hostId` → `/network`, `/devices/:agentId` → `/devices`.

---

## 2. Chrome, shared components, and the rhythm contract

### 2.1 Top bar

Full-bleed white bar, bottom hairline `--rule`, contents held to `--container-frame` on a
`1fr auto 1fr` grid. The page beneath holds the same frame, so the wordmark and the page title
start on the same vertical.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- Wordmark: the word **"Dmitri"**, `--text-title-xs`. Not `DMITRI`, no icon, no ornament.
- Nav: `--text-body-md`. Active is **bold, no underline**. Hover is **also bold**. The current
  accent bottom-border is removed.
- `Users` is **absent** for viewers (`AdminOnly`), never disabled.
- Right cluster: identity text then a ghost `Log out` button, step `4` apart.
- Bar height comes from step `4` vertical padding on `--text-body-md` contents.

### 2.2 Shared components that change

| Component | Change |
| --- | --- |
| `SeverityBadge` | **Retired.** Replaced by `SeverityWord` — the label (`Critical` / `High` / `Medium` / `Low`) as a `font-semibold` `--ink` span. No border, no background, no hue. Ships with **no outer margin**. |
| `StatusPill` | **Retired** and deleted, with `StatusPill.test.tsx`. Scan and command status become **plain text** — the label in `--ink`, its detail line in `--ink-muted`. No pill, for status or for anything else. `lib/scanStatus.ts` and `lib/commandStatus.ts` return a label with no tone (see `ARCHITECTURE.md` §4.3). |
| `Ornament` | **Retired** and deleted, with `Ornament.test.tsx`. Foundations ships no decorative mark. |
| `EmptyMark` | Kept. The em dash in `--ink-muted`. |
| `DataTable` | Row height becomes **fixed 56px** for every row. Column widths come from an explicit `colgroup`, never from content. A numeric column followed by a code column keeps step `6` between them. Gains the quiet-row and grouped-row pattern (§6.3). Whole rows navigate; no trailing "View" column. |
| `PageHeader` | The trailing `<hr>` is removed — the step `12` inter-section gap does the separating (Foundations: proximity before rules). Title becomes `--text-title-lg` on a list screen. |
| `EmptyState` | One sentence + one button. The `Ornament` is removed. |
| `Pagination` | Previous/next become **icon-only** Lucide `chevron-left` / `chevron-right` ghost buttons with `aria-label` "Previous page" / "Next page". The words "Previous"/"Next" are removed. The `Showing 1–20 of N` range line and its `{testId}-range` id are **removed** — Foundations §Pagination enumerates ghost buttons, page numbers and an ellipsis, and the exemplar draws no range line (`ARCHITECTURE.md` §4.4). |
| `AuthShell` | Wordmark becomes **"Dmitri"** at `--text-title-md`; the `Ornament` is removed; the card gets `--radius` and step `6` padding on `--card`. |
| `AppShell` | `main` holds `--container-frame`, horizontal padding step `6`, top padding step `12`. |

All shared components ship **flush to their own box, with no outer margin**. Every gap around
them belongs to the parent screen's layout, named in that screen's rhythm table.

### 2.3 Vertical rhythm, per screen family

At most three steps per screen (Foundations §Spacing rule 4). Card padding (`6`) is padding, not
rhythm, and is not counted.

| Screen family | intra-group | inter-group | inter-section |
| --- | --- | --- | --- |
| List screens — Home, Scans, Network, Devices, Users | `2` | `4` | `12` |
| Detail screens — Scan detail, Network detail, Device detail | `2` | `8` | `12` |
| Settings | `2` | `4` | `12` |
| Auth screens | `2` | `4` | `6` |

On the detail screens the back link sits **inside the header group**, step `2` above the title —
that is the "step from the spacing scale" Foundations §Chrome asks for, and it keeps the screen
to three steps.

**Home's clear state is the one quiet screen.** Its title block gets a step `24` top offset
inside the frame and nothing after it. An implementer told nothing will pack it to the top and
the calm is lost — see §3.

---

## 3. Home (`/`)

**Epicenter: the attention table.** The title states the count; each row is a vulnerability, the
machine it sits on, and its severity; the whole row navigates.

### 3.1 Regular state — something needs attention

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  4 things need your attention                                    ← title-lg              │
│  Last scan finished today at 06:12                               ← body-md, muted (step 2│
│                                                                                          │
│                                                    ↕ step 12                             │
│  VULNERABILITY                       MACHINE                 SEVERITY                    │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Router firmware is out of date      192.168.1.1            Critical                     │
│    CVE-2024-33112                                                                        │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Remote desktop is open to the       192.168.1.22           High                         │
│  whole network                                                                           │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Camera still uses the password …    192.168.1.51           High                         │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Old file sharing is switched on     192.168.1.30           Medium                       │
│    CVE-2020-0796                                                                         │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Regions, top to bottom: the **title block** (count line, then the muted last-scan line at step
`2`), then step `12`, then the **attention table**. Nothing else. Column shares 46 / 34 / 20;
`Severity` closes the row per Foundations §Tables. Rows are fixed 56px; the CVE sub-line sits
under the title in `--text-body-sm` `--ink-muted` mono and truncates rather than wraps.

**Ordering.** Critical first, then High; newest first inside each severity. This is today's
`deriveReview` order, unchanged.

**Attention notes.** When the latest scan failed, or no scan has succeeded for
`STALE_COVERAGE_DAYS` (3) days, that fact is one extra muted line inside the title block, below
the last-scan line, at step `2`. No card, no eyebrow label, no accent. Those two conditions still
count toward the title's number, exactly as today.

**What is removed here, and why.** The `FindingDeck` carousel, the `ReviewItemCard` deck and the
`HomeFooter` Pi-status line all go. The deck is replaced by the table the owner specified. The
footer's Pi line is not a feature loss: the new **Machines** list answers "is each box reporting"
directly (user story 3), and the footer's last-scan line is already the title block's second
line. The Events panel and the Activity log are **not drawn** — no data feeds them.

### 3.2 Blank state — nothing needs attention

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│                                     ↕ step 24                                            │
│                                                                                          │
│  Nothing needs your attention                                                            │
│  Last scan finished today at 06:12                                                       │
│                                                                                          │
│                                     (nothing else is drawn)                              │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Per Foundations §Copy rules, **nothing at all** is rendered in the table's place — no text, no
empty card, no ornament. The canvas shows through and the title carries the message. The title
block keeps its step `24` top offset so the calm reads as deliberate rather than as a page that
failed to load. This is the one screen where whitespace *is* the design.

### 3.3 First-run state — no scan yet

```
│  No scans yet                                                                            │
│  Your first scan finds the machines on your network and what needs fixing.                │
│                                                                                          │
│  [ Run first scan ]              ← admin only; absent for a viewer                       │
│  Ask your admin to run the first scan.        ← viewer only, muted                       │
```

One sentence, one button (Foundations §Copy rules). The button links to `/machines`. For a viewer
the button is **absent** and the muted line stands in its place. Same step `24` top offset as the
blank state.

### 3.4 Error state

```
│  Couldn't load what needs your attention.                                                │
│                                                                                          │
│  [ Try again ]                                                                           │
```

Every error has a next step: the retry button re-runs all four Home reads.

### 3.5 Loading

`LoadingSkeleton` for the table body on first load only, never on background refetch. The title
block renders as soon as the latest-scan read lands.

### 3.6 Home — data

| Endpoint | Fields consumed |
| --- | --- |
| `GET /api/v1/scans?per_page=1&…` (latest, and latest completed) | `scan_id`, `timestamp`, `status` |
| `GET /api/v1/findings?scan_id=&severity=critical&per_page=100` | `finding_id`, `scan_id`, `title`, `cve_id`, `host_ip`, `severity`, `detected_at`, `total` |
| `GET /api/v1/findings?scan_id=&severity=high&per_page=100` | same |

The `Machine` cell shows `host_ip` in `--font-mono`, or `EmptyMark` when it is null. A finding
carries no hostname — see open question **Q1**.

### 3.7 Home — keyboard and focus

Focus starts on the document body; the first `Tab` reaches the top bar's first nav item. Tab
order: nav items → `Log out` → each table row in visual order → (retry button, in the error
state). A row is a link: `Enter` opens it; the whole row shows the focus ring.

### 3.8 Home — copy

| Where | String |
| --- | --- |
| Title, 1 item | `1 thing needs your attention` |
| Title, N items | `{n} things need your attention` |
| Title, clear | `Nothing needs your attention` |
| Title, first run | `No scans yet` |
| Last-scan line | `Last scan finished {relative-or-absolute time}` |
| Failed-scan note | `Last night's scan didn't finish.` |
| Stale-coverage note | `No successful scan in {n} days.` |
| First-run sentence | `Your first scan finds the machines on your network and what needs fixing.` |
| First-run button | `Run first scan` |
| First-run, viewer | `Ask your admin to run the first scan.` |
| Error | `Couldn't load what needs your attention.` |
| Error button | `Try again` |
| Column headings | `Vulnerability` · `Machine` · `Severity` |

The old body copy ("Dmitri scans your network for machines and known vulnerabilities…") is
**deleted**, not reworded: Foundations §Copy rules forbids product restatement.

### 3.9 Home — `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `home-verdict` | The title line | kept |
| `home-context` | The last-scan line | kept |
| `home-item-scan` | Failed-scan note | kept (was a card, now a line) |
| `home-item-coverage` | Stale-coverage note | kept (was a card, now a line) |
| `home-table` | The attention table | new |
| `home-table-row-{finding_id}` | One attention row | new (`DataTable` convention) |
| `home-blank-body` | First-run sentence | kept |
| `first-scan-cta` / `first-scan-note` | First-run button / viewer line | kept |
| `home-error` / `home-retry` | Error line / retry button | kept |
| `home-deck`, `home-deck-card`, `home-deck-prev`, `home-deck-next`, `home-deck-position`, `home-item-severity`, `home-footer`, `home-footer-scan`, `home-footer-pi`, `home-stub` | — | **retired**: the carousel, the severity badge and the footer no longer exist |

---

## 4. Scans (`/scans`)

**Epicenter: the scans table.** The scan-settings block does **not** live here — it moved to
Machine detail (§0).

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Scans                                                          ← title-lg               │
│                                                    ↕ step 12                             │
│  WHEN                MODE        STATUS      MACHINES   VULNERABILITIES   HIGHEST SEVERITY │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  2 Sep 2026, 06:12   Standard    Complete         14                 2   High            │
│  1 Sep 2026, 06:10   Standard    Complete         14              None   —               │
│  31 Aug 2026, 22:04  Extensive   Complete         14                 5   Critical        │
│  30 Aug 2026, 06:11  Standard    [Failed]          —                 —   —               │
│  29 Aug 2026, 06:09  Quick       Complete         13              None   —               │
│  28 Aug 2026, 06:10  NSPi        Complete         14                 1   Medium          │
│                                                                                          │
│                                                    ↕ step 4                              │
│                                                            ‹  1  2  3  4  ›              │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Column shares 24 / 14 / 14 / 12 / 16 / 20. `Machines` and `Vulnerabilities` right-align in
tabular figures; `Highest severity` closes the row as a bold ink word. Step `6` minimum sits
between `Vulnerabilities` and `Highest severity`. A whole row opens `/scans/:scanId`.

**Mode** renders the display label (`Quick`, `Standard`, `Extensive`, `Max`, `NSPi`), not the raw
`nspi` enum value it prints today.

**Not drawn:** Duration, a new-versus-known Result column, and a Box column. No data feeds them.

### 4.1 States

| State | Render |
| --- | --- |
| Regular | The table above plus pagination. |
| Loading | `LoadingSkeleton` table body, first load only. |
| Blank | `No scans yet` + `Run first scan` (admin) / `Ask your admin to run the first scan.` (viewer). One sentence + one button. |
| Error | `Couldn't load the scans.` + `Try again`. |

Blank state mockup:

```
│  Scans                                                                                   │
│                                                                                          │
│                            No scans yet                                                  │
│                            Your first scan finds the machines on your network and         │
│                            what needs fixing.                                            │
│                            [ Run first scan ]                                            │
```

### 4.2 Data

`GET /api/v1/scans?page=&per_page=20&sort_by=timestamp&sort_order=desc` →
`ScanListResponse{ data[], total, page }`; per row `scan_id`, `timestamp`, `scan_mode`, `status`,
`host_count`, `finding_count`, `highest_severity`.

### 4.3 Keyboard and focus

Nav → `Log out` → each row in order → pagination previous → page numbers → next. No submit.

### 4.4 Copy

| Where | String |
| --- | --- |
| Title | `Scans` |
| Columns | `When` · `Mode` · `Status` · `Machines` · `Vulnerabilities` · `Highest severity` |
| Zero vulnerabilities cell | `None` |
| Unknowable cell | `—` (`EmptyMark`) |
| Blank heading | `No scans yet` |
| Blank sentence | `Your first scan finds the machines on your network and what needs fixing.` |
| Blank button | `Run first scan` |
| Error | `Couldn't load the scans.` |
| Error button | `Try again` |
| Caption (screen-reader) | `Scan run log` |

### 4.5 `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `scans-page` | Page container | kept |
| `scans-table`, `scans-table-row-{scan_id}` | Table, rows | kept |
| `scans-status-{scan_id}` | Status cell | kept |
| `scans-blank` | Blank state | kept |
| `scans-error`, `scans-error-retry` | Error, retry | kept |
| `scans-pagination`, `scans-previous`, `scans-next` | Pagination | kept (`scans-range` retired with the range line) |

---

## 5. Scan detail (`/scans/:scanId`)

**Epicenter: what this scan found**, grouped by severity. The summary strip is context above it.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Scan · 31 Aug 2026, 22:04                                       ← title-lg (step 2 below) │
│                                                    ↕ step 12                             │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│   MODE            NETWORK            MACHINES SEEN      VULNERABILITIES                  │
│   Extensive       192.168.1.0/24     14                5                                 │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│                                                    ↕ step 12                             │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ Critical                                                        ← title-sm         │   │
│ │ VULNERABILITY                      MACHINE            PORT           CVE            │  │
│ │ ──────────────────────────────────────────────────────────────────────────────────  │  │
│ │ Router firmware is out of date     Netgear R7000      443    CVE-2024-33112        │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                    ↕ step 8                              │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ High                                                                               │   │
│ │ …                                                                                  │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          (Medium, Low: same card)                        │
│                                                    ↕ step 12                             │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ Machines seen                                                                       │  │
│ │ MACHINE               ADDRESS          MAC                 VENDOR         SERVICES  │  │
│ │ ──────────────────────────────────────────────────────────────────────────────────  │  │
│ │ Front-door camera    192.168.1.51     C0:56:E3:1A:4B:70   Hikvision             4  │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Summary strip.** Aligned to the tables' left and right edges, hairline above and below, step
`4` vertical padding. Label `--text-caption-md` uppercase `--edge`; value `--text-body-md`
tabular. Step `12` horizontal gap between entries. **Duration is not drawn** — no data.

**Severity cards.** One white `Card` per severity that has at least one vulnerability, in the
order Critical · High · Medium · Low, step `8` apart, step `6` internal padding, `--radius`. The
heading is inside the card and is the **bold severity word** — no coloured outline, no ink
eyebrow, no tinted band (Foundations §Cards). A severity with no vulnerabilities gets **no card**.
Columns 40 / 22 / 12 / 26; step `6` minimum between `Port` (right-aligned, tabular) and `CVE`
(mono).

A vulnerability row **expands in place** to a panel carrying the description, the recommendation
and the evidence — a vulnerability has no detail screen of its own, so the row is not a link and
the "whole row navigates" rule does not apply. `?finding=<id>` opens the matching row on arrival,
which is how a Home row lands here.

**Machines seen.** A white card, step `12` below the last severity card. Whole row navigates to
`/network/:hostId`. The old expand-to-see-ports panel and its `Open {name}` button are removed:
a machine has a detail screen, so the row itself goes there. Columns 24 / 18 / 22 / 22 / 14;
`Services` right-aligns and holds `ports.length`. **Per-machine vulnerability count is not drawn.**

### 5.1 States

| State | Render |
| --- | --- |
| Regular | As above. |
| Scan failed | The strip, then one centred block: the word `Failed` in `--ink`, `This scan didn't finish.`, and the reason line from the error-code deck in `--ink-muted`. No pill. No severity cards, no machines table. |
| Scan still running | The strip, then a centred block: the word `Running…` in `--ink`, `This scan is still running.`, `Vulnerabilities appear here when it finishes. This page doesn't update on its own.`, and a `Check again` button. |
| No vulnerabilities | Strip, then the sentence `No vulnerabilities. Every machine in this scan came back clean.` in place of the severity cards, then the machines-seen card. Good news reads as good news. |
| Not found | `That scan doesn't exist.` + `Back to scans`. |
| Error | `Couldn't load this scan.` + `Try again`. |

Failed-state mockup:

```
│  ← Back                                                                                  │
│  Scan · 30 Aug 2026, 06:11                                                               │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│   MODE            NETWORK                                                                 │
│   Standard        192.168.1.0/24                                                          │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│                                                                                          │
│                              [ Failed ]                                                  │
│                              This scan didn't finish.                                    │
│                              The box lost its network connection.                        │
```

When the scan is unfinished or failed, the strip drops `Machines seen` and `Vulnerabilities` —
those counts are not knowable yet, and Foundations forbids a placeholder mark standing in.

### 5.2 Data

`GET /api/v1/scans/{scan_id}` → `ScanDetailResponse`: `scan_id`, `timestamp`, `subnet`,
`scan_mode`, `status`, `error_code`, `host_count`, `finding_count`, `hosts[]`
(`host_id`, `ip`, `mac`, `hostname`, `vendor`, `ports[]`), `findings[]` (`finding_id`, `title`,
`host_id`, `host_ip`, `port`, `cve_id`, `severity`, `description`, `recommendation`, `evidence`,
`references`).

### 5.3 Keyboard and focus

Nav → `Log out` → `Back` → each vulnerability row in card order (`Enter`/`Space` toggles the
panel; `aria-expanded` on the row) → each machines-seen row (`Enter` navigates) → in the
unfinished state, `Check again`.

### 5.4 Copy

| Where | String |
| --- | --- |
| Back link | `Back` |
| Title | `Scan · {timestamp}` |
| Strip labels | `Mode` · `Network` · `Machines seen` · `Vulnerabilities` |
| Severity card headings | `Critical` · `High` · `Medium` · `Low` |
| Vulnerability columns | `Vulnerability` · `Machine` · `Port` · `CVE` |
| Machines-seen heading | `Machines seen` |
| Machines-seen columns | `Machine` · `Address` · `MAC` · `Vendor` · `Services` |
| No vulnerabilities | `No vulnerabilities. Every machine in this scan came back clean.` |
| Failed heading | `This scan didn't finish.` |
| Failed reason | from `lib/scanFailureReasons.ts`, unchanged |
| Running heading | `This scan is still running.` |
| Running body | `Vulnerabilities appear here when it finishes. This page doesn't update on its own.` |
| Running button | `Check again` / `Checking…` |
| Not found | `That scan doesn't exist.` |
| Not-found link | `Back to scans` |
| Error | `Couldn't load this scan.` |

`Findings` as a heading and a column label is **gone everywhere** — the reader-facing word is
`Vulnerability` / `Vulnerabilities`.

### 5.5 `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `scan-detail` | Page container | kept |
| `scan-detail-header` | Title block | kept |
| `scan-detail-not-found`, `scan-detail-back` | Not-found notice and its link | kept |
| `scan-detail-error`, `scan-detail-error-retry` | Error, retry | kept |
| `scan-summary-strip` | The summary strip | new |
| `findings-critical`, `findings-high`, `findings-medium`, `findings-low` | One table per severity card | **new; replaces `findings-table`** — one table became four, so a single id can no longer address them |
| `findings-{severity}-row-{finding_id}`, `findings-{severity}-panel-{finding_id}` | Row, expanded panel | **changed** with the id above |
| `scan-no-findings` | The no-vulnerabilities sentence | kept |
| `scan-hosts-table`, `scan-hosts-table-row-{host_id}` | Machines-seen table and rows | kept |
| `scan-failed`, `scan-failed-reason` | Failed block | kept |
| `scan-unfinished`, `scan-unfinished-check` | Running block | kept |
| `scan-hosts-open-{host_id}`, `scan-hosts-ports-{host_id}`, `host-ports-panel-{host_id}` | — | **retired**: the row navigates instead of expanding |

---

## 6. Network (`/network`)

Today's Hosts list. **Epicenter: the machine table.**

### 6.1 Regular state

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Network                                                                                 │
│  14 machines · last scan today 06:12                                                     │
│                                                    ↕ step 12                             │
│  MACHINE                    ADDRESS         VENDOR       SERVICES  HIGHEST SEV  LAST SEEN │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  Netgear R7000             192.168.1.1     Netgear             6  Critical     Today 06:12│
│  Office PC                 192.168.1.22    Dell                4  High         Today 06:12│
│  Front-door camera         192.168.1.51    Hikvision           4  High         Today 06:12│
│  Office NAS                192.168.1.30    Synology            7  Medium       Today 06:12│
│  192.168.1.63              192.168.1.63    Espressif           0  —            Today 06:12│
│    No name yet                                                                           │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  ▸ Not seen recently (2)                                                                 │
│                                                    ↕ step 4                              │
│                                                                 ‹  1  ›                  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Column shares 26 / 16 / 16 / 10 / 16 / 16. `Services` right-aligns in tabular figures.
`Highest severity` sits **second to last**, because `Last seen` closes the row (Foundations
§Tables). Step `6` minimum between `Services` and `Highest severity`. A whole row opens
`/network/:hostId`.

The first column always starts flush left. A machine with no hostname is listed **by its address
in mono**, with the muted sub-line `No name yet` — the same rule the detail header uses. The old
`(unnamed)` placeholder is deleted.

**Not drawn:** a machine-type column, a per-machine open-vulnerability count, a search box, a
filter select. No data, or not in the MVP.

**Sorting.** `Machine`, `Address`, `Vendor` and `Last seen` are sortable through the existing
`sort_by`/`sort_order` params, marked with a Lucide chevron sized off the type scale — never a
`▲▼` glyph. Default `last_seen_at desc`, which naturally sinks quiet machines to the bottom.

### 6.2 Quiet-machine row (in place)

```
│  Living-room TV            192.168.1.44   Samsung            2  Low          12 Aug 2026 │   ← whole row --ink-muted
│    Not seen for 3 weeks                                                                  │
```

Whole row in `--ink-muted`, second line `Not seen for {n} weeks`. **No chip, no icon, no colour,
and not an error.** The severity word keeps weight 600 and inherits the row's muted ink.

### 6.3 Collapsed / expanded "Not seen recently"

Quiet rows (last seen more than 14 days ago) leave the main list and collapse behind one group
row at the bottom of the table, **always last**, after the sort.

```
Collapsed:
│  192.168.1.63              192.168.1.63   Espressif          0  —            Today 06:12 │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  ▸ Not seen recently (2)                                                                 │

Expanded:
│  ▾ Not seen recently (2)                                                                 │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  Living-room TV            192.168.1.44   Samsung            2  Low          12 Aug 2026 │
│    Not seen for 3 weeks                                                                  │
│  Old laptop                192.168.1.77   Lenovo             1  Low          28 Jul 2026 │
│    Not seen for 5 weeks                                                                  │
```

The group row spans every column. Its control is a text-shaped button carrying a Lucide
`chevron-right` that rotates to `chevron-down` on open, at `--duration-base` / `--ease-standard`,
suppressed under `prefers-reduced-motion`. `aria-expanded` tracks the state. Expanded rows behave
exactly like regular rows: fixed 56px, whole row navigates, muted ink.

This is a `DataTable` pattern, not a Network-page one. See open question **Q2** — the grouping is
computed over the current page.

### 6.4 States

| State | Render |
| --- | --- |
| Regular | As above. |
| Loading | `LoadingSkeleton` table body, first load only. |
| Blank | `No machines yet` + `Run first scan` (admin) / viewer line. |
| Error | `Couldn't load your network.` + `Try again`. |
| All quiet | The table renders with an empty main body and the group row holding every machine. A table never renders bare with no rows. |

### 6.5 Data

`GET /api/v1/hosts?page=&per_page=20&sort_by=&sort_order=` → `HostListResponse`; per row
`host_id`, `hostname`, `ip`, `mac`, `vendor`, `open_ports_count`, `highest_severity`,
`last_seen_at`. The subtitle's machine count is `total`; its last-scan time comes from the same
latest-scan read Home uses.

### 6.6 Keyboard and focus

Nav → `Log out` → each sortable column header → each row → the group-row toggle
(`Enter`/`Space`) → any newly revealed rows → pagination.

### 6.7 Copy

| Where | String |
| --- | --- |
| Title | `Network` |
| Subtitle | `{n} machines · last scan {relative time}` |
| Subtitle, one machine | `1 machine · last scan {relative time}` |
| Columns | `Machine` · `Address` · `Vendor` · `Services` · `Highest severity` · `Last seen` |
| Unnamed machine sub-line | `No name yet` |
| Quiet sub-line | `Not seen for {n} weeks` |
| Group row | `Not seen recently ({n})` |
| Blank heading | `No machines yet` |
| Blank sentence | `Your first scan finds the machines on your network and what needs fixing.` |
| Error | `Couldn't load your network.` |
| Caption | `Machines on your network` |

### 6.8 `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `network-page` | Page container | **changed** from `hosts-page` — the screen and the route are renamed |
| `network-table`, `network-table-row-{host_id}` | Table, rows | **changed** from `hosts-table…` |
| `network-table-sort-{column}` | Sort controls | **changed** from `hosts-table-sort-…` |
| `network-blank` | Blank state | **changed** from `hosts-blank` |
| `network-error`, `network-error-retry` | Error, retry | **changed** from `hosts-error…` |
| `network-pagination`, `network-previous`, `network-next` | Pagination | **changed** from `hosts-…`; `hosts-range` is retired, not renamed |
| `network-quiet-group` | The group row | new |
| `network-quiet-toggle` | Its expand control | new |

---

## 7. Network detail (`/network/:hostId`)

**Epicenter: this machine's vulnerabilities.**

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Front-door camera                                               ← title-lg              │
│  192.168.1.51 · C0:56:E3:1A:4B:70 · Hikvision                    ← muted, mono for data  │
│  First seen 12 Jul 2026 · last seen today 06:12                                          │
│                                                    ↕ step 12                             │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ Vulnerabilities                                                                    │   │
│ │ VULNERABILITY                                   PORT        CVE          SEVERITY  │   │
│ │ ──────────────────────────────────────────────────────────────────────────────────  │  │
│ │ Camera still uses the password it came with      554        —            High      │   │
│ │ Old TLS version still enabled                    443   CVE-2016-2183     Medium    │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                    ↕ step 8                              │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ Services running on this machine                                                    │  │
│ │ SERVICE                            PROTOCOL          VERSION                       │   │
│ │ ──────────────────────────────────────────────────────────────────────────────────  │  │
│ │ rtsp                               tcp               Hikvision RTSP 1.0            │   │
│ │   554                                                                              │   │
│ │ https                              tcp               nginx 1.18.0                  │   │
│ │   443                                                                              │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                    ↕ step 8                              │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│ │ Scan history                                                                       │   │
│ │ WHEN                    MODE            SERVICES        HIGHEST SEVERITY           │   │
│ │ ──────────────────────────────────────────────────────────────────────────────────  │  │
│ │ 2 Sep 2026, 06:12       Standard               4        High                       │   │
│ └────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Three white cards, headings inside, step `8` apart. The identity block groups its three lines at
step `2` and the back link sits step `2` above the title.

**Vulnerabilities.** Columns 52 / 12 / 20 / 16; `Port` right-aligns tabular, `CVE` is mono, step
`6` minimum between them, `Severity` closes the row. Rows expand in place to the description,
recommendation and evidence, as on Scan detail. **`First seen` is not drawn** — no data.

**Services running on this machine.** The retired heading was "Open ports". `Port` sits under the
service name as a muted mono sub-line (exemplar). Columns 40 / 20 / 40. **`Last seen` is not
drawn** — no data.

**Scan history.** The retired heading was "Seen in these scans". Columns 34 / 22 / 18 / 26;
`Services` right-aligns; whole row opens `/scans/:scanId`.

### 7.1 States

| State | Render |
| --- | --- |
| Regular | As above. |
| No vulnerabilities | The card renders with the sentence `No vulnerabilities on this machine.` in place of the table. |
| No services | `No services are running on this machine.` in place of the table. |
| Vulnerabilities failed to load | Only that card shows `Couldn't load this machine's vulnerabilities.` + `Try again`. The identity, services and history stay — a second request failing never takes down the screen. |
| Quiet machine | The identity block's last line reads `First seen 12 Jul 2026 · not seen for 3 weeks`, in `--ink-muted` like the rest of the block. No banner, no colour. |
| Not found | `That machine doesn't exist.` + `Back to the network`. |
| Error | `Couldn't load this machine.` + `Try again`. |

### 7.2 Data

`GET /api/v1/hosts/{host_id}` → `HostDetailResponse`: `host_id`, `hostname`, `ip`, `mac`,
`vendor`, `first_seen_at`, `last_seen_at`, `open_ports_count`, `highest_severity`,
`ports[]` (`port`, `protocol`, `state`, `service`, `version`), `scan_history[]` (`scan_id`,
`timestamp`, `scan_mode`, `open_ports_count`, `highest_severity`).

`GET /api/v1/findings?host_id={host_id}&per_page=100` → `FindingListResponse`.

### 7.3 Keyboard and focus

Nav → `Log out` → `Back` → each vulnerability row (toggles its panel) → each scan-history row
(navigates) → the vulnerabilities retry button when that card is in error.

### 7.4 Copy

| Where | String |
| --- | --- |
| Back link | `Back` |
| Title | `{hostname}`, or `{ip}` when there is no hostname |
| Identity line | `{ip} · {mac} · {vendor}` (`—` for a missing MAC) |
| Seen line | `First seen {time} · last seen {time}` |
| Seen line, quiet | `First seen {time} · not seen for {n} weeks` |
| Card headings | `Vulnerabilities` · `Services running on this machine` · `Scan history` |
| Vulnerability columns | `Vulnerability` · `Port` · `CVE` · `Severity` |
| Services columns | `Service` · `Protocol` · `Version` |
| History columns | `When` · `Mode` · `Services` · `Highest severity` |
| Empty vulnerabilities | `No vulnerabilities on this machine.` |
| Empty services | `No services are running on this machine.` |
| Vulnerabilities error | `Couldn't load this machine's vulnerabilities.` |
| Not found | `That machine doesn't exist.` |
| Not-found link | `Back to the network` |
| Error | `Couldn't load this machine.` |

### 7.5 `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `host-detail` | Page container | kept (the record is a *host* in the contract) |
| `host-detail-header`, `host-detail-identity`, `host-detail-seen` | Identity block | kept |
| `host-detail-not-found`, `host-detail-back` | Not-found notice, link | kept |
| `host-detail-error`, `host-detail-error-retry` | Error, retry | kept |
| `host-findings-table`, `host-findings-table-row-{finding_id}`, `host-findings-table-panel-{finding_id}` | Vulnerabilities card | kept |
| `host-findings-error`, `host-findings-error-retry` | That card's error | kept |
| `host-no-findings` | Empty vulnerabilities sentence | kept |
| `host-ports-table` | Services card | kept |
| `host-no-ports` | Empty services sentence | kept |
| `host-history-table`, `host-history-table-row-{scan_id}` | Scan-history card | kept |

---

## 8. Devices (`/devices`) — new

**Epicenter: the box table.** Every Dmitri box in the organisation, so nothing disappears without
telling you (user story 6). Today's `/agents` renders one card and a paragraph of product copy;
both go.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Devices                                                                                 │
│  The Dmitri boxes reporting to this organisation.                                        │
│                                                    ↕ step 12                             │
│  BOX                            NETWORK                STATUS      LAST REPORT           │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  Rontho HQ                      192.168.1.0/24         Online      Today 06:12           │
│  Warehouse                      10.0.4.0/24            Online      Today 06:14           │
│  Reception spare                No network chosen yet  Online      Today 05:58           │
│  Old office                     172.16.0.0/24          Offline     14 Aug 2026           │   ← whole row muted
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Column shares 30 / 30 / 15 / 25. `Network` renders the CIDR in `--font-mono`. **No per-row
action** — the whole row opens `/devices/:agentId`, and no trailing column is drawn.

**Offline box:** the whole row is `--ink-muted`. It stays in the list; it is not an error and
carries no chip, icon or colour.

**Box with no network:** the `Network` cell reads `No network chosen yet` in `--ink-muted`, with
**no error styling**. It is a state, not a fault.

There is no pagination — `GET /api/v1/agents` returns the whole list.

### 8.1 States

| State | Render |
| --- | --- |
| Regular | As above. |
| Loading | `LoadingSkeleton` table body, first load only. |
| Blank | `No box connected yet` + the sentence + the muted note. |
| Error | `Couldn't load your devices.` + `Try again`. |

Blank-state mockup:

```
│  Devices                                                                                 │
│                                                                                          │
│                       No box connected yet                                               │
│                       Your installer connects the box on site; it appears here           │
│                       once it comes online.                                              │
│                       Contact whoever installed Dmitri if you were expecting one.        │
```

No button: there is no action the reader can take from here, and Foundations forbids inventing
one. The second line is the next step, in words.

### 8.2 Data

`GET /api/v1/agents` → `AgentListResponse{ data: AgentSummary[] }`: `agent_id`, `display_name`,
`online`, `last_seen_at`, `target_subnet`, `active_command_id`.

`AgentSummary` carries no `available_subnets`, so the `Network` cell shows the raw CIDR rather
than an interface label. That is the real value the box is scanning, so it is honest; the
friendlier label exists only on the detail read.

### 8.3 Keyboard and focus

Nav → `Log out` → each row in order. `Enter` opens the box.

### 8.4 Copy

| Where | String |
| --- | --- |
| Title | `Devices` |
| Subtitle | `The Dmitri boxes reporting to this organisation.` |
| Columns | `Box` · `Network` · `Status` · `Last report` |
| Status values | `Online` · `Offline` |
| No network cell | `No network chosen yet` |
| Never reported | `—` (`EmptyMark`) |
| Blank heading | `No box connected yet` |
| Blank sentence | `Your installer connects the box on site; it appears here once it comes online.` |
| Blank note | `Contact whoever installed Dmitri if you were expecting one.` |
| Error | `Couldn't load your devices.` |
| Caption | `Dmitri boxes` |

### 8.5 `data-testid`

| id | Element | Status |
| --- | --- | --- |
| `devices-page` | Page container | **changed** from `agents-page` — that page is now this list |
| `devices-table`, `devices-table-row-{agent_id}` | Table, rows | new |
| `devices-loading` | Skeleton | **changed** from `agents-loading` |
| `devices-blank`, `devices-blank-note` | Blank state | **changed** from `agents-blank`, `agents-blank-note` |
| `devices-error`, `devices-error-retry` | Error, retry | **changed** from `agents-error`, `agents-error-retry` |
| `agents-note`, `agents-scans-link`, `agents-hosts-link`, `agents-card` | — | **retired**: the product-restatement paragraph and the single-box card are deleted |

---

## 9. Device detail (`/devices/:agentId`) — new

**Epicenter: this box's scan controls** — the network it watches, the scan type, and Scan now.
This screen is where the per-box settings live (§0).

### 9.1 Admin, network chosen, at rest

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Rontho HQ                                                       ← title-lg              │
│  Online · last report today 06:12                                ← muted                 │
│                                                    ↕ step 12                             │
│  Watched network                                                 ← title-sm              │
│  192.168.1.0/24 (eth0)                                        [ Change ]                 │
│                                                    ↕ step 12                             │
│  Scan type                                                       ← title-sm              │
│  ┌───────┬──────────┬───────────┬─────┬──────┐                                           │
│  │ Quick │ Standard │ Extensive │ Max │ NSPi │      ← Tabs, Standard selected            │
│  └───────┴──────────┴───────────┴─────┴──────┘                                           │
│  Same 1000 connection points, and also inspects the common services — file sharing,      │
│  remote login, web — for weak settings. About 5–10 minutes.        ← muted, step 4 below │
│                                                                                          │
│                                                    ↕ step 8                              │
│  [ Scan now ]                                                                            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Three sections — identity, watched network, scan type — step `12` apart, no rules and no cards
between them: proximity does the grouping (Foundations §Spacing rule 3). Section headings are
`--text-title-sm`; each groups its contents at step `2` and its parts at step `4`.

The watched-network row is a `1fr auto` line: value left, `Change` outlined button right.

`Scan now` is the primary filled button, step `8` below the description, left-aligned under the
tab strip. It is the screen's action, not a card footer, so the card-footer rule does not apply.

**Not drawn:** the "Use this scan type" button, its confirm dialog, the "Daily scan uses: …"
line, and this box's own scan history (DMI-133 and the scan-attribution issue). No placeholders.

### 9.2 The five tabs, with the descriptions shipped verbatim

Selecting a tab is **preview only** — nothing is saved, the description below changes, and
leaving the screen reverts the selection to the box's default. `Scan now` runs the selected type
once and does not change any default.

| Tab | Description, shipped verbatim from `FOUNDATIONS.md` §Scan settings |
| --- | --- |
| `Quick` | `Checks the 1000 most-used connection points on each device for known vulnerabilities. About 2–5 minutes.` |
| `Standard` | `Same 1000 connection points, and also inspects the common services — file sharing, remote login, web — for weak settings. About 5–10 minutes.` |
| `Extensive` | `Checks the 10,000 most-used connection points, adds certificate and encryption checks, and reports lower-severity problems as well. About 20–35 minutes.` |
| `Max` | `Checks every connection point on every device and reports everything it finds, however small. 45 minutes or more.` |
| `NSPi` | `For networks with industrial equipment: checks the control-system connection points (Modbus, OPC UA, EtherNet/IP) plus Windows remote-access ones. About 20–30 minutes.` |

The tab strip is a shadcn `Tabs` segmented control on `--hover` ground, `--control-radius`, the
selected tab on `--card` with a one-pixel shadow. Tab order is fixed: Quick · Standard ·
Extensive · Max · NSPi.

### 9.3 Viewer

```
│  ← Back                                                                                  │
│  Rontho HQ                                                                               │
│  Online · last report today 06:12                                                        │
│                                                                                          │
│  Watched network                                                                         │
│  192.168.1.0/24 (eth0)                                        ← no Change control        │
│                                                                                          │
│  Scan type                                                                               │
│  Standard                                                     ← plain text, no tab strip │
│  Same 1000 connection points, and also inspects the common services — file sharing,      │
│  remote login, web — for weak settings. About 5–10 minutes.                              │
│                                                               ← no Scan now              │
```

Everything is readable; the `Change` control, the tab strip and `Scan now` are **absent from the
DOM**, never disabled. The box's current scan type reads as a plain bold word with its
description beneath, so a viewer learns the same thing without a control they cannot use.

### 9.4 No network chosen (admin)

```
│  ← Back                                                                                  │
│  Reception spare                                                                         │
│  Online · last report today 05:58                                                        │
│                                                                                          │
│  Which network should this box scan?                                                     │
│  This box is connected to more than one network. Pick the one you want scanned;          │
│  usually the office network, not the internet connection.                                │
│                                                                                          │
│   ( ) 192.168.1.0/24 (eth0)                                                              │
│   ( ) 10.0.9.0/24 (wlan0, internet connection)                                           │
│                                                                                          │
│                                              [ Set this network ]                        │
│                                                                                          │
│                                    ← Scan type and Scan now are absent                   │
```

The chooser is **open on arrival** for an admin. Neither the scan-type control nor `Scan now` is
drawn until a network is saved — scanning is not an action the person can take yet, so it is
absent, not disabled. After a successful save the screen re-renders into §9.1 and focus moves to
`Scan now`.

For a **viewer** on an unconfigured box: no chooser. The watched-network value reads
`No network chosen yet. Ask your admin to choose one.` in muted ink.

### 9.5 Scan running

```
│  Scan type                                                                               │
│  ┌───────┬──────────┬───────────┬─────┬──────┐                                           │
│  │ Quick │ Standard │ Extensive │ Max │ NSPi │                                           │
│  └───────┴──────────┴───────────┴─────┴──────┘                                           │
│  Same 1000 connection points, and also inspects …                                        │
│                                                                                          │
│  Running…                              ← replaces Scan now, takes focus, role="status"   │
```

The command's status replaces the `Scan now` control **on the same screen** and **takes keyboard
focus** (TRUTH acceptance criterion). The status is a plain `--ink` label following
queued → delivered → running → uploading → done. On `done` a `View scan` button appears beside it
linking to `/scans/:scanId`. On `failed` or `expired` the reason line and a `Retry` button appear
(admin only). Only this transition animates — Foundations §Motion: animate the rare, not the
constant.

### 9.6 Offline box

```
│  ← Back                                                                                  │
│  Old office                                                                              │
│  Offline · last report 14 Aug 2026                            ← whole line muted         │
│                                                                                          │
│  Watched network                                                                         │
│  172.16.0.0/24 (eth0)                                         [ Change ]                 │
│                                                                                          │
│  Scan type                                                                               │
│  ┌───────┬──────────┬───────────┬─────┬──────┐                                           │
│  │ Quick │ Standard │ Extensive │ Max │ NSPi │                                           │
│  └───────┴──────────┴───────────┴─────┴──────┘                                           │
│  Same 1000 connection points, and also inspects …                                        │
│                                                                                          │
│  [ Scan now ]                                                                            │
│  This box is offline. A scan will start when it reconnects.                              │
```

`Scan now` stays present — an admin may take the action; the queued command waits for the box,
and if it never arrives the command expires and says so. The muted line beneath states what will
happen. Nothing is disabled.

### 9.7 States summary

| State | Render |
| --- | --- |
| Loading | Skeleton for the identity block and the two sections. |
| Admin, network chosen | §9.1 |
| Viewer | §9.3 |
| Admin, no network | §9.4 |
| Viewer, no network | §9.4 note only |
| Scan running | §9.5 |
| Offline | §9.6 |
| Not found | `That device doesn't exist.` + `Back to devices` |
| Error | `Couldn't load this device.` + `Try again` |
| Save refused (stale subnet) | The chooser reopens with the refusal announced through the existing polite live region. |

### 9.8 Data

| Call | Fields |
| --- | --- |
| `GET /api/v1/agents/{agent_id}` | `agent_id`, `display_name`, `online`, `last_seen_at`, `available_subnets[]` (`interface`, `cidr`, `is_default_route`), `target_subnet`, `active_command_id` |
| `PATCH /api/v1/agents/{agent_id}` | body `UpdateAgentTargetSubnetRequest{ target_subnet }` |
| `POST /api/v1/agents/{agent_id}/commands` | body `CreateCommandRequest{ scan_mode, subnet }` → `CommandSummary{ command_id, scan_id, agent_id, status }` |
| `GET /api/v1/commands/{command_id}` | `CommandDetail`: `status`, `scan_id`, `error_code`, `completed_at` |

The box's **current scan type** has no field in `AgentDetail` — see open question **Q4**. Until
it lands, the tab strip opens on `Standard`, the type the daily scan ships with, and the screen
states no default anywhere (it must not, since it cannot read one).

### 9.9 Keyboard and focus

- Arrival, admin with a network: focus starts on the document body; first `Tab` reaches the nav.
  Tab order: nav → `Log out` → `Back` → `Change` → the tab strip (one stop; ← / → move between
  tabs per the `Tabs` roving-tabindex pattern) → `Scan now`.
- Arrival, admin with no network: focus starts on the first radio in the chooser. `Tab` order:
  radio group → `Set this network`. `Enter` inside the chooser submits it.
- After a successful save: focus moves to `Scan now`.
- After `Scan now` is pressed: focus moves to the command-status region (`tabIndex={-1}`,
  `role="status"`, `aria-live="polite"`).

### 9.10 Copy

| Where | String |
| --- | --- |
| Back link | `Back` |
| Title | `{display_name}` |
| Presence line | `Online · last report {time}` / `Offline · last report {time}` |
| Presence, never reported | `Offline · no report yet` |
| Section heading | `Watched network` |
| Change button | `Change` |
| No network, admin | (the chooser stands in its place) |
| No network, viewer | `No network chosen yet. Ask your admin to choose one.` |
| Chooser heading | `Which network should this box scan?` |
| Chooser body | `This box is connected to more than one network. Pick the one you want scanned; usually the office network, not the internet connection.` |
| Chooser submit | `Set this network` / `Saving…` |
| Section heading | `Scan type` |
| Tab labels | `Quick` · `Standard` · `Extensive` · `Max` · `NSPi` |
| Tab descriptions | verbatim, §9.2 |
| Primary action | `Scan now` / `Starting…` |
| Offline note | `This box is offline. A scan will start when it reconnects.` |
| Command done | `View scan` |
| Command failed / expired | `Retry`, plus the existing reason lines |
| Not found | `That device doesn't exist.` |
| Not-found link | `Back to devices` |
| Error | `Couldn't load this device.` |

The old `Set this Network` capital N is corrected to `Set this network`.

### 9.11 `data-testid`

Every `agents-*` id below is **kept** deliberately: these controls move screens but keep their
meaning, and `Agents.command.test.tsx`, `Agents.invalidation.test.tsx` and `Agents.test.tsx`
assert on them. The renamed ids are only those whose meaning changed.

| id | Element | Status |
| --- | --- | --- |
| `device-detail` | Page container | new |
| `device-detail-not-found`, `device-detail-back` | Not-found notice, link | new |
| `device-detail-error`, `device-detail-error-retry` | Error, retry | new |
| `agents-identity`, `agents-name`, `agents-presence` | Identity block | kept |
| `agents-network` | Watched-network value | kept |
| `agents-network-change` | `Change` button | kept |
| `agents-chooser`, `agents-chooser-confirm`, `agents-chooser-option-{interface}` | The chooser | kept |
| `agents-scan-now` | `Scan now` | kept |
| `agents-command-status`, `agents-view-scan`, `agents-retry` | Running-scan region | kept |
| `agents-pill` → `agents-status` | The command-status label | renamed — it is no longer a pill |
| `device-scan-type` | The `Tabs` root | new |
| `device-scan-type-{quick\|standard\|extensive\|max\|nspi}` | Each tab trigger | new |
| `device-scan-type-description` | The one-line description | new |
| `device-offline-note` | The offline note under `Scan now` | new |

---

## 10. Users (`/users`, admin only)

**Epicenter: the people table.** Restyle only; the behaviour and the dialogs are unchanged.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Users                                                                                   │
│                                                    ↕ step 12                             │
│  PERSON                       ROLE        STATUS       LAST SEEN                         │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  gui@ronthocorp.com           Admin ⌄     Active       Today 08:40                       │
│    You                                                                                   │
│  maria@ronthocorp.com         Viewer ⌄    Active       Yesterday 17:05          Remove   │
│  joao@ronthocorp.com          Viewer      Invited      —                        Revoke   │
│                                            Sent 1 Sep                                    │
│                                                    ↕ step 4                              │
│                                                            [ Invite a user ]             │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Column shares 34 / 14 / 18 / 20 / 14. Rows are fixed 56px. The role cell is a shadcn `Select`
with a **ghost, borderless trigger** — the text plus a small chevron close to it, **aligned with
the `ROLE` column header** (Foundations §Tables). Your own row and every invite row render the
role as plain text, on that same left edge.

The trailing column holds `Remove` (a member who is not you) or `Revoke` (an invite) as a small
outlined button, right-aligned. This is not a "View" column — Foundations forbids a trailing
*navigation* column, not a row action. The table itself does not navigate.

The screen's own action, `Invite a user`, sits **below the table, bottom-right**, sized about 5%
taller than the default control (Foundations §Cards & sections). On a list screen the table is
the epicenter.

### 10.1 States

| State | Render |
| --- | --- |
| Regular | As above. |
| Loading | Skeleton rows at the fixed 56px height. |
| Blank | `You're the only person here.` — one muted sentence, plus the `Invite a user` button below it. |
| Error | `Couldn't load your organisation.` + `Try again`. |
| Role change | Confirm dialog, unchanged copy. |
| Remove | `ConfirmByTyping` on the target's email, unchanged. |
| Revoke | Confirm dialog, unchanged. |
| Invite created | The dialog shows the one-time link with a copy control, unchanged. |
| Toast | On success, the existing toast copy, unchanged. |

### 10.2 Data

`GET /api/v1/users` → `OrgMemberListResponse` (`user_id`, `email`, `role`, `last_seen_at`);
`GET /api/v1/invites` → `PendingInviteListResponse` (`invite_id`, `email`, `role`, `expires_at`);
`PATCH /api/v1/users/{user_id}`, `DELETE /api/v1/users/{user_id}`,
`POST /api/v1/invites`, `DELETE /api/v1/invites/{invite_id}`.

### 10.3 Keyboard and focus

Nav → `Log out` → for each row: the role select (when present) → the row's `Remove`/`Revoke`
button → `Invite a user`. A dialog traps focus and returns it to the control that opened it.

### 10.4 `data-testid`

Every Users id is **kept**: `users-table`, `users-loading`, `users-blank`, `users-error`,
`users-error-retry`, `user-row-self`, `user-row-{id}`, `row-role-{id}`, `row-role-text-{id}`,
`row-status-{id}`, `row-last-seen-{id}`, `row-remove-{id}`, `row-revoke-{id}`, `invite-open`,
`invite-dialog`, `invite-email`, `invite-role`, `invite-submit`, `invite-created`, `invite-link`,
`invite-copy`, `invite-done`, `invite-again`, `invite-error`, `invite-role-note`,
`role-dialog`, `role-confirm`, `role-error`, `revoke-dialog`, `revoke-confirm`, `revoke-error`,
`confirm-by-typing-*`, `toast`.

---

## 11. Settings (`/settings`)

**Epicenter: your account.** Four sections, step `12` apart, no dashed rules between them —
spacing groups, rules decorate.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Settings                                                                                │
│                                                    ↕ step 12                             │
│  Your details                                                    ← title-sm              │
│  Email   gui@ronthocorp.com                                                              │
│  Role    Admin                                                                           │
│                                                    ↕ step 12                             │
│  Password                                                                                │
│  [ Change password ]                                                                     │
│                                                    ↕ step 12                             │
│  Activity                                                                                │
│  ▸ What's recorded?                                                                      │
│                                                    ↕ step 12                             │
│  Leave this organisation                                                                 │
│  Your account is deleted and you lose access to this organisation's scans, network       │
│  and vulnerabilities straight away. This can't be undone — an admin would have to        │
│  invite you again.                                                                       │
│  [ Delete my account ]                                                                   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

The `Delete my account` button keeps the destructive variant, restyled to Foundations: an
outlined button with `--edge` boundary and `--ink` text, no red fill. The confirmation is the
existing type-your-email dialog and carries the weight; a red button in the page is decoration
the design does not need.

### 11.1 States

| State | Render |
| --- | --- |
| Regular | As above. |
| Password changed | `Password changed.` in the polite live region under the button. |
| Password dialog | Current / new / confirm fields, unchanged copy and errors. |
| Leave, refused | `You're the only admin. Make someone else an admin first, then you can leave.` |
| Leave, failed | `Couldn't delete your account.` |
| Leave, succeeded | Navigates to `/login` with `Your account has been deleted.` |

### 11.2 Copy changes

Only two strings change, both vocabulary:

| Where | Was | Now |
| --- | --- | --- |
| Leave-section body | `…this organization's scans, hosts and findings straight away.` | `…this organisation's scans, network and vulnerabilities straight away.` |
| Section heading | `Leave this organization` | `Leave this organisation` |

Everything else — `Your details`, `Email`, `Role`, `Password`, `Change password`, `Activity`,
`What's recorded?`, the activity note, `Delete my account`, the dialog copy — is unchanged.

### 11.3 Keyboard and focus

Nav → `Log out` → `Change password` → the `What's recorded?` disclosure → `Delete my account`.
Each dialog traps focus and returns it to its trigger.

### 11.4 `data-testid`

All kept: `settings-idle`, `settings-details`, `settings-details-email`, `settings-details-role`,
`settings-password-trigger`, `settings-password-dialog`, `settings-current`, `settings-new`,
`settings-confirm`, `settings-new-hint`, `settings-current-error`, `settings-new-error`,
`settings-confirm-error`, `settings-error`, `settings-form`, `settings-submit`,
`settings-password-cancel`, `settings-success`, `settings-activity`, `settings-activity-label`,
`settings-activity-disclosure`, `settings-activity-caret`, `settings-activity-note`,
`settings-leave`, `settings-leave-body`, `settings-leave-trigger`, `confirm-by-typing-*`.

---

## 12. Auth screens

One shell for all four: the wordmark **"Dmitri"** at `--text-title-md`, then a white card at
`--radius` with step `6` padding, held to `--container-form` (384px), vertically placed with a
step `24` top offset. The `Ornament` is deleted. Rhythm: intra-group `2` (label→input),
inter-group `4` (field→field, field→button), inter-section `6` (card→secondary link).

### 12.1 Login (`/login`)

```
                          ┌───────────────────────────────────┐
                                       Dmitri
                          ┌───────────────────────────────────┐
                          │  Sign in                          │
                          │                                   │
                          │  Email                            │
                          │  [                            ]   │
                          │                                   │
                          │  Password                         │
                          │  [                            ]   │
                          │                                   │
                          │  [        Sign in             ]   │
                          └───────────────────────────────────┘
                                  Forgot password?
```

Error state: `That email and password don't match.` in `--ink` above the button (no red — the
message is the signal; there is one accent and it is not for errors). Service failure:
`Couldn't reach Dmitri. Try again in a moment.` Arrival messages (`Password set. Sign in with
your new password.` / `Your account has been deleted.`) render above the form in `--ink` and take
focus.

**Focus** starts in the `Email` field (`autoFocus`). Tab: Email → Password → `Sign in` →
`Forgot password?`. `Enter` in either field submits.

### 12.2 Forgot password (`/forgot-password`)

Idle: heading `Reset your password`, the sentence `Enter your email and we'll send you a link to
set a new password.`, one `Email` field, `Send reset link` / `Sending…`, then `Back to sign in`.

Sent: heading `Check your email.` with the body `If {email} has a Dmitri account, a reset link is
on its way. The link works once and expires shortly.` and `Back to sign in`. The heading takes
focus.

Focus starts in `Email`. On a service error, focus returns to `Email`.

### 12.3 Reset password (`/reset-password?token=`)

Idle: heading `Set a new password`, `New password` with the hint below it, `Confirm new
password`, `Set password` / `Setting your password…`.

Dead link: heading `This link has expired.`, body `Reset links work once and don't last long.`,
link `Request a new link`. The heading takes focus. Every error has a next step.

Focus starts in `New password`. A mismatch moves focus to `Confirm new password`; a policy
refusal moves it to `New password`.

### 12.4 Accept invite (`/invite?token=`)

Heading `Create your account`, the invited email and role shown as read-only context,
`Password` + hint, `Confirm password`, `Create account` / `Creating your account…`. Dead-token,
already-signed-in and loading states keep their existing copy and their existing testids.

### 12.5 Auth `data-testid`

Every auth id is **kept unchanged**: `login-form`, `login-email`, `login-password`,
`login-submit`, `login-error`, `login-success`, `login-route`; `forgot-idle`, `forgot-form`,
`forgot-email`, `forgot-submit`, `forgot-error`, `forgot-success`, `forgot-back`; `reset-idle`,
`reset-form`, `reset-password`, `reset-password-hint`, `reset-password-error`, `reset-confirm`,
`reset-confirm-error`, `reset-error`, `reset-submit`, `reset-dead`, `reset-request`;
`invite-ready`, `invite-form`, `invite-password`, `invite-password-hint`,
`invite-password-error`, `invite-confirm`, `invite-confirm-error`, `invite-submit`,
`invite-error`, `invite-account-error`, `invite-sign-in`, `invite-loading`, `invite-dead`,
`invite-signed-in`, `invite-sign-out`, `invite-retry`.

---

## 13. Not-found, and the browser title

`NotFound` keeps `not-found` and `not-found-home`, restyled: one sentence and one link back to
Home, step `24` top offset. The document title is `Dmitri` on every screen — per-page titles are
out of scope.

---

## 14. `data-testid` changes, in one place

Every id not listed here is unchanged.

| Old id | New id | Why it had to change |
| --- | --- | --- |
| `nav-hosts` | `nav-network` | The nav item and the route are renamed. |
| `nav-agents` | `nav-devices` | Same. |
| `hosts-page` | `network-page` | Same. |
| `hosts-table`, `hosts-table-row-*`, `hosts-table-sort-*` | `network-table`, `network-table-row-*`, `network-table-sort-*` | Same (`ListSurface` derives them from one `testId`). |
| `hosts-blank`, `hosts-error`, `hosts-error-retry`, `hosts-pagination`, `hosts-previous`, `hosts-next` | `network-…` | Same. |
| `agents-page` | `devices-page` | The route now renders a list of boxes, not one box. |
| `agents-loading`, `agents-blank`, `agents-blank-note`, `agents-error`, `agents-error-retry` | `devices-…` | Same. |
| `agents-pill` | `agents-status` | `StatusPill` is retired; the element is a plain label, not a pill. |
| `findings-table`, `findings-table-row-*`, `findings-table-panel-*` (Scan detail) | `findings-{severity}`, `findings-{severity}-row-*`, `findings-{severity}-panel-*` | One table became four severity cards; one id can no longer address them. The Network-detail copy keeps `host-findings-table`. |

**Retired with no replacement** — the element no longer exists: `scans-range`, `hosts-range`, `ornament`, `home-deck`,
`home-deck-card`, `home-deck-prev`, `home-deck-next`, `home-deck-position`, `home-item-severity`,
`home-footer`, `home-footer-scan`, `home-footer-pi`, `home-stub`, `agents-card`, `agents-note`,
`agents-scans-link`, `agents-hosts-link`, `scan-hosts-open-{host_id}`,
`scan-hosts-ports-{host_id}`, `host-ports-panel-{host_id}`.

**New:** `home-table`, `home-table-row-*`, `scan-summary-strip`, `network-quiet-group`,
`network-quiet-toggle`, `devices-table`, `devices-table-row-*`, `device-detail`,
`device-detail-back`, `device-detail-not-found`, `device-detail-error`,
`device-detail-error-retry`, `device-scan-type`, `device-scan-type-{mode}`,
`device-scan-type-description`, `device-offline-note`, `user-identity`.

---

## 15. Contract endpoints and fields, in one place

Nothing new is asked of the API. Every field below exists in
`frontend/src/types/openapi.d.ts` today.

| Screen | Endpoint | Fields |
| --- | --- | --- |
| Home | `GET /scans`, `GET /findings?scan_id&severity` | `scan_id`, `timestamp`, `status`; `finding_id`, `title`, `cve_id`, `host_ip`, `severity`, `detected_at`, `total` |
| Scans | `GET /scans` | `scan_id`, `timestamp`, `scan_mode`, `status`, `host_count`, `finding_count`, `highest_severity`, `total`, `page` |
| Scan detail | `GET /scans/{scan_id}` | `ScanDetailResponse` in full, less `metadata` |
| Network | `GET /hosts` | `host_id`, `hostname`, `ip`, `mac`, `vendor`, `open_ports_count`, `highest_severity`, `last_seen_at`, `total` |
| Network detail | `GET /hosts/{host_id}`, `GET /findings?host_id` | `HostDetailResponse`, `FindingRecord` |
| Devices | `GET /agents` | `agent_id`, `display_name`, `online`, `last_seen_at`, `target_subnet` |
| Device detail | `GET /agents/{id}`, `PATCH /agents/{id}`, `POST /agents/{id}/commands`, `GET /commands/{id}` | `AgentDetail`, `UpdateAgentTargetSubnetRequest`, `CreateCommandRequest`, `CommandDetail` |
| Users | `GET/PATCH/DELETE /users`, `GET/POST/DELETE /invites` | `OrgMember`, `PendingInvite` |
| Settings | `GET /users/me`, `POST /auth/change-password`, `DELETE /users/{id}` | `UserProfileResponse` |
| Auth | `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`, `/invites/lookup`, `/invites/accept` | as today |

`first_seen_at` on a finding, a scan's duration, a per-machine vulnerability count, a service's
last-seen time and a scan's owning box **have no field**, which is why none of them is drawn.

---

## 16. Out of scope, deliberately

This feature restyles. It adds exactly two screens, because the owner moved a setting onto the
thing it belongs to. It adds nothing else.

- **Scan duration, new-versus-known scan results, and a Box column on Scans.** No data.
- **A box's own scan history on Device detail.** Scans are not attributed to a box yet.
- **Machine type classification, per-machine vulnerability counts, service last-seen,
  vulnerability first-seen.** No data.
- **The Home events panel and the Home activity log.** No data.
- **The "Daily scan uses:" line, the "Use this scan type" button and its confirm dialog.**
  DMI-133.
- **Search, filters and column pickers on Network.** "Later, not MVP" in `docs/ui/status.md`.
- **Multi-box scheduling, per-box notifications, and any per-box setting beyond the watched
  network and the scan type.**
- **Dark theme, tablet and mobile layouts, per-page browser titles.**
- **Backend and hardware-agent changes.** No API contract is altered.

None of these is drawn as a placeholder, an empty column or a greyed control.

---

## 17. Open questions for the approval gate

**Q1 — RESOLVED: ship the IP.** Owner, 2026-09-02: ship the address now; a friendly hostname is a
later improvement, tracked on the machine-inventory follow-up issue. Original question below.

**Q1 — The Home attention table's Machine column shows an IP, not a name.**
`FindingRecord` carries `host_ip` but no hostname, so the row reads `192.168.1.51` where the
exemplar reads `Front-door camera`. Joining against `GET /hosts` would give the friendly name at
the cost of one more request on the product's first screen. Ship the IP, or add the join?
*Recommendation: ship the IP now.* It is real, and the row's destination shows the name.

**Q2 — STILL OPEN, and it is about machines, not boxes.** `GET /hosts` paginates the customer's
network at 20 per page; an office network passes 20 machines easily. Needs the owner's answer.
Original question below.

**Q2 — "Not seen recently (N)" is computed over the current page.**
`GET /hosts` paginates at 20 with no quiet/active split, so the group holds the quiet machines
**on the page you are looking at** and `N` is that page's count. The default `last_seen_at desc`
sort sinks quiet machines to the last page, so the common case reads correctly, but an
organisation with more than 20 devices can see the group appear on more than one page. A correct
version needs a server-side split. Accept the page-local grouping for v1?

**Q3 — RESOLVED: keep the email.** Owner, 2026-09-02: the email ships, truncated with an ellipsis
if it crowds the bar (full value in `title`). `FOUNDATIONS.md` §Chrome is amended to say email
(Task 12). Original question below.

**Q3 — The top bar shows an email, not a name.**
Foundations §Chrome says "the user's name". `UserProfileResponse` has `user_id`, `email` and
`role` — there is no name. The bar ships the email. Is that the intended reading of Foundations,
or should §Chrome be amended to say "the user's email"?

**Q4 — RESOLVED: open on `Standard` and claim no default.** Confirmed by `TRUTH.md`'s
*"No default is claimed"* criterion. Original question below.

**Q4 — A box's current scan type cannot be read.**
`AgentDetail` carries `target_subnet` but no scan-type field, so Device detail cannot show the
box's actual default; the tab strip opens on `Standard`. TRUTH's criterion "the selection has
reverted to the box's default" is therefore satisfied only against a hard-coded `Standard`.
This is the same gap DMI-133 must close. Confirm that opening on `Standard` is acceptable for
v1, and that Device detail must state no default anywhere until the field exists.

**Q5 — RESOLVED: keep it.** Owner, 2026-09-02. Original question below.

**Q5 — Settings keeps its Activity disclosure.**
The task named three Settings sections: account, password, leave organisation. The screen also
ships an Activity disclosure today. Removing it is a product change, not a restyle, so it is
retained as a fourth section. Confirm, or say to remove it.

**Q6 — RESOLVED: confirmed, and the flow is already a modal.** Owner, 2026-09-02 asked for the
delete-account flow to be a modal; `ConfirmByTyping` already composes `DialogShell`, so nothing new
is built — it inherits the regenerated `ui/dialog` and the new tokens (Tasks 3 and 11). The button
loses its red fill. Original question below.

**Q6 — `Delete my account` loses its red fill.**
Foundations ships one accent and no semantic colours. The destructive button becomes a plain
outlined button; the type-your-own-email confirmation carries the weight. Confirm.
