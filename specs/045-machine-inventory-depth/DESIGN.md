# DESIGN — Deepened machine inventory

Spec only. No implementation code. Every value comes from
[`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md); this document owns layout, copy, states
and `data-testid`s for the three screens DMI-135 touches.

**Rendered preview:** https://claude.ai/code/artifact/3e5b4924-04f3-4df0-a308-6e504a68f35f

**Approved mockup (owner, 2026-09-07):**
https://claude.ai/code/artifact/cbf8db53-4813-4040-b44f-f94489e92ad2

The preview is built from the Foundations tokens and the real typefaces (Inter Variable, Geist
Mono for data). The box-drawing renders below are structural notes only — arrangement and
proportion; the numbers live in the layout tables. **The human performs the visual check on the
preview, and that check closes this feature** (`TRUTH.md` business rule 13). No agent signs off on
how it looks.

This spec **supersedes `specs/042-design-system/DESIGN.md` §16** for four items and **closes its
§17 Q1 and Q2**. Everything in 042 that is not restated here still stands.

---

## 0. What this document changes, and what it does not

Three shipped screens change. Nothing else on them moves.

| Screen | What changes |
| --- | --- |
| **Network** (`/network`) | `Vendor` → `Type`. `Services` → `Vulnerabilities`. Every column left-aligns. Quiet is 7 days, split server-side, counted over the whole inventory, and paged on its own. `Vulnerabilities` becomes sortable. |
| **Network detail** (`/network/:hostId`) | Vendor and the open-port count join the identity line. Vulnerabilities gains `First seen`; Services gains `Last seen`. `Port` left-aligns. |
| **Home** (`/`) | The attention table's `Machine` cell shows the machine's current name, falling back to its address in mono. |

**Not changed, and not re-decided.** The tokens in `FOUNDATIONS.md`; the six-item nav; the frame;
the 56px row; the severity-as-bold-ink-word rule; the top bar; every other screen. Scans, Scan
detail, Devices, Device detail, Users, Settings and the auth screens are untouched.

### 0.1 Overrides recorded, so the older rule is not restored

| Where | 042 said | This spec says |
| --- | --- | --- |
| §16 | Machine type, per-machine vulnerability counts, service last-seen and vulnerability first-seen are out of scope — *"No data."* | All four are in scope and drawn. The data now exists. |
| §6.1 | Columns are `Machine · Address · Vendor · Services · Highest severity · Last seen`. | `Machine · Address · Type · Vulnerabilities · Highest severity · Last seen`. Same six columns, same shares, same order. |
| §6.1 | *"`Services` right-aligns in tabular figures."* | **Every column left-aligns, headers and values.** Numeric columns keep `tabular-nums`. This is an explicit override of `FOUNDATIONS.md` §Tables' "numbers right-align" clause **for these two screens only** — see §7.1. |
| §6.1 | `Machine`, `Address`, `Vendor` and `Last seen` are sortable. | `Machine`, `Address`, **`Vulnerabilities`** and `Last seen` are sortable. `Vendor`'s sort leaves with its column. |
| §6.3 | Quiet is *"last seen more than 14 days ago"*, computed over the current page. | **Quiet is more than 7 days**, split server-side, counted over the whole inventory, paged on its own. |
| §7 | *"`First seen` is not drawn — no data."* / *"`Last seen` is not drawn — no data."* | Both are drawn. |
| §17 Q1 | *Resolved: ship the IP*, deferred to this issue. | **Closed.** Home names the machine; the address is the fallback. |
| §17 Q2 | *Still open: accept the page-local quiet grouping?* | **Closed: no.** The split is server-side. |

---

## 1. Screen flow

No route is added, removed or renamed. Every arrow below already exists; the only new *event* is
the quiet group's own paging, which is state on `/network` and never navigation.

```
  /                     Home
    │ attention row (a vulnerability) — the row's label now names the machine
    └──────────────────────────────► /scans/:scanId?finding=:findingId

  /network              Network — active machines, quiet group at the bottom
    │ active row ──────────────────► /network/:hostId
    │ quiet row (group expanded) ──► /network/:hostId
    │ group toggle  ─────────────┐
    │ group pager   ─────────────┤  state only, stays on /network
    │ sort header   ─────────────┤  (sorting resets the active list to page 1
    │ list pager    ─────────────┘   and leaves the group untouched)
    ▼
  /network/:hostId      Network detail
    │ scan-history row ──────────► /scans/:scanId
    └ Back ──────────────────────► /network
```

**Independence, stated once.** The active list and the quiet group are two reads of the same
endpoint. Paging or sorting the active list does not collapse, reload or re-page the group.
Paging the group does not touch the active list, its page number, or its sort.

---

## 2. Network (`/network`)

**Epicenter: the machine table.** Unchanged from 042 — the table is still the whole screen. What
changes is what two of its columns mean.

### 2.1 Regular state

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri        Home  Scans  Network  Devices  Users  Settings     gui@ronthocorp.com [Log out]│
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  Network                                                                                   │
│  45 machines · last scan today 06:12                                        ↕ step 2       │
│                                                                             ↕ step 12      │
│  MACHINE ⌃⌄        ADDRESS ⌃⌄     TYPE       VULNERABILITIES ⌃⌄  HIGHEST SEV   LAST SEEN ⌄ │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  Netgear R7000     192.168.1.1    Router      3                  Critical      today 06:12 │
│  Office PC         192.168.1.22   Computer    2                  High          today 06:12 │
│  Front-door camera 192.168.1.51   Camera      2                  High          today 06:12 │
│  Office NAS        192.168.1.30   Storage     1                  Medium        today 06:12 │
│  Warehouse printer 192.168.1.40   Printer     1                  Low           today 06:12 │
│  192.168.1.63      192.168.1.63   —           0                  —             today 06:12 │
│    No name yet                                                                             │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ▸ Not seen recently (6)                                                                   │
│                                                                             ↕ step 4       │
│                                        ‹  1  2  3  ›                                       │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

Regions, top to bottom: the **title block** (title, then the muted subtitle at step `2`), then
step `12`, then the **table**, then step `4`, then the **pager**. Nothing else — no search box, no
filter, no column picker (still out of scope, per 042 §16 and `docs/ui/status.md`).

**The table does not grow.** Six columns, the 042 shares, the 042 order. `Highest severity` is
still second to last because `Last seen` still closes the row (`FOUNDATIONS.md` §Tables).

| # | Heading | Share | `colgroup` width | Content | Sortable |
| --- | --- | --- | --- | --- | --- |
| 1 | `Machine` | 26% | `w-13/50` | Hostname, or the address in mono with the `No name yet` sub-line. Flush left, always. | yes |
| 2 | `Address` | 16% | `w-8/50` | `ip`, mono, tabular. | yes |
| 3 | `Type` | 16% | `w-8/50` | One word from the closed vocabulary, sentence case. `unknown` → `EmptyMark`. | **no** — see Q3 |
| 4 | `Vulnerabilities` | 10% | `w-5/50` | The open count, `tabular-nums`, **left**. | **yes — new** |
| 5 | `Highest severity` | 16% | `w-8/50` | `SeverityWord`; `EmptyMark` when null. | no |
| 6 | `Last seen` | 16% | `w-8/50` | `Timestamp`. | yes |

The two columns leaving (`Vendor`, `Services`) hand their shares to the two arriving in place, so
no width in the `colgroup` changes and no other column moves. A whole row opens `/network/:hostId`.

**Type, drawn.** The vocabulary is closed at nine (`TRUTH.md`). Eight render as a word; the ninth
renders as nothing:

| Contract value | Cell shows |
| --- | --- |
| `router` | `Router` |
| `computer` | `Computer` |
| `camera` | `Camera` |
| `storage` | `Storage` |
| `tv` | `TV` — the only all-caps label; it is an initialism, not a word |
| `phone` | `Phone` |
| `printer` | `Printer` |
| `sensor` | `Sensor` |
| `unknown` | `EmptyMark` — the em dash in `--ink-muted`, exactly as an absent `Highest severity` |

**No guessed type and no placeholder word.** `Unknown`, `Unclassified`, `Other` and `—  (unknown)`
are all wrong. The em dash already means *the scan never observed this*, on this same table, in the
column two to the right. It means the same thing here.

**Vulnerabilities, drawn.** A plain integer. `0` is drawn as `0`, not as an em dash: zero is a fact
the scan established, not an absence. It stays in `--ink` like every other value; a count is not a
severity and takes no weight, no hue and no emphasis.

**Sorting.** `Vulnerabilities` joins `Machine`, `Address` and `Last seen` as a sortable header,
through the same `sort_by` / `sort_order` params and the same `DataTable` affordance already
shipped: a Lucide `chevrons-up-down` at `size-4` when the column is not the sort, swapping to
`chevron-up` / `chevron-down` when it is, with the active label at weight 600 and `aria-sort` on
the `th`. **Never a `▲▼` glyph** (`FOUNDATIONS.md` §Icons). Because the column is now left-aligned,
the chevron sits immediately right of the label, like every other sortable header on the screen —
the `justify-end` branch is simply never taken.

- **The default sort remains `last_seen_at desc`.** It is unchanged by this feature.
- First click on `Vulnerabilities` sorts **descending** — the owner's question is *"which machine
  is worst"*, and the worst machine is the first row (user story 6). Second click reverses.
- Sorting is server-side and whole-inventory: with 45 machines across three pages, the first row of
  page 1 is the worst machine **on the network**, not on the page.
- Changing the sort resets the active list to page 1. It does **not** collapse the quiet group,
  reset the group's page, or re-sort the group.

**The quiet group is not sorted with the list.** It is always last, after the sort, per
`FOUNDATIONS.md` §Tables.

### 2.2 A quiet machine's row

Unchanged from 042 §6.2 except for the threshold and one grammar fix.

```
│  Living-room TV     192.168.1.44   TV         2                  Low           Aug 12, 21:04 │  ← whole row --ink-muted
│    Not seen for 3 weeks                                                                      │
│  Boiler sensor      192.168.1.90   Sensor     0                  —             Aug 30, 06:09 │
│    Not seen for 1 week                                                                       │
```

Whole row in `--ink-muted`, second line `Not seen for {n} weeks`. No chip, no icon, no colour, and
not an error. The severity word keeps weight 600 and inherits the row's muted ink.

**The singular now exists.** At the 14-day threshold the floored week count was never below 2, so
`Not seen for 1 weeks` could not occur. At 7 days it can, for anything quiet for 7–13 days. The
copy is `Not seen for 1 week` at `n === 1` and `Not seen for {n} weeks` above it.

**A quiet machine's `Last seen` is always absolute.** The quiet threshold (7 days) and
`Timestamp`'s relative window (7 days) are the same number, so a machine in the group is always
past the window and always renders as `Aug 12, 21:04`. That is a consequence worth knowing, not a
rule to enforce — `Timestamp` needs no change.

### 2.3 The quiet group — collapsed, expanded, and its own pager

Quiet rows do not appear in the active list at all. They live behind one group row at the bottom of
the table, always last.

```
Collapsed:
│  192.168.1.63       192.168.1.63   —          0                  —             today 06:12  │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ▸ Not seen recently (6)                                                                    │

Expanded:
│  ▾ Not seen recently (6)                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  Living-room TV     192.168.1.44   TV         2                  Low           Aug 12, 21:04│
│    Not seen for 3 weeks                                                                     │
│  Old laptop         192.168.1.77   Computer   1                  Low           Jul 28, 06:11│
│    Not seen for 5 weeks                                                                     │
│  Boiler sensor      192.168.1.90   Sensor     0                  —             Aug 30, 06:09│
│    Not seen for 1 week                                                                      │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│                                                          ‹  1  2  ›     ← Quiet machine pages│
```

**The count is the whole inventory's.** `Not seen recently (6)` means six quiet machines on the
network, on every page of the active list, whether the group is open or shut. It comes from the
active list's own response (`quiet_total`), so the number is right before the group is ever opened
and does not require a second request to be correct.

**The group's control.** A text-shaped button carrying a Lucide `chevron-right` that rotates to
point down on open, at `--duration-base` / `--ease-standard`, suppressed under
`prefers-reduced-motion`. `aria-expanded` tracks the state; `aria-controls` points at the group's
`tbody`. Muted ink, `--text-caption-md`, flush left in a cell spanning all six columns. Unchanged
from the shipped `DataTable` group row.

**The group's pager.** The group holds up to 20 rows per page, like the active list. When it holds
more, a pager appears **as the last row of the group's `tbody`**, spanning all six columns, aligned
to the right edge of the table:

- It is the shared `Pagination` component — ghost `chevron-left` / `chevron-right` icon buttons
  with the accessible names `Previous page` / `Next page`, page numbers, an ellipsis. Never
  hand-rolled, never the words "Previous"/"Next" (`FOUNDATIONS.md` §Pagination).
- Its `nav` accessible name is **`Quiet machine pages`**. The active list's stays
  **`Machine pages`**. Two paginations on one screen never share a name.
- It hides itself when the group fits one page, exactly as `Pagination` already does.
- It sits *inside* the table rather than below it, so a reader never has to work out which of two
  stacked pagers belongs to which set of rows. It lines up with the list pager below.

  **Corrected 2026-09-08:** the two bullets above asked for right-alignment *and* for alignment with
  the list pager, which are not the same thing — the shared `Pagination` root is `mx-auto
  justify-center`, so the list pager is centred. The group pager reuses `Pagination` unchanged (§6.3
  forbids editing it) and is therefore centred too, which satisfies the requirement that matters:
  the two pagers line up with each other. Right-aligning both would mean giving `Pagination` a
  `className` and restyling every screen that uses it — out of scope here.
- Paging the group leaves the active list, its page and its sort exactly as they were. Collapsing
  the group and reopening it returns to page 1 of the group.

**Not a trailing empty row.** The pager row carries content, so `FOUNDATIONS.md` §Cards' "no
trailing empty row" is satisfied. When the group fits one page the row is absent entirely, not
rendered empty.

### 2.4 The group loading and failing on its own

Opening the group issues a request. That request has its own two failure-side states, drawn inside
the group and never taking down the active list — the same principle Network detail already applies
to its vulnerabilities card.

```
Loading (the group's first open):
│  ▾ Not seen recently (6)                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  ▬▬▬▬▬▬▬▬▬     ▬▬▬▬▬▬     ▬▬▬▬▬▬▬▬     ▬▬▬▬▬     ▬▬▬▬▬▬     ▬▬▬▬▬▬▬▬                        │
│  ▬▬▬▬▬▬       ▬▬▬▬▬▬▬▬     ▬▬▬▬▬▬      ▬▬▬▬▬▬    ▬▬▬▬▬▬▬▬   ▬▬▬▬▬                          │
│  ▬▬▬▬▬▬▬▬     ▬▬▬▬▬       ▬▬▬▬▬▬      ▬▬▬▬▬▬▬▬   ▬▬▬▬▬      ▬▬▬▬▬▬▬                        │
```

```
Error:
│  ▾ Not seen recently (6)                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  Couldn't load the machines you haven't seen recently.   Retry                              │
```

- **Loading** is `LoadingSkeleton` at three rows and six columns, as a `tbody` inside the group.
  First open only; a background refetch never replaces rows with bars.
- **Error** is one inert row spanning all six columns, holding the muted sentence and an inline
  `Retry` text button step `4` after it, flush left. It is **not** the `ErrorRetry` component —
  that is a centred page-level block with step `16` padding and would blow the 56px row. Same
  strings, row-shaped.
- The group row itself stays visible and still reads its true count in both states. The active list
  above is untouched.

### 2.5 States

| State | Render |
| --- | --- |
| **Regular** | §2.1. Active rows, group row last, list pager below. |
| **Loading** | `LoadingSkeleton` table body, six columns, first load only, never on background refetch. The title block renders as soon as the count lands. |
| **Blank** | No machines at all — active total `0` **and** `quiet_total` `0`. `EmptyState`: `No machines yet` + the first-scan sentence + `Run first scan` (admin) / the viewer line. Absent, not disabled. |
| **Error** | `Couldn't load your network.` + `Retry`, as `ErrorRetry`. |
| **All quiet** | Active total `0` but `quiet_total` above `0`. The table renders with its headings, one inert full-width row reading `No machines seen in the last 7 days.` in muted ink, then the group row holding every machine. **A table never renders bare with no rows.** The list pager is absent (one page of nothing to page). |
| **Group collapsed** | §2.3, top. The default on every load. **It does not re-collapse on a sort or a page change** — corrected 2026-09-08; this cell previously said it did, contradicting §2.1, which is the more specific statement and wins. A group the owner opened deliberately stays open; re-collapsing it would undo their action every time they re-sorted the list above it. |
| **Group expanded** | §2.3, bottom, plus its pager when it needs one. |
| **Group loading / group error** | §2.4. |

The all-quiet sentence names the threshold in words rather than making the reader infer it from the
group label, and it is the one place on the screen where "7 days" is written down.

### 2.6 Layout and vertical rhythm

Network is a list screen, so it keeps the 042 §2.3 contract exactly:

| Step | Where |
| --- | --- |
| intra-group `2` | Title to subtitle inside the title block. |
| inter-group `4` | Table to its pager; the group's error sentence to its `Retry`. |
| inter-section `12` | Title block to the table. |

Three steps, no fourth. The pager row inside the group introduces no new step — its height is the
table's fixed 56px row and its horizontal inset is the table's own `pr-4` cell padding.

Horizontal: the frame is `--container-frame` with step `6` page padding, as `AppShell` already
gives it. Column gaps come from the fixed `colgroup` shares, never from content. Foundations' step
`6` minimum between a numeric and a code column does not arise on this table — `Address` (code) and
`Vulnerabilities` (numeric) are separated by `Type`.

### 2.7 Keyboard and focus

Focus starts on the document body; the first `Tab` reaches the top bar's first nav item.

1. Nav items → `Log out`
2. Sort headers, in visual order: `Machine`, `Address`, `Vulnerabilities`, `Last seen`.
   `Type` and `Highest severity` are not sortable, carry no button, and are skipped.
3. Each active row, in visual order. A row is a link: `Enter` opens it, the whole row shows the
   focus ring.
4. The **group toggle**. `Enter` or `Space` opens it.
5. When open: each quiet row, in visual order, then the **group pager** (`Previous page`, the page
   numbers, `Next page`). When shut, both are out of the tab order because they are not in the DOM.
6. When the group is loading, nothing between the toggle and the list pager is focusable. When it
   has failed, the group's `Retry` button takes that position.
7. The **list pager**.

Opening the group moves focus nowhere — the toggle keeps it, and `aria-expanded` announces the
change. Paging the group keeps focus on the pressed pager button, so a reader can page again
without hunting. A disabled pager arrow leaves the tab order (`tabIndex={-1}`), as the shipped
`Pagination` already does.

### 2.8 Copy

| Where | String |
| --- | --- |
| Title | `Network` |
| Subtitle | `{n} machines · last scan {time}` |
| Subtitle, one machine | `1 machine · last scan {time}` |
| Columns | `Machine` · `Address` · `Type` · `Vulnerabilities` · `Highest severity` · `Last seen` |
| Type values | `Router` · `Computer` · `Camera` · `Storage` · `TV` · `Phone` · `Printer` · `Sensor` |
| Type, unknown | *(no string — `EmptyMark`)* |
| Unnamed machine sub-line | `No name yet` |
| Quiet sub-line, 1 week | `Not seen for 1 week` |
| Quiet sub-line, n weeks | `Not seen for {n} weeks` |
| Group row | `Not seen recently ({n})` |
| Group pager name | `Quiet machine pages` |
| List pager name | `Machine pages` |
| Group loading | *(no string — skeleton bars)* |
| Group error | `Couldn't load the machines you haven't seen recently.` |
| Group error button | `Retry` |
| All-quiet main body | `No machines seen in the last 7 days.` |
| Blank heading | `No machines yet` |
| Blank sentence | `Your first scan finds the machines on your network and what needs fixing.` |
| Blank button (admin) | `Run first scan` |
| Blank note (viewer) | `Ask your admin to run the first scan.` |
| Error | `Couldn't load your network.` |
| Error button | `Retry` |
| Caption (screen-reader) | `Machines on your network` |
| Row accessible name | `Open {hostname or ip}` |

Every string above except the five marked new in the table is the string already shipped. The
`Vendor` and `Services` headings are **deleted**, not reworded.

### 2.9 Data

`GET /api/v1/hosts` is read twice on this screen — once for the active list, once for the quiet
group, and only when the group is open.

| Read | Params | Fields consumed |
| --- | --- | --- |
| Active list | `page`, `per_page=20`, `sort_by`, `sort_order`, `group=active` | per row `host_id`, `hostname`, `ip`, `machine_type`, `vulnerability_count`, `highest_severity`, `last_seen_at`; plus `total` and `quiet_total` |
| Quiet group | same, `page` independent, `group=quiet` | the same row fields, plus `total` for the group's pager |
| Subtitle's scan time | `GET /api/v1/scans?status=completed&per_page=1` | `timestamp` — unchanged |

`sort_by` gains the value `vulnerability_count`. `HostSummary.vendor` and
`HostSummary.open_ports_count` are **no longer read by this screen**; they remain in the contract
and are read by Network detail (§3.2).

> **Contract names, reconciled against `ARCHITECTURE.md` (Q1, closed 2026-09-07).** The fields
> and params named above do not exist in `frontend/src/types/openapi.d.ts` today.
> `ARCHITECTURE.md` fixes them as `machine_type` (§2.1, `NULL` read as `"unknown"`),
> `vulnerability_count` (§2.1), `quiet_total` on `HostListResponse` (§5.2), the activity filter as
> the query parameter **`group`** with values `active` and `quiet` (§5.2), and the new sort value
> as `sort_by=vulnerability_count` (§5.1). Those are the names this screen is built against.

---

## 3. Network detail (`/network/:hostId`)

**Epicenter: this machine's vulnerabilities.** Unchanged. What arrives is the two facts that left
the list, and one date on each of the two tables above the fold.

### 3.1 Regular state

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri        Home  Scans  Network  Devices  Users  Settings     gui@ronthocorp.com [Log out]│
├────────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                     ↕ step 2       │
│  Front-door camera                                                          ← title-lg     │
│  192.168.1.51 · C0:56:E3:1A:4B:70 · Hikvision · Camera · 4 open ports       ← muted        │
│  First seen Jul 12, 21:40 · last seen today 06:12                                          │
│                                                                             ↕ step 12      │
│ ┌────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Vulnerabilities                                                                        │ │
│ │ VULNERABILITY                        PORT    CVE             FIRST SEEN     SEVERITY   │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │ Camera still uses the password …     554     —               Jul 12, 21:40  High       │ │
│ │ Old TLS version still enabled        443     CVE-2016-2183   today 06:12    Medium     │ │
│ └────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                             ↕ step 8       │
│ ┌────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Services running on this machine                                                       │ │
│ │ SERVICE                  PROTOCOL     VERSION                    LAST SEEN             │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │ rtsp                     tcp          Hikvision RTSP 1.0         today 06:12           │ │
│ │   554                                                                                  │ │
│ │ https                    tcp          nginx 1.18.0               today 06:12           │ │
│ │   443                                                                                  │ │
│ │ telnet                   tcp          —                          Aug 30, 06:09         │ │
│ │   23                                                                                   │ │
│ └────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                             ↕ step 8       │
│ ┌────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Scan history                                                                           │ │
│ │ WHEN                MODE          SERVICES     HIGHEST SEVERITY                        │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │ today 06:12         Standard      4            High                                    │ │
│ │ Sep 5, 06:11        Standard      5            High                                    │ │
│ └────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 The identity line takes vendor and the open-port count

042's second identity line read `{ip} · {mac} · {vendor}`. It now reads five facts, in the order
*where it is · what it is · how much of it is exposed*:

```
192.168.1.51 · C0:56:E3:1A:4B:70 · Hikvision · Camera · 4 open ports
```

- Address and MAC stay mono; vendor, type and the port phrase are prose in `--ink-muted`, at
  `--text-body-md`, on the one line the block already had. **No new line, no new group, no new
  step.** The identity block is still three lines at step `2`.
- **A missing MAC** keeps its em dash, as today.
- **An unknown type is omitted from the line**, separator and all, rather than drawing a dash
  inside a sentence. An em dash in a table cell reads as *this column is empty for this row*; an em
  dash mid-sentence reads as a typo. The line simply becomes
  `192.168.1.63 · — · Espressif · 2 open ports`.
- **The count is a phrase, not a bare number**, because it stands in prose with no column heading
  to name it: `4 open ports`, and `1 open port` at one. At zero the phrase is `no open ports` — a
  plain fact, not an achievement, and never *"no open ports found"*, which edges toward certifying
  safety.
- **`open_ports_count` is the count the contract already carries.** It is not the same number as
  the rows in the Services table, which now include services last seen in an earlier scan. The
  phrase names open ports; the table names services, including closed ones. That is why the count
  belongs on the identity line and not as a caption on the card.

The **quiet variant** of the third line is unchanged from 042 §7.1: `First seen {time} · not seen
for {n} weeks`, with the same 1-week singular as §2.2.

### 3.3 The Vulnerabilities table gains `First seen`

Five columns now. `Severity` still closes the row.

| # | Heading | Share | `colgroup` width | Content |
| --- | --- | --- | --- | --- |
| 1 | `Vulnerability` | 40% | `w-2/5` | Title; the row expands in place to description, recommendation and evidence, as today. |
| 2 | `Port` | 10% | `w-1/10` | `tabular-nums`, **left**; `EmptyMark` when null. |
| 3 | `CVE` | 18% | `w-9/50` | Mono; `EmptyMark` when null. |
| 4 | `First seen` | 16% | `w-4/25` | `Timestamp`. **New.** |
| 5 | `Severity` | 16% | `w-4/25` | `SeverityWord`. |

`First seen` sits immediately before `Severity` because `Severity` closes the row
(`FOUNDATIONS.md` §Tables) and because the two dates the owner compares — *when it appeared* and
*when the scan ran* — read better beside the verdict than buried next to the port.

**It answers "is this new?" without arithmetic.** `Timestamp` gives `today 06:12` for a problem
found tonight and `Jul 12, 21:40` for one open since July, so the two rows in the render above are
distinguishable at a glance. Re-detection never moves the value (`TRUTH.md`).

**The step-6 gap between `Port` and `CVE`** is still owed (`FOUNDATIONS.md` §Tables). It is met by
the column widths, not by padding: inside a card at the 1120px frame less step `6` padding on each
side, `Port` is ~107px wide holding three or four left-aligned digits, so the trailing slack is far
past 24px. No extra padding is added anywhere.

### 3.4 The Services table gains `Last seen`

Four columns now.

| # | Heading | Share | `colgroup` width | Content |
| --- | --- | --- | --- | --- |
| 1 | `Service` | 34% | `w-17/50` | Service name, with the port beneath as a muted mono sub-line, as today. |
| 2 | `Protocol` | 14% | `w-7/50` | `tcp` / `udp`. |
| 3 | `Version` | 30% | `w-3/10` | Version string; `EmptyMark` when null. |
| 4 | `Last seen` | 22% | `w-11/50` | `Timestamp`. **New.** |

`Last seen` closes the row, matching the Network list. It is the column that lets an owner tell a
service still open from one that has closed since — a service whose `Last seen` is older than the
machine's has stopped answering. **No second styling carries that difference**: no strikethrough,
no muted row, no "closed" word. The date is the whole signal, exactly as `Not seen recently` is on
the list. Adding a state word here would need a vocabulary decision the owner has not made — raised
as **Q4**.

### 3.5 The Scan history table left-aligns its `Services` count

No column is added. `Services` drops its right alignment so the card does not contradict the two
cards above it on the same screen — a numeric column that right-aligns three inches below one that
left-aligns is the sort of inconsistency the owner's decision was made to remove. Shares stay
34 / 22 / 18 / 26. `tabular-nums` stays.

### 3.6 States

| State | Render |
| --- | --- |
| **Regular** | §3.1. |
| **Loading** | Unchanged from today: the gate renders the page skeleton; the vulnerabilities card carries its own pending table. |
| **No vulnerabilities** | The card renders `No vulnerabilities on this machine.` in place of the table. Unchanged. |
| **No services** | `No services are running on this machine.` in place of the table. Unchanged. |
| **Vulnerabilities failed** | Only that card shows `Couldn't load this machine's vulnerabilities.` + `Retry`. The identity, services and history stay up. Unchanged. |
| **Quiet machine** | The third identity line reads `First seen {time} · not seen for {n} weeks`, muted like the rest of the block. No banner, no colour. Unchanged but for the 7-day threshold. |
| **Unknown type** | The type is omitted from the identity line, separator and all (§3.2). |
| **Not found** | `That machine doesn't exist.` + `Back to the network`. Unchanged. |
| **Error** | `Couldn't load this machine.` + `Retry`. Unchanged. |

None of these is a new state. Only the unknown-type variant of the identity line is new, and it is
a variant of the regular state, not a state of its own.

### 3.7 Layout and vertical rhythm

Detail-screen contract from 042 §2.3, unchanged:

| Step | Where |
| --- | --- |
| intra-group `2` | Back link → title → identity line → seen line, inside the header group. |
| inter-group `8` | Between the three cards. |
| inter-section `12` | Header group → the card stack. |

Card padding is step `6` and is padding, not rhythm. **No new step is introduced by either new
column** — a column costs horizontal share, which the `colgroup` reallocates, and nothing vertical.

### 3.8 Keyboard and focus

Unchanged in shape; two tables are wider, none gains a control.

1. Nav → `Log out`
2. `Back`
3. Each vulnerability row — `Enter` toggles its panel; `Escape` closes an open one
4. Each scan-history row — `Enter` navigates
5. The vulnerabilities `Retry`, when that card is in error

The Services table has no row action and takes no tab stop, as today.

### 3.9 Copy

| Where | String |
| --- | --- |
| Identity line | `{ip} · {mac} · {vendor} · {Type} · {n} open ports` |
| Identity line, unknown type | `{ip} · {mac} · {vendor} · {n} open ports` |
| Open-port phrase, 0 | `no open ports` |
| Open-port phrase, 1 | `1 open port` |
| Open-port phrase, n | `{n} open ports` |
| Vulnerability columns | `Vulnerability` · `Port` · `CVE` · `First seen` · `Severity` |
| Services columns | `Service` · `Protocol` · `Version` · `Last seen` |
| History columns | `When` · `Mode` · `Services` · `Highest severity` |

Everything else on this screen — title, back link, seen line, card headings, the three empty and
error sentences, the not-found notice — is the string 042 shipped, unchanged.

### 3.10 Data

`GET /api/v1/hosts/{host_id}` → `HostDetailResponse`: `host_id`, `hostname`, `ip`, `mac`,
`vendor`, `first_seen_at`, `last_seen_at`, `open_ports_count`, `highest_severity`,
`machine_type`, `vulnerability_count`, `ports[]` (`HostPort`: `port`, `protocol`, `service`,
`version`, `first_seen_at`, `last_seen_at`), `scan_history[]` (`scan_id`, `timestamp`,
`scan_mode`, `open_ports_count`, `highest_severity`).

`GET /api/v1/findings?host_id={host_id}&per_page=100` → `FindingListResponse`, whose records now
carry `first_seen_at`, `last_seen_at` and `fixed_at` alongside `detected_at`.

**Q1, closed 2026-09-07.** The names above are `ARCHITECTURE.md`'s (§5.3, §6). Note that
`HostPort` carries **no `state`** — `host_ports` only ever holds ports observed open, so the
Services table's `Last seen` date is the only thing that tells a closed service from an open one
(Q4). This screen reads `vendor` and `open_ports_count`, which the list stops reading — neither
field is removed from the contract.

---

## 4. Home (`/`) — the attention table names the machine

**Only the `Machine` cell changes.** Columns, shares, headings, order, ordering rule, pagination,
the title block, the notices and the two feed panels below are all untouched.

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  4 things need your attention                                                              │
│  Last scan finished today 06:12                                             ↕ step 2       │
│                                                                             ↕ step 12      │
│  VULNERABILITY                                MACHINE               SEVERITY               │
│  ─────────────────────────────────────────────────────────────────────────────────────────  │
│  Router firmware is out of date               Netgear R7000         Critical               │
│    CVE-2024-33112                                                                          │
│  Remote desktop is open to the whole network  Office PC             High                   │
│  Camera still uses the password it came with  Front-door camera     High                   │
│  Old file sharing is switched on              192.168.1.63          Medium                 │
│    CVE-2020-0796                                                                           │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

**The cell, in three cases:**

| The problem's machine | Cell shows | Type treatment |
| --- | --- | --- |
| Has a current name | The name | `--ink`, sans, truncated with the full value in `title` |
| Can be identified but has no name | The address | `--ink`, **mono** — the same fallback the Network list's first column uses |
| Cannot be identified at all | `EmptyMark` | muted em dash |

- **Current, not historical.** A machine renamed since the problem appeared shows the new name.
  The name is read from the machine, not stamped onto the problem.
- **The cell stays a link to the machine** when the problem carries a machine id, as today; the
  surrounding row still opens the scan detail at that vulnerability. Neither destination changes.
- **The row's accessible name** becomes `{title} on {name}`, falling back to the address and then
  to `unknown machine` — so a screen reader hears the same thing the eye reads.
- No column widens. `Front-door camera` and `192.168.1.51` both fit the 34% share; anything longer
  truncates with its full value in `title`, as every other cell on the screen does.

**This closes 042 §17 Q1.** Its "ship the IP" resolution was explicitly deferred to this issue, and
the deferral is now spent: an owner reading Home no longer has to recognise an address (user
story 4).

### 4.1 States

No state is added. The blank, clear, first-run, loading and error states of Home are unchanged, and
none of them renders the `Machine` cell. The **regular** state is the only one this section
touches, and its two cell variants are drawn above.

### 4.2 Data

`GET /api/v1/home` → `HomeSnapshot.attention.data[]`, per row `finding_id`, `scan_id`, `title`,
`cve_id`, `host_id`, `host_ip`, `severity`, and **`host_hostname`** — the machine's current name,
`null` when the machine cannot be identified. The name is a field on the record — Home issues no
second request, and 042's "one more request on the product's first screen" objection is answered
by the contract rather than by the client. (Q1, closed 2026-09-07: the field is `host_hostname`,
`ARCHITECTURE.md` §6.)

---

## 5. Alignment: the override, stated once

`FOUNDATIONS.md` §Tables says *"Text left-aligns; numbers right-align in tabular figures."*

**Owner decision, 2026-09-07: on Network and Network detail, every column left-aligns — headings
and values alike — and numeric columns keep `tabular-nums`.** This is a deliberate override of that
clause and of 042 §6.1. It is recorded here, in `TRUTH.md` §Overrides, and it must be raised as an
amendment to `FOUNDATIONS.md` §Tables rather than quietly diverging — **Q2**.

Columns affected:

| Table | Column | Was | Is |
| --- | --- | --- | --- |
| Network | `Vulnerabilities` (replacing `Services`) | right | **left**, tabular |
| Network detail — Vulnerabilities | `Port` | right | **left**, tabular |
| Network detail — Scan history | `Services` | right | **left**, tabular |

Columns **not** affected, and deliberately left alone: the numeric columns on Scans, Scan detail's
findings table, Scan detail's hosts table, and Device detail's scan history. Those screens are out
of scope for DMI-135 and are not restyled by a spec that does not otherwise touch them. The result
is a real inconsistency between Scan detail's `Port` and Network detail's `Port` — flagged as
**Q2**, for the owner to settle as a follow-up rather than for this feature to take unasked.

The `align: 'right'` option on `DataTable` is **not removed**. It is still used by four other
screens; removing it is a change to those screens.

---

## 6. Files under `frontend/src/`

Every path an implementer creates or touches. No other file under `frontend/src/` changes.

### 6.1 New

| File | Why |
| --- | --- |
| `lib/machineType.ts` | The nine-value label map and the unknown check. One place owns the vocabulary, so no screen hand-writes `Router`. |
| `lib/machineType.test.ts` | Every one of the nine values maps to its label or to the unknown branch; `TV` stays capitalised. |
| `pages/hosts/QuietMachineGroup.tsx` | The quiet group's own read, its pager, and its loading and error rows. It owns the second `GET /hosts` so `Network.tsx` stays a page and `DataTable` stays generic. |
| `pages/hosts/QuietMachineGroup.test.tsx` | Independence from the active list; the whole-inventory count; the pager's name; the loading and error rows. |

### 6.2 Changed

| File | Change |
| --- | --- |
| `pages/hosts/hostListColumns.tsx` | `vendor` → machine type; `open_ports_count` → vulnerability count; `align: 'right'` removed; the vulnerability column becomes `sortable: true`; the quiet sub-line gains its 1-week singular. |
| `pages/Network.tsx` | Reads the active list with the activity filter; renders the quiet group from the new component instead of `partitionQuietHosts`; passes the whole-inventory quiet count to the group label. |
| `components/ListSurface.tsx` | `partitionRows` is replaced by a slot that takes an already-rendered collapsed group, so the group can own its own query. `DataTable`'s group contract is otherwise unchanged. |
| `components/DataTable.tsx` | The collapsed group accepts rendered content (skeleton, error row, rows + pager row) rather than only a row array. Nothing else changes — not the 56px row, not the sort affordance, not `align`. |
| `lib/hostLastSeen.ts` | The quiet threshold becomes 7 days. `isQuietHost` stays exported for the row tone; `partitionQuietHosts` is **deleted** — the split is server-side now. |
| `lib/hostLastSeen.test.ts` | 8 days is quiet, 6 days is not; the singular week. |
| `api/hosts.ts` | The activity filter param, the new `sort_by` value in `HOST_SORT_DEFAULT_ORDER` (descending first), and a `listQuietHosts` read or an activity argument on `listHosts`. |
| `api/queryKeys.ts` | A key for the quiet read, distinct from the active list's, so paging one never invalidates the other. |
| `pages/home/AttentionTable.tsx` | The `Machine` cell renders the name, falls back to the address in mono, then to `EmptyMark`; the row's accessible name uses the same value. |
| `pages/hosts/HostIdentity.tsx` | The identity line gains type and the open-port phrase; the unknown-type omission. |
| `pages/scans/findingColumns.tsx` | **`hostFindingColumns` only** — gains `First seen`, drops `align: 'right'` from `Port`, re-shares to 40/10/18/16/16. `scanFindingColumns` is untouched (§5). |
| `pages/hosts/portColumns.tsx` | Gains `Last seen`; re-shares to 34/14/30/22. |
| `pages/hosts/HostScanHistoryTable.tsx` | `Services` drops `align: 'right'`. |
| `types/openapi.d.ts` | Regenerated from the contract. **Never hand-edited** — it is generated output. |
| `test/hostsHarness.ts`, `test/mswHandlers.ts` | Fixtures gain the new fields; the hosts handler honours the activity filter and pages the two sets independently. |
| `pages/Network.test.tsx` | The column swap, the em-dash type, left alignment, the whole-inventory count, group independence, the vulnerability sort. |
| `pages/HostDetail.test.tsx` | The identity line's five facts and its unknown-type variant; `First seen`; the services `Last seen`. |
| `pages/Home.test.tsx` | The name, the address fallback, the accessible name. |
| `components/DataTable.test.tsx`, `components/ListSurface.test.tsx` | The group's rendered-content contract. |

### 6.3 Untouched, and worth saying so

`components/SeverityWord.tsx`, `components/Timestamp.tsx`, `components/EmptyMark.tsx`,
`components/Pagination.tsx`, `components/ui/*` and `index.css`. This feature introduces **no new
token, no new component and no new size**. If an implementer finds themselves editing `index.css`,
something has gone wrong.

---

## 7. `data-testid`

Marked against 042 §6.8 (Network) and §7.5 (Network detail), plus §3.9 (Home).

### 7.1 Network

| id | Element | Status |
| --- | --- | --- |
| `network-page` | Page container | **unchanged** |
| `network-table` | The table | **unchanged** |
| `network-table-row-{host_id}` | One machine row, active or quiet | **unchanged** |
| `network-table-sort-hostname` | `Machine` sort control | **unchanged** |
| `network-table-sort-ip` | `Address` sort control | **unchanged** |
| `network-table-sort-last_seen_at` | `Last seen` sort control | **unchanged** |
| `network-table-sort-vulnerability_count` | `Vulnerabilities` sort control | **new** |
| `network-table-sort-vendor` | `Vendor` sort control | **retired** — the column is gone |
| `network-blank` | Blank state | **unchanged** |
| `network-error` / `network-error-retry` | Page error, retry | **unchanged** |
| `network-pagination` / `network-previous` / `network-next` / `network-page-{n}` | The active list's pager | **unchanged** |
| `network-quiet-group` | The group row | **unchanged** |
| `network-quiet-toggle` | Its expand control | **unchanged** |
| `network-quiet-pagination` | The group's pager `nav` | **new** |
| `network-quiet-previous` / `network-quiet-next` | The group's pager arrows | **new** |
| `network-quiet-page-{n}` | The group's page numbers | **new** |
| `network-quiet-loading` | The group's skeleton `tbody` | **new** |
| `network-quiet-error` | The group's error sentence | **new** |
| `network-quiet-error-retry` | Its `Retry` | **new** |
| `network-no-active` | The all-quiet main-body sentence | **new** |

The group's pager ids follow the shared `Pagination` convention from the `network-quiet` testId
prefix the group row already uses, so the three families (`-group`, `-toggle`, `-pagination`) read
as one component in a test file.

### 7.2 Network detail

| id | Element | Status |
| --- | --- | --- |
| `host-detail` | Page container | **unchanged** |
| `host-detail-header` | Header group | **unchanged** |
| `host-detail-identity` | The title | **unchanged** |
| `host-detail-meta` | The address/MAC/vendor/type/ports line | **new** — 042 left this line without an id; the type and the port phrase are now asserted on |
| `host-detail-seen` | The first-seen / last-seen line | **unchanged** |
| `host-detail-not-found` / `host-detail-back` | Not-found notice, link | **unchanged** |
| `host-detail-error` / `host-detail-error-retry` | Page error, retry | **unchanged** |
| `host-findings-table` | Vulnerabilities table | **unchanged** — five columns now, same id |
| `host-findings-table-row-{finding_id}` / `host-findings-table-panel-{finding_id}` | Row, expanded panel | **unchanged** |
| `host-findings-error` / `host-findings-error-retry` | That card's error | **unchanged** |
| `host-no-findings` | Empty vulnerabilities sentence | **unchanged** |
| `host-ports-table` | Services table | **unchanged** — four columns now, same id |
| `host-no-ports` | Empty services sentence | **unchanged** |
| `host-history-table` / `host-history-table-row-{scan_id}` | Scan-history card | **unchanged** |

### 7.3 Home

| id | Element | Status |
| --- | --- | --- |
| `home-table` | The attention table | **unchanged** |
| `home-table-row-{finding_id}` | One attention row | **unchanged** |
| `home-verdict` / `home-context` | Title, last-scan line | **unchanged** |
| `home-attention-pagination` / `home-attention-previous` / `home-attention-next` | Attention pager | **unchanged** |

**No id on Home changes**, because no element on Home changes — only the text inside one cell. A
test asserting the machine name reads it out of the existing row id.

---

## 8. Out of scope (v1), deliberately

Beyond `TRUTH.md` §Out of scope, which stands in full:

- **Sorting or filtering by type.** The column is drawn and read; it is not a sort key and not a
  filter. Filters remain out of scope from 042 and `docs/ui/status.md`, and a sort key needs a
  contract value nobody has asked for. Raised as **Q3**.
- **A count of quiet machines anywhere but the group row.** The subtitle's `{n} machines` stays the
  whole inventory, quiet included, as it is today. Two counts in the title block would need a
  vocabulary the screen does not have.
- **Re-aligning the numeric columns on Scans, Scan detail and Device detail.** §5, **Q2**.
- **Any visual mark for a closed service** on the Services table. §3.4, **Q4**.
- **Showing when a problem was fixed.** `TRUTH.md` puts the fixed moment in the data; no screen in
  this feature draws it. A fixed problem simply stops being counted. The screen that reads fixed
  dates over time is the security screen, explicitly a separate issue.
- **The security screen.** Named out of scope in `TRUTH.md`; this feature lands the dates it will
  need and draws none of it.
- **Search, filters and column pickers on Network.** Still "later, not MVP".
- **Dark theme, tablet and mobile layouts.** Still out, everywhere.

Nothing above is drawn as a placeholder, an empty column, or a greyed control.

---

## 9. Approval gate — decided (owner, 2026-09-07)

The gate is closed. All five questions carried an owner decision; each is recorded here and
applied above, so no reader restores the open version.

**Q1 — contract field names. Closed by reconciliation against `ARCHITECTURE.md`.** Every name this
document proposed is fixed there, and §2.9, §3.10, §4.2 and §7 now use the fixed spelling:

| This document proposed | The contract's name | Where `ARCHITECTURE.md` fixes it |
| --- | --- | --- |
| machine type | `machine_type`, `NULL` read as `"unknown"` | §2.1, §6 |
| per-machine vulnerability count | `vulnerability_count` | §2.1, §6 |
| whole-inventory quiet count | `quiet_total` on `HostListResponse` | §5.2, §6 |
| the activity filter | query parameter `group`, values `active` \| `quiet` | §5.2 |
| the new sort value | `sort_by=vulnerability_count` | §5.1 |
| the problem's first-seen moment | `first_seen_at` (also `last_seen_at`, `fixed_at`) on `FindingRead` | §3, §6 |
| the service's last-seen moment | `first_seen_at`, `last_seen_at` on the new `HostPort` | §2.2, §5.3, §6 |
| the finding's machine name | `host_hostname` | §6 |

One correction fell out of it: `HostPort` has **no `state`** field, because `host_ports` only ever
holds ports observed open. §3.10 said `state`; it no longer does.

**Q2 — alignment. Amend `FOUNDATIONS.md` product-wide.** §Tables becomes *every column
left-aligns; numbers keep tabular figures*, replacing the right-align rule. The four screens that
still right-align are a follow-up restyle, raised separately — the product does not ship two
alignment rules for the same kind of number. This feature's own screens are already drawn
left-aligned (§5).

**Q3 — `Type` is not sortable.** TRUTH asks for one new sort, and `ARCHITECTURE.md` §5.1
deliberately keeps `machine_type` out of `HostSortBy`. `Type` is the one unsortable text column on
Network; it gets no sort control and no `data-testid` for one. Grouping by kind is a filter, and
filters stay out of scope.

**Q4 — the date carries it.** A closed service is told apart by its `Last seen` date alone. No
state word, no muted row, no strikethrough — naming the state needs a vocabulary decision this
feature does not own, and `FOUNDATIONS.md` §Copy allows one owner-facing word per concept.

**Q5 — the word is `Retry`.** The shipped `ErrorRetry` string wins; this document already uses it
throughout, including the quiet group's new error. `042`'s copy tables saying `Try again` are
wrong and get a documentation correction — no code and no copy changes anywhere in the product.

---

## 10. Related specs

- Truth: [`TRUTH.md`](TRUTH.md) — do not edit; it is the source.
- Architecture: `ARCHITECTURE.md` — written in parallel; owns the contract names Q1 depends on.
- Supersedes, in part: [`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) §16,
  and closes its §17 Q1 and Q2.
- Inherited and never re-decided: [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md).
