# UI Screens — Specs

> **Status:** template (2026-07-10) — no screen specced yet. Bottom layer of the UI docs ladder:
> [`REFERENCE.md`](REFERENCE.md) (principles) → [`FLOWS.md`](FLOWS.md) (breadboards) →
> **SCREENS.md** (layouts, states, copy). A screen section may only be written after its flow is
> locked in FLOWS.md, and each section is filled **top to bottom** — the template order is the
> method: epicenter first, chrome last ([`REFERENCE.md`](REFERENCE.md) §2, §5, §6, §7).

## Foundations

Shared decisions every screen inherits. Fill these before the first screen spec.

### Severity tokens

<!-- Re-validate the March palette (AA contrast in both themes — IDEAS.md → Theming) before locking. -->

| Severity | Color | Usage |
| --- | --- | --- |
| Critical | `<hex>` | |
| High | `<hex>` | |
| Medium | `<hex>` | |
| Low | `<hex>` | |
| Informational | `<hex>` | visual token only — not a contract severity |

### Viewport

<!-- Desktop-only? Target and minimum widths; behavior below minimum. -->

### Shared components

<!-- Confirm/trim the list; add only components two or more screens actually use. -->
<!-- Candidates: Sidebar · TopBar · PageHeader · MetricCard · DataTable · SeverityBadge · EmptyState · LoadingSkeleton · Breadcrumbs -->

### Consistency rules

<!-- Cross-screen rules: clickable rows, timestamp format, ID truncation, every table ships skeleton + blank + error, … -->

## Screen index

Status: `☐` not specced · `◐` draft · `✅` locked. Routes and roles per
[`FLOWS.md`](FLOWS.md) places inventory.

| Screen | Route | Shell | Roles | Flow | Status |
| --- | --- | --- | --- | --- | --- |
| Login | `/login` | outside | public | B1 | ☐ |
| Accept invite | `<route>` | outside | public | B2 | ☐ |
| Forgot password | `<route>` | outside | public | B1 | ☐ |
| Reset password | `<route>` | outside | public | B1 | ☐ |
| Forced password change | `<route>` | outside | public | B1 | ☐ ⚠️ blocked (contract gap) |
| Dashboard (Review) | `/dashboard` | inside | admin, viewer | B2, B3 | ◐ |
| Scan list | `/scans` | inside | admin, viewer | B3 | ☐ |
| Scan detail | `/scans/:scanId` | inside | admin, viewer | B3, B4 | ☐ |
| Host inventory | `/hosts` | inside | admin, viewer | B3 | ☐ |
| Host detail | `/hosts/:hostId` | inside | admin, viewer | B3 | ☐ |
| Agents | `/agents` | inside | admin, viewer (ro) | B4 | ☐ |
| Users & invites | `<route>` | inside | admin | B2 | ☐ |

---

## Per-screen template

Copy this block once per screen, in the order the screens get built (admin-first). Fill it top
to bottom; do not start the ASCII layout until everything above it is written.

```markdown
### <SCREEN NAME>

**Route:** `<path>` · **Shell:** <inside | outside> · **Roles:** <admin | viewer | public> ·
**Flow:** <B# in FLOWS.md>

**Epicenter** — the one thing this screen cannot live without; design it first, chrome last:
<one sentence>

**Data** — endpoints and fields consumed (contract names, not invented ones):
- `GET/POST <endpoint>` — <what it feeds>

**Three states** — each deliberately designed, none inherited by accident:
- **Regular:** <what the screen shows flush with data>
- **Blank:** <first-run state — what it teaches, and the CTA it offers>
- **Error:** <what failure looks like, and what the user can do next>

**Copy** — real words written here, never lorem ipsum; buttons say what they do:
| Element | Copy |
| --- | --- |
| <button / toast / empty state / error> | "<exact text>" |

**Layout** — ASCII wireframe, written LAST:
​```text
+----------------------------------------------------------+
| <sketch>                                                 |
+----------------------------------------------------------+
​```

**Open questions:** <list, or "none">
```

---

## Screens

### DASHBOARD (REVIEW)

**Route:** `/dashboard` · **Shell:** inside · **Roles:** admin, viewer ·
**Flow:** B2 (blank slate), B3

Not a metrics dashboard — a review. The nav item is labeled **Review**. The product
interprets; the operator reads a judgment, not numbers (REFERENCE.md §6, §8, §10). On a
normal day the page is mostly empty on purpose.

**Epicenter** — the one thing this screen cannot live without, designed first, chrome last:
the verdict line — one plain sentence stating whether anything needs the operator's
attention since they last looked.

**Data** — endpoints and fields consumed (contract names):
- `GET /api/v1/scans?per_page=1` (default sort `timestamp` desc) — latest scan feeds the
  verdict, the scan-failed item (`status: failed`), and the context footer (`timestamp`,
  `device_count`, `finding_count`, `highest_severity`, `scan_mode`)
- `GET /api/v1/findings?scan_id={latest}&severity=critical` (and `severity=high`) — finding
  review items (`title`, `cve_id`, `ip`, `severity`)
- `GET /api/v1/agents/{agent_id}` — `online`, `last_seen_at`, `display_name` feed the
  coverage-stale item and the footer Pi status
- New-device item: **no contract support yet** — `HostSummary` lacks `first_seen_at`
  (FLOWS.md open decision #4); the item is cut until the field exists

**Three states** — each deliberately designed, none inherited by accident:
- **Regular, all clear (the common case):** verdict + context sentence, centered, generous
  whitespace; small engraving ornament; muted footer with Pi status. No review items, no
  empty-table scaffolding — the near-empty page *is* the design (positive framing).
- **Regular, items pending:** verdict states the count; below it, one square-edged card per
  review item in plain language, each linking where the operator deals with it (finding →
  scan detail, failure → scan detail, stale coverage → Agents). Deep purple marks the item
  label; red appears only inside a critical-severity badge. Medium/low findings and routine
  successful scans never appear here.
- **Blank:** first-run onboarding per B2 — explains what a scan is, admin gets
  [Run first scan] → AGENTS; viewer gets the explainer with "Ask your admin to run the
  first scan." instead of a CTA (affordance omitted, not disabled).
- **Error:** page-level failure copy + [Retry]; no partial skeletons pretending to be a verdict.

**Copy** — real words, buttons say what they do:
| Element | Copy |
| --- | --- |
| Verdict — all clear | "Nothing needs your attention." |
| Context — all clear | "Last scan finished yesterday at 21:40 — 12 hosts, no critical findings." |
| Verdict — items pending | "2 things need your review." |
| Review item — finding | "Critical: CVE-2024-4577 on synology-nas (192.168.1.42). Found in last night's scan." · [View finding] |
| Review item — scan failed | "Last night's scan didn't finish." · [See why] |
| Review item — coverage stale | "The Pi hasn't been seen since Tuesday." · [Check the Pi] |
| Blank — heading | "No scans yet." |
| Blank — body | "Dmitri scans your network for devices and known vulnerabilities, then reports anything worth your attention here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the review." · [Retry] |
| Footer | "Last scan: yesterday 21:40 · 12 hosts · quick mode" / "Pi status: online · last seen 2 min ago" |

**Layout** — fat-marker fidelity; paddings and exact columns not fixed here:

Regular — items pending:
```text
+------------------------------------------------------------------------------+
| DMITRI          Review  Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|   ~ small engraving ornament ~                                               |
|                                                                              |
|   2 THINGS NEED YOUR REVIEW.                                                 |
|   ------------------------------------------------------------------        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   | ▓ CRITICAL FINDING                                              |        |
|   |   CVE-2024-4577 on synology-nas (192.168.1.42)                  |        |
|   |   Found in last night's scan.                                   |        |
|   |                                              [View finding] →   |        |
|   +----------------------------------------------------------------+        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   | ▓ THE PI HASN'T BEEN SEEN SINCE TUESDAY                         |        |
|   |                                               [Check the Pi] →  |        |
|   +----------------------------------------------------------------+        |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Last scan: yesterday 21:40 · 12 hosts · quick mode         (muted)         |
|   Pi status: online · last seen 2 min ago                                    |
+------------------------------------------------------------------------------+
```

Regular — all clear:
```text
+------------------------------------------------------------------------------+
| DMITRI          Review  Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                                                                              |
|                     NOTHING NEEDS YOUR ATTENTION.                            |
|                                                                              |
|          Last scan finished yesterday at 21:40 — 12 hosts,                   |
|          no critical findings.                                               |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Pi status: online · last seen 2 min ago                                    |
+------------------------------------------------------------------------------+
```

Blank — first run (admin):
```text
+------------------------------------------------------------------------------+
| DMITRI          Review  Scans  Hosts  Agents  Users              [Log out]   |
+==============================================================================+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                                                                              |
|                              NO SCANS YET.                                   |
|                                                                              |
|          Dmitri scans your network for devices and known                     |
|          vulnerabilities, then reports anything worth your                   |
|          attention here.                                                     |
|                                                                              |
|                        +---------------------+                              |
|                        | ▓  Run first scan   |   → Agents                   |
|                        +---------------------+                              |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. New-device review item — blocked on contract (`first_seen_at` on `HostSummary`,
   FLOWS.md open decision #4); cut from v1 until resolved.
2. Coverage-stale thresholds: Pi `online: false` is immediate, but "no completed scan in
   N days" needs an N.
3. "Not seen before" phrasing needs a backend finding-delta (IDEAS.md backend note); v1
   copy claims only "found in last night's scan".
4. Rename route `/dashboard` → `/review` to match the nav label, or keep the route stable?
