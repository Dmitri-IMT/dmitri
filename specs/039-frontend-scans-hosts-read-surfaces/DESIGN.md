# DESIGN — Scans and Hosts read surfaces (`/scans`, `/hosts`, `/agents`)

React web screens. Copy and interaction, not pixels.

**`docs/ui/SCREENS.md` §§ SCAN LIST, SCAN DETAIL, HOST INVENTORY, HOST DETAIL, AGENTS are the
source of truth for these screens** and are **not** restated here. Their per-screen copy tables,
epicenter reasoning, column lists and state lists stand as written; read them alongside this
document. §Foundations — two faces, six neutrals, purple accent, light only, the spacing steps,
the nine consistency rules — is inherited and never re-decided.

This document specifies only what SCREENS.md leaves open: the `DataTable` component and every one
of its states, the three other shared components this feature creates, the `/agents` screen, the
top bar at six items, the finding panel as one spec for two call sites, sort and pagination
together, and two deliberate divergences.

Behaviour: [`TRUTH.md`](TRUTH.md). Where this document and `SCREENS.md` disagree, `SCREENS.md`
wins **except** at the two divergences in §12, which are argued there and are the shape that ships.

## Rendered preview — the approvable artefact

**https://claude.ai/code/artifact/3db23fb4-6cbd-461e-95e7-fc764e72d90b**

Fifteen plates, drawn with the product's own tokens from `frontend/src/index.css` and its two real
faces, at the 1120px frame. The ASCII below is structural notes; the preview is what gets approved.
Plate numbers match the section numbers here.

**The human performs the visual check and it closes this feature** (TRUTH business rule 13). No
agent signs off on how this looks. Plate 15 lists the five calls worth a deliberate look.

---

## 0. What is new here

Four screens, but the work is one component and three small ones. `SCREENS.md` §Shared components
names `DataTable`, `EmptyState`, `LoadingSkeleton` and `StatusPill` as foundations and specifies
none of them. Every table-led screen after this feature inherits whatever this feature builds, so
the component design is the deliverable and the four screens are its call sites.

`DataTable` is **one** component with a discriminated row action:

```ts
rowAction: { kind: 'link'; to: string } | { kind: 'expand'; panel: ReactNode } | undefined
```

Seven tables, three behaviours:

| Table | `rowAction` | Sortable head |
|---|---|---|
| Scan list | `link` → `/scans/:scanId` | no — the run log is chronological |
| Host inventory | `link` → `/hosts/:hostId` | **yes** — Host, IP, Vendor, Last seen |
| Host detail · scan history | `link` → `/scans/:scanId` | no |
| Scan detail · findings | `expand` (finding panel) | no |
| Scan detail · hosts | `expand` (ports + host link) | no |
| Host detail · findings | `expand` (finding panel) | no |
| Host detail · ports | `undefined` — inert | no |

Two other things are new to the product: **nothing sorted before this**, so the sort affordance is
designed from scratch (§3.2); and **nothing paginated before this**, so the pagination footer is
designed here too (§5.5).

---

## 1. Screen flow

```
TopBar ─┬─> /scans ──row──> /scans/:scanId ──host row (expand) ──[Open <host>]──> /hosts/:hostId
        │      ▲                   │                                                    │
        │      │                   └── finding row ──> panel opens in place (no navigation)
        │      │
        ├─> /hosts ─row──> /hosts/:hostId ── history row ────────> /scans/:scanId
        │                        └── finding row ──> panel opens in place
        │
        └─> /agents  (no outbound action; two links back to /scans and /hosts)

Home  ──[View finding]──> /scans/:scanId?finding=:findingId   (that row opens, page does not fetch twice)

/scans/:scanId  404 ──> "That scan doesn't exist." ──[Back to scans]──> /scans
/hosts/:hostId  404 ──> "That host doesn't exist." ──[Back to hosts]──> /hosts
```

All five routes are inside the shell and readable by **both roles**. Nothing on them is role-gated,
so no screen here has an admin variant and no `AdminOnly` wrapper appears in any of them.

`/hosts` and `/scans` carry their list state in **component state**, not in the URL — locked
decision 3, recorded in `ARCHITECTURE.md` §2.3. The consequence is designed, not accidental: a
reload, a back-navigation from a detail page, or a shared link returns to page 1 in the default
ordering. Moving this state into the URL is a later change, not a per-screen one.

---

## 2. The top bar at six items — Plate 1

```text
+--------------------------------------------------------------------------------+
| DMITRI      Home  Scans  Hosts  Agents  Users  Settings            [Log out]    |   admin
+--------------------------------------------------------------------------------+
| DMITRI        Home  Scans  Hosts  Agents  Settings                 [Log out]    |   viewer
+--------------------------------------------------------------------------------+
              ^                                        ^
       nav centred on the FRAME, not on the leftover space
```

The count goes from three to six for the first time. Nothing about the bar changes: it is still the
`1fr auto 1fr` grid, still centred on the frame, and losing `Users` for a viewer moves nothing else
— that is the whole point of measuring the centre against the frame rather than against the space
the wordmark leaves over.

Three items are added in nav order — `Scans`, `Hosts`, `Agents` — between `Home` and `Users`. Order
is the reading order of the product: the verdict, then the runs, then the machines, then the box
that produces them, then administration.

Six items at `text-nav` (11px) with a step-4 gap measure roughly 330px, plus a ~60px wordmark and a
~70px button. At the 1280px minimum the frame is 1120px, so the bar keeps clear space either side
of the nav; no wrap, no truncation, no overflow rule needed. The active item is the only purple on
any of these screens.

---

## 3. `DataTable` and the three components beside it

### 3.1 Anatomy — Plate 2

```text
  HOST            IP             MAC                VENDOR        PORTS   HIGHEST SEVERITY
  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -   ← dashed
  synology-nas    192.168.0.42   00:11:32:AA:BB:CC  Synology          4   [ Critical ]
  ─────────────────────────────────────────────────────────────────────────────────────   ← solid
  pi-lab          192.168.0.17   DC:A6:32:11:22:33  Raspberry Pi      2   [ High ]
  ─────────────────────────────────────────────────────────────────────────────────────
  (unnamed)       192.168.0.88   —                  Apple             1   —
```

| Part | Decision |
|---|---|
| Outer chrome | **None.** No border, no card, no shadow, no zebra. The rules are the only structure. |
| Head | `text-caption-md`, uppercase, letterspaced, `--ink-muted`, `font-weight: normal`, left-aligned, row height step 8 (32px). |
| Head separator | A **dashed** hairline at `--rule`. |
| Row separator | A **solid** hairline at `--rule`; no rule above the first row or below the last. |
| Row height | Step 8 (32px), one line. Rows never grow to fit; cells truncate. |
| Cell padding | Step 4 to the right of every cell. No left padding — the leading cell holds the table's left edge, which is the frame's left edge. |
| Numeric cells | Right-aligned, `tabular-nums`. |
| Column widths | `table-fixed` + a `colgroup` of **percentage shares**. Never pixels: the row scales with the frame. |
| Outer margin | **None.** The component renders flush to its own box; the screen supplies the space around it (§7). |

One dash weight distinguishes head from body, so the head needs no second colour and no background
fill. Dashed-for-structure is already the house idiom — `/settings` separates its sections the same
way.

### 3.2 The sort header — Plate 3

Nothing in the product sorts today, so this affordance is designed here.

```text
   idle          hover           focus-visible      sorted asc      sorted desc
  ┌───────────┐ ┌───────────┐   ┌───────────┐      ┌───────────┐   ┌───────────┐
  │ HOST  ▴▾  │ │ HOST  ▴▾  │   │ HOST  ▴▾  │      │ HOST   ▴  │   │ LAST SEEN ▾│
  │  muted    │ │ ‾‾‾‾ ink  │   │ ‾‾‾‾ +ring│      │  ink      │   │  ink       │
  └───────────┘ └───────────┘   └───────────┘      └───────────┘   └───────────┘
   chevrons      chevrons        same underline     single solid    single solid
   at --rule     at --ink-muted  the pointer gets   caret, ink      caret, ink
```

| State | Owes |
|---|---|
| Rest | A `<button>` inside the `<th>`: muted label plus a paired chevron glyph at `--rule`. Faint, but present — the column must never look like plain text. |
| Hover | `cursor: pointer`, label to full `--ink`, underline at offset 3, chevrons to `--ink-muted`. |
| Focus-visible | The `--ring` at `ring-3`, **plus** the same underline hover gets. |
| Active | The label's underline thickens on press; no nudge (a nudge inside a table head shifts the column). |
| Disabled | Does not exist. A column that cannot be sorted has no button at all. |

**The active column is marked by contrast and weight, not by purple.** Accent is the nav item, the
primary button and the Home review label; spending it on a sort caret would put a second focal
point on a screen that already has one. Full-ink label + a single solid caret is a bigger visual
step than a hue change would be anyway.

`aria-sort` on the `<th>` is `ascending` / `descending` / `none`, so the state is announced and not
only drawn. Non-sortable columns (MAC, Ports, Highest severity) render as plain `<th>` text — the
absence of the affordance is itself the honest signal that the server does not offer that ordering.

**Direction rules.** First activation of an idle column applies that column's *natural* first
direction: `asc` for Host, IP and Vendor (A→Z is how you look something up), `desc` for Last seen
(newest first is what "last seen" means). Activating the already-sorted column flips it. There is
no third click that clears the sort — the list always has an ordering, and `last_seen_at desc` is
the default.

**Changing sort returns to page 1**, always (TRUTH rule 16). A page number means nothing across two
orderings.

**The server sorts.** The page in hand is never re-ordered in the browser. Every activation is a
new request with new `sort_by` / `sort_order` and `page=1`.

### 3.3 The link row — Plate 4

| State | Treatment |
|---|---|
| Rest | Nothing. On a table of link rows, a permanent affordance on every row is noise. |
| Hover | Background to `--card` white on `--paper` — separation by warmth, the only wash the palette offers — **plus an underline on the leading cell**, so the row reads as a link and not as a highlight. `cursor: pointer`. |
| Focus-visible | The `--ring`, drawn inset on the row, **plus** the same wash and underline. The keyboard is never worse off than the pointer. |
| Active | The wash deepens toward `--rule`. **No 1px nudge** — nudging a table row shifts every cell in it. |
| Disabled | Does not exist. |

Whole rows navigate (consistency rule 4): a real `<a>` in the leading cell stretches over the row,
so middle-click, right-click → open in new tab, and the status-bar URL preview all work. There is
no trailing "View" column anywhere in this feature.

### 3.4 The expand row — Plate 5

```text
  ▸ [ Critical ]  PHP CGI argument injection      synology-nas   443   CVE-2024-4577    ← closed
  ▾ [ Critical ]  PHP CGI argument injection      synology-nas   443   CVE-2024-4577    ← open
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │  the panel, full width of the table, on --card                                   │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

The caret sits first in the leading cell and **rotates 90°** when open — the same transform
`Disclosure` already ships, so the gesture is learned once in the product. The open row keeps the
`--card` wash so the row and its panel read as one object; a dashed hairline closes the panel off
from the next row. The panel lives in a `<tr><td colspan>` beneath its row, so it never breaks the
column grid.

The row is the toggle: `aria-expanded`, `aria-controls` pointing at the panel. Hover and
focus-visible are the link row's, minus the underline (there is nothing to navigate to).

**More than one row may be open at once.** Comparing two findings on a host is a real thing to do,
and closing one row because another opened is the kind of helpfulness that loses the operator's
place. Nothing collapses on its own.

**The inert row** (`rowAction: undefined`, the ports table) has no caret, no wash, no pointer and
no focus stop. A table of facts is a table of facts.

### 3.5 `LoadingSkeleton` — Plate 6

Headings are real; only the body is stood in for. Five rows at the real row height.

- Bars are **`--rule`**, not `--muted`. On this palette `--muted` resolves to `--card` white, and a
  white skeleton on paper is an invisible one. This is worth stating because
  `pages/users/DirectoryTable.tsx` currently uses `bg-muted` and is, in practice, drawing nothing.
- Widths are **fixed per column** (60–90% of the column), so the block never reflows between
  renders. Not random.
- **No pulse, no shimmer.** Motion in this product is a transform that outlasts nothing; an
  animation that runs for the length of a request is exactly what §Interaction states rules out.
- **First load only** (TRUTH rule 25). A refetch of something already on screen never blanks it.

### 3.6 `EmptyState` — Plate 6, Plate 9

Two variants, one component.

| Variant | Shape | Used by |
|---|---|---|
| `inline` | Replaces the table body, **keeps** the headings, one muted sentence at step 12 of vertical room. | a table that is legitimately empty but whose columns still describe the shape of the answer |
| `page` | Replaces the table entirely: IM Fell heading at `text-title-sm`, body and note in muted `text-body-md` held to 65 characters, `Ornament` beneath, centred, step 6 between lines and **step 16 of paper above and below**. | Scans blank, Hosts blank |

Where the copy is **positive** — "No findings. Every host in this scan came back clean.", "No open
ports. This host isn't exposing anything." — the headings go too. Column names standing over good
news read as a table that failed to load.

**`EmptyState` takes no action prop.** Not an optional one, not an unused one. Nothing in this
feature has a button to put in it (§12), and the prop is added when DMI-89 has one.

### 3.7 `StatusPill` — Plate 7

Scan status only. The seven-state command lifecycle is DMI-89's and is out of scope.

| Variant | Copy | Treatment |
|---|---|---|
| `pending` / `accepted` / `processing` | `Running…` | Square, hairline `--edge`, `--ink-muted` text, **no fill**. Not good news or bad news — not news yet. |
| `failed` | `Failed` | Square, hairline `--sev-critical`, `--sev-critical` text, **no fill**. |
| `completed` | `Completed` | Square, hairline `--rule`, `--ink-muted` text, **no fill**. The quietest of the three. |

**The completed pill is a correction to `SCREENS.md`, settled at the visual gate 2026-08-26.** The
copy table there specifies `—` in the Status cell of a finished scan, on the reasoning that the
counts beside it are the answer. Against the rendered plate that reads as *missing data* rather
than as *this worked* — an em dash everywhere else in this product means "the product looked and
there was nothing to see" (§4), which is the wrong sentence about a scan that succeeded.

It is deliberately **not green.** This palette's only colors are the four severity ramps, so a
success color would be a new Foundations token, and it would sit two columns from the severity
badge and compete with the one thing on the row that has earned color. Neutral ink at a `--rule`
hairline says "finished, nothing to report" without raising its voice — which is also why the
completed pill is the quietest of the three despite being the most common.

Square, `text-caption-md`, padding step 2 across and step 1 down — the same geometry as
`SeverityBadge`, deliberately, so the two read as one family. And deliberately a **different
fill**: severity badges carry a 10% tint, status pills are outline-only. That one difference is
what keeps a red `Failed` from being read as a severity, which matters because severity owns red in
this product and a lifecycle state must not borrow its meaning.

The pill is **not interactive** and declares no hover, focus, active or disabled state.

---

## 4. Long values and absent values

- Every cell is `max-w-0 truncate` inside a `table-fixed` grid, with the full value in `title`.
- UUIDs render as their first eight characters with the full value in `title` (consistency rule 6),
  and never wrap.
- Evidence inside the finding panel is the one exception: it is not truncated. It sits in its own
  bordered block with `overflow-x: auto`, so a request line scrolls rather than wrapping mid-token.
- A table wider than the frame scrolls inside its own container. The page body never scrolls
  sideways.
- **Absent is an em dash in muted ink, never a blank cell** — `mac: null`, `highest_severity: null`,
  `version: null`, and every cell of an unfinished or failed scan's row. A blank cell reads as a
  rendering bug; the em dash says the product looked and there was nothing to see.
- `hostname` empty → `(unnamed)`, muted, in the Host cell. The row is otherwise normal: the machine
  is real, one identifier is not observable.
- A **zero** is not an absence. A completed scan with no findings reads `None` under Findings and
  `—` under Highest severity, and those two cells are saying different things.

---

## 5. The screens

### 5.1 Scans — regular — Plate 8

```text
+------------------------------------------------------------------------------------+
| DMITRI      Home  Scans  Hosts  Agents  Users  Settings              [Log out]      |
+====================================================================================+
|                                                                                    |
|   Scans                                                                            |
|   ──────────────────────────────────────────────────────────────────────────────   |
|                                                                                    |
|   WHEN              MODE    STATUS        HOSTS  FINDINGS   HIGHEST SEVERITY        |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -      |
|   2 min ago         quick   [Running…]        —         —   —                       |
|   yesterday 21:40   quick   [Completed]      12         3   [ Critical ]            |
|   Jul 11, 21:40     quick   [Completed]      12      None   —                       |
|   Jul 10, 21:40     quick   [Failed]          —         —   —                       |
|   Jul 9, 21:40      quick   [Completed]      11         1   [ Medium ]              |
|                                                                                    |
|   Showing 1–20 of 47                              ░░Previous░░   [ Next ]           |
+------------------------------------------------------------------------------------+
```

All four row kinds in one view. The running scan shows its state **in place of** its counts and
carries no severity — three em dashes, because a scan that has not looked yet must never render as
a scan that found nothing (TRUTH rule 3). The failed row does the same.

Regions, top to bottom: `PageHeader` ("Scans", rule beneath, no subtitle) → the table → the
pagination footer. The head is not sortable: the run log is chronological, fixed, and offers no
other ordering.

**Pagination footer.** Count left (`Showing 1–20 of 47`), controls right. `[Previous]` on page 1
and `[Next]` on the last page are **greyed, unclickable and out of the tab order** rather than
removed. This is the §Consistency rule 3 *progress* carve-out, not the permission rule: the
operator is allowed to page, the precondition just isn't met, and a footer whose controls change
position between pages is worse than a greyed one. When `total <= per_page` the entire footer is
absent — SCREENS.md's mock shows "Showing 1–20 of 12", which is a line that should never render.

### 5.2 Scans — blank and error — Plate 9

```text
|   Scans                              |     |   Scans                              |
|   ────────────────────────────────   |     |   ────────────────────────────────   |
|                                      |     |                                      |
|            (step 16 of paper)        |     |            (step 16 of paper)        |
|            No scans yet.             |     |     Couldn't load the scans.         |
|   Dmitri scans your network for      |     |          [ Retry ]                   |
|   devices and known vulnerabilities. |     |            (step 16)                 |
|   Every scan you run shows up here.  |     |                                      |
|   Scanning is set up on the Pi       |     |
|   itself.                            |     |
|          ───────◆───────             |     |
|            (step 16 of paper)        |     |
```

**No CTA, for either role** — the first divergence, argued in §12. The third line is the sentence
`HomeBlank` already ships, verbatim, so the two blank slates tell one story. With no action to
gate, the admin and the viewer see the identical screen; there is no admin/viewer split here at
all.

Both blocks get step 16 above and below. On a screen whose regular state is a dense table, the
empty one is mostly room; an implementer told nothing would pack it to the top and it would read as
a page that failed rather than a page with nothing in it yet.

The error state renders **no rows**, whatever partial data is in hand. A run log missing rows reads
as a complete answer to "what has this thing been doing" while being a wrong one.

Hosts blank and Hosts error are the same two shapes with the copy from `SCREENS.md` § HOST
INVENTORY, and the same removed CTA.

### 5.3 Scan detail — regular — Plate 10

```text
|   Scan — yesterday 21:40                                                           |
|   quick mode · 192.168.0.0/24 · 12 hosts · 3 findings                    (muted)   |
|   ──────────────────────────────────────────────────────────────────────────────   |
|                                                                                    |
|   Findings                                                                         |
|   SEVERITY     FINDING                        HOST          PORT   CVE             |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -      |
|   ▸ [Critical] PHP CGI argument injection     synology-nas    443   CVE-2024-4577   |
|   ▸ [High]     OpenSSH pre-auth double free   pi-lab           22   CVE-2023-38408  |
|   ▸ [Low]      Telnet service reachable       printer-hp       23   —               |
|                                    (step 12)                                       |
|   Hosts                                                                            |
|   HOST           IP             MAC                VENDOR        OPEN PORTS        |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -      |
|   ▾ synology-nas  192.168.0.42   00:11:32:AA:BB:CC  Synology               4        |
|   ┌──────────────────────────────────────────────────────────────────────┐         |
|   │  PORT  PROTOCOL  SERVICE  VERSION                                    │         |
|   │    22  tcp       ssh      OpenSSH 8.4p1                              │         |
|   │   443  tcp       https    nginx 1.18.0                               │         |
|   │  5000  tcp       http     Synology DSM                               │         |
|   │  [ Open synology-nas ]                                               │         |
|   └──────────────────────────────────────────────────────────────────────┘         |
|   ▸ pi-lab        192.168.0.17   DC:A6:32:11:22:33  Raspberry Pi          2        |
```

Findings above hosts, ordered worst-first: findings are the epicenter, hosts are context, and the
host table reads as the quieter of the two. Sections are separated by step 12 of paper and an IM
Fell heading — **no rules between them**. On a near-monochrome surface, space says it more quietly
than a line, and this screen's sections are tall enough for space to carry the grouping.

**Two standing rules meet on the host row.** TRUTH rule 8 says a host row opens its ports in place;
rule 12 says a host row links to that host's page. One row cannot have two activations, and a link
nested inside a row-level toggle is neither valid DOM nor operable by keyboard. Resolution: **the
row expands, and the panel carries `Open <hostname>` as an explicit destination.** The port list
inside the panel is the same `DataTable` with `rowAction: undefined` — no caret, no wash, no
pointer.

### 5.4 Scan detail — unfinished, failed, clean — Plate 11

```text
|   Scan — 2 min ago                   |  |   Scan — Jul 10, 21:40                  |
|   quick mode · 192.168.0.0/24        |  |   quick mode · 192.168.0.0/24           |
|   ────────────────────────────────   |  |   ───────────────────────────────────   |
|            (step 16)                 |  |            (step 16)                    |
|          [ Running… ]                |  |          [ Failed ]                     |
|      This scan is still running.     |  |    This scan didn't finish.             |
|   Findings appear here when it       |  |    The Pi stopped responding while the  |
|   finishes. This page doesn't        |  |    scan was running. Check that it's    |
|   update on its own.                 |  |    powered on and online, then try      |
|        [ Check again ]               |  |    again.                               |
|            (step 16)                 |  |            (step 16)                    |
```

**Unfinished — the second divergence (§12).** Nothing here polls, so the page is honest about it:
it says so, and gives a `Check again` that re-reads this one scan. In flight the button reads
`Checking…`. A page that silently never changes while the operator waits is the version that loses
trust; a manual re-read is not a timer and does not violate TRUTH rule 27.

Both tables are suppressed. An unfinished scan has no hosts either, and an empty table would
present an absence as an answer.

**Failed — the failure is the page.** The reason comes from `scanFailureReason(error_code)` in
`frontend/src/lib/scanFailureReasons.ts` — the approved DMI-75 deck — and never from the raw code.
Every sentence in that deck already ends with the operator's next step, which is why there is no
`[Try another scan]` button (§12). With no `error_code` the same function returns the `unknown`
sentence; SCREENS.md's separate "no `command_id`" line is superseded by the deck, which is exactly
what C10's resolution moved this copy to. Both tables are suppressed.

**Clean** keeps the section headings and states the good news in a sentence — "No findings. Every
host in this scan came back clean." — with the host table carrying the page. There is no empty
findings table anywhere in this product.

### 5.5 Hosts — sort and pagination together — Plate 12

```text
|   Hosts                                                                            |
|   Every device Dmitri has found on your network.                         (muted)   |
|   ──────────────────────────────────────────────────────────────────────────────   |
|                                                                                    |
|   HOST ▴     IP ▴▾      MAC          VENDOR ▴▾   PORTS  HIGHEST   LAST SEEN ▴▾      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -      |
|   (unnamed)  192.168.0.88   —         Apple          1  —         Jul 9, 21:40      |
|   pi-lab     192.168.0.17   DC:A6:…   Raspberry      2  [High]    2 min ago         |
|   printer-hp 192.168.0.31   3C:D9:…   HP             3  [Low]     2 min ago         |
|   synology-… 192.168.0.42   00:11:…   Synology       4  [Critical] 2 min ago        |
|   unifi-udm  192.168.0.1    78:8A:…   Ubiquiti       3  [Medium]  2 min ago         |
|                                                                                    |
|   Showing 1–20 of 34                              ░░Previous░░   [ Next ]           |
```

**Sorting lives in the head; paging lives in the foot.** That is the whole answer to how the two
coexist: they never compete for the same strip of the page and no separate toolbar is needed.
SCREENS.md mocks the footer alone; nothing else about it changes.

Four columns sort — Host, IP, Vendor, Last seen — because those are the four the contract's
`HostSortBy` offers. MAC, Ports and Highest severity carry no affordance and stay plain headings.

Shown sorted by Host ascending, and therefore on **page 1**: every sort change resets the page
(TRUTH rule 16), and the count line re-reads from 1. `(unnamed)` sorts wherever the server puts it;
the client does not special-case it.

### 5.6 Host detail — Plate 13

```text
|   synology-nas                                                                     |
|   192.168.0.42 · 00:11:32:AA:BB:CC · Synology                            (muted)   |
|   First seen Jul 3, 21:40 · last seen 2 min ago                          (muted)   |
|   ──────────────────────────────────────────────────────────────────────────────   |
|   Findings                                                                         |
|   SEVERITY     FINDING                              PORT   CVE                     |
|   ▸ [Critical] PHP CGI argument injection            443   CVE-2024-4577           |
|   ▸ [Medium]   TLS certificate expired              5001   —                       |
|                                    (step 12)                                       |
|   Open ports                                                                       |
|   PORT  PROTOCOL  SERVICE  VERSION                                                 |
|     22  tcp       ssh      OpenSSH 8.4p1                                           |
|    443  tcp       https    nginx 1.18.0                                            |
|   5001  tcp       https    —                                                       |
|                                    (step 12)                                       |
|   Seen in these scans                                                              |
|   WHEN              MODE    OPEN PORTS   HIGHEST SEVERITY                          |
|   yesterday 21:40   quick            4   [ Critical ]                              |
|   Jul 11, 21:40     quick            4   —                                         |
```

Three tables, three different row actions, one component: findings expand, ports are inert, history
navigates. Identity is a header — the name in IM Fell, then two muted lines carrying the addresses
and the dates — and the page's weight sits on what the machine exposes.

**The findings table drops the Host column** that scan detail carries. Every row on this page is
the same host; repeating it is a column of one repeated value. Context over consistency (§9) — the
panel is byte-identical, only the row's columns differ.

**Findings are a second request, so that section owns its own three states.** It can be loading,
empty or failed while the ports and history around it are fine, and a failed findings section shows
its own retry without taking the page down: the ports are still a complete answer to "what does
this thing expose". This is the only place in the feature where two independent reads share one
screen, and treating it as one page-level state would throw away good data.

### 5.7 Agents — Plate 14

```text
|   Agents                                                                           |
|   The Dmitri box on your network.                                        (muted)   |
|   ──────────────────────────────────────────────────────────────────────────────   |
|                                                                                    |
|                             (step 16 of paper)                                     |
|                    Scanning is set up on the Pi itself.                            |
|                                                                                    |
|            The Dmitri box is installed and configured on site. It scans            |
|            the network it is connected to and uploads what it finds here.          |
|                                                                                    |
|            Every scan it runs appears under Scans, and every device it             |
|            finds appears under Hosts.                                              |
|                                                                                    |
|                             ───────◆───────                                        |
|                             (step 16 of paper)                                     |
```

One state, no controls. The screen **reads nothing**, so it has one state by construction: no
loading, no empty, no error. It exists so the navigation names a real destination and so every
blank state in the product tells the same story — this is the sentence `HomeBlank` and both blank
tables point at, said in full and in the same voice.

**Every sentence is permanently true.** Nothing says "coming soon", nothing describes a control
that does not exist, and nothing needs deleting when the trigger ships: DMI-89 **adds the agent's
live row and `Scan now` above this text**, and the text stays underneath as the explanation of
where scanning is configured. A "this is coming" line would have been the one thing that had to be
removed, which is why there isn't one.

`Scans` and `Hosts` are real links, so the screen has a job today instead of being a dead end.

---

## 6. The finding panel — Plate 5

One spec, two call sites. SCREENS.md sketches it inside the scan-detail layout; it is used
identically on host detail, and this is the specification both consume.

```text
  ▾ [Critical]  PHP CGI argument injection      synology-nas    443   CVE-2024-4577
  ┌────────────────────────────────────────────────────────────────┬──────────────┐
  │  WHAT IT IS    This host serves PHP through CGI. The way …     │  CVE          │
  │                                                                │  CVE-2024-4577│
  │  WHAT TO DO    Update PHP to 8.3.8, 8.2.20 or 8.1.29. If …     │               │
  │                                                                │  CVSS         │
  │  EVIDENCE      ┌──────────────────────────────────────────┐    │  9.8          │
  │                │ GET /cgi-bin/php-cgi.exe?%ADd+allow_url… │    │               │
  │                │ HTTP/1.1 200 OK                          │    │  SEEN ON      │
  │                │ X-Powered-By: PHP/8.1.2                  │    │  https · 443/ │
  │                └──────────────────────────────────────────┘    │  tcp          │
  │                                                                │               │
  │  REFERENCES    https://nvd.nist.gov/vuln/detail/CVE-2024-4577  │               │
  │                https://www.php.net/ChangeLog-8.php#8.1.29      │               │
  └────────────────────────────────────────────────────────────────┴──────────────┘
```

| Region | Content | Treatment |
|---|---|---|
| Labels | `What it is` / `What to do` / `Evidence` / `References` | `text-caption-md`, uppercase, letterspaced, `--ink-muted`. Fixed-width label column, value column beside it. |
| What it is | `description` | Prose held to 65 characters however wide the frame gets. |
| What to do | `recommendation` | Same. |
| Evidence | `evidence` | Mono, whitespace preserved, in a `--card` block with a `--rule` hairline and `overflow-x: auto`. Never wraps mid-token. |
| References | `references[]` | One external link per line, truncated with the full URL in `title`, `target="_blank" rel="noreferrer noopener"`. |
| Margin | `cve_id`, `cvss_score`, `service` on `port`/`protocol` | Parked at the panel's right behind a `--rule` hairline, small uppercase labels over their values. |

The margin is the Nous idiom applied where it earns its place: CVE, CVSS and the service/port are
**verification material**, not reading. An operator checking the claim against NVD wants them
findable; an operator reading what to do wants them out of the way. Both are served by the margin.

**An empty section is omitted, not shown as an em dash.** A heading standing over nothing is noise,
and the contract allows every one of these strings to be empty. If nothing at all is populated the
panel renders the margin alone. If `cve_id` and `cvss_score` are both absent the margin is omitted
and the panel is single-column.

**Ordering.** Findings render worst-first — `critical → high → medium → low` — tie-broken by host
IP then port so the order is stable across renders. On scan detail the array arrives embedded in
the scan; ordering an already-complete array in hand is not the "re-sorting the visible page" that
TRUTH rule 15 forbids, which is about paginated server results. See §14 open question 2.

**Deep link.** `/scans/:scanId?finding=:findingId` matches the id inside the already-loaded
`findings`, opens that row, scrolls it into view and moves focus to its toggle. **No extra
request.** An absent or unmatched id renders the page normally with nothing open — no error, no
toast.

---

## 7. Layout, spacing and rhythm

Every screen holds `--container-frame`, like the bar above it. `--container-form` appears nowhere in
this feature.

**Vertical rhythm — three steps per screen, no more:**

| Screen | Intra-group | Inter-group | Inter-section |
|---|---|---|---|
| Scans, Hosts | **3** — table cell padding, header lines | **4** — `PageHeader` internals, table ↔ pagination footer | **12** — header ↔ table |
| Scan detail, Host detail | **3** — table cell padding | **4** — section heading ↔ its table | **12** — between sections |
| Agents | **4** — between the statement's lines | **6** — statement ↔ ornament | **16** — header ↔ statement |

Step 12 is the table-led inter-section step named in §Spacing and rhythm rule 4, and it is what
lets these screens separate sections **with space rather than rules**. Every section heading is IM
Fell against Plex Mono body, so the face change plus 48px carries the grouping without a line.
The only hairlines on these screens are the `PageHeader` rule, the table head's dashed rule, the
row rules and the finding panel's margin divider.

**Around the epicenter on a near-empty screen: step 16.** The Scans blank, Hosts blank, both error
states, the unfinished and failed scan pages, and the whole Agents statement each get step 16 of
paper above and below. Told nothing, an implementer packs these to the top and the calm is lost.

**Components carry no outer margin.** `DataTable`, `EmptyState`, `LoadingSkeleton`, `StatusPill`
and the finding panel all render flush to their own boxes. Every gap around them is set by the page
that places them, in one place per page. No `mb-*` is baked into anything two screens use.

Horizontal padding inside the frame never drops below step 6, and prose is held to 65 characters
wherever it sits, however wide the column gets.

---

## 8. Copy — only what SCREENS.md does not already fix

The per-screen copy tables in `SCREENS.md` §§ SCAN LIST, SCAN DETAIL, HOST INVENTORY, HOST DETAIL
stand verbatim and are not restated. These are the additions, changes and removals.

| Element | Copy | Why it is here |
|---|---|---|
| Scans blank — third line | "Scanning is set up on the Pi itself." | Replaces the removed CTA. Verbatim from `HomeBlank`. |
| Scans blank — CTA | *(removed)* | §12 divergence 1 |
| Scans blank — viewer line | *(removed)* | §12 divergence 1 — with no action to gate, there is no split |
| Hosts blank — third line | "Scanning is set up on the Pi itself." | Same |
| Hosts blank — CTA / viewer line | *(removed)* | §12 divergence 1 |
| Scan unfinished — added line | "Findings appear here when it finishes. This page doesn't update on its own." | §12 divergence 2 |
| Scan unfinished — button | "Check again" / in flight: "Checking…" | §12 divergence 2 |
| Scan failed — reason | *from `scanFailureReason(error_code)`* | The DMI-75 deck is the single source; SCREENS.md's `` "The Pi reported: `<error_code>`." `` and its "no `command_id`" line are both superseded |
| Scan failed — `[Try another scan]` | *(removed)* | §12 divergence 1, same rule |
| Ports table — inline empty | "No open ports. This host isn't exposing anything." | SCREENS.md copy, rendered without headings |
| Agents — heading | "Scanning is set up on the Pi itself." | §5.7 |
| Agents — body | "The Dmitri box is installed and configured on site. It scans the network it is connected to and uploads what it finds here." | §5.7 |
| Agents — links line | "Every scan it runs appears under Scans, and every device it finds appears under Hosts." | §5.7 |
| Agents — blank/needs-network/pill copy | *(not built — DMI-89)* | The `SCREENS.md` § AGENTS copy table is for the full screen |
| Pagination — count | "Showing 1–20 of 47" | Absent entirely when `total <= per_page` |
| Sort header — accessible name | The column label; state via `aria-sort` | No "Sort by Host ascending" duplication |
| Host findings section — error | "Couldn't load this host's findings." · [Retry] | New: this section fails independently of the host |
| Host findings section — empty | "No findings on this host." | SCREENS.md copy, rendered inline without headings |

Timestamps everywhere go through `Timestamp`: relative inside 7 days, absolute beyond, exact value
always in `title`.

---

## 9. Keyboard and focus

Tab order is DOM order throughout: top bar (wordmark is not a stop → nav items → Log out), then the
page. Focus starts at the document body on every route change; nothing is moved programmatically
except the one case below.

| Moment | Behaviour |
|---|---|
| Table with sortable head | The sort buttons are the first stops in the table, before any row. |
| Link row | One stop per row, on the row's anchor. **Enter** navigates. Space scrolls, as on any link. |
| Expand row | One stop per row. **Enter or Space** toggles. **Escape** closes the row the focus is in and leaves focus on it. Focus never moves into the panel on open. |
| Inside an open panel | Panel links and `Open <hostname>` are the next stops after the row, before the following row. |
| Inert row | No stop. |
| Pagination | `[Previous]` then `[Next]`, after the table. A greyed one is out of the tab order. |
| Sort activation | Focus stays on the header button across the refetch, so a second activation flips direction without re-finding it. |
| `?finding=` deep link | The one programmatic move: on first render the matched row is scrolled into view and focus lands on its toggle. |
| Retry buttons | The only stop in an error state. |

**No roving tabindex, no arrow-key grid navigation, no type-ahead.** These are `<table>` elements
with links and toggles in them, not a grid widget; adding a roving focus model would make Tab stop
doing what a keyboard user expects it to do on a list of links. Explicitly out of scope, not an
oversight.

---

## 10. Data — contract names only

| Screen | Call |
|---|---|
| Scans | `GET /api/v1/scans?page&per_page=20&sort_by=timestamp&sort_order=desc` → `ScanListResponse` (`data: ScanSummary[]`, `total`, `page`) |
| Scan detail | `GET /api/v1/scans/{scan_id}` → `ScanDetailResponse` — one request, everything embedded |
| Hosts | `GET /api/v1/hosts?page&per_page=20&sort_by&sort_order` → `HostListResponse` (`data: HostSummary[]`, `total`, `page`) |
| Host detail | `GET /api/v1/hosts/{host_id}` → `HostDetailResponse` |
| Host detail · findings | `GET /api/v1/findings?host_id={host_id}&per_page=100` → `FindingListResponse` |
| Agents | **none** |

Fields consumed:

- `ScanSummary`: `scan_id`, `timestamp`, `scan_mode`, `status`, `host_count`, `finding_count`,
  `highest_severity`. `subnet` is **not** shown in the list.
- `ScanDetailResponse`: `timestamp`, `subnet`, `scan_mode`, `status`, `host_count`,
  `finding_count`, `error_code`, `findings: FindingRecord[]`, `hosts: ScanHostView[]`.
  `command_id` is **not** consumed — the failure sentence comes from `error_code` alone.
- `ScanHostView`: `host_id`, `ip`, `mac`, `hostname`, `vendor`, `ports: Port[]`.
- `HostSummary`: `host_id`, `ip`, `mac`, `hostname`, `vendor`, `last_seen_at`, `open_ports_count`,
  `highest_severity`. `first_seen_at` is not shown in the list.
- `HostDetailResponse`: all of the above plus `first_seen_at`, `ports: Port[]`,
  `scan_history: HostScanHistoryEntry[]`.
- `Port`: `port`, `protocol`, `service`, `version`. `state` is not rendered — the section is called
  *Open ports* and only open ports are in it.
- `HostScanHistoryEntry`: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`,
  `highest_severity`.
- `FindingRecord`: `finding_id`, `severity`, `title`, `host_id`, `host_ip`, `port`, `protocol`,
  `service`, `cve_id`, `cvss_score`, `description`, `recommendation`, `evidence`, `references`.

Two contract notes: the finding schema is **`FindingRecord`**, not the `FindingRead` SCREENS.md
names — the doc is drifting from the generated types. And `ScanHostView` carries `hostname` but the
scan-detail host row needs a fallback to `ip` when it is empty, exactly as host detail's title does.

Sort values sent by Hosts are the contract's `HostSortBy` — `last_seen_at | hostname | vendor | ip`
— and `SortOrder` — `asc | desc`. Both are held in component state and initialised to the defaults,
so no unrecognised value can reach the request.

`q` (free-text search on hosts) and `status` (the filter on scans) exist in the contract and are
**never sent**.

---

## 11. `data-testid`

Kebab-case, matching the convention in `frontend/src/`.

**Navigation**

| Value | On |
|---|---|
| `nav-scans`, `nav-hosts`, `nav-agents` | the three new nav items |
| `nav-home`, `nav-users`, `nav-settings`, `top-bar`, `log-out` | unchanged |

**`DataTable` — every call site passes a prefix; these are the shapes**

| Value | On |
|---|---|
| `{prefix}-table` | the `<table>` in its regular state |
| `{prefix}-loading` | the skeleton body |
| `{prefix}-empty` | the empty body or block |
| `{prefix}-row-{id}` | one row |
| `{prefix}-caret-{id}` | an expand row's caret |
| `{prefix}-panel-{id}` | an open panel |
| `{prefix}-sort-{column}` | a sort header button |
| `{prefix}-pagination`, `{prefix}-range`, `{prefix}-previous`, `{prefix}-next` | the footer |

**Scans** — prefix `scans`

`scans-page` · `scans-table` · `scans-loading` · `scans-empty` · `scans-error` ·
`scans-error-retry` · `scans-row-{scan_id}` · `scans-status-{scan_id}` (the `StatusPill` cell) ·
`scans-pagination` · `scans-range` · `scans-previous` · `scans-next`

**Scan detail**

`scan-detail` · `scan-detail-header` · `scan-detail-error` · `scan-detail-error-retry` ·
`scan-detail-not-found` · `scan-detail-back` · `scan-unfinished` · `scan-unfinished-check` ·
`scan-failed` · `scan-failed-reason` · `scan-clean` ·
findings prefix `findings`: `findings-table` · `findings-row-{finding_id}` ·
`findings-caret-{finding_id}` · `findings-panel-{finding_id}` ·
`findings-panel-refs-{finding_id}` · `findings-panel-cvss-{finding_id}` ·
hosts prefix `scan-hosts`: `scan-hosts-table` · `scan-hosts-row-{host_id}` ·
`scan-hosts-caret-{host_id}` · `scan-hosts-panel-{host_id}` · `scan-hosts-open-{host_id}` (the
`Open <hostname>` link) · `scan-hosts-ports-{host_id}`

**Hosts** — prefix `hosts`

`hosts-page` · `hosts-table` · `hosts-loading` · `hosts-empty` · `hosts-error` ·
`hosts-error-retry` · `hosts-row-{host_id}` · `hosts-sort-hostname` · `hosts-sort-ip` ·
`hosts-sort-vendor` · `hosts-sort-last_seen_at` · `hosts-pagination` · `hosts-range` ·
`hosts-previous` · `hosts-next`

**Host detail**

`host-detail` · `host-detail-header` · `host-detail-identity` · `host-detail-seen` ·
`host-detail-error` · `host-detail-error-retry` · `host-detail-not-found` · `host-detail-back` ·
findings prefix `host-findings`: `host-findings-table` · `host-findings-loading` ·
`host-findings-empty` · `host-findings-error` · `host-findings-error-retry` ·
`host-findings-row-{finding_id}` · `host-findings-caret-{finding_id}` ·
`host-findings-panel-{finding_id}` ·
ports prefix `host-ports`: `host-ports-table` · `host-ports-empty` ·
history prefix `host-history`: `host-history-table` · `host-history-row-{scan_id}`

**Agents**

`agents-page` · `agents-note` · `agents-scans-link` · `agents-hosts-link`

The finding panel is one component, so a test written against `findings-panel-{id}` and one written
against `host-findings-panel-{id}` are asserting the same rendering with different prefixes. That
is intentional: the prefix names the call site, not a second component.

---

## 12. Two deliberate divergences from `SCREENS.md`

### Divergence 1 — the blank states ship with no CTA

`SCREENS.md` gives the Scans and Hosts blank states a `[Run first scan]` button pointing at
`/agents`, with an admin/viewer split around it, and gives the failed scan page a
`[Try another scan]` doing the same. **None of the three ships.**

`/agents` cannot start a scan until DMI-89. A button that names an action its destination cannot
perform is precisely the failure §Consistency rule 8 exists to prevent — it does not say what it
does, it says what it will do next quarter. The alternative, a button that navigates to a page that
then explains it cannot help, spends the operator's click on a dead end.

The precedent is already set and shipped: `pages/home/HomeBlank.tsx` states the same fact in words
and offers no action. These two blank states close on its exact sentence, so Home, Scans, Hosts and
Agents all say one thing. The CTA and the role split return together when there is something behind
the button — this is TRUTH rule 24, which requires exactly that.

A consequence worth stating: with no action to gate, **both roles see the identical screen** on all
five routes in this feature, and no test here asserts an absent affordance.

### Divergence 2 — the unfinished scan renders but does not poll

`SCREENS.md` says the unfinished scan page "says so and polls". TRUTH rule 27 says nothing on these
screens refreshes itself, and polling belongs with the trigger that starts the scan. So the page is
static — and the design problem is that a static page which silently never changes is
indistinguishable, to the person waiting, from a broken one.

The design answers it in two lines rather than pretending: the copy says *this page doesn't update
on its own*, and a `Check again` button re-reads that one scan. A manual re-read on a button press
is not a timer; it is the same query invalidation `[Retry]` already performs, on a page that is not
in error. Telling the operator to press F5 instead would be the same behaviour with worse manners.

Both tables are suppressed on this state, so there is no empty findings table to mistake for an
answer, and the `Running…` pill is the same one the run log shows on that scan's row — one visual
fact, two places.

---

## 13. Out of scope — deliberate, v1

- **No trigger, no live agent state, no command lifecycle.** `StatusPill` covers scan status only.
- **No polling and no timed refresh** anywhere, including the run log during a scan.
- **No search on hosts** (`q` exists in the contract and is never sent) and **no filter on scans**
  (`status` likewise).
- **No sorting on the run log** — chronological, fixed.
- **No charts, metric cards or dashboards**, and no LLM explainer panel.
- **No export, no bulk actions, no saved views.**
- **No roving-tabindex grid keyboard model** on any table (§9).
- **No pagination inside the host-findings section** — it asks for 100 and shows them all. A pilot
  host with more than 100 findings is a problem when it is a problem.
- **No rework of Home or Users onto these shared components.** Tracked separately. `DirectoryTable`
  keeps its own markup for now, including the invisible `bg-muted` skeleton noted in §3.5.
- **No `mac`, `state` or `first_seen_at` columns** beyond what §10 lists.
- **No dark-theme variants.**

---

## 14. Open questions

### Settled at the visual gate — 2026-08-26

Answered by the operator against the rendered plates. Recorded here so no later reader reopens
them as unknowns.

1. **The sort affordance at rest — settled: as drawn.** The idle chevron pair stays at `--rule`,
   and the active column stays marked by ink weight rather than by the purple accent.
2. **Two blank states with no button — settled: as drawn.** Scans and Hosts explain and offer
   nothing, and that reads as finished for this issue rather than as missing. The call to action
   arrives with the trigger (DMI-89), not before.
3. **The static running page — settled: keep both.** `Check again` ships alongside the sentence
   saying the page does not refresh itself. It is a manual re-read, not a timer, so it stands with
   the no-polling decision rather than against it.
4. **Density — settled: as drawn, for now.** Seven columns of 12px mono inside the 1120px frame is
   accepted. The size floor and the Plex Sans escape hatch remain the levers if it later proves
   hostile; a per-screen exception is still not one of them.
5. **Agents' permanence — settled: yes.** "Scanning is set up on the Pi itself." is the sentence
   the product keeps saying after the trigger ships.

6. **Worst-first ordering — settled: required, and the client owns it.** Findings are worst-first
   on both call sites. Neither `ScanDetailResponse.findings` nor `GET /findings` documents an
   order, so the client sort is **load-bearing, not redundant**: it is the only thing guaranteeing
   the requirement, and it must not be deleted as belt-and-braces if the backend is later observed
   to return sorted rows. TRUTH rule 7 is the contract; `bySeverityDesc` in `src/lib/severity.ts`
   (`ARCHITECTURE.md` §4.2) is where it is kept, and it is unit-tested against a shuffled fixture.
7. **Pagination at a page boundary — settled: greyed, not removed.** As drawn on the plate. This is
   the §Consistency rule 3 *progress* carve-out, not the permission rule — the operator may page,
   there is simply no page there, and removing the control shifts the footer between pages.
   `ARCHITECTURE.md` §6 has been corrected to match.

### Still open

Nothing. Every question raised by this design has been answered.

Nothing here is blocked on a missing API contract. C1, C2, C9, C10, C11 and C12 are all resolved,
and every endpoint this feature consumes is shipped.
