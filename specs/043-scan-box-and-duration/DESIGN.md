# DESIGN: Scan box attribution and duration (DMI-134)

Spec only. No implementation code. Completes the layouts deferred in
[`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) §4 Scans, §5 Scan detail,
and §9 Device detail now that producing-box and duration data exist. Every visual value inherits
[`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) and the 042 restyle; this document adds
Box and Duration only. It does not restyle the app.

**Rendered preview:** [`208b8e49-a47c-4dd3-a361-4840de59affa`](https://claude.ai/code/artifact/208b8e49-a47c-4dd3-a361-4840de59affa),
extending the 042 preview ([`47ec803b`](https://claude.ai/code/artifact/47ec803b-591f-46e1-b209-cd9426be3680)):
the Scans table (Box + Duration columns, EmptyMark rows), the scan-detail summary strip
(Duration entry), and the device-detail scan-history section with its four columns.
Built from Foundations tokens and the real typefaces (Inter Variable, Geist Mono for data).
Box-drawing renders below are structural notes only. **The human performs the visual check on the
preview, and that check closes this feature** (`TRUTH.md` acceptance). No agent signs off on how
it looks.

**Behaviour source:** [`TRUTH.md`](TRUTH.md).

---

## 1. Screen flow

No new routes. Three existing screens gain cells or sections; navigation rules stay as in 042.

```
/scans                          Scans run log
  │ whole row (unchanged)          Box cell is text only (see §2.1)
  └────────────────────────────► /scans/:scanId

/scans/:scanId                  Scan detail
  │ summary strip gains Duration fifth entry; no Box field (TRUTH rule 16)
  └─ (unchanged links to /network/:hostId from machines seen)

/devices/:agentId               Device detail
  │ scan controls (unchanged, 042 §9)
  │ new Scan history section below (step 12)
  │   each history row ──► /scans/:scanId
  └─ owner reaches a box from Devices, not from the Scans Box cell
```

**Box cell vs whole-row link (binding for this spec).** FOUNDATIONS §Tables: whole rows are links;
042 §4 wires the scans row to `/scans/:scanId` with no nested links. TRUTH rule 13 says the Box
cell "opens that box." **This spec follows FOUNDATIONS:** the Box cell shows the producing box's
current `display_name` as plain `--text-body-md` text inside the row link. It is not a nested
`<a>`. The owner opens the box from **Devices** or from a bookmark; the row still opens the scan.
See **Open questions** for the TRUTH rule 13 conflict.

---

## 2. Scans (`/scans`)

**Epicenter: the scans table.** Inherits 042 §4 layout, rhythm, pagination, blank and error
states. **Adds** Box and Duration columns in the order TRUTH rule 15 fixes.

**Vertical rhythm (unchanged from 042):** intra-group `2`, inter-group `4`, inter-section `12`.

### 2.1 Regular state (attributed, unattributed, failed duration)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Scans                                                          ← title-lg               │
│                                                    ↕ step 12                             │
│  WHEN           BOX           MODE       STATUS    DURATION  MACHINES  VULNERABILITIES  HIGHEST SEVERITY │
│  ─────────────────────────────────────────────────────────────────────────────────────────────────────────│
│  2 Sep 2026,    Rontho HQ     Standard   Completed  8 min         14            2       High            │
│  06:12                                                                                                   │
│  1 Sep 2026,    Warehouse     Standard   Completed  45s         14         None       —               │
│  06:10                                                                                                   │
│  31 Aug 2026,   —             Extensive  Completed  22 min      14            5       Critical        │
│  22:04                          ↑ unattributed                                                           │
│  30 Aug 2026,   Rontho HQ     Standard   Failed    —             —            —       —               │
│  06:11                          ↑ failed duration dash                                                   │
│  29 Aug 2026,   Reception     Quick      Running…  —             —            —       —               │
│  06:09        spare             ↑ unfinished duration dash                                               │
│                                                                                          │
│                                                    ↕ step 4                              │
│                                                            ‹  1  2  3  4  ›              │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Regions.** Title block (`Scans`, step `12` below), then the run-log table, then pagination at
step `4`. Chrome and frame match 042.

**Column order (binding):** When · Box · Mode · Status · Duration · Machines · Vulnerabilities ·
Highest severity.

**Column widths (`colgroup`, explicit shares):** When `w-9/50` · Box `w-7/50` · Mode `w-1/10` ·
Status `w-1/10` · Duration `w-1/12` · Machines `w-1/10` · Vulnerabilities `w-3/25` · Highest
severity `w-9/50`. Duration, Machines, and Vulnerabilities right-align in tabular figures. Step
`6` minimum between Vulnerabilities and Highest severity. Highest severity closes the row
(Foundations §Tables).

**When** uses the shared `Timestamp` component (relative inside 7 days, absolute beyond, exact
value on hover).

**Box** renders `ScanSummary.box_name` when the producing box is present (API returns the
current display name at read time, TRUTH rule 13). When absent (unattributed scan, TRUTH rules 5
and 6), render `EmptyMark` (`—` in `--ink-muted`). Plain text only; no link, no mono.

**Mode** unchanged: display label from `SCAN_MODE_LABEL`, not the raw enum.

**Status** unchanged: plain label from `scanStatusLabel` (`Completed`, `Failed`, `Running…`).

**Duration** uses `formatScanDuration` (§6) on `ScanSummary.duration`. When
`duration` is absent (failed, unfinished, or completed without a reported time, TRUTH
rules 8–9), render `EmptyMark`. The column header always exists (TRUTH rule 14).

**Machines**, **Vulnerabilities**, **Highest severity** unchanged from 042: `hidesCounts`
statuses get `EmptyMark`; zero vulnerabilities still read `None`.

**Row navigation.** Whole row opens `/scans/:scanId`. Focus ring on the row; no nested links.

### 2.2 Loading

`LoadingSkeleton` table body on first load only, same as 042 §4.1. Eight column placeholders.

### 2.3 Blank

Unchanged from 042 §4.1: `No scans yet` + first-run sentence + `Run first scan` (admin) /
`Ask your admin to run the first scan.` (viewer). No table headers drawn.

### 2.4 Error

Unchanged from 042: `Couldn't load the scans.` + `Try again`.

### 2.5 Keyboard and focus

Nav → `Log out` → each row in visual order → pagination previous → page numbers → next. Enter on a
row opens the scan. No submit-on-enter elsewhere.

---

## 3. Scan detail (`/scans/:scanId`)

**Epicenter unchanged:** vulnerability cards, then machines seen. **Adds** Duration as the fifth
summary-strip entry on completed scans. **Does not** add a Box field (TRUTH rule 16, out of scope).

**Vertical rhythm (unchanged):** intra-group `2`, inter-group `8`, inter-section `12`.

### 3.1 Regular state (completed scan with duration)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Scan · 31 Aug 2026, 22:04                                       ← title-lg (step 2 below) │
│                                                    ↕ step 12                             │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│   MODE            NETWORK            MACHINES SEEN      VULNERABILITIES       DURATION       │
│   Extensive       192.168.1.0/24     14                5                   22 min         │
│  ──────────────────────────────────────────────────────────────────────────────────────  │
│                                                    ↕ step 12                             │
│  (severity cards and machines seen, unchanged from 042 §5)                               │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Summary strip.** Same hairline, step `4` vertical padding, step `12` horizontal gap between
entries, labels `--text-caption-md` uppercase `--edge`, values `--text-body-md` tabular where
numeric. Entry order: Mode · Network · Machines seen · Vulnerabilities · **Duration** (fifth,
TRUTH rule 16). Duration value from `formatScanDuration(ScanDetailResponse.duration)`; when
absent on a **completed** scan that did not report time, value is `EmptyMark`.

Strip aligns to the tables' left and right edges (Foundations §Cards & sections).

### 3.2 Completed scan with no reported duration

Same strip layout; Duration value cell is `EmptyMark` (`—`). Not zero, not hidden.

### 3.3 Failed scan

Inherits 042 §5.1 failed mockup: strip shows **Mode** and **Network** only. Duration is omitted
with Machines seen and Vulnerabilities (`hidesCounts` applies). Failed block below unchanged.

### 3.4 Running scan

Inherits 042 §5.1 running mockup: strip shows Mode and Network only. Duration omitted. Unfinished
notice unchanged.

### 3.5 No vulnerabilities, not found, error

Unchanged from 042 §5.1. On the no-vulnerabilities path, the strip includes all five entries
including Duration when the scan completed.

### 3.6 Keyboard and focus

Unchanged from 042 §5.3.

---

## 4. Device detail (`/devices/:agentId`)

**Epicenter unchanged:** identity, watched network, scan type, Scan now (042 §9). **Adds** a
**Scan history** section below scan controls at inter-section step `12`. Columns are **When ·
Mode · Status · Duration** (TRUTH rule 18, decided 2026-09-05).

### 4.1 Regular state (history present)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Dmitri          Home  Scans  Network  Devices  Users  Settings      gui@ronthocorp.com  [Log out] │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back                                                                                  │
│  Rontho HQ                                                       ← title-lg              │
│  Online · last report today 06:12                                                        │
│  … watched network, scan type, Scan now (042 §9.1, unchanged) …                          │
│                                                    ↕ step 12                             │
│  Scan history                                                       ← title-sm           │
│  WHEN                       MODE          STATUS         DURATION                        │
│  ────────────────────────────────────────────────────────────────────────────────────────│
│  2 Sep 2026, 06:40          Quick         Running…              —                        │
│  Today                                                                                   │
│  2 Sep 2026, 06:12          Standard      Completed         8 min                        │
│  Today                                                                                   │
│  30 Aug 2026, 06:11         Standard      Failed                —                        │
│  27 Aug 2026, 06:12         Standard      Completed         7 min                        │
│                                                    ↕ step 4                              │
│                                                            ‹  1  2  ›                    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Regions.** Scan history is a plain section (no card wrapper), heading `--text-title-sm`, step
`4` to the table or blank copy, step `4` to pagination when rows exist. Pagination matches the
run log (`SCANS_PER_PAGE` = 20, same ghost control pattern as 042).

**Columns (binding):** When · Mode · Status · Duration. It is the run log with the findings
columns removed — the table says that a scan ran and how it ran, and the row opens the scan for
anything more. **Box is absent** because every row on this screen is the same box. **Machines,
Vulnerabilities and Highest severity are absent** by the same decision; do not add them back
without amending TRUTH rule 18.

**Column widths (`colgroup`, explicit shares):** When `w-17/50` · Mode `w-11/50` · Status
`w-11/50` · Duration `w-11/50`. Duration right-aligns in tabular figures and closes the row.

**Cells.** `When` is the shared `Timestamp` component, same as the run log. `Mode` is
`SCAN_MODE_LABEL`. `Status` is `scanStatusLabel`. `Duration` is `formatScanDuration(scan.duration)`
or `EmptyMark` — the same rule as §2.1, so a failed or unfinished row reads `—`.

**Unfinished rows belong here.** A scan belongs to its box from delivery, so a pending or running
scan appears in this table before it has any counts (TRUTH rule 12, acceptance "Stub already
belongs"). Do not filter the query to `status=completed`.

**Row navigation.** Each row opens `/scans/:scanId`. Whole row is the link.

### 4.2 Blank (no scans from this box)

```
│  Scan history                                                                            │
│                                                                                          │
│  No scans from this box yet.                                                             │
```

One sentence only (TRUTH rule 19). No button, no pagination, and **no column headers** — a table
never renders bare with no rows (Foundations §Tables).

### 4.3 Loading

Skeleton for the history block on first load: heading and column headings render immediately;
step `4` below, three skeleton rows at 56px. `data-testid="device-scan-history-loading"`.

### 4.4 Error

Section-scoped, same pattern as Network detail vulnerabilities card error (042 §7.1): the rest
of the screen stays. Copy: `Couldn't load this box's scan history.` + `Try again`. Does not
replace the page error gate.

### 4.5 Viewer, offline, chooser, running scan

Scan history section is **readable for both admin and viewer** (TRUTH rule 20). It renders in all
042 device-detail states where the identity block renders, including viewer (§9.3), offline
(§9.6), and while a scan is running (§9.5). It does not hide behind the network chooser.

### 4.6 Keyboard and focus

After existing device-detail tab order (042 §9.9), history rows (when present) → history retry
(when in error) → history pagination. Enter on a row opens the scan.

---

## 5. Copy

### 5.1 Scans list (new and changed strings)

| Where | String |
| --- | --- |
| Column headings (full set) | `When` · `Box` · `Mode` · `Status` · `Duration` · `Machines` · `Vulnerabilities` · `Highest severity` |
| Box, attributed | `{box_name}` from API (e.g. `Rontho HQ`) |
| Box, unattributed | `—` (`EmptyMark`) |
| Duration, under 60s | `{n}s` (e.g. `45s`) |
| Duration, 60s or more | `{n} min` whole minutes only (e.g. `8 min` for 500 seconds) |
| Duration, absent | `—` (`EmptyMark`) |
| All other scans-list strings | Unchanged from 042 §4.4 |

### 5.2 Scan detail (new strings)

| Where | String |
| --- | --- |
| Strip label | `Duration` |
| Strip value, under 60s | `{n}s` |
| Strip value, 60s or more | `{n} min` |
| Strip value, absent on completed scan | `—` (`EmptyMark`) |
| All other scan-detail strings | Unchanged from 042 §5.4 |

### 5.3 Device detail (new strings)

| Where | String |
| --- | --- |
| Section heading | `Scan history` |
| Column headings | `When` · `Mode` · `Status` · `Duration` |
| Blank | `No scans from this box yet.` |
| History error | `Couldn't load this box's scan history.` |
| History retry button | `Try again` |
| All other device-detail strings | Unchanged from 042 §9.10 |

---

## 6. `formatScanDuration` helper

**Path:** `frontend/src/lib/scanDuration.ts` (tests beside it in `scanDuration.test.ts`)

**Input:** `duration: number | null | undefined` from the contract.

**Output:** Owner-facing string, or `null` when the caller must render `EmptyMark`.

| Condition | Copy |
| --- | --- |
| `null` / `undefined` | `null` → `EmptyMark` |
| `0`–`59` | `{n}s` |
| `60`+ | `{Math.floor(n / 60)} min` (whole minutes; no hours form, TRUTH rule 10) |

**Tests** (when implemented): `45` → `45s`; `500` → `8 min`; `59` → `59s`; `60` → `1 min`;
`null` → `null`.

---

## 7. Data

Fields below are added to the OpenAPI contract by the backend work for this feature. Consume
regenerated `frontend/src/types/openapi.d.ts`; do not invent parallel names in the frontend.

### 7.1 Scans list

| Call | Fields consumed |
| --- | --- |
| `GET /api/v1/scans` (`listScans`) | Existing: `scan_id`, `timestamp`, `scan_mode`, `status`, `host_count`, `finding_count`, `highest_severity`, `total`, `page`. **New on each `ScanSummary` row:** producing box (`agent_id`, `box_name` at read time) and `duration` (nullable integer, whole seconds). **New query param (optional):** filter by producing box (`agent_id`) per TRUTH rule 12. |

**UI mapping**

| Cell | Contract field | Render |
| --- | --- | --- |
| Box | `box_name` when `agent_id` present; absent when unattributed | text or `EmptyMark` |
| Duration | `duration` | `formatScanDuration` or `EmptyMark` |

### 7.2 Scan detail

| Call | Fields consumed |
| --- | --- |
| `GET /api/v1/scans/{scan_id}` (`getScanById`) | **New:** `duration` on `ScanDetailResponse`. Producing-box fields may be present on the contract but **are not shown** on this screen (TRUTH rule 16). |

### 7.3 Device scan history

| Call | Fields consumed |
| --- | --- |
| `GET /api/v1/scans` (`listScans`) with `agent_id={agentId}` | Same paginated `ScanListResponse` as the run log; only scans belonging to that box (TRUTH rules 12, 17). Fields consumed per row: `scan_id`, `timestamp`, `scan_mode`, `status`, `duration`. `box_name` / `agent_id` are not read here — every row is the same box. |

---

## 8. New and changed frontend files

| Path | Role |
| --- | --- |
| `frontend/src/lib/scanDuration.ts` | **New.** `formatScanDuration(seconds)`: seconds → owner duration copy; returns `null` for EmptyMark. |
| `frontend/src/lib/scanDuration.test.ts` | **New.** Vitest beside source; `45`, `59`, `60`, `500`, `null` cases. |
| `frontend/src/pages/scans/scanListColumns.tsx` | **Changed.** Insert Box after When, Duration after Status; update `colgroup` widths §2.1. |
| `frontend/src/pages/scans/ScanDetailHeader.tsx` | **Changed.** `ScanSummaryStrip` adds fifth `StripEntry` for Duration when not `hidesCounts`. |
| `frontend/src/pages/agents/DeviceScanHistory.tsx` | **New.** Section heading, the four-column table, list/query/pagination/blank/loading/error. |
| `frontend/src/pages/agents/deviceScanHistoryColumns.tsx` | **New.** `DataTableColumn<ScanSummary>[]` for When · Mode · Status · Duration; reuses `Timestamp`, `SCAN_MODE_LABEL`, `scanStatusLabel`, `formatScanDuration` and `EmptyMark`. |
| `frontend/src/pages/DeviceDetail.tsx` | **Changed.** Mount `DeviceScanHistory` below scan controls at step `12`. |
| `frontend/src/api/scans.ts` | **Changed.** Accept optional `agent_id` on `listScans` params for device history. |

No new routes. No Box on scan detail. No restyle of shared components beyond new cells.

---

## 9. `data-testid`

### 9.1 Scans list (new)

| id | Element |
| --- | --- |
| `scans-box-{scan_id}` | Box cell |
| `scans-duration-{scan_id}` | Duration cell |

All other scans ids unchanged from 042 §4.5 (`scans-page`, `scans-table`, `scans-table-row-{scan_id}`, etc.).

### 9.2 Scan detail (new)

| id | Element |
| --- | --- |
| `scan-summary-duration` | Duration strip entry (label + value wrapper) |

All other scan-detail ids unchanged from 042 §5.5.

### 9.3 Device detail (new)

| id | Element |
| --- | --- |
| `device-scan-history` | Section container |
| `device-scan-history-table` | Table/list wrapper when rows exist |
| `device-scan-history-row-{scan_id}` | One history row link |
| `device-scan-history-blank` | Blank sentence container |
| `device-scan-history-loading` | Loading skeleton block |
| `device-scan-history-error` | Section error message |
| `device-scan-history-error-retry` | Section retry button |
| `device-scan-history-pagination` | Pagination root |
| `device-scan-history-previous` | Previous page control |
| `device-scan-history-next` | Next page control |

Existing device-detail ids unchanged (`device-detail`, `agents-scan-now`, etc.).

---

## 10. States summary

| Surface | Loading | Blank | Error | Attributed box | Unattributed box | Duration present | Duration absent (failed / running / no report) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Scans list | Skeleton body | No scans yet (042) | Couldn't load… (042) | Box = display name | Box = `EmptyMark` | Duration copy | Duration = `EmptyMark` |
| Scan detail strip | (page gate) | n/a | (page gate) | n/a (no Box) | n/a | Duration copy | Completed: `EmptyMark`; failed/running: entry omitted |
| Device history | Section skeleton under column headings | No scans from this box yet. | Section error + retry | n/a (no Box column) | n/a (no Box column) | Duration copy | Duration = `EmptyMark` |

---

## 11. Out of scope (v1)

From TRUTH and 042, unchanged:

- Box field on scan detail.
- Nested link in the Scans Box cell (whole row wins; see §1).
- New-versus-known result column (DMI-70).
- Daily scan schedule / default scan type (DMI-133).
- Filter UI on `/scans` for box (API filter exists for device history; no global filter control required).
- Status label changes (`Complete` vs `Completed`).
- Hardware-agent TUI, restyle, dark theme, mobile.

---

## 12. Open questions for the approval gate

**Q1 (CLOSED 2026-09-05): Device-detail scan history columns.** Decided at the visual review
against the rendered preview: **When · Mode · Status · Duration** (§4.1). The table says that a
scan ran and how it ran; findings stay on the scan the row opens. Box is absent because every row
is the same box. TRUTH rule 18 was amended to match, and `device-scan-history-open` is gone with
the line it labelled.

**Q2 (CLOSED): TRUTH rule 13 vs whole-row link.** Resolved to match FOUNDATIONS. The Box cell is
display text. The whole row opens the scan. The owner opens a box from Devices. TRUTH rule 13
was amended to match.

**Q3 (CLOSED 2026-09-05): Rendered preview artifact.** Published and reviewed; the link is at the
top of this document. Three review notes fell **outside this spec**. Two are not drawn into it and
each needs its own ticket against Foundations; the third landed here, as noted:

- Rename the run-log `Highest severity` column to `Severity` (Foundations §Tables names the
  highest-severity column; `scanListColumns.tsx` ships the long label).
- Replace the top bar's `[Log out]` with a menu under the user's email. **Landed on this branch**
  rather than deferred: `components/ui/dropdown-menu.tsx` adds the popover-menu pattern and
  `TopBar.tsx` makes the identity its trigger. Foundations §Chrome was updated to match.
- Show a column heading's full name on hover when it truncates.

**Q4 (CLOSED 2026-09-05): Interim history row content.** Moot — Q1 closed, so there are no
placeholder rows. Rows carry the four cells in §4.1.

---

## 13. Related specs

| Doc | Role |
| --- | --- |
| [`TRUTH.md`](TRUTH.md) | Behaviour and acceptance |
| [`specs/042-design-system/DESIGN.md`](../042-design-system/DESIGN.md) | Layout inherited for all three screens |
| [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md) | Tokens, EmptyMark, Timestamp, tables |
| Backend / OpenAPI update (same feature) | `ScanSummary` / `ScanDetailResponse` fields and `listScans` `agent_id` filter |
