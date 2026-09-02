# DMI-131 — Design-system research (UI revamp)

**Status:** research output, 2026-09-02. Foundations decisions are settled — see §9.
Owner review of the rendered comparison page rejected three patterns; §4.8, §4.11 and §4.12 carry
the replacements. A second owner review, of the screen map (2026-09-02), then **overturned the
urgency-group presentation (§4.8) and the header-only primary action (§4.12)**, and added the
nav, Home and Scans decisions in §9. A third review, of the **full-screen mockups (2026-09-02)**,
closed most of the open items: severity is a **bold ink word, never coloured text in a table**
(§4.8), the chrome and layout patterns are settled (§4.13), the copy list grew (§4.11), and the
per-screen layouts are recorded in §9. A fourth review, of **mockups v2 (2026-09-02)**, then
**rejected severity-varying cards outright** (§4.12) and settled pagination, the inline table
select, the Home empty state and the panel rows (§4.14, §9). A fifth review, of **mockups v3
(2026-09-02)**, restored an **arrow on the back link** (§4.13), made pagination **icon-only**
(§4.14, §8), settled the Home empty state as **nothing rendered at all** (§4.14), added a
**Remove action on every Users row**, put **scan modes on the Scans page** (presentation still
open) and added a **column-gap rule for tables** (§4.14). A sixth review, of **mockups v4
(2026-09-02)**, settled the **Scan settings** section as **tabs + description** and its behaviour
(§4.15), and moved the **manual scan trigger to the Scans page as "Scan now"** (§9). A final
owner review on **2026-09-02 approved mockups v4 in full** — the Scans page and its five-tab scan
settings, the confirm-dialog copy, the five scan-type descriptions as written, the **Network list
page**, and the **silent-device treatment** (§4.16, §9). The research note and mockups v4 are
**done**. A closing owner pass on **2026-09-02** confirmed the **56px fixed row height** and
deferred the **per-device start scan** to future work. Only one item in §9's short *still open*
list remains.
**Inputs:** [`specs/research/dmi-131-audit.md`](../../specs/research/dmi-131-audit.md) (what exists) ·
[`specs/research/dmi-131-references.md`](../../specs/research/dmi-131-references.md) (sourced references).
**Next:** DMI-132 plans and implements from this note. No code is written here.

---

## 1. Decision context

| Item | Statement |
| --- | --- |
| Audience | A **non-technical business owner**. Confirmed by the owner on 2026-09-02. Not an analyst, not an operator. |
| Scope | A **complete revamp**, not a tune. The paper/serif/mono direction is retired as a whole; values and faces change together. |
| Not in scope | Screen features. Those stay on **DMI-110 / DMI-117 / DMI-123 / DMI-127**. This note changes how screens look, not what they do. |
| Folded in | **DMI-124 (icons)**. Icons are a foundation, not a feature; the icon rules live in §4 of this system. |
| Stack | Unchanged. ADR-008 keeps React 19 / Vite 8 / Tailwind v4 / shadcn / Lucide. |

**Why the comparables are friendly SaaS, not security consoles.** Security consoles (SIEM,
vulnerability managers) are designed for an operator who lives in the tool all day: dense grids,
jargon, colour-coded severity as a working language. Our reader opens Dmitri occasionally and
wants to know if anything is wrong. So the references are Linear, Stripe, Notion, Basecamp,
Vercel/Geist and T3 Code — products whose job is to make a first-time reader confident. The one
console habit worth keeping is Stripe's: **zone the density** — tight tables inside a generous
shell, not a uniformly dense app.

---

## 2. Keep — rules that survive the revamp

One line each, from the audit §2.

- **The type scale is closed.** Eight named tokens; raw `text-sm`/`text-base` stay banned.
- **Nine spacing steps on a 4px base** (`0 1 2 3 4 6 8 12 16 24`), no `--space-*` layer.
- **Named containers only** — `max-w-frame`, `max-w-form`. Nothing else is a layout width.
- **Five interaction states declared per control** — rest, hover, focus-visible, active, disabled.
- **No outer margin** — the parent owns the gap between children.
- **Absent, not disabled** for permissions, with the input-not-yet-supplied carve-out.
- **Lint enforces the mechanical rules.** Without the gate the new tokens rot in a sprint.
- **Light only.** No `dark:` classes, no toggle; the neutralised dark variant stays neutralised.
- **Desktop-only, fluid within** — 1440 target, 1280 minimum.
- **Top bar, no sidebar**, nav centred on the `1fr auto 1fr` grid. Re-litigated twice already.
- **Cross-screen rules:** whole rows are links, severity reads down the right edge, IDs truncate,
  one `Timestamp` component.
- **Three states per screen** (regular / blank / error), and an error always offers a next step.

---

## 3. Throw out

| Current value | Replacement direction | Source |
| --- | --- | --- |
| `IM Fell English` for all titles | One friendly sans, headings differentiated by **weight and size**, not by a second family. Linear uses one family in two optical cuts. | <https://linear.app/blog/how-we-redesigned-the-linear-ui> |
| `IBM Plex Mono` as body copy (`html { font-mono }`) | Sans for all prose and UI; **mono quarantined to inline technical data** (IP, MAC, port, CVE, UUID). Mono + square corners is the shadcn `lyra` dev-tool look we are leaving. | <https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira> |
| `--radius: 0` | A positive base radius; the derived `sm…4xl` ladder is kept. T3 Code ships 10px; `maia` wants more. | <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css> |
| Warm paper palette (`--paper #FAF8F4` / `--card #FFFFFF`, 1.06 apart) | **Near-white canvas, pure-white cards**, separation carried by a hairline border, not by warmth. | <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css> |
| Beige `--rule` / `--edge` lines as the main structure | Fewer lines. Group by surface and spacing; keep the decoration-vs-control-boundary *distinction*, restate the values on white. | <https://www.beautifului.dev/> |
| `Ornament` (hairline–lozenge–hairline) | Nothing, or an icon/illustration in an empty state that shows the destination. | <https://memorable.design/empty-state-design-examples/> |
| Dashed rules | Solid hairline, or no line where spacing already separates. | <https://primer.style/product/primitives/color/> |
| `text-nav` at 11px | Nav at body size; the active item marked by weight and colour. Linear's move was to raise contrast, not shrink type. | <https://linear.app/blog/how-we-redesigned-the-linear-ui> |
| `▲▼` glyph sort markers | Lucide chevron/arrow icons sized off the type scale. | <https://github.com/pingdotgg/t3code/blob/main/apps/web/components.json> |
| `h-8` as the universal control height | Generous default controls; dense rows only inside tables. Stripe zones density instead of applying one. | <https://www.925studios.co/blog/stripe-dashboard-design-breakdown> |
| `bg-*/10` hard-bordered badges | No per-row status chip at all. Severity reads as a plain word — see §4.8. | <https://primer.style/product/primitives/color/> |
| Deep purple `#7C3AED` as the sole accent | Keep the *rule* (one accent, never severity); re-pick the value on true white and add hover/active steps. | contrast table §8 of the references file |
| shadcn style `radix-nova` | `radix-maia` — `nova` is "tighter padding and reduced margins" for dense dashboards. | <https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira> |
| Prose blocks that explain the product mid-screen | Labels and affordance instead of paragraphs; one vocabulary word per concept. | <https://basecamp.com/guides/how-we-communicate> |

---

## 4. Proposed Foundations v2

Everything below lands in `frontend/src/index.css` (~105 lines today). Tailwind v4 has no JS
config; there is nowhere else for it to go.

### 4.1 shadcn preset — **`radix-maia`** (decided 2026-09-02)

`nova` is defined as *"tighter padding and reduced margins"* for information-dense dashboards.
`maia` is *"larger border radii — often fully rounded — with generous spacing"* for *"consumer
products and softer aesthetics."* The brief is the second sentence. Migration is one field in
`components.json` plus a re-add and hand-trim of the four vendored primitives (`select.tsx` was
already trimmed once, so this is a known cost). Stay on **Radix**, not Base UI — the primitives
in `ui/` are Radix today and the library switch buys nothing here.

### 4.2 Type face — **Inter Variable** (decided 2026-09-02)

| Option | License / availability | Verdict |
| --- | --- | --- |
| **Inter Variable** | OFL-1.1, `@fontsource-variable/inter@5.3.0` | **Chosen.** Ships with Linear, tall x-height text cut built for UI, one variable file covers every weight. Safest legible choice. |
| Figtree Variable | OFL-1.1, `@fontsource-variable/figtree@5.3.0` | Alternative if "round and friendly" outranks "safe". Geometric-humanist, closest legal stand-in for OpenAI Sans. |
| Nunito Variable | OFL-1.1, `@fontsource-variable/nunito@5.3.0` | Alternative, the roundest of the three. Risk: reads playful, and the product reports security problems. |
| OpenAI Sans | Proprietary, unlicensable | **Cannot ship.** It is the actual Codex face; the two above approximate it. |

**Mono, data face only:** `@fontsource-variable/geist-mono@5.3.0` (OFL-1.1). It replaces IBM Plex
Mono, which has no variable build. Mono never sets prose, labels, buttons or headings.

Tokens: `--font-sans` (default, `html { @apply font-sans }`), `--font-mono` (data only).
`--font-title` is deleted. **One family, two cuts, never two families.**

### 4.3 Type scale — same token names, new values

| Token | Now | Proposed | Line height | Weight | Used for |
| --- | --- | --- | --- | --- | --- |
| `--text-title-lg` | 2rem | **2rem** (32px) | 1.2 | 600 | page titles |
| `--text-title-md` | 1.5rem | **1.5rem** (24px) | 1.25 | 600 | prominent titles, auth wordmark |
| `--text-title-sm` | 1.25rem | **1.375rem** (22px) | 1.3 | 600 | section and card titles |
| `--text-title-xs` | 1rem | **1rem** (16px) | 1.4 | 600 | smallest title, inside-shell wordmark |
| `--text-body-md` | 0.875rem | **0.9375rem** (15px) | 1.5 | 400 | default body, labels, values, controls, **nav** |
| `--text-body-sm` | 0.8125rem | **0.875rem** (14px) | 1.5 | 400 | helper and error copy, dense table cells |
| `--text-caption-md` | 0.75rem | **0.8125rem** (13px) | 1.45 | 400 | captions, dense metadata |
| `--text-nav` | 0.6875rem | **dropped** | — | — | nav moves to `text-body-md` |

The serif's 16px floor is gone, so headings differentiate by weight. Everything moves up one
notch: 11px and 12px text is the wrong floor for this reader.

**`text-title-sm` grew by ~10% on the mockup review (2026-09-02).** The owner read the section
titles on the detail screens as too close to body copy, so the step moves **20px → 22px**. The
token name does not change; only its value does, and every section title on a detail screen picks
it up.

**Dropping `text-nav` is a lint-and-test change, not just a token change** — see §5.

### 4.4 Spacing — unchanged

Nine steps on Tailwind's 4px base: `0 1 2 3 4 6 8 12 16 24` (plus `px`, `auto`). No `--space-*`
layer. The inter-section step stays a per-screen choice from `6 | 8 | 12`. `maia` buys generosity
by *choosing larger steps*, not by adding new ones.

### 4.5 Radius

```
--radius: 0.75rem;            /* 12px — one notch above T3 Code's 10px, because maia */
--control-radius: 0.5rem;     /* 8px — buttons, inputs, select triggers, tooltips, pills */
```

Derive the ladder with **shadcn's multiplicative form only** (`sm` 0.6× · `md` 0.8× · `lg` 1× ·
`xl` 1.4× · `2xl` 1.8× · `3xl` 2.2× · `4xl` 2.6×) — never T3 Code's additive `calc(± Npx)`. Two
derivation forms in one file is how an agent mixes them. `--control-radius` exists so small
controls do not inherit the card radius and look bloated.

### 4.6 Neutrals

| Token | Hex | Role | Contrast |
| --- | --- | --- | --- |
| `--canvas` (was `--paper`) | `#FCFCFC` | page surface, near-white | — |
| `--card` | `#FFFFFF` | cards, dialogs, table headers, popovers | 1.01 vs canvas — the border separates, not the tint |
| `--ink` | `#0F172A` | primary text | **17.85** on white |
| `--ink-muted` | `#475569` | secondary text, timestamps, helper copy | **7.58** on white |
| `--rule` | `#E2E8F0` | decorative separators, table row lines | non-text |
| `--edge` | `#64748B` | control boundaries: input, select, button outlines | **4.76** on white (floor is 3:1) |

`#64748B` is the hard floor for any text; do not go lighter. Linear's redesign made text and
icons **darker**, not lighter — pale grey is the standard way a friendly-minimal UI becomes
unusable. Keep the `--rule` / `--edge` split: an input outline owes 3:1 (WCAG 1.4.11), a row line
owes nothing.

### 4.7 Accent — **`#4F46E5` indigo-600** (decided 2026-09-02)

Contrast as text/icons on `#FFFFFF`, computed 2026-09-02:

| Candidate | Ratio | AA normal | Note |
| --- | --- | --- | --- |
| `#1D4ED8` blue-700 | 6.70 | PASS | **Collides with severity `low`, which is this exact hex today.** |
| **`#4F46E5` indigo-600** | **6.29** | **PASS** | **Chosen.** Friendly, clearly not the severity blue, adjacent to today's purple so "purple never carries severity" survives as "indigo never carries severity". |
| `#533AFD` Stripe indigo | 6.19 | PASS | Louder, more branded. Fine alternative. |
| `#2563EB` blue-600 | 5.17 | PASS | Friendliest, lightest — but same blue-vs-`low` confusion. |
| `#7C3AED` violet-600 (today) | 5.70 | PASS | **Retired.** Passes on white, but the owner picked indigo. |
| `#0284C7` · `#059669` · `#0D9488` | 4.10 / 3.77 / 3.74 | **fail** | Large text only. Reject. |

Rules that come with it: **one accent, used sparingly** — primary button, active nav item, focus
ring. Never in the greys, never carrying severity. Ship `--accent`, `--accent-hover`,
`--accent-active` (one step darker each) and `--accent-foreground: #FFFFFF`.

### 4.8 Severity presentation

**The severity words stay; only their presentation changed.** The owner rejected the urgency-group
wording (*Fix now / Fix soon / Good to know / All clear*) on 2026-09-02 and kept **Critical, High,
Medium, Low** as the user-facing vocabulary — "more impactful". These are the same words the API
uses, so the reader and the backend share one taxonomy.

**What is rejected is the decoration**, in both earlier forms:

- **No chip, pill, tag, dot or badge** on a finding row.
- **No coloured side bar and no coloured card edge** — not per row, not per group.
- No grouping cards headed *Fix now* / *Fix soon* / *Good to know* / *All clear*.

**What severity looks like instead:** plain text. Either

- a **bold word in a table column** (`Critical`, `High`, `Medium`, `Low`), or
- a **section heading** when a screen groups findings by severity.

Nothing else marks it. The word carries the meaning.

**Decided on the full-screen mockups (2026-09-02): no coloured text in tables.** The owner:
*"I don't like colored text on the table, bold is fine."* So a severity word is set in **`--ink`,
bold** — in a table cell and as a section heading alike. There is no severity hue anywhere in the
system today: not as text, not as a bar, edge, chip or fill. This is **not 100% final** — the owner
may revisit it on a later pass — but it is **binding for now**, and nothing should ship a coloured
severity word before that revisit.

**Cards do not vary with severity either (mockups v2, 2026-09-02).** All four compared patterns —
full coloured outline, ink eyebrow, tinted header band, coloured icon — and the colour ramp behind
them were rejected. **A vulnerability card is a plain white card**; severity appears only as the
bold ink word. There is now **no severity hue anywhere in the system**, on text or on a surface.

**Kept:** the **highest-severity column** on list tables. The owner explicitly kept it, so a row
that summarises several findings still shows its worst one as a word.

**The API severity taxonomy is unchanged.** Critical / high / medium / low / informational stay
exactly as the backend defines them. The previously proposed pill hexes (tint, border,
per-severity text) and the retired group-edge hexes remain in
[`specs/research/dmi-131-references.md`](../../specs/research/dmi-131-references.md) for history.

**Scope.** The design system owns *how a severity word is set*. **Which findings a screen shows and
how it orders them is a screen decision**, owned by the Home issues (**DMI-117 / DMI-123**).

### 4.9 Icons — Lucide (DMI-124)

| Rule | Value |
| --- | --- |
| Set | **Lucide**, already installed and already the `iconLibrary` in `components.json`. No migration. |
| Size | `size-4` (16px) beside body text and in table cells · `size-5` (20px) in headings, primary buttons and empty states. Two sizes only. |
| Stroke | `stroke-width: 1.75` as the app default (Lucide ships 2). Softer, matches a rounded sans. Set once, not per call site. |
| Colour | Inherits `currentColor`. An icon never has its own hex. |
| Accessible name | Decorative icon → `aria-hidden="true"`. Icon-only control → `aria-label` with the action in words. An icon beside a label needs neither. |
| Where they go | Section headings, empty states, table sort markers, nav-free buttons, status rows. Not decoration for its own sake. |

### 4.10 Motion

```
--duration-fast: 125ms;   /* tooltips */
--duration-base: 180ms;   /* the default: hover, open, expand */
--duration-slow: 300ms;   /* the ceiling — nothing is slower */
--ease-out:  cubic-bezier(0, 0, 0.2, 1);      /* entrances */
--ease-in:   cubic-bezier(0.4, 0, 1, 1);      /* exits, and shorter than the entrance */
--ease-standard: cubic-bezier(0.4, 0, 0.2, 1); /* moves and resizes */
```

- `ease-out` for anything entering. **Never `ease-in` for an entrance.**
- Never animate from `scale(0)` — start at 0.95+. Buttons press to `0.97`.
- **Animate the rare, not the constant.** A live scan list must not animate every row; reserve
  motion for scan start/finish and for state changes the owner should notice.
- `prefers-reduced-motion: reduce` is **mandatory**: a global block that drops non-essential
  animation to `0.01ms`. WCAG 2.3.3; unnecessary motion causes real harm to people with
  vestibular disorders.
- Motion lives in tokens. A duration written inline in a component is a bug, like a raw hex.

### 4.11 Copy rules

| Rule | Shape |
| --- | --- |
| Empty state | **One sentence + one button.** Nothing else. The sentence says what will be here; the button puts it there. |
| Helper text | On demand, not by default. If a field needs a paragraph, the label is wrong. |
| No product restatement | "Dmitri scans your network…" appears on `Scans`, `Hosts` and `HomeBlank` today. Delete all three. The reader is already inside the product. |
| Labels over paragraphs | Say the thing in a label, a group heading or an icon before saying it in prose. |
| One word per concept | Fix the owner-facing word for *device*, *finding*, *scan*, *risk* — one each, used everywhere. Basecamp's largest simplification was shrinking its vocabulary. |
| Buttons | Verb + noun (`Start scan`, `Remove device`). Never `Confirm`, `OK`, or a bare verb. |
| Good news reads as good news | Zero findings is a reassuring sentence, not a blank panel. |
| **Never certify safety** | Describe what needs attention; never claim the network is safe. **"Nothing needs your attention"**, not **"Your network is safe"**. The demo line *"Your network is safe today"* was mock copy and is rejected. |

**Vocabulary, decided on the mockups (2026-09-02).**

| Was | Is | Note |
| --- | --- | --- |
| *Finding* | **Vulnerability** | Both the table column and the general word. `Finding` leaves the owner-facing vocabulary; the API taxonomy is untouched. |
| *Open ports* | **A plain phrase — "Services running on this device"** | The heading says what the reader gains, not what the scanner found. **Exact wording open**; the shape is a plain sentence-case phrase, not the term *ports*. |
| *Seen in these scans* | **Rejected** | The owner rejected the heading. A replacement is needed for the scan-history block on the detail screens; **wording open**. |
| *"Who can open this account."* and its kind | **Deleted** | Explanatory copy under a control is removed outright, not reworded. It is the §4.11 *no product restatement* and *labels over paragraphs* rules applied to Users and Settings. |

### 4.12 Action placement

**The earlier rule — one primary action per screen, always in the page header — is rejected**
(owner, 2026-09-02: "this is bad").

- **Placement is decided per screen, on mockups.** There is no system-wide slot.
- On **list screens the table is the epicenter**. Actions like `Invite` are *functions of* the
  screen, not its focus, and must not be staged as if they were.
- Still true: secondary actions are row-level or menu-level, and are not styled as the primary.

**Decided on the full-screen mockups (2026-09-02):**

| Question | Answer |
| --- | --- |
| May a button live inside a content card? | **Yes.** The chosen pattern is a **small outlined button in the card footer** — not a filled primary, not a button floating in the card body. |
| Where does a list screen's own action go? | **Below the table, bottom-right.** On **Users** the `Invite a user` button sits under the table at the right edge, and is **~5% taller than the default control** so it reads as the screen's action without being staged above the table. |
| Do cards react to severity? | **No — closed on mockups v2 (2026-09-02).** All four patterns (full coloured outline, ink eyebrow, tinted header band, coloured icon) and the colour ramp were **rejected**. A vulnerability card is a **plain white card**; severity is only the bold ink word (§4.8). |

### 4.13 Chrome and navigation (decided 2026-09-02)

From the full-screen mockup review. These are system-wide, not per screen.

| Element | Rule |
| --- | --- |
| Nav active item | **Bold, no underline.** Hover is **also bold** — the weight change is the whole affordance. No rule, no pill, no bottom border. |
| Wordmark | The word **"Dmitri"** only. **No icon, no mark, no lockup.** |
| User identity | **The user's name.** **No avatar** — the product has no profile pictures, so a letter-circle stand-in is inventing a feature that does not exist. |
| Back link | **A Lucide `arrow-left` icon + the word "Back"**, as one text link **above the page title** (decided on mockups v3, 2026-09-02). This replaces the earlier *no arrow* rule — the owner disliked the previous rendering, not arrows. The gap between the back link and the page title is a **step from the spacing scale** (§4.4), never an ad-hoc value. |
| Table row height | **All rows the same fixed height — 56px**, as shown on mockups v4. Owner, verbatim: **"set default to 2"**, which meant only that every row has the same fixed height. Confirmed 2026-09-02; write 56px into `DataTable`. |
| Summary strip | The key/value rows above a table **align to the table's width** — same left and right edges, so the strip and the table read as one block. |

Section titles on detail screens grew with `text-title-sm` (§4.3) as part of the same review.

### 4.14 Grouping, controls and panels (decided 2026-09-02, mockups v2)

| Element | Rule |
| --- | --- |
| Grouped sections on detail screens | **White cards on the `#FCFCFC` canvas, heading inside the card.** On **Scan detail** each severity group (`Critical` / `High` / `Medium` / `Low`) is one such card. The card is plain white — it never varies with severity (§4.8). |
| Pagination | **The shadcn `Pagination` component** in shape — ghost buttons, page numbers, an ellipsis — but **icon-only previous/next** (mockups v3, 2026-09-02): a Lucide `chevron-left` / `chevron-right` button with the accessible name **"Previous page"** / **"Next page"** and **no "Previous" / "Next" words**. Owner: use shadcn primitives and their best practice for such controls, **never a hand-rolled one**. |
| Inline select in a table cell | **Borderless trigger**: the text plus a **small chevron close to the text**, and the text **aligned with the column header**. Built on shadcn `Select` with a **ghost trigger**. This is the Users role cell. |
| Panels (Events / Activity) | **No trailing empty row after the last item.** A list carries **no bottom padding beyond its last row** — the rule exists to prevent the rendering defect seen on v2. |
| Empty state inside the attention board | **Nothing is rendered at all** (mockups v3, 2026-09-02) — no text, and **no empty card**: the canvas shows through, and the **page title carries the message**. This overrides the §4.11 *one sentence + one button* shape for this one surface. |
| Home rhythm | The gap between the attention board and the Events/Activity row is **step 12 (48px)** — larger than the default inter-section step. |
| `DataTable` column gaps | Gaps come from the **spacing scale (§4.4) and fixed column widths**, never from content or ad-hoc padding. A **numeric column followed by a code column — `Port` then `CVE` — sits no closer than step 6 (24px)**. Owner flagged the Port/CVE gap on two screens (mockups v3, 2026-09-02). |

### 4.15 Scan settings (decided 2026-09-02, mockups v4)

**Presentation: tabs + description.** The three compared patterns are closed — the owner picked the
**shadcn `Tabs` segmented control**, one tab per scan type, with a **one-line plain description
beneath the tab strip** and a **secondary "Use this scan type" button**. Radio cards and the
selectable list with a description column are rejected. The section sits below the scans table on
the **Scans** page.

**The five scan types** (`SCAN_MODES` in `hardware-agent/src/agent/config.py`), each with the
owner-facing line:

| Tab | Plain description |
| --- | --- |
| **Quick** | Checks the 1000 most-used connection points on each device for known vulnerabilities. About 2–5 minutes. |
| **Standard** | Same 1000 connection points, and also inspects the common services — file sharing, remote login, web — for weak settings. About 5–10 minutes. |
| **Extensive** | Checks the 10,000 most-used connection points, adds certificate and encryption checks, and reports lower-severity problems as well. About 20–35 minutes. |
| **Max** | Checks every connection point on every device and reports everything it finds, however small. 45 minutes or more. |
| **NSPi** | For networks with industrial equipment: checks the control-system connection points (Modbus, OPC UA, EtherNet/IP) plus Windows remote-access ones. About 20–30 minutes. |

Durations come from the TUI mode picker (`tui/screens/scan_mode.py`); the "lower-severity" and
"reports everything" lines come from `min_cvss_for_mode` (5.0 → 3.0 → 1.0). The exact owner-facing
wording is drafted here and shown on mockups — **the words are open, the shape is not**.

**Behaviour (feeds DMI-127 and a Scans issue).**

| Action | Result |
| --- | --- |
| Selecting a tab | **Preview only.** Nothing is saved; the description below changes. |
| **"Use this scan type"** | Confirms the selected type as the **default for the daily scan**. **Confirmation required** — this changes what runs unattended. |
| **"Scan now"** (a button on the Scans page) | Runs a scan **immediately** with the **currently selected** type, and **does not change the default**. |
| Leaving the page | The selection **reverts to the default**. A preview never survives navigation. |

### 4.16 Silent devices (approved 2026-09-02, mockups v4)

A device the scanner has not seen for weeks is **not removed and not flagged as an error**. Two
treatments apply together:

- **Muted row.** The row is set in `--ink-muted`, with a second line reading **"Not seen for N
  weeks"** under the device name. No chip, no icon, no colour.
- **Collapsed group.** Every device in that state also collapses into a single group row at the
  **bottom of the table**, labelled **"Not seen recently (N)"**, which expands to show the muted
  rows.

The group row is always last, after the severity/name sort. This is a `DataTable` pattern, not a
Network-list one-off.

---

## 5. Constraints and risks

| Constraint | What it means for DMI-132 |
| --- | --- |
| **Lint rules hard-code token names.** `no-raw-type-size.js` maps `text-sm → text-body-md` etc.; `no-arbitrary-utility.js` names `max-w-frame`/`max-w-form` in its error text. | **Ship tokens and lint in the same commit.** Dropping `text-nav` without editing the rule leaves the gate suggesting a token that no longer exists — and it fails silently. Re-run `node --test frontend/eslint-rules/*.test.js`. |
| **41 `toHaveClass` assertions** test styling, not behaviour. `TopBar.test.tsx` asserts `text-nav` and `border-accent`; `Disclosure.test.tsx` asserts `text-body-md`; `Ornament.test.tsx` (68 lines) asserts `h-px`/`size-3`. | Budget test edits into the same commits. `Ornament.test.tsx` is deleted outright with the component. |
| **`src/components/ui/**` is lint-exempt.** | Vendored primitives carry raw sizes (`text-base`, `text-xs`, `text-[0.8rem]`, `h-8`, `rounded-[min(...)]`) that the gate cannot see. **Audit them by hand** during the restyle, and again after any `npx shadcn add`. |
| **`dark:` is neutralised, not removed** (`@custom-variant dark (&:is(.dmitri-dark-unused *))`). | Leave the neutraliser alone. Strip the dead `dark:` classes in `button.tsx` / `input.tsx`; never add new ones. "Fixing" that selector switches on a half-built dark mode. |
| **Tests key off `data-testid` and exact copy** — 494 `getByTestId`, 42 `getByText` across 37 files. | A restyle is safe while testids and copy are untouched. **Any copy trim is a separate commit** from the restyle. |
| **`shadcn/tailwind.css` is imported.** | A renamed token silently falls through to its defaults instead of erroring. Rename deliberately, and check the rendered result. |
| **Spacing allowlist lives in three places** — `spacing-scale.js`, SCREENS.md, the conventions skill. | We are not changing the steps, so this stays untouched. If that changes, all three move together. |
| **`no-bare-interactive`** | New primitives must land in `src/components/ui/` or `src/components/`. A restyle may not inline a `<button>` in a screen. |
| **`max-w-sm` / `max-w-md` used as dialog widths** (`DialogShell.tsx`, `Toast.tsx`). | If dialogs are re-proportioned, add a named container token. Do not swap in another framework size. |
| **Full gate** | `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`. Long cva strings reflow — run prettier on touched files only. |

---

## 6. Migration order

**Values before components, components before screens.** The alias layer in `index.css` means
most of the visible change lands in step 1.

1. **Tokens** — `index.css`: `--font-sans`, mono demoted, new neutrals, new accent, `--radius`
   + `--control-radius`, motion tokens, `html { font-sans }`.
   *Verify:* build + visual pass.
2. **Lint and docs, same PR as step 1** — `no-raw-type-size.js` map, both error messages,
   SCREENS.md token tables, `frontend-conventions` §Styling.
   *Verify:* `node --test frontend/eslint-rules/*.test.js`, `npm run lint`.
3. **Vendored primitives** — switch `components.json` to `radix-maia`; hand-audit
   `button|input|label|select` for raw sizes; strip dead `dark:`; add `card`, `separator`,
   `badge`, `tooltip`, hand-trimmed.
4. **Shared components** — delete `Ornament` (5 call sites + its test); restyle `DataTable`,
   `EmptyState`, `ErrorRetry`, `NotFoundNotice`, `PageHeader`, `TopBar`, `Pagination`, `Toast`,
   `SeverityBadge`, `StatusPill`, `LoadingSkeleton`, `DialogShell`, `AuthShell`, `FirstScanCta`.
   `ListSurface`, `ReadDetailGate`, `Timestamp`, `AdminOnly`, `EmptyMark`, `ConfirmByTyping`
   need **no change**.
5. **Screens, cheapest first:**
   1. **Scans, Hosts** — *cheapest*, near-pure `ListSurface` composition. Do these first as the
      proof that steps 1–4 landed: anything wrong here is a token or component bug.
   2. Host detail, Scan detail — cheap.
   3. NotFound, Login, Forgot, Reset — cheap once `AuthShell` is done.
   4. **Home** — medium code, **highest design stakes**. Do it after the proof, before the dear ones.
   5. Settings — medium.
   6. Accept invite — dear (299 lines, own form and branches).
   7. **Agents** — *dearest* (7 files, ~400 lines: subnet chooser, scan control, command status).
   8. **Users & invites** — *dearest* (~680 lines + ~1100 lines of tests, heaviest copy, and the
      one outstanding `DataTable` retrofit).

---

## 7. Docs restructure

`SCREENS.md` is 1893 lines; §Foundations is lines 14–421 and is roughly **60% binding rule / 40%
history** — and most of that history argues for values this revamp discards, so it becomes
actively misleading rather than merely long.

| New home | Contents | Length |
| --- | --- | --- |
| **`docs/ui/FOUNDATIONS.md`** (new) | The binding one-pager: token tables (type, spacing, radius, neutrals, accent, severity, motion), the icon rules, the copy rules, the interaction-state table, the container table. Values only, no argument. This is what an agent loads. | ~1 page |
| **`docs/ui/FOUNDATIONS-DECISIONS.md`** (new, appendix) | The history: the centred-nav story, the `--rule`-vs-whitespace argument, the inter-section-step trade, the paper-direction rationale, the reversals. Marked as **history — superseded values may appear here**. | the ~160 history lines |
| **`docs/ui/SCREENS.md`** | Keeps §App shell and every per-screen section. §Foundations becomes a short pointer to the two files above. Still the source of truth for *screens*. | −408 lines |
| `docs/ui/REFERENCE.md`, `FLOWS.md` | Unchanged. | — |
| `docs/adr/ADR-008` | Unchanged — it owns the stack, not the look. | — |

---

## 8. Skill outline — `frontend-design-system`

A new Claude Code skill at `.claude/skills/frontend-design-system/SKILL.md`, ~1 page, loaded
before any work under `frontend/`.

| Section | Contents |
| --- | --- |
| **Token sheet** | The whole of `FOUNDATIONS.md` §tokens, inline. Names and values, no prose. The agent must never invent a value. |
| **Component inventory** | A "need X → use Y" table: *a container* → `Card` · *a severity word* → a **bold `--ink`** cell or heading, no colour (§4.8) · *a list* → `DataTable` via `ListSurface`, **fixed row height for every row** · *a key/value strip above a table* → `SummaryStrip`, aligned to the table's width · *a way back* → `BackLink`, a Lucide **`arrow-left` + "Back"** above the page title, spaced by a scale step · *an action inside a card* → a **small outlined `Button` in the card footer** · *a confirm* → `DialogShell` (+ `ConfirmByTyping` if destructive) · *a destructive row action* → a **text link in the row plus a confirm dialog** (`ConfirmByTyping`), never a bare icon button · *a divider* → `Separator` · *a hint* → `Tooltip` · *a grouped section on a detail screen* → a **white `Card` with the heading inside**, on the canvas (§4.14) · *paging through a list* → the shadcn **`Pagination`** component with **icon-only** previous/next (accessible names "Previous page" / "Next page"), never hand-rolled · *a select inside a table cell* → shadcn **`Select` with a ghost, borderless trigger**, text aligned to the column header · *nothing here yet* → `EmptyState` · *a load* → `LoadingSkeleton`. Plus: **if it is not in this table, ask — do not hand-roll.** |
| **Copy rules** | §4.11 verbatim, including the vocabulary table. The glossary is **device / vulnerability / scan / risk** — *finding* is retired. |
| **Do / don't gallery** | One-line testable pairs: raw hex vs token · `text-sm` vs `text-body-md` · inlined `<button>` vs `Button` · `p-[13px]` vs step `3` · a disabled control the user has no permission for vs absent · placeholder-as-label vs `<label htmlFor>` · a paragraph of helper text vs a label · an animated list row vs animation reserved for state changes · a per-row severity chip, coloured edge **or coloured severity text** vs a plain **bold `--ink`** severity word · an underlined or pill active nav item vs **bold** · a wordmark with an icon vs the word **"Dmitri"** · an avatar circle vs the **user's name** · a bare-text back link, or a `←` glyph, vs a Lucide **`arrow-left` + "Back"** above the title, spaced by a scale step · rows that grow with their content vs **one fixed row height** · a summary strip wider or narrower than its table vs **aligned to the table** · the word *Finding* vs **Vulnerability** · *Open ports* vs a plain phrase about the **services running on this device** · explanatory copy under a control (*"Who can open this account."*) vs **nothing** · a hand-rolled pager (bare arrows, custom buttons) vs the shadcn **`Pagination`** primitive · the words *Previous* / *Next* on a pager vs **icon-only chevrons** named "Previous page" / "Next page" · a numeric column touching a code column (`Port` next to `CVE`) vs **step 6 (24px) minimum**, from fixed column widths · a bordered select trigger in a table cell vs a **borderless ghost trigger** aligned to the column header · a card outlined, tinted or iconed by severity vs a **plain white card** · a list with a trailing empty row vs **no bottom padding past the last row** · a sentence, or an empty card, in the attention board's empty state vs **nothing rendered at all — the canvas shows through and the page title carries it**. |
| **Exemplar screens** | `Scans.tsx` + `Hosts.tsx` (pure composition — copy this shape), `Home.tsx` (the epicenter treatment), `AuthShell.tsx` (a standalone form card). Updated as DMI-132 lands them. |
| **References folder** | `references/t3code.md` — the files to read: `apps/web/src/index.css` (tokens, themes, motion), `components.json`, `src/components/ui/`, `appearanceContrast.ts`. `references/beautifului.md` — the four transferable shapes (records tables, filter tables, task rows, insight cards) and the registry URL. `references/shadcn.md` — MCP usage and the `radix-maia` note. |
| **Verification** | 1. `npm run lint` (catches raw sizes, arbitrary values, off-scale spacing, bare interactives). 2. `npm run typecheck && npm run test`. 3. **Visual check** at 1440 and 1280: every control shows hover *and* focus-visible; every icon-only control has an accessible name; no pill without its border; no text lighter than `#64748B`. |

**Changes to the existing agents and skills:**

- **`frontend-conventions`** — keeps the code rules (version traps, API types, TanStack Query,
  absent-not-disabled). Its §Styling shrinks to one line: *"Styling is owned by
  `frontend-design-system`; load it too."* No duplicated token list — a token duplicated in two
  skills is a token that will disagree with itself.
- **`frontend-design-agent`** — its "inherits `SCREENS.md` §Foundations" line becomes "inherits
  `docs/ui/FOUNDATIONS.md`, and loads the `frontend-design-system` skill". It still never
  re-decides foundations.

**Agent tooling — recommendation.**

| Option | What it gives | Verdict |
| --- | --- | --- |
| **shadcn MCP server** (`npx shadcn@latest mcp` in `.mcp.json`) | Agents browse, search and install from any shadcn registry — including Beautiful UI's MIT registry — conversationally, against live docs. | **Adopt.** Low cost, and it is what makes the component inventory reachable rather than merely written down. |
| **`google-labs-code/design.md`** + `npx @google/design.md lint` | A YAML-front-matter token format for agents, with a linter that checks WCAG contrast and token references. | **Borrow the idea, not the tool.** Our tokens already live in one 105-line CSS file with an ESLint gate that knows our token names; a second token format is a second source of truth. Steal the split — *tokens give exact values, prose says why* — as the shape of `FOUNDATIONS.md` vs its decisions appendix. Revisit if the palette starts drifting. |

---

## 9. Decisions (2026-09-02)

Made by the owner across six reviews on 2026-09-02: a rendered comparison page, the screen map,
the **full-screen mockups**, **mockups v2**, **mockups v3** and **mockups v4**. All rows below are
closed; the short list after them is not.

| Decision | Made | Note |
| --- | --- | --- |
| shadcn preset | **`radix-maia`** | `nova` is built for dense dashboards and fights the brief. |
| Type face | **Inter Variable** | Safest and most legible; Figtree and Nunito are not pursued. |
| Accent hex | **`#4F46E5` indigo-600** | 6.29:1 on white; does not collide with the blue that means severity `low`. `#7C3AED` purple is retired. |
| `design.md` tooling | **Borrow the idea only** | Adopt the **shadcn MCP server** instead of a second token format. |
| Foundations one-pager | **`docs/ui/FOUNDATIONS.md`** | History in `FOUNDATIONS-DECISIONS.md`; the skill quotes the token sheet. **Foundations is tokens only.** |
| Severity presentation | **Plain words: Critical / High / Medium / Low** | §4.8. Overturned the urgency groups. No chip, no coloured bar or edge. Highest-severity column kept. API taxonomy unchanged. |
| Severity **colour** | **None — bold `--ink` only** | §4.8. Mockup review: *"I don't like colored text on the table, bold is fine."* Bold word in a table cell, and the same word as a section heading. Not 100% final, **binding for now**. |
| Safety copy | **Never certify safety** | §4.11. "Nothing needs your attention", not "Your network is safe". Stands. |
| Action placement | **Per screen, on mockups** | §4.12. Overturned "one primary action in the page header". On list screens the table is the epicenter. |
| Buttons inside cards | **Allowed — small outlined button in the card footer** | §4.12. Closed the earlier open item. |
| Severity-varying cards | **Rejected — cards do not vary with severity** | §4.12 · mockups v2. All four patterns (full coloured outline, ink eyebrow, tinted header band, coloured icon) and the colour ramp rejected. A vulnerability card is a **plain white card**; severity is only the bold ink word. |
| Grouped sections on detail screens | **White cards on the canvas, heading inside** | §4.14 · mockups v2. A DS pattern, not a Scan-detail one-off. |
| Pagination | **The shadcn `Pagination` shape, icon-only previous/next** | §4.14 · §8 · mockups v3. Ghost chevron buttons named "Previous page" / "Next page", page numbers, ellipsis, **no "Previous"/"Next" words**. Owner wants shadcn primitives and their best practice, not hand-rolled controls. |
| Inline select in a table cell | **shadcn `Select`, ghost borderless trigger** | §4.14 · mockups v2. Text + a small chevron close to the text, aligned with the column header. The Users role cell. |
| Home: attention-board empty state | **Nothing rendered — no text, no empty card** | §4.14 · mockups v3. The canvas shows through; the page title carries the message. |
| Home: gap to the Events/Activity row | **Step 12 (48px)** | §4.14 · mockups v2. |
| Panels (Events / Activity) | **No trailing empty row** | §4.14 · mockups v2. A list carries no bottom padding beyond its last row. |
| Nav active state | **Bold, no underline; hover also bold** | §4.13. |
| Wordmark | **The word "Dmitri", no icon** | §4.13. |
| User identity in the chrome | **The user's name, no avatar** | §4.13. Profile pictures are not a product feature. |
| Back links | **Lucide `arrow-left` + "Back", above the page title; scale-step gap to the title** | §4.13 · mockups v3. Replaces the earlier *no arrow* note — the owner disliked the previous rendering, not arrows. |
| Table column gaps | **From the spacing scale and fixed column widths; `Port` → `CVE` no closer than step 6 (24px)** | §4.14 · mockups v3. A `DataTable` rule, flagged on two screens. |
| Table row height | **Fixed and equal for every row — 56px** | §4.13 · mockups v4, confirmed 2026-09-02. *"Set default to 2"* meant same fixed height for every row, nothing more. |
| Summary strips | **Align to the table's width** | §4.13. |
| Section titles on detail screens | **~10% larger — `text-title-sm` 20px → 22px** | §4.3. Token name unchanged. |
| Vocabulary: *Finding* | **→ Vulnerability** | §4.11. Column heading and the general word. |
| Vocabulary: *Open ports* | **→ a plain phrase, e.g. "Services running on this device"** | §4.11. Exact wording **open**. |
| Heading "Seen in these scans" | **Rejected** | §4.11. Replacement wording **open**. |
| Explanatory copy ("Who can open this account.") | **Deleted, not reworded** | §4.11. |
| **Users screen** | **The table is the page** | `Invite a user` sits **bottom-right under the table**, ~5% taller than the default control. The role cell is a **dropdown**. **No count line, no helper copy.** **Every row carries a `Remove` action** (mockups v3) — admins may remove viewers **and other admins**. It is destructive: a **text link plus a confirm dialog** (`ConfirmByTyping`). Who may remove whom belongs to the Users issue; the design system only fixes *destructive row action = text link + confirm dialog*. |
| **Home layout** | **Attention table + event board + logs** | A table of vulnerabilities to review, **rows clickable through to the detail page**, and **no "To review" heading**. The attention board has a **fixed height** so its empty state does not shift what is below. Under it a **half/half split**: **left** an event board (paginated; small-scoped events such as *"Pi disconnected for a long time"*, *"user idle too long"*), **right** minimal logs with a title. Feeds **DMI-117 / DMI-123**. |
| **Scans list: mode switcher** | **Cut — "serves no purpose"** | Mode is a **column** on the list, not a control. |
| Where scan modes are chosen | **The Scans page — a "Scan settings" section below the scans table** | Closed on mockups v3 (2026-09-02). The section explains **in plain language what each scan type does**. |
| **Scan settings presentation** | **Tabs + description** — a shadcn `Tabs` segmented control, a one-line plain description beneath, and a secondary **"Use this scan type"** button | §4.15 · mockups v4 (2026-09-02). Closes the open item; radio cards and the selectable list are rejected. The five types are **Quick · Standard · Extensive · Max · NSPi**. |
| **Scan settings behaviour** | **Tab = preview · "Use this scan type" = set the daily default (confirm) · "Scan now" = run once, default untouched · leaving the page reverts to the default** | §4.15 · mockups v4. Feeds **DMI-127** and a Scans issue. |
| **Scan-type descriptions** | **Approved as written** | §4.15 · mockups v4. The five owner-facing lines (Quick · Standard · Extensive · Max · NSPi) ship verbatim. Closes the "wording open" item. |
| **Confirm dialog for the daily default** | **Approved copy** | §4.15 · mockups v4. Verbatim: *"Make Max your daily scan? Every morning's scan will take 45 minutes or more instead of about 8 minutes."* The pattern is the named type plus the two durations compared. |
| **Network list page** | **Approved as drawn** | Mockups v4. A **search input**, a **ghost filter select**, and a table **sorted by severity then name**. Rows lead to the Network detail screen. |
| **Silent devices** | **Muted row + collapsed group** | §4.16 · mockups v4. A device not seen for weeks is a **muted row with a "Not seen for N weeks" line**, and those rows also collapse into a **"Not seen recently (N)" group row at the bottom of the table**. |
| Confirmed on mockups v3 | **Scan-detail severity cards · the ghost select chevron** | Both liked as drawn; no change. |
| **Scan detail layout** | **Summary strip → vulnerabilities grouped under plain `Critical` / `High` / `Medium` / `Low` headings → devices-seen table** | Closes the earlier open item. **Each severity group is a white card with its heading inside, on the `#FCFCFC` canvas** (mockups v2, §4.14). |
| **Network (host) detail layout** | **Header → vulnerabilities → services → scan history** | Header shows the name, with address + vendor secondary; when the host has no name the **address is the title**. Closes "ports before or after findings" — **vulnerabilities first**. |
| Nav: Hosts → **Network** | Renamed | The screen shows the client's network. |
| Nav: Agents → **Devices** | Renamed | A device is the Dmitri box running inside a network. |
| Nav: Users | **Open** | Not commented in the review. Keep "Users" until decided. |
| Role words | **Admin / Viewer** | Unchanged. |
| Manual scan trigger | **The Scans page — "Scan now"** | **Updated on mockups v4 (2026-09-02).** Overturns the earlier *"`Start scan` lives only on the Devices screen"* row: the manual trigger sits beside the Scan settings section, because that is where the type is chosen. It runs the **currently selected** type without changing the default (§4.15). The **Devices** screen keeps **device management only** — a per-device start-scan action is **future work, not in this revamp** (decided 2026-09-02); candidate follow-up epic **"Personalize scans"** (per-device scan, custom scan abilities), to be created in Linear later. Still true: **not on Home**. |
| Home's job | **The work board** | What needs review, new findings, events. Not a scan launcher. |
| Home **event board** | **New requirement** | Title optional. E.g. a device silent for weeks raises "likely dead, check on it". Use cases still to be collected. Owned by the Home issues (**DMI-117 / DMI-123**); noted for **DMI-127**. |
| Scans: mode switching | **New requirement** | Users switch between the product's scan modes, and possibly customise scan abilities. **DMI-127**, not a design-system matter. |
| Device naming fallback | **Open** | Need a rule when no name is found — e.g. hostname → vendor + address → address. Belongs to the **Network** screen issue. |
| Home engraving ornament | **Cut** | Confirmed. |
| "Dmitri scans your network…" ×3 | **Cut** | Confirmed; see §4.11. |
| Settings screen | **Parked** | Waits for its own revamp, **DMI-110**. |

**Still open — a short list after the mockup review:**

| Open item | Owner |
| --- | --- |
| Final wording for the services heading, and a replacement for "Seen in these scans" | §4.11 |

**Deliverables are complete.** Mockups v4 were reviewed and **approved in full** on 2026-09-02:
the Scans page with its five-tab scan settings, the confirm-dialog copy, the five scan-type
descriptions as written, the **Network list page**, and the **silent-device treatment**. This
research note is **done**. What remains is the one item on the *still open* list, which does not
block DMI-132.

| Deliverable | Contents | Feeds |
| --- | --- | --- |
| **Screen map** (done, 2026-09-02) | Every screen · its epicenter · its actions · its content | This note's §9 |
| **Mockups v1** (done, 2026-09-02) | Full screens: Home, Users, Scans, Scan detail, Network detail | §4.8 · §4.11 · §4.12 · §4.13 · §9 |
| **Mockups v2** (reviewed, 2026-09-02) | The severity-varying card, compared — **all patterns rejected**; plus pagination, the inline role select, Home empty state and panel rows | §4.8 · §4.12 · §4.14 · §9 |
| **Mockups v3** (reviewed, 2026-09-02) | The settled screens redrawn with plain white cards, shadcn `Pagination` and the ghost inline select | §4.13 · §4.14 · §8 · §9 |
| **Mockups v4** (**approved**, 2026-09-02) | The arrow back link, icon-only pagination, the empty attention board, the Users `Remove` row action, the table column gaps, the **Scan settings** tabs + descriptions and confirm copy, the **Network list page**, and the **silent-device treatment** | §4.15 · §4.16 · §9 · **DMI-127** and the per-screen issues (DMI-110 / DMI-117 / DMI-123) |
| **Research note** (done, 2026-09-02) | This document — foundations, per-screen decisions, migration order, the skill outline | **DMI-132** |

**Process — one artifact per round.** Each mockup round is published as a **new artifact page with
a fresh URL**, never a redeploy of the previous one, so comment threads do not carry over from a
round into the next.

---

## 10. Sources

- <https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira> — the five shadcn styles
- <https://ui.shadcn.com/docs/theming> — CSS-variable theming, the radius multipliers
- <https://ui.shadcn.com/docs/tailwind-v4> — Tailwind v4 setup, `tw-animate-css`
- <https://ui.shadcn.com/docs/components-json> — `style`, `iconLibrary`, registries
- <https://ui.shadcn.com/docs/mcp> — the shadcn MCP server
- <https://ui.shadcn.com/docs/components/badge> — the badge variants the severity set extends
- <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css> — measured tokens, radius, canvas/card, status colours, motion
- <https://github.com/pingdotgg/t3code/blob/main/apps/web/components.json> — Lucide, shadcn style
- <https://www.beautifului.dev/> — AI-native primitives, "one blue accent, semantic colours used sparingly"
- <https://linear.app/blog/how-we-redesigned-the-linear-ui> — one family two cuts, darker text, neutral chrome
- <https://www.925studios.co/blog/stripe-dashboard-design-breakdown> — zoned density
- <https://basecamp.com/guides/how-we-communicate> — vocabulary as a design surface
- <https://memorable.design/empty-state-design-examples/> — empty state as onboarding
- <https://primer.style/product/primitives/color/> — emphasis/muted colour pairs
- <https://rsms.me/inter/> — Inter, optical sizes, OFL
- <https://www.npmjs.com/package/@fontsource-variable/inter> · <https://www.npmjs.com/package/@fontsource-variable/figtree> — variable builds and licences
- <https://vercel.com/font> — Geist Sans/Mono, OFL
- <https://vercel.com/geist/introduction> — foundations split, accessibility as a foundation
- <https://emilkowal.ski/ui/7-practical-animation-tips> — durations, `ease-out`, animate the rare
- <https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html> — WCAG 2.3.3, `prefers-reduced-motion`
- <https://www.ruixen.com/blog/motion-design-tokens> — motion as tokens
- <https://github.com/google-labs-code/design.md> — design systems written for agents
- <https://vercel.com/blog/teaching-agents-product-design-at-vercel> — observable rules, linter vs skill split
- <https://www.wallpaper.com/tech/openai-has-undergone-its-first-ever-rebrand-giving-fresh-life-to-chatgpt-interactions> — OpenAI Sans, "friendly and circular"

---

## 11. Hand-off to DMI-132

DMI-132 plans and implements from this note. It starts with **step 1+2 of §6 in one commit** —
the `index.css` tokens and the ESLint rules together, because the gate hard-codes token names and
fails silently when they drift. Then the `components.json` preset switch to **`radix-maia`**,
**Inter Variable** as `--font-sans`, and the re-add and hand-trim of the vendored **shadcn**
primitives (§6 steps 3–4) before any screen is touched.

[`docs/ui/mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html) is the **visual
exemplar for every screen** — build to it, and raise a question rather than deviate.
[`docs/ui/mockups/dmi-131-look-picker.html`](mockups/dmi-131-look-picker.html) is the token
comparison behind §4. The **`frontend-design-system` skill outlined in §8 is written as part of
DMI-132**, not before it.
