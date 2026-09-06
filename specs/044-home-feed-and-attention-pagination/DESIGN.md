# DESIGN — Home feed and attention paging (DMI-136)

Spec only. No implementation code. Completes the Home layouts deferred in
[`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) §3 and §16 now that
`GET /api/v1/home` feeds Events, Activity, and paged attention. Every visual value inherits
[`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) and the 042 restyle; this document adds
the two feed panels, attention pagination, and the single-snapshot data wiring.

**Rendered preview:** [`preview.html`](preview.html) — open in a browser at 1440px (or zoom as
needed). Built from Foundations tokens and Inter Variable (Geist Mono for data in implementation).
Box-drawing renders below are structural notes only. **The human performs the visual check on the
preview, and that check closes this feature** (`TRUTH.md` acceptance). No agent signs off on how
it looks.

**Behaviour source:** [`TRUTH.md`](TRUTH.md). **API shape:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
(when present) and the synthesis in [`specs/_scratch-044-home-feed/SYNTHESIS.md`](../_scratch-044-home-feed/SYNTHESIS.md).

---

## 1. Screen flow

No new routes. Home stays at `/` inside `AppShell`.

```
/login ── sign in ──► /  Home

Home (signed in)
  │ attention table row (whole row) ──► /scans/:scanId?finding=:findingId   (unchanged, 042 §3)
  │ machine cell link (when host_id present) ──► /network/:hostId           (unchanged)
  │ [Run first scan] (admin, first-run only) ──► /devices                   (unchanged)
  │ attention / events / activity pagination ──► local React state only; no URL change
  │ [Try again] (error) ──► refetch GET /home
  └─ nav chrome unchanged (Home · Scans · Network · Devices · Users · Settings)
```

**Single read.** The page issues one query: `GET /api/v1/home?attention_page=&events_page=&activity_page=`.
Changing any page integer refetches the snapshot with the other two pages unchanged. There is no
per-panel HTTP surface and no per-panel error UI in v1 — a failed read replaces the whole page with
the existing Home error state.

**Settings privacy disclosure** (`settings-activity` / “What's recorded?”) **changes with this
feature** (TRUTH rule 23). The shipped paragraph promises that *admins* see sign-in times and that
Dmitri records “not what you viewed or did”. Home now shows sign-in recency to every member and
logs invites, role changes, removals and departures. New copy, replacing
`settings-activity-note` verbatim:

> Everyone in your organization can see when you last signed in, and a log of changes to the
> organization: scans, machines that join the network, invitations, role changes, and members
> joining or leaving. We don't record what you viewed.

---

## 2. Home (`/`)

**Epicenter: the attention table** when `review_state` is `pending`. When nothing needs attention,
the epicenter becomes the **Events and Activity row** — the table is not drawn and the panels move
up under the title (v4 exemplar, TRUTH rule 20).

### 2.1 Vertical rhythm (binding)

| Step | Where |
| --- | --- |
| **Intra-group `2`** | Title count line → last-scan line → notice lines (failed scan, stale coverage) |
| **Inter-group `4`** | Inside each feed panel: heading → first row / blank sentence; panel content → pagination |
| **Inter-section `12`** | Title block → attention table (pending only); title block → side panels (clear / blank-with-panels); attention table block → side panels row |

Horizontal padding inside `--container-frame` never drops below step `6`. Components carry **no
outer margin**; the page root is a `flex flex-col gap-12` column (step `12` between major blocks).

**Title alignment.**

| Composition | Title block alignment | Top offset |
| --- | --- | --- |
| Pending (table + panels) | Left | Default shell padding (no extra `pt-24`) |
| Clear (panels only) | Left | Default |
| First-run (`review_state` `blank`) | Centred | Step `24` above the title block |
| Error | Centred | Step `16` around the error epicenter |
| Loading | — | Full-page skeleton; no title until data lands |

When first-run also renders feed panels, step `12` separates the centred first-run block from the
full-width panels row below.

### 2.2 Side panels row

Two equal columns in a `grid grid-cols-2 gap-8` (step `8` gutter). Each column is one **white
card** on the canvas: `--card` fill, `--rule` hairline, `--radius` corners, step `6` internal
padding. Headings sit **inside** the card (`text-title-xs`, weight 600).

| Panel | Widget `id` | Heading | Content |
| --- | --- | --- | --- |
| Events | `home-events-panel` | `Events` | Plain-text rows from `events.data[].text` |
| Activity | `home-activity-panel` | `Activity` | Timestamp + server sentence per row |

**Events row.** One line per event, `--text-body-md`, truncates with ellipsis. No timestamp column
on Events — ordering is server-side; the sentence carries the day count where relevant.

**Activity row.** Two columns on one line: `Timestamp` on `occurred_at` (step `4` gap to text),
then `activity.data[].text`. Timestamp column width is fixed (~104px at 1440) so rows align;
exact width follows the Activity mock in v4. Text is `--text-body-md`; timestamp is
`--text-caption-md` `--ink-muted` (via `Timestamp` styling).

The SPA **never** formats activity verbs from `kind` or payload — it prints `text` only.

**Pagination (all three surfaces).** Shared `Pagination` component (Foundations §Pagination):
icon-only chevron ghost buttons, `aria-label` **Previous page** / **Next page**, page numbers,
ellipsis when needed. Rendered at step `4` below the panel content or table, **right-aligned**.
**Hidden** when `total <= perPage` for that surface. Separate `aria-label` roots:
`Attention pages`, `Events pages`, `Activity pages`.

**Component change required.** `Pagination` today hardcodes `aria-label="Pagination"` on its
`nav` root (`frontend/src/components/Pagination.tsx`) and has only ever been mounted once per
page, through `ListSurface`. Home is the first screen with three, and three identically named
navigations are ambiguous to a screen reader. `Pagination` gains a **required** `label: string`
prop that drives `aria-label`; `ListSurface` gains a matching required `label` in its `pagination`
prop and forwards it, so its existing call sites name their own list rather than inheriting a
generic default. Prop order and the `testId` contract are otherwise unchanged.

**Page sizes (mirror server constants; not client-configurable).**

| Constant | Value | Surface |
| --- | --- | --- |
| `HOME_ATTENTION_PER_PAGE` | `8` | Attention table |
| `HOME_EVENTS_PER_PAGE` | `5` | Events panel |
| `HOME_ACTIVITY_PER_PAGE` | `8` | Activity panel |

### 2.3 Pending — table + both panels

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  14 things need your attention                                     ← title-lg, left       │
│  Last scan finished today at 06:12                               ← body-md muted, step 2 │
│  No successful scan in 4 days.                                 ← notice, optional        │
│                                                                                          │
│                                                    ↕ step 12                             │
│  VULNERABILITY                       MACHINE                 SEVERITY                    │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Router firmware is out of date      192.168.1.1            Critical                     │
│    CVE-2024-33112                                                                        │
│  ────────────────────────────────────────────────────────────────────────────────────    │
│  Remote desktop is open to the       192.168.1.22           High                         │
│  whole network                                                                           │
│  ─ … up to 8 rows (HOME_ATTENTION_PER_PAGE) … ─                                        │
│                                                                                          │
│                                                    ↕ step 4                              │
│                                                            ‹  1  2  ›                    │
│                                                    ↕ step 12                             │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐                    │
│  │ Events                        │  │ Activity                      │                    │
│  │ Rontho HQ has been offline…   │  │ Today 06:12  Standard scan …  │                    │
│  │ maria@… has not signed in…    │  │ Today 06:07  Standard scan …  │                    │
│  │ New machine joined…           │  │ Yesterday …  gui@… changed …  │                    │
│  │                     ‹ 1 2 ›   │  │                     ‹ 1 ›     │                    │
│  └───────────────────────────────┘  └───────────────────────────────┘                    │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Attention table** inherits 042 §3.1: no heading above the table; columns **Vulnerability ·
Machine · Severity** (46 / 34 / 20); 56px rows; CVE sub-line in mono muted; severity as bold ink
word; whole row links to scan detail. **Only critical and high** rows — medium/low never appear on
Home.

**Title count** uses `review_count` from the snapshot (full attention total + notice extras), not
`attention.data.length`.

**Ordering** is server-enforced: critical then high, newest `detected_at` first within each
severity, stable across pages.

Walkthrough: the owner sees at most eight vulnerability rows, pagination when `attention.total >
8`, then the Events and Activity cards on the same viewport without scrolling on a typical laptop.
Changing the attention page refetches the snapshot; Events and Activity page state in React is
unchanged.

### 2.4 Clear — no table, panels up

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  Nothing needs your attention                                                            │
│  Last scan finished today at 06:12                                                       │
│                                                                                          │
│                                                    ↕ step 12                             │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐                    │
│  │ Events                        │  │ Activity                      │                    │
│  │ … rows or panel blank …       │  │ … rows or panel blank …       │                    │
│  └───────────────────────────────┘  └───────────────────────────────┘                    │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Per Foundations §Copy rules and TRUTH rule 20: **no table, no empty card, no attention placeholder
text** — the canvas shows through where the table would be. The title carries “Nothing needs your
attention”. Panels sit at step `12` below the title block (not step `24` centred whitespace — the
feed is now part of the screen).

### 2.5 First-run — no scan yet

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                     ↕ step 24                                            │
│  No scans yet                                                                            │
│  Your first scan finds the machines on your network and what needs fixing.                │
│  [ Run first scan ]              ← admin only; absent for viewer                         │
│  Ask your admin to run the first scan.        ← viewer only, muted                       │
│                                                                                          │
│                                     ↕ step 12                                            │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐                    │
│  │ Events                        │  │ Activity                      │                    │
│  │ (rows or blank)               │  │ (rows or blank)               │                    │
│  └───────────────────────────────┘  └───────────────────────────────┘                    │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

`review_state` `blank`: centred first-run copy unchanged from 042 §3.3. TRUTH rule 21: Events and
Activity still render when the snapshot includes rows — the SPA does not invent attention rows.
Admin/viewer CTA rules unchanged (`FirstScanCta` / `FirstScanNote`).

### 2.6 Empty Events and empty Activity

When `events.total === 0` or `activity.total === 0`, the panel **still renders** (heading + blank
sentence). The page does not break; sibling panel and attention regions are unaffected.

```
│  Events                                                                                  │
│  Nothing to report right now.          ← body-md, muted, left-aligned in card           │
```

```
│  Activity                                                                                │
│  Nothing has been recorded yet.        ← body-md, muted, left-aligned in card           │
```

Panel blanks are **one sentence, no button** — a sub-panel empty, not a full-screen empty state.
Do not use the centred `EmptyState` page pattern here.

Both panels empty under a clear title is valid (TRUTH acceptance: “No events”).

### 2.7 Attention page 2 — Events still visible

Same layout as §2.3; page 2 shows the next slice of attention rows (≤8). Pagination current page
is `2`. Events and Activity panels remain **fully visible below** the shorter table block — this
is the primary viewport constraint the page size constants enforce.

Test intent: with `attention.total = 14`, `attention.page = 2`, assert `home-events-panel` and
`home-activity-panel` are in the document without scrolling on the test viewport (or assert both
testids visible — implementer chooses a stable viewport height in `Home.test.tsx`).

### 2.8 Error

Whole-page replacement — unchanged copy from 042 §3.4:

```
│                                     ↕ step 16                                            │
│  Couldn't load what needs your attention.                                                │
│  [ Try again ]                                                                           │
```

Retry refetches `GET /home` with the three current page integers. No partial render of title +
panels on error.

### 2.9 Loading

First load only: `LoadingSkeleton` blocks for the attention table height (eight 56px rows) and
compact skeleton lines inside both panel cards. **No** background-refetch skeleton when a page
integer changes — the existing snapshot stays visible until the next snapshot lands (or use a
subtle in-place pending state only if the implementer already has that pattern elsewhere; default:
keep showing previous snapshot during page change).

---

## 3. Copy (exact strings)

### 3.1 Title block (unchanged from 042 §3.8)

| Where | String |
| --- | --- |
| Title, 1 item | `1 thing needs your attention` |
| Title, N items | `{n} things need your attention` (`n` = `review_count`) |
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

### 3.2 Feed panels

| Where | String |
| --- | --- |
| Events heading | `Events` |
| Activity heading | `Activity` |
| Events empty | `Nothing to report right now.` |
| Activity empty | `Nothing has been recorded yet.` |
| Pagination `aria-label` (attention) | `Attention pages` |
| Pagination `aria-label` (events) | `Events pages` |
| Pagination `aria-label` (activity) | `Activity pages` |
| Previous control | `aria-label="Previous page"` (no visible text) |
| Next control | `aria-label="Next page"` (no visible text) |

### 3.3 Server-rendered row text (display only — SPA does not compose)

**Events** (`events.data[].text`) — examples the UI must render verbatim:

| Kind | Example admin/viewer text |
| --- | --- |
| `box_offline` | `Rontho HQ has been offline for 3 days` |
| `member_idle` | `maria@ronthocorp.com has not signed in for 62 days` |
| `machine_first_seen` | `New machine joined the network: iPhone` |

Vocabulary: **machine** on the network, **box** for the Dmitri device (never “device joined the
network” in owner copy). The v4 exemplar’s “device” wording is **wrong**; Foundations wins.

**Activity** (`activity.data[].text`) — admin examples; viewer receives role-safe variants from the
server (same row set, different sentence where required):

| Kind | Admin example |
| --- | --- |
| `scan_started` | `Standard scan started` |
| `scan_finished` | `Standard scan finished` |
| `scan_failed` | `Standard scan didn't finish` |
| `machine_first_seen` | `iPhone first seen on the network` |
| `role_changed` | `gui@ronthocorp.com changed maria@ronthocorp.com's role to Viewer` |
| `member_invited` | `gui@ronthocorp.com invited alex@example.com` |
| `member_removed` | `gui@ronthocorp.com removed maria@ronthocorp.com` |
| `account_deleted` | `maria@ronthocorp.com deleted their account` |

Viewer wording for admin-only verbs is defined in `ARCHITECTURE.md` / backend `activity_text` — the
SPA prints `text` only.

---

## 4. Data

| Endpoint | Query params | Fields consumed |
| --- | --- | --- |
| `GET /api/v1/home` | `attention_page` (int ≥1), `events_page`, `activity_page` | Full `HomeSnapshot` |

**`HomeSnapshot` (wire names).**

| Field | Use on Home |
| --- | --- |
| `review_state` | `blank` \| `clear` \| `pending` — drives layout branch |
| `review_count` | Title count (includes notices) |
| `latest_successful_scan` | Last-scan line (`timestamp`) |
| `notices[]` | `kind`, `text`, optional `days` → `AttentionNotices` |
| `attention.data[]` | `FindingRecord` rows for table |
| `attention.total`, `attention.page` | Attention pagination |
| `events.data[]` | `kind`, `text`, `occurred_at` (text only in UI) |
| `events.total`, `events.page` | Events pagination |
| `activity.data[]` | `kind`, `occurred_at`, `text` |
| `activity.total`, `activity.page` | Activity pagination |

No `per_page` query param. Page sizes are constants (§2.2). A page past the end returns `200`
with `data: []` and the real `total`.

**Removed client reads for Home:** separate `GET /scans`, dual `GET /findings` by severity, and
client-side `deriveReview` merge for this page.

---

## 5. Keyboard and focus

Focus starts on the document body; first `Tab` reaches the top bar (042 §3.7).

**Tab order (pending with all regions visible):**

1. Top bar nav items → user menu → `Log out`
2. Attention table rows (visual order, one tab stop per row)
3. Attention pagination controls (when shown): Previous → page numbers → Next
4. Events panel: pagination controls only (rows are not links)
5. Activity panel: pagination controls only

**Clear / first-run:** skip table stops; include first-run CTA when rendered.

**Error:** `Try again` follows the chrome.

**Enter:** activates focused pagination button or the focused table row link. Feed rows are not
interactive.

**Page changes:** when attention pagination updates, focus stays on the clicked control; do not
move focus to the table head.

---

## 6. New and changed frontend files

| Path | Action |
| --- | --- |
| `frontend/src/api/home.ts` | **New.** `getHome(pages)`, exported page-size constants mirroring server. |
| `frontend/src/hooks/useHome.ts` | **New.** Single `useQuery` on `getHome`; maps snapshot to `loading` \| `error` \| `blank` \| `clear` \| `pending`; exposes `retry` and snapshot. |
| `frontend/src/hooks/useHome.test.ts` | **New.** Hook tests for snapshot states and page-param refetch. |
| `frontend/src/pages/home/HomeSidePanels.tsx` | **New.** Two-column grid mounting Events + Activity panels. |
| `frontend/src/pages/home/EventsPanel.tsx` | **New.** Card, row list, blank, pagination. |
| `frontend/src/pages/home/ActivityPanel.tsx` | **New.** Card, timestamp + text rows, blank, pagination. |
| `frontend/src/pages/home/EventsPanel.test.tsx` | **New.** Rows print `text` verbatim; blank sentence; pagination hidden at `total <= perPage`. |
| `frontend/src/pages/home/ActivityPanel.test.tsx` | **New.** Timestamp and text cells per §7.6; blank sentence; pagination. |
| `frontend/src/pages/Home.tsx` | **Changed.** Three page `useState`s; compose `Verdict`, notices, table, panels; switch on `useHome`. |
| `frontend/src/pages/home/AttentionTable.tsx` | **Changed.** Accept optional pagination prop; render `Pagination` below table at step `4`. |
| `frontend/src/pages/home/HomeBlank.tsx` | **Changed.** Allow panels below first-run block (layout wrapper moves to `Home.tsx` or optional `children`). |
| `frontend/src/pages/Home.test.tsx` | **Changed.** MSW handler for `GET /home`; cases for paging, panel blanks, viewer activity text, clear layout. |
| `frontend/src/api/queryKeys.ts` | **Changed.** `home.snapshot(attentionPage, eventsPage, activityPage)`. |
| `frontend/src/components/Pagination.tsx` | **Changed.** Required `label` prop → `aria-label` on the nav root (§2.2). |
| `frontend/src/components/Pagination.test.tsx` | **Changed.** Assert the nav carries the passed name. |
| `frontend/src/components/ListSurface.tsx` | **Changed.** Required `label` inside `pagination`; forwarded to `Pagination`. |
| `frontend/src/components/ListSurface.test.tsx` | **Changed.** Fixture passes `label`. |
| `frontend/src/pages/Scans.tsx` | **Changed.** `pagination.label = "Scan pages"`. |
| `frontend/src/pages/Network.tsx` | **Changed.** `pagination.label = "Machine pages"`. |
| `frontend/src/pages/agents/DeviceScanHistory.tsx` | **Changed.** `pagination.label = "Scan pages"`. |
| `docs/ui/FOUNDATIONS.md` | **Changed.** §Pagination gains: the nav root is named for its surface (`{Thing} pages`); never two with the same name on one screen. |

`frontend/src/pages/Devices.tsx` mounts `ListSurface` without `pagination` — untouched.
| `frontend/src/types/openapi.d.ts` | **Changed.** Regenerated — `HomeSnapshot` and nested types. |
| `frontend/src/hooks/useHomeReview.ts` | **Removed** after `useHome` ships (delete file). |
| `frontend/src/hooks/useHomeReview.test.ts` | **Removed** with hook. |
| `frontend/src/test/mswHandlers.ts` | **Changed.** Default `GET /home` fixture for tests. |

| `frontend/src/pages/Settings.tsx` | **Changed.** New `settings-activity-note` copy (§1). |
| `frontend/src/pages/Settings.test.tsx` | **Changed.** Assert the new disclosure sentence. |

**Removed with the client review merge:** `frontend/src/lib/review.ts` and `frontend/src/lib/review.test.ts`
(server owns attention order, notices, and count).

---

## 7. `data-testid` and widget ids

### 7.1 Widget `id`s (landmarks)

| `id` | Element |
| --- | --- |
| `home-events-panel` | Events card root |
| `home-activity-panel` | Activity card root |

### 7.2 State containers

| id | Element |
| --- | --- |
| `home-page` | Page root wrapper (all success states) |
| `home-loading` | Loading skeleton wrapper |
| `home-side-panels` | Two-column grid wrapper |

### 7.3 Title block (kept from 042 §3.9)

| id | Element |
| --- | --- |
| `home-verdict` | Title line |
| `home-context` | Last-scan line |
| `home-item-scan` | Failed-scan notice |
| `home-item-coverage` | Stale-coverage notice |
| `home-blank-body` | First-run sentence |
| `first-scan-cta` / `first-scan-note` | First-run button / viewer line |
| `home-error` / `home-retry` | Error line / retry button |

### 7.4 Attention table

| id | Element |
| --- | --- |
| `home-table` | Attention `DataTable` |
| `home-table-row-{finding_id}` | One row |
| `home-attention-pagination` | Pagination root |
| `home-attention-previous` | Previous control |
| `home-attention-next` | Next control |
| `home-attention-page-{n}` | Page number `n` |

Hidden when `attention.total <= HOME_ATTENTION_PER_PAGE`.

### 7.5 Events panel

| id | Element |
| --- | --- |
| `home-events-heading` | “Events” heading |
| `home-events-list` | Row list wrapper (omit when blank) |
| `home-events-row-{index}` | One event row (`index` 0-based in `data`) |
| `home-events-blank` | Empty sentence |
| `home-events-pagination` | Pagination root |
| `home-events-previous` | Previous control |
| `home-events-next` | Next control |
| `home-events-page-{n}` | Page number `n` |

### 7.6 Activity panel

| id | Element |
| --- | --- |
| `home-activity-heading` | “Activity” heading |
| `home-activity-list` | Row list wrapper (omit when blank) |
| `home-activity-row-{index}` | One activity row |
| `home-activity-row-{index}-time` | Timestamp cell |
| `home-activity-row-{index}-text` | Sentence cell |
| `home-activity-blank` | Empty sentence |
| `home-activity-pagination` | Pagination root |
| `home-activity-previous` | Previous control |
| `home-activity-next` | Next control |
| `home-activity-page-{n}` | Page number `n` |

---

## 8. States summary

| State | Attention table | Events panel | Activity panel | Pagination |
| --- | --- | --- | --- | --- |
| Pending | Up to 8 rows | Rows or blank | Rows or blank | Per-surface when `total > perPage` |
| Clear | Not drawn | Rows or blank | Rows or blank | Same |
| First-run | Not drawn | Rows or blank | Rows or blank | Same |
| Empty feeds | Any | Blank sentence | Blank sentence | Hidden |
| Attention page 2 | Next slice | Unchanged page | Unchanged page | Independent |
| Loading (first load) | Skeleton | Panel skeleton | Panel skeleton | Hidden |
| Loading (page change) | Previous page's rows held | Held | Held | Visible, controls live |
| Error | Not drawn | Not drawn | Not drawn | Not drawn |

---

## 9. Out of scope (v1)

From TRUTH: email/push notifications; audit retention; configurable thresholds or page sizes;
infinite scroll; URL-synced pages; medium/low on Home; backfilling historical activity; hardware
agent/TUI; separate `GET /events` or `GET /activity`
routes; per-panel error envelopes inside a 200 snapshot.

---

## 10. Open questions for the approval gate

**Q1 — Machine column still IP-only.** Resolved in 042 Q1: ship `host_ip` in mono; hostname join
is a follow-up. This spec inherits that.

**Q2 — Refetch flicker on page change. Resolved.** `useHome` sets TanStack Query v5
`placeholderData: keepPreviousData`. A page change keeps the previous snapshot on screen until the
new one lands, so the page never falls back to `home-loading` and the two panels the owner did not
touch do not blink. The full-page skeleton is reserved for the first load. This is the only
mitigation needed for the accepted coupling in `ARCHITECTURE.md` §5.6.

**Q3 — Activity invite withdrawn kind.** Resolved in ARCHITECTURE. Wire kind is `invite_revoked`.
Admin text: `{actor} withdrew the invitation for {email}`. Viewer text: `{email}'s invitation is no longer outstanding`.

**Q4 — Rendered preview sign-off.** Operator opens [`preview.html`](preview.html) at desktop width
and confirms spacing, panel cards, and pagination match intent. Record approve/revise on the PR or
spec approval thread.

---

## 11. Related specs

| Doc | Role |
| --- | --- |
| [`TRUTH.md`](TRUTH.md) | Behaviour and acceptance |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | `GET /home`, activity writes, page constants |
| [`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) | Base Home layout §3 |
| [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) | Tokens, pagination, vocabulary |
| [`docs/ui/mockups/dmi-131-mockups-v4.html`](../../docs/ui/mockups/dmi-131-mockups-v4.html) | Visual proportion reference (fix device→machine in copy) |
