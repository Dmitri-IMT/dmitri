# DESIGN — Scan and vulnerability screens for non-experts

> **Status:** draft, decided with the owner on 2026-10-23.
> **Visual source:** [Dmitri scan visual cues canvas](https://claude.ai/artifact/UVnbjzroi7jkG1Xz6BsWFf).
> Canvas tab **Options**: boards **1A**, **2B** (with the **2A** hint) and **3C** are the
> chosen pieces; the other boards are rejected options (§8). Canvas tab **Scans page**: all
> five boards are approved (2026-10-23) and are specified in §14–§19.
> **Product context:** [`PRD.md`](PRD.md) — information plan, output shape, voice rules.
> **Binding look:** [`docs/ui/FOUNDATIONS.md`](../../docs/ui/FOUNDATIONS.md). Where this
> document and FOUNDATIONS disagree, FOUNDATIONS wins and the difference is an open item.

## 1. Scope

| Screen | Change |
|--------|--------|
| Scan Detail | Whole page re-ordered (§14): header with **Explain this scan**, **scan story strip** (§4), **to-do list** (§15), **meaning table** (§5), **All problems** table (§16), **For your IT person** sections (§14). Terms open **hints** (§6). |
| Finding panel (scan and host views) | Rebuilt as the **vulnerability view** (§7), opened inline in the table row; other states in §17. |
| Explain this scan | Side panel (§18). |
| AI assistant dialog | Answer layout and waiting state (§19). |
| Any screen showing a Dmitri risk score | Score hint (§6.3) next to the number. |

Not in scope here: Home (code-only status, its small scan review is a PRD open item), PDF
reports.

## 2. Principles applied

From FOUNDATIONS and the interview:

- The reader is a non-technical owner. The page **interprets** first; raw data is behind
  "Technical details".
- **Say it in a label.** Short labelled parts and lists, not paragraphs.
- **Severity has no hue.** `Critical` / `High` / `Medium` / `Low` are a bold `--ink` word.
  No chip, pill, badge, coloured text, coloured border or coloured bar anywhere.
- **One accent, used sparingly.** `--accent` only for links and focus.
- Explain a term where it appears (hint), not on a separate help page.
- **Code writes facts, the AI writes advice.** Each element below names its source:
  `code` (deterministic, from the API), `copy` (fixed i18n text), or `AI` (fix tasks and
  plain titles from the analysis job).

## 3. Tokens used

All values are FOUNDATIONS tokens. Nothing new is added.

| Use | Token |
|-----|-------|
| Page | `--canvas` `#FCFCFC` |
| Cards, panels | `--card` `#FFFFFF`, 1px `--rule` `#E2E8F0`, radius 12px |
| Inner boxes (fact cards, score tiles, fix block) | 1px `--rule`, radius 8px (`--control-radius`) |
| Primary text, bars "full" | `--ink` `#0F172A` |
| Secondary text, labels | `--ink-muted` `#475569` |
| Bar track | `--rule` `#E2E8F0` |
| Lighter bar (Medium, Low), dashed outlines | `--edge` `#64748B` |
| Links, focus ring | `--accent` `#600BB5` |
| Hint surface | `--ink` background, `#FFFFFF` text, radius 8px |
| Data (IP, port, CVE, version, CIDR) | `--font-mono` |

Type: only the seven FOUNDATIONS tokens. Board mapping: page title `title-lg` (32px), big
numbers `title-md` (24px) or `title-lg`, section titles `title-sm` (22px) or `title-xs`
(16px), body `body-md` (15px), helper `body-sm` (14px), labels and metadata `caption-md`
(13px).

Spacing: 4px steps only. Card padding 24px (step 6), vulnerability article padding 32px
(step 8), gap between groups 16px or 24px, between sections 32px.

## 4. Scan story strip (board 1A)

**Purpose:** answer "what did this scan do?" with no AI text.

**Placement:** Scan Detail, directly under the page header. Full content width.

**Layout:** one card, title `What this scan did` (`title-xs`). Inside, an ordered list of
four steps in a 4-column grid, gap 24px. Each step is a vertical stack, gap 8px:

1. Label row: 20px stroke icon (`--ink`, stroke 1.75) + `N · Label` in `caption-md`
   `--ink-muted`.
2. Value in `title-sm` (22px, 600).
3. Optional data line or bar.
4. Helper sentence in `body-sm` `--ink-muted`.

| # | Label | Value | Data line | Helper | Source |
|---|-------|-------|-----------|--------|--------|
| 1 | `1 · Looked at` | `Your network` (see open item 4) | subnet in mono, e.g. `192.168.1.0/24` | `The part of your network Dmitri was allowed to check.` | `code`: `ScanDetailResponse.subnet` |
| 2 | `2 · Found` | `{n} machines` | — | type breakdown `1 router · 4 cameras · 6 computers · 2 printers · 1 unknown` | `code`: `host_count`; breakdown from each host's `machine_type` (see §10 gap) |
| 3 | `3 · Checked` | scan mode label from `SCAN_MODE_LABEL`: `Quick` / `Standard` / `Extensive` / `Max` / `NSPi` (the boards' "Deep check" is a placeholder) | `Took {duration}` | one plain sentence per mode, shortened from `SCAN_MODE_DESCRIPTION` | `code`: `scan_mode`, `duration`; `copy` per mode |
| 4 | `4 · Finished` | `{done} of {total} checks` | progress bar, 8px, `--ink` on `--rule`, `role="img"` with the same text as label | `{k} machine did not answer. Its problems may be missing from this scan.` (omit when k = 0) | `code`: `coverage`, `evidence_completeness`, `incomplete_check_count` |

Icons (inline stroke SVG, `aria-hidden="true"`): globe, monitor, magnifier, check.

**Removed:** the "Next: see your to-do list" link under the strip. The owner rejected it.

**States:**

| State | Behaviour |
|-------|-----------|
| Completed, all checks done | Step 4 shows `12 of 12 checks`, full bar, no helper. |
| Completed, partial (`evidence_completeness = partial`) | As drawn. Helper names what is missing. |
| Completeness `unknown` | Step 4 value `Not reported`, no bar, helper `This scan does not say whether every check finished.` |
| Stopped early (`terminated_by`) | Step 4 value `Stopped early`, helper says by whom (operator, timeout, error), existing stop notice stays. |
| Running | Strip not shown; the existing progress UI stays. |
| 0 machines found | Step 2 `No machines`, helper `Dmitri found no machines that answered on this network.` Steps 3–4 still show. |
| Machine type unknown for all | Step 2 shows only `{n} machines`, no breakdown line. |

## 5. Meaning table (board 2B)

**Purpose:** answer "how serious is this, and how soon do I act?" with fixed copy and
this scan's counts.

**Placement:** Scan Detail, under the story strip, above the vulnerability list. The owner
will adjust the table design; this section is the baseline.

**Layout:** card, title `How serious are the problems, and how soon should you act?`
(`title-xs`). A real `<table>` with four columns:

| Column | Header (`caption-md`, `--ink-muted`, weight 400) | Cell |
|--------|------|------|
| Level | `Level` | `<th scope="row">`, bold `--ink` severity word; a hint trigger (§6) |
| Yours | `Yours` | count bar + bold count |
| What it means | `What it means` | `body-md` copy |
| Act | `Act` | timing copy; bold only for Critical |

Rows, top to bottom, 1px `--rule` line between rows:

| Level | What it means | Act | Bar fill |
|-------|---------------|-----|----------|
| **Critical** | `An attacker can use it easily, often without a password.` | **`This week`** | `--ink` |
| **High** | `Serious, but the attacker needs some access first.` | `This month` | `--ink` |
| **Medium** | `Hard to use, or causes limited harm.` | `When you can` | `--edge` |
| **Low** | `Small risk. Fix it with other work.` | `No rush` | `--edge` |
| Not checked (regular weight, `--ink-muted`) | `Did not answer. It can have problems that are not listed.` | `Scan again` | dashed 1px `--edge` outline, no fill |

**Bar rule:** height 12px, radius 2px, `aria-hidden="true"` (the count is the text).
Width = `count / max(count over the four levels) × 160px`; minimum 4px when count > 0; no
bar when count = 0, and the count shows `0` in `--ink-muted`. The Not checked bar is a
fixed 20×10px dashed box. Bars differ by lightness (ink vs edge), never by hue.

**Sources:** counts are `code` (`risk.severity` counts; not-checked from coverage), all
text is `copy`.

**States:** no vulnerabilities → the table still shows, all counts `0`, and the card adds
one line `No known problems were found. This does not prove the network is safe.` (the
PRD voice rule). Not checked row hidden when every machine answered.

## 6. Hints (board 2A behaviour)

One shared component for every explained term. The owner chose this behaviour: **click or
tap the term to open the hint.**

### 6.1 Behaviour

- Trigger: the term itself, a real `<button type="button">`, dotted underline
  (`--edge`, offset 4px). Open state: solid `--ink` underline.
- Click, tap, Enter or Space toggles. Escape closes and returns focus to the trigger.
  Click outside closes. Only one hint is open at a time.
- `aria-expanded` and `aria-controls` on the trigger; the panel has `role="tooltip"` and
  an `id`. Hover alone does not open it (touch and keyboard parity).
- Panel: `--ink` background, white text, radius 8px, padding 16px (20px for the risk
  breakdown), width 320px (380px for the risk breakdown), gap 8px. Placed below the
  trigger, flipped to stay in the viewport.
- Content: line 1 term in `body-md` 600; line 2 the fixed meaning (`copy`); optional line
  3 with this scan's numbers (`code`), e.g. `Yours: 23 doors on 14 machines. 6 of them
  are on the router.`

### 6.2 Hint copy (English baseline)

| Term | Meaning |
|------|---------|
| Critical | `An attacker can use it easily, often without a password. Fix it this week.` |
| High | `Serious, but the attacker needs some access first. Fix it this month.` |
| Medium | `Hard to use, or causes limited harm.` |
| Low | `Small risk. Fix it together with other work.` |
| Not checked | `The machine did not answer, so Dmitri could not check it.` |
| Open ports | `Doors on a machine that accept connections from the network. Each door is a way in. Fewer is better.` |
| Used in real attacks | `A US government agency (CISA) lists this flaw as used by attackers today.` |
| CVSS | `How bad the flaw is in general, from 0 to 10, set by security experts. It does not know your network.` |
| EPSS | `The chance that attackers try this flaw somewhere in the next 30 days. A public model updates it every day.` Line 3: `{p}% is {very high / high / low}. Most flaws are below 1%.` |
| CISA KEV | `A public list of flaws that attackers use today. If a flaw is on it, fix it first.` |
| Dmitri risk | See §6.3. |

pt-BR and ru copy: written in the i18n task, reviewed by the owner. Same keys.

### 6.3 Dmitri risk hint (risk breakdown)

Title `How Dmitri scores risk`. Line `Four parts, added up to a score from 0 to 100. Higher
means fix it sooner.` Then four rows, each `label` + `value / max` (600) and a 6px bar
(white fill on `--ink-muted` track):

| Row label | Max | Value from | Formula (`services/risk.py`) |
|-----------|-----|------------|------------------------------|
| `How serious the flaw is` | 45 | `severity` | weight (low .25, medium .5, high .75, critical 1) × 45 |
| `How likely attackers use it` | 35 | `exploitability` | min(1, EPSS × 0.7 + 0.3 if KEV + 0.1 if ransomware) × 35 |
| `How sure Dmitri is` | 15 | `confidence` | weight (tentative .5, probable .75, confirmed 1; missing .5) × 15 |
| `Reachable on your network` | 5 | `port` | 5 when the finding has a port, else 0 |

Footer `caption-md`: `Severity, EPSS and the CISA list come from public data. Confidence
and reachability come from this scan.` Values show one decimal; the total is capped at
100.

The breakdown must come from the backend (see §10), so the formula lives in one place.

## 7. Vulnerability view (board 3C)

**Purpose:** answer "what is this, can it hurt me, how do I fix it?" first; keep every
technical fact one click away.

**Container:** article, max width 820px, `--card`, 1px `--rule`, radius 12px, padding
32px, gap 32px between the four blocks below. Replaces today's finding panel stack
(Severity, Method, Status, Confidence, Recorded observations, Risk score, Exploitability,
What it is, What to do, Evidence, References, CVSS, Seen on, AI explanation).

### 7.1 Header

Two columns, gap 32px.

**Left (flexible):**
- Meta line `caption-md` `--ink-muted`: bold `--ink` severity word ` · ` machine name
  (`code`: host display name or machine type + label, e.g. `Front door camera`).
- Title `title-md` (24px): a plain-language sentence about the effect, e.g. `Anyone on
  your network can take control of this camera`. Source `AI` (plain title from the
  analysis). Fallback: scanner `title`.
- Subtitle `body-md` `--ink-muted`: one sentence on the cause, e.g. `The camera runs old
  software with a known flaw. No password is needed to use it.` Source `AI`. Hidden when
  absent.

**Right (fixed 200px), the Dmitri risk block:**
- Label `Dmitri risk` (`caption-md`, 600, `--ink`) + 20px info button (§6.3 hint),
  `aria-label="How Dmitri risk is calculated"`.
- Number `title-lg` (32px) + ` of 100` (`body-md`, `--ink-muted`). Rounded to an integer.
- Bar 8px, `--ink` fill on `--rule` track, `role="img"` `aria-label="Risk {n} of 100"`.
- Rank line `caption-md` `--ink-muted`: `Fix {k} of {n} on your to-do list` — the position
  of the fix task that covers this finding. Hidden when there is no to-do list yet.
- `risk_score` null → number `—`, no bar, line `Not calculated yet`.

### 7.2 Three facts

Definition list in a 3-column grid, gap 16px. Each fact: 1px `--rule` box, radius 8px,
padding 16px, label `caption-md` `--ink-muted`, answer `body-md`, first word bold.

| Label | Answer | Source |
|-------|--------|--------|
| `What could happen` | Effect on this kind of machine, e.g. `Someone watches the video, or uses the camera to reach other machines.` | `AI` |
| `Used in real attacks?` | **Yes.** `The US cyber agency lists it as actively used.` / **Not known.** `No public report of attacks yet.` | `code`: KEV flag (+ EPSS ≥ 10% → `Likely.`) |
| `How sure is Dmitri?` | **Confirmed.** / **Likely.** / **Possible.** + method sentence, e.g. `Based on the software version the camera reported.` | `code`: `confidence` + `detection_method` |

When the AI part is missing, "What could happen" shows the scanner `description`.

### 7.3 "What do I do?" block

Box: `--canvas` background, 1px `--rule`, radius 8px, padding 24px, gap 12px. Title
`What do I do?` (`title-sm`).

1. **Easiest fix:** name `body-md` 600, e.g. `Easiest: update the camera`. Meta
   `caption-md` `--ink-muted`: `{who} · about {time} · {fixes it fully | reduces the
   risk}`.
2. **Steps:** ordered list, up to 3 items, `body-md`. Source names are links (`--accent`)
   built only from citation data (PRD R5), e.g. `Hikvision security advisory`.
3. **Fallback** (when a second, faster option exists): top border `--rule`, padding-top
   12px. Name 600, e.g. `If you cannot update now: unplug it`; meta `You · 1 minute ·
   stops the risk until the update`.
4. **Check line** `body-sm` `--ink-muted`: `Check: run a new scan. This problem disappears
   from the list.`

Source: `AI` fix task / R3 fix record (`title`, `who`, `effort`, `steps`,
`how_to_verify`, `sources`, `fixes_fully`). `who` copy: `You`, `Your IT person`, `The
vendor`.

**States:**

| State | Behaviour |
|-------|-----------|
| Fix task ready | As drawn. |
| AI analysis running | Block shows the waiting state (§9) with `Finding the easiest fix…`. |
| No AI fix (AI off, failed, or no cited source) | Block shows the scanner `recommendation` as one paragraph under `What do I do?`, no meta, no fallback. Never two "what to do" texts. |
| Fixed (`fixed_at` set) | Block replaced by `Fixed on {date}. Dmitri did not see this problem in the last scan.` |

### 7.4 Technical details

Section with top border `--rule`, padding-top 24px. Header row: `Technical details`
(`title-xs`) and a text button `Show` / `Hide` (`body-sm` `--ink-muted`,
`aria-expanded`). **Closed by default**; board 3C draws it open.

**a) Scores** — sub-label `Scores` (`caption-md`). 4-column grid of tiles, gap 12px. Each
tile: 1px `--rule`, radius 8px, padding 16px; label `caption-md` + 14px info icon that
opens the §6.2 hint; value `title-sm` + unit `caption-md` `--ink-muted`.

| Tile | Value | Unit | Source |
|------|-------|------|--------|
| CVSS | `9.8` | `of 10` | `cvss_score` |
| EPSS | `{p}%` | — | EPSS for the CVE (§10 gap) |
| CISA KEV | `Listed` / `Not listed` | — | KEV flag (§10 gap) |
| Dmitri risk | `{n}` | `of 100` | `risk_score` |

A tile whose hint is open gets a 2px `--ink` border (padding 15px). Tiles with no value
show `—` and stay (no CVE → CVSS, EPSS and KEV show `—` with hint line `This problem has
no public CVE record.`).

**b) Where and how it was found** — sub-label, then a 2-column definition list (180px
labels, `body-sm`):

| Label | Value | Source |
|-------|-------|--------|
| `CVE` | mono, link to NVD | `cve_id` |
| `Machine` | mono `{ip} · port {port} · {service}` | `host_ip`, `port`, `service` |
| `Software seen` | mono product and version | observed version (§10 gap) |
| `How Dmitri found it` | plain sentence per `detection_method` | `code` + `copy` (reuse `evidence.explanation.*`) |
| `Confidence` | `Confirmed` / `Probable` / `Tentative` | `confidence` |
| `Seen` | date and time | `last_seen_at` or `detected_at` |

Recorded observations (`evidence_observations`) stay available inside this section with
the existing `RecordedObservations` component, below this list.

**c) References** — sub-label, bullet list of links: vendor advisory (from the fix
record), NVD record, CISA KEV entry (when listed), then the scanner `references`.

## 8. Rejected options (kept on the canvas)

| Board | Why rejected |
|-------|--------------|
| 1A "Next: see your to-do list, 4 tasks" link | Owner: unclear, not liked. |
| 1B Machine map | 1A preferred. Machine-type tiles may return on Home later. |
| 2A as a standalone summary row | 2B preferred as the structure; 2A survives as the hint behaviour (§6). |
| 3A alone | Top facts kept; its "How to fix it" layout lost to 3B's block. |
| 3B alone | Question tabs dropped; its "What do I do?" block kept. |

Known error on boards 2A, 3A, 3B: the risk score is drawn as `8.7 of 10` / `9.6`. The
real scale is 0–100 (board 3C is correct).

## 9. Waiting state (shared component)

PRD R6 owns behaviour. Inspiration: [Beautiful UI Loading State](https://www.beautifului.dev).
One component, two sizes:

| Part | Large (to-do list) | Small (fix block, chat) |
|------|--------------------|-------------------------|
| Grid loader | 3×3 squares, 8px, gap 3px, radius 2px | 3×3 squares, 6px, gap 2px, radius 1px |
| Square colours | mix of `--ink`, `--edge`, `--rule`; animation shifts which squares are filled | same |
| Stage label | `body-md` 600 | `body-md` |
| Detail line | `body-sm` `--ink-muted`, e.g. `Reading group 3 of 7 · usually 2 to 4 minutes` | `caption-md` `--ink-muted`, e.g. `This can take up to a minute` |
| Elapsed time | `caption-md` `--ink-muted`, `m:ss`, tabular numbers, right-aligned | same |
| Container | 1px `--rule`, radius 8px, padding 16px, gap 16px | inline row, gap 12px (bordered box in chat) |

- Reduced motion: the grid is static.
- `role="status"` on the container. It announces the stage label when it changes, never
  the timer.
- Scan analysis adds a 6px progress bar (`--ink` on `--rule`) for `group n of m`. Chat has
  no progress bar, because nothing arrives before the answer.
- Chat adds a `Cancel` button (32px high, outline).

## 10. Data contract consumed and gaps

Available today on `FindingRead`: `severity`, `title`, `description`, `recommendation`,
`cve_id`, `cvss_score`, `host_ip`, `host_hostname`, `port`, `service`, `risk_score`,
`exploitability`, `confidence`, `risk_rationale`, `detection_method`, `evidence_status`,
`evidence_observations`, `references`, `detected_at`, `last_seen_at`, `fixed_at`.
On `ScanDetailResponse`: `subnet`, `scan_mode`, `host_count`, `duration`, `coverage`,
`evidence_completeness`, `terminated_by`.

Gaps to add in the backend task (typed fields, not parsed from `risk_rationale`):

1. `epss_score`, `kev_listed`, `known_ransomware` on the finding.
2. `risk_breakdown` `{severity, likelihood, confidence, reachable}` on the finding, from
   `refresh_risk_snapshot`, so the frontend does not copy the formula.
3. Observed product and version on the finding (also the R3 research input).
4. Machine-type counts for the scan (story strip step 2).
5. The AI fields: plain title, cause sentence, "What could happen", and the fix task that
   covers the finding with its rank.

## 11. Keyboard, focus, accessibility

- Tab order follows reading order: header, risk info button, facts, fix links, Technical
  details toggle, score info buttons, links.
- Every hint trigger is a `<button>`; focus ring 2px `--accent`. Escape closes the open
  hint.
- Bars are decorative (`aria-hidden`) when the number is shown as text; progress and risk
  bars that carry meaning have `role="img"` and an `aria-label` with the same text.
- Text contrast meets FOUNDATIONS: nothing lighter than `#64748B` for text; white on
  `--ink` in hints.
- Definition lists (`<dl>`) for facts, tiles and details; a real `<table>` with `scope`
  for the meaning table; ordered lists for steps.

## 12. Test selectors

| Element | `data-testid` |
|---------|---------------|
| Story strip | `scan-story` |
| Story steps | `scan-story-looked`, `scan-story-found`, `scan-story-checked`, `scan-story-finished` |
| Meaning table | `meaning-table` |
| Meaning rows | `meaning-row-critical`, `-high`, `-medium`, `-low`, `-not-checked` |
| Hint trigger / panel | `term-hint-trigger-{term}`, `term-hint-{term}` |
| Risk block / breakdown | `finding-risk`, `finding-risk-breakdown` |
| Facts | `finding-facts` |
| Fix block / fallback | `finding-fix`, `finding-fix-fallback` |
| Technical details | `finding-tech`, `finding-tech-toggle` |
| Score tiles | `score-tile-cvss`, `score-tile-epss`, `score-tile-kev`, `score-tile-risk` |
| Explain button / panel | `scan-explain-open`, `scan-explain-panel` |
| To-do list / task / state | `todo-list`, `todo-task-{n}`, `todo-task-toggle-{n}`, `todo-waiting`, `todo-failed`, `todo-fallback`, `todo-empty` |
| Problems table / risk cell | `problems-table`, `problems-risk-{finding_id}`, `problems-show-more` |
| IT sections | `it-section-ports`, `it-section-machines`, `it-section-targeted`, `it-section-coverage` |
| Fix waiting / scanner fallback / fixed | `finding-fix-waiting`, `finding-fix-scanner`, `finding-fixed` |
| Assistant waiting / cancel / sources | `assistant-waiting`, `assistant-cancel`, `assistant-source-link` |

## 13. Open items

1. The owner adjusts the meaning table (§5).
2. Final hint copy in pt-BR and ru.
3. ~~Layout of the AI to-do list card~~ — decided in §15.
4. Step 1 value: a friendly network name needs a source (today only the subnet exists).
5. EPSS thresholds for "very high / high / low" and for `Likely.` in §7.2.
6. Whether board 3C replaces the finding panel inside the scan table drawer and on the
   host page alike (assumed yes).
7. The machine links in a to-do task (§15) go to the host page or open the matching
   table row.
8. ~~Network and Devices screens~~ — approved, moved to specs 053 and 054.

---

# Scans page (canvas tab "Scans page", approved 2026-10-23)

## 14. Scan Detail page composition (board "Scan Detail · full page")

Desktop target 1440px. Content padding 32px top, 80px sides, 64px bottom. Gap between
sections 32px (the one inter-section step for this screen).

### 14.1 Order, top to bottom

| # | Block | Spec |
|---|-------|------|
| 0 | Top bar | Today's app bar, unchanged: wordmark left, nav centred (Home, Scans, Network, Devices, Users, Settings; gap 16px; the active item is **bold `--ink` text only**, no background, no accent), preferences icon button right. **One change:** the `AI assistant` outline button with icon moves from the floating position into the top bar, left of preferences. |
| 1 | Header | `← Scans` back link (`body-sm`, `--ink-muted`). Meta line `Scan · {date, time} · {status}` (`caption-md`). Title `title-lg`. Right-aligned, bottom-aligned actions: `Explain this scan` and `Download report`, both 40px outline buttons (1px `--edge`, radius 8px). |
| 2 | What this scan did | §4, without icons in the compact page version (icons optional). |
| 3 | Your to-do list | §15. |
| 4 | Meaning table | §5. Level words are hint triggers (§6). |
| 5 | All problems | §16. |
| 6 | For your IT person | §14.2. |

Today's summary strip (Mode, Network, Machines seen, Attack surface, Vulnerabilities,
Duration) is removed; its facts move into the story strip and the IT sections. Existing
notices (failed, stopped, unfinished, partial) keep their place above block 2.

### 14.2 For your IT person

Sub-label `For your IT person` (`caption-md`, `--ink-muted`), then one collapsed card per
technical section, gap 12px. Each card: `--card`, 1px `--rule`, radius 12px, padding 16px
24px, title `body-md` 600 + count in `--ink-muted` (`· 23 on 14 machines`), chevron on the
right, `aria-expanded`. Opening a card shows today's component unchanged.

| Card | Title and count | Today's component |
|------|-----------------|-------------------|
| Open ports | `Open ports · {n} on {m} machines` | Attack surface / `ExposureTable` |
| Machines seen | `Machines seen · {n}` | `ScanHostsTable` |
| Targeted checks | `Targeted checks · {n} results` | `ServiceTargetedFindings` |
| Check coverage | `Check coverage · {done} of {total} finished` | `ScanCoverage` |
| Industrial services | `Industrial services · {n}` (only when present) | `ScanIndustrialServices` |

## 15. To-do list card (boards "Scan Detail · full page" and "To-do list · states")

**Source:** `AI` fix tasks (PRD "Output shape"); counts and risk are `code`.

### 15.1 Ready state

- Card: `--card`, 1px `--rule`, radius 12px, padding 24px, gap 16px.
- Title row: `Your to-do list` (`title-sm`) and, right-aligned, `{n} tasks · fixes {k} of
  {total} problems` (`caption-md`, `--ink-muted`).
- Line `Easiest and most important first.` (`body-sm`, `--ink-muted`).
- Ordered list of tasks. Each task is a row with a 1px `--rule` top line (and bottom line
  on the last), padding 16px 0, gap 16px:
  - Number marker 28px circle: task 1 filled `--ink` with white number; others 1px
    `--ink` outline.
  - Title `body-md` 600, e.g. `Update the software on 2 cameras`.
  - Meta `caption-md` `--ink-muted`: `{who} · about {time} · fixes {n} problems`.
  - Right column 120px: `Risk` (`caption-md`) + highest Dmitri risk of the covered
    problems (`body-md` 600). Number only, no bar.
  - 32px chevron button, `aria-expanded`, `aria-label` `Show steps` / `Hide steps`.
- Task 1 opens by default. Open task body (indented 44px, gap 8px): ordered steps
  (`body-md`, up to 3, source names as citation links), then one line `body-sm`
  `--ink-muted`: `Cannot update now? {fallback}. · {machine links}`.
- After the list: `{n} problems have no simple fix yet. They are in the list below.`
  (`body-sm`, `--ink-muted`), hidden when 0.
- Footer `caption-md` `--ink-muted`: `Written by Dmitri AI from this scan and public
  advisories. Check each step before you act.`

Order: by effort (lowest first) and impact (risk, problems fixed), as the PRD sets. The
rank shown in §7.1 (`Task {k} on your to-do list`) is this order.

### 15.2 Other states

| State | Title | Body |
|-------|-------|------|
| A · Waiting | `Your to-do list` | Large waiting component (§9): stage `Finding the easiest fixes`, detail `Reading group {n} of {m} · usually 2 to 4 minutes`, elapsed `m:ss`, 6px progress bar at n/m. Then `You can leave this page. The list will be here when it is ready. Meanwhile, all problems are in the list below.` |
| B · Failed | `Your to-do list` | `Dmitri could not write the list this time. Your scan results are safe and complete.` + primary button `Try again` (`--accent`, 40px). |
| C · AI off | `Start here` | `The 3 problems with the highest Dmitri risk.` + ordered list: **machine name** — scanner `recommendation`. |
| D · Nothing to fix | `Your to-do list` | `Nothing to fix from this scan.` + `body-sm` `--ink-muted`: `This does not prove the network is safe. Dmitri only knows about the problems it can check. Scan again after you add a machine.` |

## 16. All problems table (board "Scan Detail · full page")

Card with title `All problems · {n}` (`title-sm`) and, right-aligned, a `Show` select
(`All problems` / `Confirmed only`, the existing evidence filter, 40px).

| Column | Width | Cell |
|--------|-------|------|
| Problem | flexible | `AI` plain title (fallback scanner `title`), `body-sm`; bold when the row is open |
| Level | 100px | bold severity word |
| Dmitri risk | 140px | **number only**, `body-sm` 600. No bar (owner decision). |
| Machine | 200px | machine name |
| CVE | 170px | mono `caption-md`, `—` in `--ink-muted` when none |
| (toggle) | 40px | chevron; header cell has a visually hidden `Details` label |

- Default sort: Dmitri risk, highest first.
- Rows open **inline**: the open row gets `--canvas` background, and the next row spans
  all columns with the §7 vulnerability view inside a `--card` article (radius 12px,
  padding 24px, gap 24px, title `title-sm` instead of `title-md`, rank line `Task {k} on
  your to-do list`). Technical details closed.
- Show the first 5 rows, then a 40px outline button `Show {n} more`.
- Empty state: today's copy (`No vulnerabilities in this scan` / no accepted evidence).

## 17. Vulnerability view — other states (board "Vulnerability row · other states")

| State | Block | Spec |
|-------|-------|------|
| A · Fix still being written | What do I do? | Small waiting component (§9): `Finding the easiest fix…`, elapsed `m:ss`. Then `body-sm` `--ink-muted`: `Meanwhile, the scanner says: {recommendation}` |
| B · No AI fix | What do I do? | The scanner `recommendation` as one `body-md` paragraph, then `caption-md` `--ink-muted` `Advice from the scanner.` No meta, no steps, no fallback. |
| C · Fixed | replaces What do I do? | Check icon + `**Fixed on {date}.** Dmitri did not see this problem in the last scan.` |
| D · No public CVE | Technical details | CVSS, EPSS, CISA KEV tiles show `—` in `--ink-muted`; Dmitri risk keeps its value. Line under the tiles: `This problem has no public CVE record. Dmitri found it with a direct check of the machine.` (the second sentence follows `detection_method`). |

## 18. Explain this scan panel (board "Explain this scan · side panel")

Opened by the header button `Explain this scan`. A right side panel, 560px wide, full
height, `--card`, 1px `--rule` left border. Focus moves into the panel; Escape and the
close button close it and return focus to the button.

- Header: `Explain this scan` (`title-sm`) + 40px close icon button
  (`aria-label="Close"`), padding 24px, bottom `--rule`.
- Body, padding 24px, gap 32px between parts. Each part has a `title-xs` heading:
  1. **In short** — 1–2 sentences (`body-md`): where the problems are and how they relate
     to the to-do list.
  2. **What your results mean** — bullet list, up to 4 items. Each item starts with a bold
     lead-in that names a number from the page (`2 critical problems.`, `1 is used in
     real attacks.`, `The router has 6 open doors.`), then one plain sentence on what it
     means for this owner. Includes good news (`Your 6 computers and 2 printers showed no
     known problems.`).
  3. **What the scan could not see** — bullet list: machines that did not answer, the
     scan's vantage point (inside the network only), and what Dmitri never checks.
  4. **Pointer box** — 1px `--rule`, radius 8px, padding 16px: `Start with task 1:
     {task title}.` (600) + `{who} · about {time}` (`body-sm`, `--ink-muted`).
- Footer, padding 16px 24px, top `--rule`: `Written by Dmitri AI from this scan.`
  (`caption-md`) and an outline button `Ask a question`, which opens the AI assistant
  (§19) with this scan as context.
- Source: `AI` for parts 1–3 (counts in the lead-ins are checked against `code` values);
  part 4 is `code` from the to-do list.
- While the explanation is written: small waiting component (§9) in the body with
  `Reading your scan…`. On failure: `Dmitri could not explain this scan right now.` +
  `Try again`.

## 19. AI assistant dialog (board "AI assistant · waiting and answer")

The existing global assistant dialog, restyled.

- Header: `Ask Dmitri` (`title-sm`) + `caption-md` `--ink-muted`: `About: {context label}
  · can search the web`.
- User message: right-aligned bubble, max 400px, `--canvas`, 1px `--rule`, radius 12px,
  padding 12px 16px, `body-md`.
- Answer (max 480px, gap 12px), following the PRD voice rules:
  1. First sentence answers the question, bold (600), followed by effort (`It takes about
     5 minutes.`).
  2. Ordered steps (`body-md`), data such as IPs in mono.
  3. Source line `body-sm` `--ink-muted`: `Steps from the {source name link}.` and a
     caveat when the steps may differ (`The menu names can differ on your model.`). The
     link comes only from citation data (PRD R5).
- Waiting: small waiting component in a bordered box (§9), stage `Looking for an answer`,
  detail `This can take up to a minute`, elapsed `m:ss`, `Cancel` button. While waiting,
  the input and the `Ask` button are disabled (input placeholder `Ask about this scan`).
- Footer, padding 16px 24px, top `--rule`: text input (40px, 1px `--edge`) and primary
  `Ask` button (`--accent`).

# Other screens in the same style

- Network screens: [`../053-network-redesign/DESIGN.md`](../053-network-redesign/DESIGN.md).
- Devices screens: [`../054-devices-redesign/DESIGN.md`](../054-devices-redesign/DESIGN.md).
