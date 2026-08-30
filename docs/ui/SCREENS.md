# UI Screens — Specs

> **Status:** draft (2026-07-13) — **Foundations written**; the severity hexes are the only value
> still open. Home is drafted; remaining screens are templates.
>
> **This document is the source of truth for the UI.** Where it disagrees with an ADR or a roadmap
> doc, it wins and they get reconciled to it — [`ADR-008`](../adr/ADR-008-frontend-stack.md) owns
> the *stack*, this owns the *screens*. Bottom layer of the UI docs ladder:
> [`REFERENCE.md`](REFERENCE.md) (principles) → [`FLOWS.md`](FLOWS.md) (breadboards) →
> **SCREENS.md** (foundations, layouts, states, copy). A screen section may only be written after its
> flow is locked in FLOWS.md, and each section is filled **top to bottom** — the template order is the
> method: epicenter first, chrome last ([`REFERENCE.md`](REFERENCE.md) §2, §5, §6, §7).

## Foundations

Shared decisions every screen inherits. A screen spec may not re-decide any of these; if a screen
needs an exception, it changes the rule here or it doesn't ship.

### App shell

**Top bar, no sidebar.** One horizontal bar above every inside-shell screen: wordmark left, nav
items (Home · Scans · Hosts · Agents · Users · Settings) centred, `[Log out]` right. **Users** is
omitted for viewers, not disabled.

**The nav is centred, and stays centred.** The wordmark holds the frame's left edge, `[Log out]`
holds its right, and the navigation sits on the frame's centre line — growing symmetrically from
it as destinations are added, never drifting toward either side. *Centred 2026-07-31; reverted
to left-adjacent 2026-08-07; centred again and made permanent 2026-08-21 (DMI-107).*

The 2026-08-07 reversal treated centring as a workaround for a **lone** link — an orphaned
control needing somewhere to sit — and so undid it the moment a second item arrived. That framing
is what changed. The nav is centred **because it is the product's spine**, not because of how
many items it currently holds, so the count is no longer an argument either way: it is centred at
three items and it will be centred at eight. Treating the count as the reason is what made this
decision reversible twice, and naming the real reason is what stops it happening a third time.

**Centred on the bar, not in the leftover space.** The bar is a three-column grid — `1fr auto
1fr` — so the nav's centre is the *frame's* centre regardless of the wordmark's or the button's
width. A viewer, who has no `Users` item, sees their items centred on the same axis an admin
does. Centring it inside a flex row instead would let it drift every time something beside it
changed width, which is the failure this spelling exists to prevent.

**Consequence, recorded:** there is no specified wordmark→nav gap any more. It is whatever the
frame leaves over, and it changes with the viewport. Any rule or test asserting a fixed gap there
is asserting something the layout no longer promises.

**The bar and the page share one frame.** The bar's contents and the content beneath it are both
`--container-frame`, so the wordmark and the page title start on the same vertical. The bar's
bottom hairline is full-bleed across the window, so the bar still reads as a band belonging to
the window rather than as a floating object. *Decided 2026-08-21 (DMI-107).*

**The nav names domains, not actions.** *Users* is the place user-related things live, and it keeps
that name even in v1, when the only thing in it is the invite form. Nav is muscle memory — an item
that renames itself between releases costs more than the thin page it was protecting the operator
from. New user-related surfaces are added *inside* Users rather than beside it.

A handful of destinations with no sub-levels do not earn a persistent vertical rail, and Home — a
mostly empty page whose epicenter is one centered sentence — is actively harmed by a heavy chrome
column beside it (§2 epicenter, §9 context over consistency). Nothing in the MVP has the
section/subsection depth a sidebar exists to express.

> [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Roteamento previously described the `AppShell` as
> *"sidebar/navbar persistente"*; it was narrowed to **top bar, no sidebar** on 2026-07-13 to match
> this section.

### Theme

**Light only.** The MVP ships one theme: paper-white surface, body text near-black with a slight
grey cast (never pure `#000`), deep purple accent. There is no theme toggle and no
`prefers-color-scheme` branch — dark mode is not built, not detected, not stubbed.

The anchor references are light ([`nous-home.png`](nous-research/nous-home.png),
[`psyche-header.png`](nous-research/psyche-header.png)), and the paper/engraving/print direction is
native to a light surface. Shipping one theme halves the palette work and removes an entire class of
contrast bug — and a product with a point of view picks a look rather than exporting it to a toggle
(§8). Dark mode stays parked in [`IDEAS.md`](IDEAS.md) → Theming.

**Dark mode is planned, not abandoned** — it is deliberately a later, separate pass
([`IDEAS.md`](IDEAS.md) → Theming).

**Consequence for tokens:** every color below is validated against the light surface only. Do not
author `dark:` variants in Tailwind as you go — a half-built dark mode is the worst outcome, since
it costs dual tokens on every component and still ships a surface nobody validated. When dark mode
is scoped it re-derives its palette from scratch rather than inheriting inversions of the light one.

### Typography

**Two faces. Titles are set; everything else is typed.**

| Face | Covers | Rationale |
| --- | --- | --- |
| **[IM Fell English](https://fonts.google.com/specimen/IM+Fell+English)** (regular + italic) | **Titles at every level** — the Home verdict, page titles, section and card titles, table captions, blank-slate headings | The brand face. 17th-century letterforms carry the engraving direction natively ([`IDEAS.md`](IDEAS.md) → Visual direction) |
| **[IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono)** | **All non-title text** — body copy, form labels and values, buttons, table cells, badges, and all technical data (IP, MAC, CVE, UUID, port) | Vintage-computer feel with real lineage (IBM Selectric / mainframe era) but legible at 13px in dense tables, which retro faces generally are not |

**No third face.** Prose and data share IBM Plex Mono, which is what
[`nous-home.png`](nous-research/nous-home.png) does — mono for section titles, body, *and* the
`OUTPUT / SEED` data. It works here because Dmitri has almost no long prose: the longest sentences
on any screen are the verdict and the blank-slate copy, and those are IM Fell.

**Escape hatch, if mono prose ever proves tiring:** [IBM Plex
Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) — same superfamily, shared metrics, so it
drops in for body copy without re-tuning anything. Adopting it is a change to *this section*, not a
per-screen decision.

**Size floor:** IM Fell is **never set below 16px** — its inked, irregular letterforms degrade
below that. Any label small enough to need 13–14px is by definition not a title, and is therefore
Plex Mono. This rule is what keeps the split honest.

> **Note on the references:** [`hermes.png`](nous-research/hermes.png) — Nous's *product* UI — uses
> a neutral sans and reserves character for small letterspaced accent labels; the expressive
> typography lives on their *marketing* site. Dmitri deliberately goes further than Hermes. If a
> dense screen (Host inventory, Scan detail) later proves hostile to read, the size floor and the
> Plex Sans escape hatch are the two levers — not a per-screen exception.

**Type sizes come from the named scale.** These tokens are the complete type-size set:

| Token | Value | Utility | Used for |
| --- | --- | --- | --- |
| `--text-title-lg` | `2rem` (32px) | `text-title-lg` | page titles |
| `--text-title-md` | `1.5rem` (24px) | `text-title-md` | prominent titles and the auth wordmark |
| `--text-title-sm` | `1.25rem` (20px) | `text-title-sm` | section and card titles |
| `--text-title-xs` | `1rem` (16px) | `text-title-xs` | the smallest title and inside-shell wordmark |
| `--text-body-md` | `0.875rem` (14px) | `text-body-md` | default body copy, labels, values and controls |
| `--text-body-sm` | `0.8125rem` (13px) | `text-body-sm` | compact helper and error copy |
| `--text-caption-md` | `0.75rem` (12px) | `text-caption-md` | captions and dense metadata |
| `--text-nav` | `0.6875rem` (11px) | `text-nav` | top-bar navigation only |

The framework's raw size utilities (`text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl` and
`text-2xl` through `text-9xl`) are **not part of the scale**. Using one is a violation even when
it renders the same pixels as a named token: the token is the product decision and the raw utility
silently opts out of it.

### Color

#### Neutrals — locked

The whole product is these six values plus one accent. Ratios are WCAG, measured against the
surface each token actually sits on; there is no dark variant to validate (§Theme).

| Token | Hex | Role | Contrast |
| --- | --- | --- | --- |
| `--paper` | `#FAF8F4` | page surface — warm off-white, the "sheet of paper" | — |
| `--card` | `#FFFFFF` | raised surface: cards, table headers | 1.06 vs paper (separation by warmth, not by grey) |
| `--ink` | `#1A1917` | primary text. Near-black with a warm grey cast, **never** `#000` | **16.6** on paper (AAA) |
| `--ink-muted` | `#6B6862` | secondary text: the Home footer, timestamps, helper copy | **5.2** on paper (AA) |
| `--rule` | `#E5E0D8` | decorative separators — table row lines, the dashed rules | non-text |
| `--edge` | `#8C8880` | real UI-component boundaries: input and button borders | **3.3** on paper (meets the 3:1 floor for controls) |

Two borders, deliberately: `--rule` is decoration and may be as faint as it likes, but the outline
of an *input* is a control boundary and owes 3:1 (WCAG 1.4.11). Using the faint one for both is the
common way a paper-white UI ends up with invisible form fields.

#### Accent and severity

The deep purple and the four severity hexes were auditioned against real screens during the
build and are now locked, measured against `--paper` `#FAF8F4`, the only surface they appear on.

| Token | Hex | Contrast on `--paper` | White text on it | Role |
| --- | --- | --- | --- | --- |
| `--accent` | `#7C3AED` | **5.37:1** (AA) | **5.70:1** (AA) | active nav item, primary buttons, the review-item label. Nothing else. |

The **hues are assigned** and the rules are locked.

- **Purple is the brand accent, and nothing else.** It marks focal points — the active nav item,
  primary buttons, the review-item label on Home — the role the muted blue plays in
  [`hermes.png`](nous-research/hermes.png): small, saturated, the only loud thing on a quiet
  surface. **Purple never carries severity.** It was briefly considered for `critical` and
  rejected: a color that means both "act here" and "you are in danger" means neither, and on Home
  the critical badge would collide with the `[View finding]` button beside it.
- **Severity owns its own hues, and never borrows the accent.** The ramp is conventional on
  purpose — the org admin is non-technical (§10 zero training) and red already means *bad* to them
  without being taught.
- **Every value clears AA on `--paper`** before it ships. Severity badges are text, so they owe
  **4.5:1**, not the 3:1 control floor — the usual trap when picking a red that "looks right".

| Severity | Hue | Hex | Contrast on `--paper` | Usage |
| --- | --- | --- | --- | --- |
| Critical | **red** | `#B91C1C` | **6.1:1** (AA) | the loudest thing in the product; surfaces on Home |
| High | **orange** | `#C2410C` | **4.9:1** (AA) | surfaces on Home |
| Medium | **amber** | `#A16207` | **4.6:1** (AA) | never surfaces on Home |
| Low | **blue** | `#1D4ED8` | **6.3:1** (AA) | never surfaces on Home |
| Informational | **ink-muted** | `#6B6862` | **5.2:1** (AA) | visual token only — not a contract severity |

Blue appears here and nowhere else. The old "no blue anywhere" rule existed to protect the accent,
and it still does in that form: **no blue as a brand color** — but as a low-severity semantic token
it is doing a different job, exactly as red does at critical.

**These were the only unfilled values in Foundations**, now resolved.

### Interaction states

**Every interactive element declares all five of its states.** Rest, hover, focus-visible, active
and disabled are each a designed property, specified beside colour and type. Cursor treatment is
explicit too. An element the user can act on and which looks identical under the pointer is a
**defect**, not a style preference — the user has no way to learn it is a control except by
clicking things at random to find out. *Decided 2026-08-18 (DMI-107).*

| State | Owes |
| --- | --- |
| **Rest** | It looks like a control: a colour, a border, a caret or an underline that a paragraph beside it does not have. Accent purple, a hairline `--edge` boundary, or a caret — one of the three, at least. |
| **Hover** | `cursor: pointer`, always, including text-shaped controls, plus one visible change: an underline, a background wash or a colour shift. Tailwind v4's preflight sets `cursor: default` on `<button>`, so the pointer is added, never inherited. |
| **Focus-visible** | A ring at `--ring`, never `outline: none` and never a ring so faint it needs looking for. Keyboard users get the same affordance the pointer gets, so a control that underlines on hover also underlines on focus. |
| **Active** | A pressed acknowledgement — the 1px downward nudge the button primitive already carries. |
| **Disabled** | Reduced opacity, `pointer-events: none`, and out of the tab order. This is only for the progress carve-out of Consistency rule 3. A permission the user does not hold is absent, and has no disabled state to design. |

**Only shared components may be interactive.** Application screens compose shared primitives and
components; they do not hand-roll native controls or one-off click targets. Vendored shadcn
primitives live in `frontend/src/components/ui/`; Dmitri-owned shared interactive components live
in `frontend/src/components/`. Keeping interactivity shared makes the state table enforceable in
one place instead of at every call site.

**Motion is a transform, and it is small.** Carets rotate and buttons nudge. No fades on layout,
no easing curves worth naming, nothing that outlasts a key press.

### Spacing and rhythm

Building rule 1 says spacing comes from the token set. This is that set. **Whitespace is the
loudest thing on these screens** — on a normal day Home is one sentence in a lot of paper, and
that emptiness is the design, not an unfinished layout. Spacing is therefore specified as
deliberately as color.

**The base unit is 4px** — Tailwind v4's `--spacing` default, so the `p-*` / `gap-*` / `space-y-*`
utilities already resolve to it and no custom token layer is needed.

**Use these steps and no others:**

| Step | Value | Used for |
| --- | --- | --- |
| `1` | 4px | icon-to-text, badge internals |
| `2` | 8px | label-to-value, items inside one group |
| `3` | 12px | tight stack — table cell padding |
| `4` | 16px | default gap between related elements |
| `6` | 24px | card internal padding; and between sections of a short-section screen |
| `8` | 32px | between cards in a list |
| `12` | 48px | between sections of a table-led or long-section screen |
| `16` | 64px | around the epicenter — the verdict's breathing room |
| `24` | 96px | top offset for a vertically-centred, near-empty screen |

Anything else — `p-5`, `gap-7`, `mt-[13px]` — is a bug by Building rule 1. An arbitrary-value
utility (`p-[13px]`) is the same bug wearing brackets: if a value is worth using it is worth
being a step.

**Four rhythm rules, binding:**

1. **The parent owns the space between children.** Components ship with **no outer margin** —
   they render flush to their own bounding box, and the layout that places them supplies the
   gap. A component with `mb-4` baked in dictates its own spacing everywhere it is ever reused,
   and the second use site always fights it. This is the single rule that keeps a component
   library composable.
2. **Gap, not margins between siblings.** Use flex/grid `gap-*` on the container. Sibling margins
   collapse unpredictably, leave orphaned space when an item is conditionally absent, and make
   "what is the space here" a question with two answers.
3. **Space groups things; it does not decorate.** Related elements sit closer than unrelated ones
   — proximity is how the eye parses the page. Where a rule and whitespace would both separate
   two regions, the choice is **per screen and stated once**, not left to the component.
   Prose-led screens with long sections prefer whitespace — the near-monochrome surface earns its
   calm by having fewer lines on it. **A screen of short, unlike sections prefers the rule**:
   when sections are two or three rows each, the space between them is too small to do the
   separating on its own, and a hairline does the work that 48px of paper used to. `/settings` is
   the first of these. *Decided 2026-08-21 (DMI-107).*

   When a screen takes the rule, it takes it at **every** boundary, including sections added
   later. A rule that appears at one boundary and not the others stops reading as structure and
   starts reading as emphasis on whatever it happens to sit above.
4. **Vertical rhythm is consistent; horizontal is generous.** A screen uses at most three vertical
   step sizes (intra-group, inter-group, inter-section). Horizontal padding inside the content
   column never drops below step `6`, so text never runs to the edge of its card.

   **The inter-section step is chosen per screen, from `6`, `8` or `12` — and only those.** A
   screen whose sections are two or three short rows (Settings: a label/value pair, a button, a
   disclosure) uses `6`; a screen whose sections are tables or long prose uses `12`; `8` is the
   middle case. What stays binding is the *shape*: three vertical steps, each visibly larger than
   the last, and the inter-section step never smaller than the inter-group step. *Decided
   2026-08-21 (DMI-107).*

   The trade is explicit. At `6` the inter-section step is 1.5× the inter-group step rather than
   3×, so **space alone stops carrying the grouping** and the section heading has to help. That
   works on Settings because its headings are IM Fell at 20px against Plex Mono body — a face
   change, not just a size change. A screen without that contrast picks `8` or `12` instead.

**One screen, one spacing owner.** A screen's page-level layout sets its section rhythm in one
place. A nested component never reaches out to adjust the space around itself.

### Viewport

**Desktop-only, but fluid within it.** Target **1440px**, minimum **1280px**. No tablet or mobile
layouts are designed: no stacked columns, no collapsed nav, no card-per-row fallback for tables.

The users are an org admin and a viewer at a desk; nobody triages a network scan on a phone. A
mobile layout is a problem when it's a problem (§12) — until real usage demands it, it is scope
paid for out of the quality of the desktop screens (§3).

**"Not designed for" is not "breaks".** Every layout is fluid, so the app degrades gracefully at
any width instead of shattering:

- **Content column:** the widths are the named containers and only the named containers — see
  §Proportion and containers. **Every inside-shell screen holds `--container-frame`**, prose-led
  and table-led alike, and so does the top bar above it: one frame, one left edge. A standalone
  short form — the auth card above all — holds `--container-form`. Both are *maximums*, not
  fixed widths: below them the column shrinks with the viewport.
- **Reading measure is separate from column width.** A paragraph is held to about 65 characters
  wherever it sits. Widening a column never lengthens a line.
- **No fixed pixel widths on layout containers.** Widths are `max-w-*` + fluid, or grid/flex
  fractions. A container never has a width it can't give back.
- **The page body never scrolls horizontally.** Wide content — tables above all — scrolls inside
  its own `overflow-x: auto` container, so the chrome and the verdict stay put.

### Proportion and containers

**Containers have names, and the names are the only layout widths.** A layout width is one of the
two named containers below or it is a bug. `max-w-[45rem]` is the same bug as `p-[13px]`: a
number that was right once, copied where nobody re-asked whether it was still right. That copy is
how the login card became a 720px letterbox band around 336px of form. *Decided 2026-08-18
(DMI-107).*

| Token | Value | Is the width of |
| --- | --- | --- |
| `--container-frame` | `70rem` (1120px) | The frame — the top bar's contents and the page content beneath it. One width for the whole shell. |
| `--container-form` | `24rem` (384px) | The form column — a short form standing on its own, above all the auth card. |

Both are maxima and fluid below themselves (§Viewport). Nothing else is a layout width. A separate
720px prose column was specified and then removed: once the bar and content share one frame there
is nothing left for it to measure.

**A card sizes to its content, never to its column.** A short form in a wide column is a narrow
card centred in that column, not a wide card with a lake of padding around its inputs. The column
and the card are different measurements; only one is about the viewport.

**The frame and the content share one width.** The top bar's contents and the page beneath it both
span `--container-frame`, so the wordmark and the page title start on the same vertical. The shell
reads as one column of paper rather than chrome floating over a narrower sheet. *Decided
2026-08-21 (DMI-107).*

**Column width and reading measure are different problems.** Widening the column does not widen
the prose in it: a paragraph is still held to about 65 characters by `max-w-prose`. The column
decides where the page structure sits; the reading measure decides how long a line may get.

### Building rules

How the above is enforced in code. These are binding on implementation, not suggestions.

1. **No magic numbers.** Spacing, type sizes, colors, radii and border widths come from the token
   set (Tailwind theme + CSS variables), defined once. A raw `padding: 13px` or `#6B21A8` in a
   component is a bug, not a shortcut — if a value is worth using it is worth being a token.
2. **Components size to their container, not to the viewport.** No component hardcodes a width
   because of what it happens to sit next to today.
3. **Relative units and intrinsic layout.** Flex and grid over absolute positioning; `min-w-0` on
   flex children so long values (UUIDs, hostnames) shrink instead of blowing out the row.
4. **Long values never break the layout.** Truncate with ellipsis, wrap, or scroll the container —
   a 64-character hostname must not widen the page (see Consistency rule 6, IDs truncate).
5. **Text sizes are tokens too.** The 16px floor on IM Fell (§Typography) is enforced by the scale,
   not by remembering it.
6. **The mechanical rules are lint rules, not reminders.** `local/no-arbitrary-utility`,
   `local/no-raw-type-size`, `local/spacing-scale` and `local/no-bare-interactive` enforce
   arbitrary values, the closed type scale, the spacing scale and shared interactive controls.

### Shared components

Only components that **two or more screens actually use**. Everything else is written inline in the
screen that needs it.

| Component | Used by |
| --- | --- |
| `TopBar` | every inside-shell screen |
| `PageHeader` | Scans, Hosts, Agents, Users — **not Home** (the verdict is the header) |
| `DataTable` | Scan list, host inventory, scan detail findings and hosts, host detail findings, ports and history. Users & invites is **not** retrofitted (tracked follow-up). |
| `Pagination` | Scan list, host inventory |
| `SeverityBadge` | Home (critical item), Scan detail, Host detail |
| `StatusPill` | Agents (command lifecycle), Scan list/detail (scan status). Shared `h-8` height; `failed` and `expired` share a tone, separated by copy. |
| `Timestamp` | everywhere a time is rendered — owns the relative/absolute rule below |
| `EmptyState` | table-led screen blanks + `AgentsBlank` (optional `action` and `note` slots) |
| `FirstScanCta` | blank Home, Scans and Hosts — admin link to `/agents`; viewer line via `FirstScanNote` |
| `LoadingSkeleton` | every table-led screen |
| `Toast` | Users & invites — role change, remove, revoke **succeeding**; Agents — scan trigger refusals (`503 device_offline`, `409 device_busy`, subnet stale) and subnet PATCH refusals |
| `Ornament` | Home, auth screens — the engraving detail: a filled lozenge on a full-width hairline, broken either side. **Inline SVG, never a Unicode glyph** — a glyph cannot be given a stroke weight, a size or a rule to sit on, and it renders differently wherever the face is missing. Sizes to its container with no props. |

**Cut from the candidate list:** `Sidebar` (top bar chosen above) · `MetricCard` (the MVP has no
metric cards, by decision) · `Breadcrumbs` (nothing is deeper than list → detail; parked in
[`IDEAS.md`](IDEAS.md)).

### Consistency rules

Cross-screen rules. A screen spec may cite these instead of restating them.

1. **Three states, no exceptions.** Every screen and every table ships a designed regular, blank
   and error state. A table never renders bare with no rows (§7).
2. **Errors have a next step.** Page-level failure = plain copy + `[Retry]`. Action failure =
   toast naming the thing that failed. Never a spinner that never resolves, never a skeleton
   standing in for a verdict (§7 get defensive).
3. **Absent, not disabled.** Actions a role cannot perform are omitted from the DOM, not greyed
   out. The viewer never learns what they're missing (§9). **This rule is about permission, not
   progress.** *Carve-out:* an action the person **is** permitted to take but hasn't yet supplied
   the required input for is a different case — the confirm-by-typing button on SETTINGS and on
   USERS & INVITES is greyed out, unclickable and out of the tab order until the typed address
   matches ([`ADR-017`](../adr/ADR-017-account-removal.md) §5). A test of this rule asserts that a
   viewer's admin affordances are **absent**; it does not sweep the tree for `[disabled]`.
4. **Whole rows are links.** In every table the entire row navigates; no trailing "View" button
   column.
5. **If it isn't a title, it's IBM Plex Mono.** There is no third face and no per-screen
   exception. IM Fell never appears below 16px (§Typography).
6. **IDs truncate, hover reveals.** UUIDs render as the first 8 characters; the full value is in
   the `title`. Never wrap a UUID.
7. **Timestamps:** relative inside 7 days (`yesterday 21:40`, `2 min ago`), absolute beyond it;
   the exact value always available on hover. One `Timestamp` component owns this.
8. **Buttons say what they do.** `Scan now`, `Invite user`, `Set password` — never `Submit`,
   `Execute`, `OK` (§6).
9. **Real content only.** Specs and mocks use real hostnames, real CVE ids, real IPs. No lorem
   ipsum, no `foo` (§6 use real words).
10. **Columns align by content, except the first.** Text left-aligns. Numbers right-align in
   tabular figures so the digits stack — a port under a port, a count under a count. **The first
   column always starts flush left whatever it holds**: a right-aligned leading column pushes the
   table's visible start into the middle of the frame while every neighbouring table begins at the
   edge, and the reader sees a broken grid rather than a tidy number. So findings `Port` and the
   `Open ports` counts right-align; the ports tables' leading `Port` does not. **A heading carries
   its column's alignment** — a label stranded over empty space while its values sit at the far
   side of the column is the defect this rule exists to prevent. *Decided 2026-08-27.*
11. **Severity reads down the right edge.** No table opens with the severity badge. It closes the
   row on scan list, scan detail findings, host detail findings and host scan history, and on host
   inventory it is second to last, with `Last seen` closing. A reader scanning for the worst thing
   follows one edge instead of hunting for the column per screen. *Decided 2026-08-27.*

## Screen index

Status: `☐` not specced · `◐` draft · `✅` locked. Routes and roles per
[`FLOWS.md`](FLOWS.md) places inventory.

| Screen | Route | Shell | Roles | Flow | Status |
| --- | --- | --- | --- | --- | --- |
| Login | `/login` | outside | public | B1 | ◐ (C16) |
| Accept invite | `/invite?token=…` | outside | public | B2 | ◐ (C14 resolved; endpoint unconsumed — DMI-87) |
| Forgot password | `/forgot-password` | outside | public | B1 | ◐ |
| Reset password | `/reset-password?token=…` | outside | public | B1 | ✅ (C15 resolved) |
| Home | `/` | inside | admin, viewer | B2, B3 | ◐ |
| Scan list | `/scans` | inside | admin, viewer | B3 | ◐ built (DMI-88) |
| Scan detail | `/scans/:scanId` | inside | admin, viewer | B3, B4 | ◐ built (DMI-88; C10 resolved) |
| Host inventory | `/hosts` | inside | admin, viewer | B3 | ◐ built (DMI-88) |
| Host detail | `/hosts/:hostId` | inside | admin, viewer | B3 | ◐ built (DMI-88; C11 resolved — `?host_id=`) |
| Agents | `/agents` | inside | admin, viewer (ro) | B4 | ✅ built (DMI-89) — scan trigger, subnet chooser, command poll |
| Users & invites | `/users` | inside | admin | B2 | ◐ API ready (C4 closed); frontend screen not built |
| Settings | `/settings` | inside | admin, viewer | B5 | ◐ details (read-only), password modal, activity disclosure and removal built; profile **editing** pending on C3 |

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

### The auth shell

The five outside-shell screens share one frame, specced once here rather than four times below.
No top bar (there is no session yet, and nowhere to navigate), no nav, no `[Log out]`.

- **Frame:** wordmark, `Ornament`, then a single centered card in the **`--container-form` column
  (384px)** (§Proportion and containers). The card is the page; there is no other content — and
  because there is no other content, the card sizes to the form rather than to the viewport. It
  is a portrait card, taller than it is wide, and it stays 384px on the longer screens (Accept
  invite, Reset password), which simply grow downward. It was briefly 720px, which read as a
  letterbox band around 336px of inputs; that is the defect §Proportion and containers exists to
  prevent. *Corrected 2026-08-18 (DMI-107).*
- **Never reveal whether an account exists.** Login's `401` and Forgot's `204` are both deliberately
  uninformative. This is why Forgot always shows the same confirmation, and why login's error names
  neither field ([`AUTH.md`](../roadmap/AUTH.md) → Forgot password).
- **State the password policy before it is violated, never after.** Every screen with a new-password
  field carries the same hint as SETTINGS: *"At least 12 characters. Avoid names, dates, and
  passwords you've used elsewhere."* Discovering the rules by failing is a §7 failure.
- **Confirm-password fields are client-side only.** No contract request body has one
  (`AcceptInviteRequest`, `ResetPasswordRequest` take a single `password` / `new_password`,
  `minLength: 12`). The mismatch error never reaches the server.
- **Submitting is a state.** The button becomes its own progress copy (`"Logging in…"`) and is
  disabled while in flight. Never a bare spinner (§7).
- **Password managers are a feature, not an edge case.** Real `<form>`, real `autocomplete`
  (`email`, `current-password`, `new-password`), submit on Enter, first field autofocused. An org
  admin forced to type a 12-character password without a manager will pick a bad one.

---

### LOGIN

**Route:** `/login` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — the two fields and the button. Nothing else earns space on this page.

**Data:**
- `POST /api/v1/auth/login` → `LoginResponse` (`access_token`, `token_type`, `expires_in`); the
  refresh token arrives as an httpOnly `Set-Cookie` and the SPA never sees it
  ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client).
- `401` → wrong credentials. There is no other failure branch: login is `200`/`401` only
  ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced password rotation is dropped, so there
  is no expired-password 403 to route anywhere).

**Where the role comes from — 🔓 C16.** `LoginResponse` carries **only a token**. Every "absent, not
disabled" decision in this product (rule 3) — the `Users` nav item, `[Scan now]`, the invite form —
depends on knowing whether this user is an `admin` or a `viewer`.
[`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis says the role arrives **in the JWT claims**,
but the contract documents no claims at all. The frontend would be decoding an undocumented payload
to decide what to render.

**Three states:**
- **Regular:** the form.
- **Blank:** **not applicable.** A login form is never empty — it is its own content. Recorded so
  nobody invents an empty state to satisfy rule 1.
- **Error:** inline, above the button. Wrong credentials name neither field. A `5xx`/network failure
  is a *different* error and says so — telling someone their password is wrong when the server is
  down is the §7 sin.

**One arrival note, above the form.** A user who has just deleted their own account in SETTINGS
lands here ([`ADR-017`](../adr/ADR-017-account-removal.md)) — their session no longer exists, so
there is nowhere else to send them. It is a *confirmation*, not an error, and is styled as one:
they did something irreversible and deserve to be told it worked. It does not persist across a
reload; a stale "your account was deleted" on a shared machine would be both confusing and a small
disclosure.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Sign in" |
| Fields | "Email" / "Password" |
| Button | "Log in" · in flight: "Logging in…" |
| Link | "Forgot password?" |
| Error — 401 | "That email and password don't match." |
| Error — server/network | "Couldn't reach Dmitri. Try again in a moment." |
| Arrival — account deleted | "Your account has been deleted." |

**Layout:**
```text
+------------------------------------------------------------------------------+
|                                                                              |
|                        ~ small engraving ornament ~                          |
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |  SIGN IN                                   |                    |
|              |                                          |                    |
|              |  Email                                   |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |  Password                                |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |  That email and password don't match.    |  ← inline, on error|
|              |                                          |                    |
|              |            [ ▓   Log in   ]              |                    |
|              |                                          |                    |
|              |            Forgot password?              |                    |
|              +------------------------------------------+                    |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. **C16** — the role is not in the contract. Blocks role gating everywhere, not just here.

---

### ACCEPT INVITE

**Route:** `/invite?token=…` · **Shell:** outside · **Roles:** public · **Flow:** B2

**Epicenter** — choosing a password. This is the first thing anyone ever does in Dmitri, and the
account exists the moment it succeeds.

**Data:**
- `POST /api/v1/invites/accept` — body `{ token, password }` (`minLength: 12`). The invite
  token moved from the URL path into the body in DMI-77 (it was being written to access logs), so
  the route reads it from the request body and the emailed link is `/invite?token=…`. **The `email`
  field was removed** (spec 027 / DR-0002, 2026-08-06): once the lookup below supplies the address,
  retyping it proves nothing, and the account was always created from the invite record anyway.
  Sending one now returns **422** rather than being ignored.
- `POST /api/v1/invites/lookup` — body `{ token }`, public, returns `{ email, role, org_name }`.
  Reading does **not** consume the invite, so the page may call it on mount and the link still
  works. A dead token answers **410** here too, with the same body the accept route gives.
- **`201` returns a full `LoginResponse`.** ✅ **C7 RESOLVED — accepting an invite issues a
  session.** Store the access token, and the invitee lands on **HOME**, in its first-run blank state
  (B2). They are never sent back to LOGIN to type the password they just chose.
- **`410`** — invite expired or already used (**not** `400`; single-use, 24–72h TTL per
  [`AUTH.md`](../roadmap/AUTH.md)). **`400`** — password rejected by policy.

**The screen can now greet you — ✅ C14 resolved.** The lookup landed 2026-08-06 (DMI-86), so both
of the consequences this section used to list are gone: the page can say *"You've been invited to
Acme with the viewer role"* — the one sentence that tells a stranger the link is legitimate — and the
invitee no longer types their own email from memory, so a typo can no longer fail identically to a
dead link. **The endpoint is unconsumed**: building the screen against it is DMI-87, which is why
this screen is still `◐`.

**Three states:**
- **Regular:** the greeting (*"You've been invited to Acme with the viewer role"*, from the lookup) plus the
  form. Password + confirm — **no email field**.
- **Blank:** not applicable (a form is its own content).
- **Error — dead link (410):** the form is **removed**, not left there to be re-submitted. The link
  is spent; nothing the user types will fix it. The only honest next step is *ask your admin*, and
  there is no self-serve escape (§7 — get defensive, and don't offer an action that cannot work).
- **Error — policy (400):** inline under the password field; the form stays.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Create your account" |
| Body | "You've been invited to {org_name} with the {role} role. Pick a password and you're in." — org and role from the lookup. The article was dropped 2026-08-06 (DMI-87): `role` is the enum `admin \| viewer`, so "as a {role}" renders "as a admin" for every admin invite, and this wording needs no per-role branch |
| Fields | "Password" / "Confirm password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Button | "Create account" · in flight: "Creating your account…" |
| Error — 410 (heading) | "This invite has expired." |
| Error — 410 (body) | "Invite links can only be used once, and they don't last long. Ask your admin to send you a new one." |
| Error — 400 policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client) | "Those two passwords don't match." |
| Error — already registered (400) | "That address already has an account. Sign in instead." |

**Layout:**
```text
+------------------------------------------------------------------------------+
|                        ~ small engraving ornament ~                          |
|                              D M I T R I                                     |
|                                                                              |
|              +------------------------------------------+                    |
|              |  CREATE YOUR ACCOUNT                     |                    |
|              |  You've been invited to Acme with the    |                    |
|              |  viewer role. Pick a password and        |                    |
|              |  you're in.                              |                    |
|              |                                 (muted)  |                    |
|              |                                          |                    |
|              |  Password                                |                    |
|              |  [__________________________________]    |                    |
|              |  At least 12 characters. Avoid names,    |                    |
|              |  dates, and passwords you've used        |                    |
|              |  elsewhere.                     (muted)  |                    |
|              |                                          |                    |
|              |  Confirm password                        |                    |
|              |  [__________________________________]    |                    |
|              |                                          |                    |
|              |        [ ▓  Create account  ]            |                    |
|              +------------------------------------------+                    |
+------------------------------------------------------------------------------+
```

Dead link (410) — the form is gone:
```text
              +------------------------------------------+
              |  THIS INVITE HAS EXPIRED.                |
              |                                          |
              |  Invite links can only be used once, and |
              |  they don't last long. Ask your admin to |
              |  send you a new one.            (muted)  |
              +------------------------------------------+
```

**Open questions:**
1. ~~**C14** — no invite-lookup endpoint.~~ **✅ RESOLVED 2026-08-06 (DMI-86, spec 027) —
   `POST /api/v1/invites/lookup`**, token in the body (not a `GET` — a query string keeps the token
   out of the path but not out of the access log), returning `{ email, role, org_name }`, with
   `410 invalid_invite_token` for expired/used/unknown alike. The screen can now name the org, state
   the role, and skip the email field entirely; a dead link is reached **on mount**, before the form
   is ever submitted, so the 410 state no longer has to double as a typo message. **This screen
   stays `◐` for a different reason now:** the endpoint exists and nothing consumes it — building
   the page against it is DMI-87.

---

### FORGOT PASSWORD

**Route:** `/forgot-password` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — one field and one button. The screen's real job is what it says *afterwards*.

**Data:**
- `POST /api/v1/auth/forgot-password` — body `{ email }`. **Always `204`.** There is no error
  branch and no 404: the contract cannot tell you whether the account exists, on purpose.

**The confirmation must be honest about being uninformative.** Since the response is identical for a
real and a fake address, the copy must not promise an email that may never arrive — *"Check your
inbox"* is a lie to anyone who mistyped. Say what was actually done and what it depends on: **if**
that address has an account. Wording around this is how products leak their user lists (§6 — the
copy *is* the security boundary here).

**Three states:**
- **Regular:** the form.
- **Blank:** not applicable.
- **Confirmed (the real second state):** the form is **replaced** by the confirmation. Leaving the
  field there invites the user to fire off three more emails when the first doesn't arrive in
  fifteen seconds.
- **Error:** only network/server failure can occur — a `204` is not a success signal about the
  address, merely that the request landed.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Reset your password" |
| Body | "Enter your email and we'll send you a link to set a new password." |
| Field | "Email" |
| Button | "Send reset link" · in flight: "Sending…" |
| Confirmation — heading | "Check your email." |
| Confirmation — body | "If **name@example.com** has a Dmitri account, a reset link is on its way. The link works once and expires shortly." |
| Confirmation — link | "Back to sign in" |
| Error — server/network | "Couldn't reach Dmitri. Try again in a moment." |

**Layout:**
```text
              +------------------------------------------+
              |  RESET YOUR PASSWORD                     |
              |  Enter your email and we'll send you a    |
              |  link to set a new password.    (muted)  |
              |                                          |
              |  Email                                   |
              |  [__________________________________]    |
              |                                          |
              |        [ ▓  Send reset link  ]           |
              |                                          |
              |            Back to sign in               |
              +------------------------------------------+
```

Confirmed — the form is replaced:
```text
              +------------------------------------------+
              |  CHECK YOUR EMAIL.                       |
              |                                          |
              |  If name@example.com has a Dmitri        |
              |  account, a reset link is on its way.    |
              |  The link works once and expires         |
              |  shortly.                       (muted)  |
              |                                          |
              |            Back to sign in               |
              +------------------------------------------+
```

**Open questions:** none.

---

### RESET PASSWORD

**Route:** `/reset-password?token=…` · **Shell:** outside · **Roles:** public · **Flow:** B1

**Epicenter** — the new-password field.

**Data:**
- `POST /api/v1/auth/reset-password` — body `{ token, new_password }` (`minLength: 12`). **The token
  travels in the body, not the path** — the screen reads it from the query string and posts it.
- `204` → **LOGIN**, with success copy. Reset does **not** issue a session (unlike accept-invite);
  the user logs in with the password they just set. That is the correct edge — it proves the
  password works and re-arms the recall the 7-day refresh window exists to encourage
  ([`AUTH.md`](../roadmap/AUTH.md) → Sessions).
- `410 invalid_reset_token` → the link is dead (never issued, already used, or expired). Remove the
  form; tell the user to request a new one.
- `400 password_policy_violation` → stay on the form; inline error under the new-password field.

**✅ C15 RESOLVED 2026-08-03 (DMI-77).** The two failures no longer share a status *or* a code. A
dead link is `410` with `error.code: invalid_reset_token`; a rejected password is `400` with
`password_policy_violation`. Both codes are pinned by an `enum` in the contract
(`ResetTokenGone` / `ResetPasswordRejected`) and gated by `test_contract_fidelity.py`, so the screen
can switch on `error.code` safely. The token is checked **before** the policy, so a dead link plus a
weak password yields the `410` — the link is the thing to fix first. `410` matches accept-invite, so
both token screens share one pattern.

**Missing token:** `/reset-password` with no `?token=` never renders the form — there is nothing to
submit. It shows the dead-link state directly.

**Three states:**
- **Regular:** the form.
- **Blank:** not applicable.
- **Error — dead link:** form removed, `[Request a new link]` → FORGOT PASSWORD. Same reasoning as
  the invite: nothing typed here can revive a spent token.
- **Error — policy:** inline; the form stays.

**Copy:**
| Element | Copy |
| --- | --- |
| Title | "Set a new password" |
| Fields | "New password" / "Confirm new password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Button | "Set password" · in flight: "Setting your password…" |
| Success (on LOGIN) | "Password set. Sign in with your new password." |
| Error — dead link (heading) | "This link has expired." |
| Error — dead link (body) | "Reset links work once and don't last long." · [Request a new link] |
| Error — policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client) | "Those two passwords don't match." |

**Layout:**
```text
              +------------------------------------------+
              |  SET A NEW PASSWORD                      |
              |                                          |
              |  New password                            |
              |  [__________________________________]    |
              |  At least 12 characters. Avoid names,    |
              |  dates, and passwords you've used        |
              |  elsewhere.                     (muted)  |
              |                                          |
              |  Confirm new password                    |
              |  [__________________________________]    |
              |                                          |
              |         [ ▓   Set password   ]           |
              +------------------------------------------+
```

**Open questions:**
1. **C15** — the `400` cannot be disambiguated. The screen's most common failure (a stale link,
   because reset emails sit in inboxes) is the one it cannot word correctly.

---

### HOME

**Route:** `/` · **Shell:** inside · **Roles:** admin, viewer ·
**Flow:** B2 (blank slate), B3

Home is not a metrics dashboard. Its job is a review: the product interprets and the operator
reads a judgment, not numbers (REFERENCE.md §6, §8, §10). On a normal day the page is mostly
empty on purpose.

**Epicenter** — the one thing this screen cannot live without, designed first, chrome last:
the verdict line — one plain sentence stating whether anything needs the operator's
attention since they last looked.

**Data** — endpoints and fields consumed (contract names):
- `GET /api/v1/scans?per_page=1` (default sort `timestamp` desc) — latest scan feeds the
  verdict, the scan-failed item (`status: failed`), and the context footer (`timestamp`,
  `host_count`, `finding_count`, `highest_severity`, `scan_mode`)
- `GET /api/v1/findings?scan_id={latest}&severity=critical` (and `severity=high`) — finding
  review items (`title`, `cve_id`, `ip`, `severity`)
- `GET /api/v1/agents/{agent_id}` — `online`, `last_seen_at`, `display_name` feed the
  coverage-stale item and the footer Pi status
- New-device item: `HostSummary` carries `first_seen_at` (**C6** resolved), so the item is no
  longer contract-blocked; it is still not built, and shipping it in v1 is a product call

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
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
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
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
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
| DMITRI          Home    Scans  Hosts  Agents  Users              [Log out]   |
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
1. ~~New-device review item — blocked on contract (`first_seen_at` on `HostSummary` — **C6**).~~
   **✅ RESOLVED — `first_seen_at` is a required property on `HostSummary`.** The item is
   unblocked but still unbuilt; whether it ships in v1 is a product call, not a contract gap.
2. Coverage-stale thresholds: Pi `online: false` is immediate, but "no completed scan in
   N days" needs an N.
3. "Not seen before" phrasing needs a backend finding-delta (IDEAS.md backend note); v1
   copy claims only "found in last night's scan".

---

### SCAN LIST

**Route:** `/scans` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — the run log: every scan, newest first, each answering *did it work, and did it find
anything*. This is the one screen in the product that is honestly a table, and it should look like
one.

**Data:**
- `GET /api/v1/scans?page&per_page=20&sort_by=timestamp&sort_order=desc` → `ScanListResponse`
  (`data: ScanSummary[]`, `total`, `page`). Server-driven sorting and pagination already exist in
  the contract; **no client-side sorting.**
- `ScanSummary`: `scan_id`, `timestamp`, `subnet`, `scan_mode`, `status`, `host_count`,
  `finding_count`, `highest_severity` (nullable).

`ScanStatus` is `pending | accepted | processing | completed | failed` — **not** the command
lifecycle. A scan triggered from Agents appears here as `pending` **immediately** (the stub row is
created at enqueue, [`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)), so this list
is live during a scan and must not look broken while a row is unfinished.

**Filters are cut from v1** ([`IDEAS.md`](IDEAS.md) → Scans). The contract supports a `status`
filter; the screen does not use it. One Pi scanning one subnet does not produce a list that needs
filtering yet (§12).

**Three states:**
- **Regular:** one row per scan. Whole row navigates (rule 4). An unfinished scan shows a
  `StatusPill` instead of counts — it has no counts yet.
- **Blank:** no scans ever. Same first-run CTA as blank Home — admin `[Run first scan]` → Agents;
  viewer "Ask your admin to run the first scan."
- **Error:** page-level copy + [Retry]. `LoadingSkeleton` for the table body on first load only —
  never on background refetch, which would make a live list flicker.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Scans" |
| Columns | "When · Mode · Status · Hosts · Findings · Highest severity" |
| Status — completed | "Completed" (neutral `StatusPill`; **not** a success color — green would be a new Foundations token competing with the severity badge on the same row. An em dash here would mean "looked, nothing there", which is the wrong sentence about a scan that succeeded.) |
| Status — pending/accepted/processing | "Running…" |
| Status — failed | "Failed" |
| Findings cell — zero | "None" |
| Highest severity — null on a completed scan | "—" |
| Pagination | "Showing 1–20 of 47" · [Previous] [Next] |
| Blank — heading | "No scans yet." |
| Blank — body | "Dmitri scans your network for devices and known vulnerabilities. Every scan you run shows up here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the scans." · [Retry] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SCANS                                                                      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   WHEN            MODE    STATUS     HOSTS  FINDINGS  HIGHEST                |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   2 min ago       quick   Running…      -         -   -                      |
|   yesterday 21:40 quick   Completed    12         3   ▓ CRITICAL             |
|   Jul 11  21:40   quick   Completed    12         0   —                      |
|   Jul 10  21:40   quick   Failed        -         -   -                      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Showing 1–20 of 47                          [Previous]  [Next]             |
+------------------------------------------------------------------------------+
```

**Open questions:** none.

---

### SCAN DETAIL

**Route:** `/scans/:scanId` · optional `?finding=:findingId` (deep link from Home, B3) ·
**Shell:** inside · **Roles:** admin, viewer · **Flow:** B3, B4

**Epicenter** — the findings list ([`REFERENCE.md`](REFERENCE.md) §2). Hosts are context; the
findings are why anyone opened this page. Design the findings table first, the host table second,
the header last.

**Data:**
- `GET /api/v1/scans/{scan_id}` → `ScanDetailResponse` — **one request, everything embedded**:
  `findings: FindingRecord[]`, `hosts: ScanHostView[]`, `timestamp`, `subnet`, `scan_mode`,
  `status`, `host_count`, `finding_count`, `command_id` (nullable), `error_code` (`ScanErrorCode | null`).
- **No `GET /findings` call here, and no `GET /findings/{id}`.** `FindingRecord` arrives complete —
  `severity`, `title`, `description`, `recommendation`, `evidence`, `references`, `cve_id`,
  `cvss_score`, `host_ip`, `port`, `protocol`, `service`. Opening a finding is **local state**.
- **Failure reason:** on `status: failed`, `error_code` is on this same body (never null). Map it
  through `scanFailureReason()` in `frontend/src/lib/scanFailureReasons.ts` — **C10 resolved
  (DMI-75)**; rendering it is DMI-88. Do not fetch `GET /commands/{id}` for the sentence.

**Three states:**
- **Regular:** header (when · mode · subnet · counts), then findings sorted critical→low, then the
  host table. Clicking a finding row expands its panel **in place**; clicking a host row expands its
  ports **in place**. Neither navigates.
- **Regular, no findings (the good day):** the findings section says so in words and the host table
  carries the page. Positive framing, not an empty table (§7).
- **Regular, unfinished:** `status` is `pending`/`accepted`/`processing` — the scan is running right
  now. The page says so and does **not** poll; the run log refreshes when a command completes on
  Agents (cache invalidation). It does not render an empty findings table as though the answer were
  "nothing".
- **Regular, failed:** the failure **is** the content. Show the reason from `error_code` and what to
  do; suppress the empty findings and host tables entirely.
- **Error:** page-level copy + [Retry]. 404 gets its own line.

**Deep link:** `?finding=:findingId` — match the id in the already-loaded `findings`, scroll to that
row, open its panel. Absent or unmatched → render normally. No extra fetch (B3).

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Scan — yesterday 21:40" |
| Header line | "quick mode · 192.168.0.0/24 · 12 hosts · 3 findings" |
| Findings section title | "Findings" |
| Findings columns | "Finding · Host · Port · CVE · Severity" |
| No findings | "No findings. Every host in this scan came back clean." |
| Finding panel — labels | "What it is" / "What to do" / "Evidence" / "References" |
| Finding panel — CVSS | "CVSS 9.8" |
| Hosts section title | "Hosts" |
| Hosts columns | "Host · IP · MAC · Vendor · Open ports" |
| Unfinished | "This scan is still running." · "Findings appear here when it finishes." |
| Failed | "This scan didn't finish." · "The Pi reported: `<error_code>`." · [Try another scan] → AGENTS (admin only) |
| Failed, no `command_id` | "This scan didn't finish. No reason was recorded." |
| Error | "Couldn't load this scan." · [Retry] |
| 404 | "That scan doesn't exist." · [Back to scans] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SCAN — YESTERDAY 21:40                                                     |
|   quick mode · 192.168.0.0/24 · 12 hosts · 3 findings           (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   FINDINGS                                                                   |
|   FINDING                      HOST          PORT   CVE            SEVERITY  |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   PHP CGI argument injection   synology-nas   443   CVE-2024-4577  ▓ CRITICAL|
|   +----------------------------------------------------------------+        |
|   |  WHAT IT IS    <description>                                    |  ← open|
|   |  WHAT TO DO    <recommendation>                                 |        |
|   |  EVIDENCE      <evidence>                (mono)                 |        |
|   |  REFERENCES    <links>                        CVSS 9.8          |        |
|   +----------------------------------------------------------------+        |
|   Outdated OpenSSH             pi-lab          22   CVE-2023-…     ▓ HIGH    |
|   Telnet port open             printer-hp      23   —              ▓ LOW     |
|                                                                              |
|   HOSTS                                                                      |
|   HOST          IP             MAC                VENDOR      OPEN PORTS     |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   synology-nas  192.168.0.42   00:11:32:AA:BB:CC  Synology    4              |
|   pi-lab        192.168.0.17   DC:A6:32:11:22:33  Raspberry   2              |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. ~~**C9** — `DevicePayload` (the `devices` array) carries **no `host_id`**, so a host row here
   cannot link to HOST DETAIL.~~ **✅ RESOLVED 2026-08-02 (DMI-85) — the array is `hosts:
   ScanHostView[]` and `host_id` is required on it.** A host row can link to `/hosts/:hostId`;
   the affordance is available whenever this screen is built.
2. ~~**C10** — `error_code` is a *code*, not a sentence. It needs a copy mapping
   (code → plain-language reason) before the failed state has real words.~~ **✅ RESOLVED
   2026-08-13 (DMI-75)** — `frontend/src/lib/scanFailureReasons.ts` is the mapping. This screen
   still needs to import it (DMI-88).

---

### HOST INVENTORY

**Route:** `/hosts` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — the machines on the network: what is out there, and does any of it need attention.
This answers "what do I own", which is the second question every operator asks after "is anything
wrong".

**Data:**
- `GET /api/v1/hosts?page&per_page=20&sort_by=last_seen_at&sort_order=desc` → `HostListResponse`
  (`data: HostSummary[]`, `total`, `page`).
- `HostSummary`: `host_id`, `ip`, `mac` (nullable), `hostname`, `vendor`, `first_seen_at`,
  `last_seen_at`, `open_ports_count`, `highest_severity` (nullable).

**Search is cut from v1** ([`IDEAS.md`](IDEAS.md) → Hosts). The contract does define a free-text `q`
parameter on this endpoint, but v1 does not send it and the backend does not implement it — one
subnet does not produce a list you cannot read (§12). Sorting is server-driven; the contract allows
`last_seen_at | hostname | vendor | ip`.

**Hosts are cumulative, not per-scan** — this is the inventory of everything ever discovered, which
is why `last_seen_at` is the default sort and why a machine that has gone away still appears.

**`mac` can be null** — a host discovered across a router has no ARP entry, so there is no MAC to
show. The column renders "—" rather than being hidden; the machine is real, one identifier is not
observable from here.

**Three states:**
- **Regular:** one row per host, whole row navigates to `/hosts/:hostId`.
- **Blank:** no scan has ever run, so nothing has been discovered. Same first-run CTA as blank Home.
- **Error:** page-level copy + [Retry].

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Hosts" |
| Subtitle | "Every device Dmitri has found on your network." |
| Columns | "Host · IP · MAC · Vendor · Open ports · Highest severity · Last seen" |
| Hostname missing | "(unnamed)" |
| MAC — null | "—" |
| Highest severity — null | "—" |
| Blank — heading | "No hosts yet." |
| Blank — body | "Once a scan runs, every device Dmitri finds on your network shows up here." |
| Blank — CTA (admin only) | "Run first scan" |
| Blank — viewer line | "Ask your admin to run the first scan." |
| Error | "Couldn't load the hosts." · [Retry] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   HOSTS                                                                      |
|   Every device Dmitri has found on your network.                (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   HOST          IP            MAC               VENDOR     PORTS  SEV  SEEN  |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   synology-nas  192.168.0.42  00:11:32:AA:BB:CC Synology       4  ▓CRIT 2m   |
|   pi-lab        192.168.0.17  DC:A6:32:11:22:33 Raspberry      2  ▓HIGH 2m   |
|   printer-hp    192.168.0.31  3C:D9:2B:44:55:66 HP             3  ▓LOW  2m   |
|   (unnamed)     192.168.0.88  A4:83:E7:77:88:99 Apple          1  —     Jul 9|
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   Showing 1–20 of 12                          [Previous]  [Next]             |
+------------------------------------------------------------------------------+
```

**Open questions:** none. (A "new device" badge needs no contract work — **C6** is resolved and
`first_seen_at` is a required property on `HostSummary` as well as `HostDetailResponse`.)

---

### HOST DETAIL

**Route:** `/hosts/:hostId` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B3

**Epicenter** — what this machine exposes: its open ports. Identity is a header; history is a
footnote; the attack surface is the page.

**Data:**
- `GET /api/v1/hosts/{host_id}` → `HostDetailResponse`: `ip`, `mac` (nullable — see HOST
  INVENTORY), `hostname`, `vendor`, `first_seen_at`, `last_seen_at`, `open_ports_count`,
  `highest_severity`, `ports: Port[]`, `scan_history: HostScanHistoryEntry[]`.
- `Port`: `port`, `protocol`, `state`, `service`, `version` (nullable).
- `HostScanHistoryEntry`: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`,
  `highest_severity`.
- **Findings are a second call:** `HostDetailResponse` carries **no findings array**, but
  `highest_severity` is shown — so the page must explain that severity. Use
  `GET /api/v1/findings?host_id={host_id}` → `FindingRecord[]`, rendered with the same row +
  in-place panel as SCAN DETAIL.

**Three states:**
- **Regular:** identity header, findings (if any), ports table, scan history. Scan-history rows
  navigate to `/scans/:scanId` (whole row, rule 4).
- **Blank:** not reachable — a host exists only because a scan found it. A host with **zero open
  ports** is the nearest thing, and it gets positive framing rather than an empty table.
- **Error:** page-level copy + [Retry]; 404 its own line.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "synology-nas" (or the IP when `hostname` is empty) |
| Header line | "192.168.0.42 · 00:11:32:AA:BB:CC · Synology" |
| Seen line | "First seen Jul 3 · last seen 2 min ago" |
| Findings section title | "Findings" |
| No findings | "No findings on this host." |
| Ports section title | "Open ports" |
| Ports columns | "Port · Protocol · Service · Version" |
| No open ports | "No open ports. This host isn't exposing anything." |
| Version missing | "—" |
| History section title | "Seen in these scans" |
| History columns | "When · Mode · Open ports · Highest severity" |
| Error | "Couldn't load this host." · [Retry] |
| 404 | "That host doesn't exist." · [Back to hosts] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SYNOLOGY-NAS                                                               |
|   192.168.0.42 · 00:11:32:AA:BB:CC · Synology                   (muted)      |
|   First seen Jul 3 · last seen 2 min ago                        (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   FINDINGS                                                                   |
|   PHP CGI argument injection      443    CVE-2024-4577      ▓ CRITICAL       |
|      (row expands in place — same panel as SCAN DETAIL)                      |
|                                                                              |
|   OPEN PORTS                                                                 |
|   PORT   PROTOCOL   SERVICE     VERSION                                      |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   22     tcp        ssh         OpenSSH 8.4p1                                |
|   443    tcp        https       nginx 1.18.0                                 |
|   5000   tcp        http        Synology DSM                                 |
|                                                                              |
|   SEEN IN THESE SCANS                                                        |
|   WHEN              MODE    OPEN PORTS   HIGHEST                             |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   yesterday 21:40   quick            4   ▓ CRITICAL                          |
|   Jul 11  21:40     quick            4   ▓ CRITICAL                          |
|   Jul 10  21:40     quick            3   —                                   |
+------------------------------------------------------------------------------+
```

**Open questions:**
1. ~~Does `GET /findings?device_id=…` accept the **`host_id`** UUID?~~ **✅ RESOLVED (C11) — the
   filter is `?host_id=`.** `read_findings()` takes `host_id: UUID | None`, and `FindingRecord`
   carries `host_id`. The read model is `hosts` end to end; only the Pi ingest payload keeps
   `devices[]` (ADR-011 §5). Host detail can show findings.

---

### AGENTS

**Route:** `/agents` · **Shell:** inside · **Roles:** admin, viewer (read-only) ·
**Flow:** B4, and the first-run step of B2

**Epicenter** — *can I scan right now?* The agent's live state and the trigger, together
([`REFERENCE.md`](REFERENCE.md) §2). Everything else on this page is caption.

**Data:**
- `GET /api/v1/agents` → the row. **✅ C1 shipped (DMI-78).** One agent in the MVP; the list is how
  the frontend discovers `agent_id`.
- `GET /api/v1/agents/{agent_id}` → `AgentDetail`: `display_name`, `online`, `last_seen_at`,
  `active_command_id`, `available_subnets`, `target_subnet`. **Read on mount** — this is what lets a
  running scan's pill survive navigation and reload (B4). **✅ C2 shipped (DMI-78).**
- `PATCH /api/v1/agents/{agent_id}` → `AgentDetail`, admin only. Body `{ target_subnet }`, one of
  the CIDRs `available_subnets` reported. The response is the full detail, so the screen needs no
  refetch. `409 device_offline` if the Pi is reporting nothing; `422 subnet_not_reported` if the
  chosen network is not one it reported.
- `POST /api/v1/agents/{agent_id}/commands` → `CommandSummary`. Body is
  `{ scan_mode: "quick", subnet: <agent.target_subnet> }` — **both are supplied by the system, never
  typed by the operator** (B4).
- `GET /api/v1/commands/{command_id}` → `CommandDetail`: `status`, `error_code`, `scan_id`. Poll
  **every 5s** while the status is pending.

`CommandStatus` is `queued | delivered | running | uploading | done | failed | expired` — **seven**
states, and the pill must render all of them. `expired` is a *backend*-set state (ADR-011): the Pi
**never took the command** — delivery gave up, and the operator already saw the `503` toast. It is not
the same event as `failed` and does not get the same words. **The split is `delivered_at` (C12):** a Pi
that dies *mid-scan* took the job, so it reports **`failed`**, not `expired`.

**Three states** — this screen has more than three; each is designed, none inherited:
- **Blank — no Pi at all.** No agent exists. **The admin cannot fix this themselves**: Pi
  provisioning is the installer's job, never the org admin's ([`AUTH.md`](AUTH.md) — B2B model). So
  the blank state must not offer a CTA it cannot honor; it explains and points at the vendor. This
  is the one blank slate in the product with **no action**, on purpose.
- **Needs a network (admin).** `target_subnet` is null. The Pi is online but **cannot be scanned**
  until a human says which network is the target — it is dual-homed and sees two (B4). `[Scan now]`
  is not shown; the choice is. This is also B2's missing first-run step.
- **Ready (admin).** Online, network chosen → `[Scan now]`.
- **Scanning.** A `StatusPill` on the row walks the lifecycle. The whole row stays readable; the
  pill is the only thing that moves.
- **Done.** Pill becomes `[View scan]` → SCAN DETAIL. Caches for scans/agents/findings invalidate.
- **Failed.** The Pi took the command and it broke — a scan error, a failed upload, or the Pi going
  dark **mid-scan**. Error pill carrying `error_code` + `[Retry]`.
- **Expired.** The Pi **never took the command** — there was no open socket, or the one send
  attempt threw. Distinct from
  `failed` — the operator's next step is *check the box*, not *try again* — so it points at the Pi and
  offers `[Retry]` second.
- **Offline.** `online: false`. `[Scan now]` **stays visible and enabled** — see Open questions.
- **Viewer.** Sees the row, the status and the network. No `[Scan now]`, no network chooser —
  omitted, not disabled (rule 3).
- **Error.** Page-level copy + `[Retry]`.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Agents" |
| Subtitle | "The Dmitri box on your network." |
| Row — online | "Online · last seen 2 min ago" |
| Row — offline | "Offline · last seen Tuesday 14:10" |
| Row — network | "Scanning: Ethernet · 192.168.0.0/24" · [Change] |
| Trigger | "Scan now" |
| Needs-network heading | "Which network should Dmitri scan?" |
| Needs-network body | "This box is connected to more than one network. Pick the one you want scanned — usually the office network, not the internet connection." |
| Needs-network options | "Ethernet · 192.168.0.0/24" / "Wi-Fi · 10.12.0.0/16 (internet connection)" — **derived** from reported `interface` by prefix (`eth*`/`en*` → Ethernet, `wl*` → Wi-Fi; unfamiliar names render raw) |
| Needs-network confirm | "Set this Network" |
| Pill — queued | "Queued" |
| Pill — delivered | "Sent to the Pi" |
| Pill — running | "Scanning…" |
| Pill — uploading | "Uploading results…" |
| Pill — done | "View scan" |
| Pill — failed | "Scan failed" pill + operator sentence from `scanFailureReason(error_code)` (not the raw code) · [Retry] |
| Pill — expired | "Not picked up" pill + "The Pi never picked up the scan. Check that it's powered on and connected to the network." · [Retry] |
| Hint under trigger | "A scan usually takes about 10 minutes." |
| Toast — 503 `device_offline` | "Pi seems to be offline." |
| Toast — 409 `device_busy` | "That Pi is already scanning. Showing the scan in progress." — only when the Pi's run is actually adopted |
| Toast — any other refused trigger | "Couldn't start the scan." — including a busy Pi that reports no run to adopt |
| Blank — heading | "No Pi connected yet." |
| Blank — body | "Dmitri scans your network from a small box installed on site. Your installer sets it up — once it's online, it shows up here and you can run your first scan." |
| Blank — viewer/admin line | "Contact whoever installed Dmitri if you were expecting to see one." |
| Error | "Couldn't load the agents." · [Retry] |

**Layout:**

Ready — admin:
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   AGENTS                                                                     |
|   The Dmitri box on your network.                               (muted)      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   +----------------------------------------------------------------+        |
|   |  DMITRI-NSPI-01                                                 |        |
|   |  Online · last seen 2 min ago                                   |        |
|   |  Scanning: Ethernet · 192.168.0.0/24            [Change]        |        |
|   |                                                                 |        |
|   |                                        +------------------+     |        |
|   |                                        | ▓   Scan now     |     |        |
|   |                                        +------------------+     |        |
|   |                       A scan usually takes about 10 minutes.    |        |
|   +----------------------------------------------------------------+        |
+------------------------------------------------------------------------------+
```

Needs a network — admin, first run:
```text
|   +----------------------------------------------------------------+        |
|   |  DMITRI-NSPI-01          Online · last seen 12 s ago            |        |
|   |  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -    |        |
|   |  WHICH NETWORK SHOULD DMITRI SCAN?                              |        |
|   |  This box is connected to more than one network. Pick the one   |        |
|   |  you want scanned — usually the office network, not the         |        |
|   |  internet connection.                                           |        |
|   |                                                                 |        |
|   |    ( ) Ethernet · 192.168.0.0/24                                |        |
|   |    ( ) Wi-Fi    · 10.12.0.0/16   (internet connection)          |        |
|   |                                                                 |        |
|   |                                   [ Set this Network ]         |        |
|   +----------------------------------------------------------------+        |
```

Scanning:
```text
|   |  DMITRI-NSPI-01          Online · last seen 4 s ago             |        |
|   |  Scanning: Ethernet · 192.168.0.0/24                            |        |
|   |                                         [ ▓ Scanning… ]         |        |
```

**Open questions:**
1. ~~**Offline: keep `[Scan now]` or hide it?**~~ **✅ RESOLVED — keep visible and enabled** (shipped DMI-89). `online` is
   derived from the WebSocket registry and can be momentarily stale. The backend makes **one**
   delivery attempt and does not retry ([`BACKEND.md` B6](../roadmap/BACKEND.md#b6--pi-command-channel-)),
   which makes keeping the button live *more* important, not less: **the operator clicking again
   is the only retry the system has.** Hiding the button on a flag that might be wrong denies a
   scan that would have worked; the `503` toast is the designed, honest failure. **This is not rule 3** — that rule is about what a *role*
   may do, not what is momentarily unavailable.
2. ~~**C12 — does a dead Pi produce `failed` or `expired`?**~~ **✅ RESOLVED 2026-07-13 — the split is
   `delivered_at`.** Never delivered → `expired`; delivered then broke → `failed`. The screen knows
   which it gets: **a Pi that dies mid-scan is `failed`** (it took the job), and `expired` is only
   *never picked up*. Pill copy updated accordingly.
3. Pill vs stepper for the five lifecycle states — pill chosen; stepper parked
   ([`IDEAS.md`](IDEAS.md) → Agents).
4. ~~Blocked on **C1** and **C2**.~~ **✅ Unblocked and built** — DMI-78 (contract) + DMI-89 (SPA).

---

### USERS & INVITES

**Route:** `/users` · **Shell:** inside · **Roles:** admin only · **Flow:** B2

**This screen ships as half a screen, on purpose (§3).** Of the four things B2 breadboarded here —
list users, list pending invites, change a role, revoke an invite — **exactly one has an endpoint**:
`POST /invites`. The other three are **C4**, and no amount of frontend work conjures them.

So v1 does not ship three dead sections and a table that says "coming soon". It ships **the one
thing that works, finished**: inviting a person. The full screen is specced below it so C4 has a
target to land against.

**The route and the nav item stay `Users` throughout.** *Users* names the domain, not today's single
action, and the page grows new user-related surfaces inside it rather than being renamed around them
(§App shell). In v1 the page is titled *Users* and its whole content is the invite form; when C4
lands, the user table appears **above** the invite action and nothing in the shell moves.

**Epicenter** — the invite form, and the link it produces. The link *is* the deliverable; the form
is how you ask for it.

**A viewer reaching `/users` directly gets the not-found page. ✅ Decided 2026-08-18.** Two
primitives, because hiding a nav item and refusing a route are different jobs and DMI-90 requires
both to be absent: `AdminOnly` wraps children and renders `null` for viewers (it hides the nav
item), and `RequireAdmin` is an outlet guard mirroring `RequireSession` that renders the existing
`NotFound` page. Not-found rather than a redirect or an access-denied message, for the same reason
the backend answers `404` and never `403` for another org's resources — an unauthorised person
should not be able to map what exists. Neither primitive takes a `fallback` or `disabled` prop, so
there is no API through which a greyed-out admin control could be produced (rule 3).

**Data:**
- `POST /api/v1/invites` — body `{ email, role: "admin" | "viewer" }` → **`201`
  `InviteCreatedResponse`: `{ invite_token, expires_at }`.**
- **The backend emails the invite, *and* the screen shows the link. ✅ Decided 2026-07-13** —
  transactional email is in scope (provider TBD, [C17](#users--invites)); the backend sends
  `https://<app>/invite?token=<invite_token>` to the invitee.
- **🔓 C4** — listing users, listing pending invites, changing a role, revoking an invite and
  **removing a member** have **no endpoints**. When it lands the screen consumes `GET /api/v1/users`
  and `GET /api/v1/invites` as **two separate calls, merged here into one table** — they have
  different lifecycles and different row actions, so they stay separate resources.
- **Removal ✅ decided 2026-08-08** ([`ADR-017`](../adr/ADR-017-account-removal.md)) —
  `DELETE /api/v1/users/{user_id}`, admin-only, **hard delete**. It **refuses to target the caller**
  (`/users/me` is the self-service path, and it lives in SETTINGS, not here), which is why an
  admin's own row carries no Remove action. Changing a role likewise refuses to target the caller:
  **self-demotion is not possible**. Between them, an org can never reach zero admins.
- **There is no `status` field on the wire.** `OrgMember` carries `user_id`, `email`, `role` and
  `last_seen_at` only. The Status column is **derived from which endpoint the row came from** —
  members read "Active", invites read "Invited — expires in 2d". Nobody should go looking for a
  field that does not exist.
- **Mutations refetch; they do not patch the cache by hand.** Role change, remove and revoke each
  invalidate the two list queries on success, which is what "updates without a full reload" means
  here. No optimistic update: all three are admin writes on a small table where a wrong guess
  briefly shows a false membership fact.
- **`last_seen_at`** is served on the user row — when the person was last active, including silent
  refresh, rendered as relative time. Pending invites have none and render `—`.
- **🔓 C18** — `POST /invites` documents **only a `201`**. Inviting an email that already has an
  account, or that already has a live invite, has **undefined behavior** — and re-inviting someone
  is the single most likely thing an admin does twice.

**Email is the convenience; the link is the guarantee.** The screen shows the copyable URL *even
though* the invite was emailed, and that is not redundancy:

- **A security product's one-time login link is structurally indistinguishable from phishing.** It
  will sometimes land in spam no matter how clean the DNS is, and the admin needs a recovery that
  doesn't depend on the thing that just failed.
- Plenty of admins would rather send it over Slack or Teams anyway.
- It keeps the screen working while deliverability is still being tuned.

**The link is still shown once, and the screen still says so.** With no `GET /invites` (C4), a token
that scrolls off the page is **gone** — email softens this (the invitee has their own copy) but does
not fix it: the *admin* cannot retrieve the link again, and their only recovery is issuing a second
invite. So the warning stays, worded as a nudge rather than an alarm (§7).

**Three states:**
- **Regular:** the invite form. Email, role, `[Send invite]`.
- **Blank:** **not applicable in v1** — a form is its own content. (When C4 lands, the *user table*
  gets a blank state, and it is never truly empty: the admin reading it is in it.)
- **Created (the state that matters):** the form is replaced by a confirmation that the invite was
  **emailed**, plus the link, a `[Copy link]` button, when it dies, and the once-only nudge.
  `[Invite someone else]` returns to the form.
- **Error:** inline under the field. A duplicate invite (C18) has no defined status, so the copy
  below is provisional.

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Users" |
| Section title (v1) | "Invite a user" |
| Subtitle (v1) | "Create a link that lets someone join your organization." |
| Fields | "Email" / "Role" |
| Role — viewer | "Viewer — can see scans, hosts and findings." |
| Role — admin | "Admin — can also run scans and invite people." |
| Button | "Create invite link" · in flight: "Creating…" |
| Created — heading | "Invite sent." |
| Created — body | "We emailed an invite to **name@example.com**. It works once, and expires **in 48 hours**." |
| Created — link label | "Or send them this link yourself:" |
| Created — nudge | "This is the only time you'll see this link. If they never get the email, copy it now." |
| Created — copy button | "Copy link" · after click: "Copied" |
| Created — again | "Invite someone else" |
| Created — dismiss (post-C4) | "Done" — closes the dialog and refetches the table |
| Error — bad email | "That doesn't look like an email address." |
| Error — already a member (`400 email_already_member`) | "That person is already in your organization." |
| Error — already invited (`409 invite_already_pending`) | "That address already has an invite waiting. Revoke it first if you need to send a new one." |
| Error — server | "Couldn't create the invite." · [Try again] |
| Table columns (post-C4) | "Person · Role · Status · Last seen" |
| Active row (post-C4) | "Active" · "2 hours ago" · [Remove] |
| Active row, no last-seen value | "Not recorded yet" — **not** "Never", and not the pending row's `—` |
| Pending row (post-C4) | "Invited — expires in 2 days" · "—" · [Revoke] |
| Own row (post-C4) | No "you" marker — **no Remove, no role control.** The absent controls are what identify the row; a label repeating it was noise in the Person column. Leaving is done in Settings |
| Blank table (post-C4) | "You're the only person here." |
| Table — load error (post-C4) | "Couldn't load your organisation." · [Try again] |
| Role control (post-C4) | a dropdown on **other members'** rows — "Viewer" / "Admin". Your own row and **pending invite rows** render the role as plain text, no control |
| Role change — confirm heading | "Make **name@example.com** an admin?" · demoting: "Make **name@example.com** a viewer?" |
| Role change — confirm body (to admin) | "They'll be able to run scans and invite people." |
| Role change — confirm body (to viewer) | "They'll only be able to see scans, hosts and findings." |
| Role change — confirm button | "Change role" · in flight: "Changing…" |
| Role change — error | "Couldn't change that role." · [Try again] |
| Remove — confirm heading | "Remove name@example.com?" |
| Remove — confirm body | "They lose access immediately and their account is deleted. This can't be undone. You can invite them again later." |
| Remove — confirm prompt | "Type their email address to confirm." |
| Remove — confirm button | "Remove" · in flight: "Removing…" |
| Remove — error | "Couldn't remove that person." · [Try again] |
| Revoke — confirm heading | "Revoke the invite to **new@example.com**?" |
| Revoke — confirm body | "Their link stops working immediately. You can invite them again later." |
| Revoke — confirm button | "Revoke" · in flight: "Revoking…" |
| Revoke — error | "Couldn't revoke that invite." · [Try again] |
| Role change — success toast | "**sam@acme.com** is now an admin." · demoting: "**sam@acme.com** is now a viewer." |
| Remove — success toast | "**sam@acme.com** was removed." |
| Revoke — success toast | "The invite to **new@acme.com** was revoked." |

**Revoke confirms with a single click, like a role change — not by typing. ✅ Decided 2026-08-18.**
DMI-90 asks for a confirmation on both role change and revoke, and revoking sits on the reversible
side of the line drawn below: the invitee has no account yet, nothing is deleted but an unused
token, and the admin can issue a new invite immediately. Typing stays reserved for removal.

**The three row actions confirm with a toast; the invite does not. ✅ Decided 2026-08-18.** Role
change, remove and revoke each take effect in a table the admin is already looking at, and the row
alone is a weak signal — a role cell changing from Viewer to Admin, or a row quietly vanishing, is
easy to miss and indistinguishable from a mis-click. Each therefore raises a toast naming the
person and what happened. **A successful invite raises none**: its modal already *is* the
confirmation, carries the link, and must be dismissed deliberately, so a toast on top would repeat
it. **`Toast` itself is built here, not split out (✅ decided 2026-08-18):** this screen is its
first call site and brings three real uses with it, so the component lands with consumers rather
than ahead of them (`.claude/CLAUDE.md` §2). Scan now's errors join as a fourth when Agents
unblocks.

**Two calls, one table — ordering and failure. ✅ Decided 2026-08-18.** Members render first, in the
order `GET /users` already returns them (`last_seen_at` descending, nulls last), then pending
invites below, soonest-to-expire first. The two groups are not interleaved: a pending row has no
`last_seen_at` to sort by, so mixing them would order rows on a value half of them lack. **If
either call fails, the whole table shows its error state** — "Couldn't load your organisation."
with `[Try again]`, and no rows at all. A member list silently missing its pending invites is not
an incomplete answer but a wrong one: this table means *everyone with access*, and an admin
auditing it would read the short version as complete. Rule 1 treats it as one unit; the same goes
for its loading skeleton and its blank state.

**The table's two `409`s are unreachable from this screen, and get no copy. ✅ Decided 2026-08-18.**
`PATCH /users/{user_id}` documents `self_target` and `last_admin`. Neither can be produced here.
`self_target` needs the admin to target their own row, and their own row draws no role control;
`last_admin` needs the target to be the org's *only* admin while not being the caller, which cannot
happen, because the caller is an admin in that same org and so the count is at least two — the
backend checks self-targeting first
([`users.py`](../../backend/src/api/routers/users.py) `update_user_role_route`). They stay as
backend guards against direct API calls. Each row action therefore carries **one** failure line and
a `[Try again]`, and no branch is written for a state this UI cannot reach (`.claude/CLAUDE.md` §2).

**Two row actions, two weights of confirmation. ✅ Decided 2026-08-18.** Removal makes the admin
type the target's address ([`ADR-017`](../adr/ADR-017-account-removal.md) §5); a role change asks a
plain "Make **sam@acme.com** an admin?" with a single confirm button. The difference is
proportionality, and it is the same reasoning ADR-017 used to justify typing in the first place:
removal is irreversible and ends a live session, while a role set wrong is corrected in two clicks
from the same dropdown. Making both feel identical would either make removal feel routine or make
role changes feel dangerous. **Typing is reserved for the actions that cannot be undone.**

**"Added" was dropped, deliberately.** The earlier column deck carried *Person · Role · Status ·
Added*. `last_seen_at` replaces it rather than joining it: the one case where Added earns its place
— telling a brand-new member apart from a long-dormant one, both reading "Never" — cannot arise,
because accepting an invite issues a session immediately, so a user's first activity timestamp *is*
their join date. For a pending row, "expires in 2 days" already carries the only time fact worth
having. Four columns, not five.

**One null case does arise, and it is not the one above. ✅ Decided 2026-08-18.** The migration that
added the column
([`20260810_16`](../../backend/alembic/versions/20260810_16_user_activity_and_invite_revoke.py))
adds it nullable **with no backfill**, so every account that existed before 2026-08-10 reads `NULL`
until that person next signs in or their session refreshes. Those rows say **"Not recorded yet"** —
not "Never", which would assert a falsehood about someone who may have logged in this morning, and
not the pending row's `—`, which is the cell doing the work of telling a member from an invite. The
state is self-healing and disappears within days of normal use; `GET /users` already sorts these
rows last (`nulls_last`), so they sit at the bottom rather than at the top of a "most recently
active" reading.

**Layout — v1 (the buildable screen):**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   USERS                                                                      |
|   ------------------------------------------------------------------        |
|                                                                              |
|   INVITE A USER                                                              |
|   Create a link that lets someone join your organization.       (muted)      |
|                                                                              |
|   Email                                                                      |
|   [__________________________________________]                               |
|                                                                              |
|   Role                                                                       |
|     (•) Viewer — can see scans, hosts and findings.                          |
|     ( ) Admin  — can also run scans and invite people.                       |
|                                                                              |
|   [ ▓  Create invite link  ]                                                 |
+------------------------------------------------------------------------------+
```

Created — the form is replaced by the confirmation:
```text
|   INVITE SENT.                                                               |
|                                                                              |
|   We emailed an invite to name@example.com. It works once, and expires       |
|   in 48 hours.                                                  (muted)      |
|                                                                              |
|   Or send them this link yourself:                                           |
|   +----------------------------------------------------------------+        |
|   | https://app.dmitri.io/invite?token=8f3c9a1e-…      [ Copy link ]|        |
|   +----------------------------------------------------------------+        |
|   This is the only time you'll see this link. If they never get the          |
|   email, copy it now.                                           (muted)      |
|                                                                              |
|   Invite someone else                                                        |
```

**Post-C4, the invite form moves into a modal. ✅ Decided 2026-08-18.** In v1 the form *was* the
page, so it rendered inline. Once the member table is the page's content, the form becomes an
action, and `[Invite a user]` opens a dialog: the email + role form, replaced in place by the
"Invite sent" confirmation carrying the link and `[Copy link]`. The reason is the once-only nudge
already in this spec — the link is shown exactly once, and a modal is the only layout that cannot
scroll out of view or be missed behind a long table. Dismissing it refetches the table so the new
pending row is present. `Dialog` already exists in the app via `ConfirmByTyping`, so this is a new
call site, not new machinery. The created state keeps **both** `[Done]` (closes and refetches) and
"Invite someone else" (resets the dialog to an empty form) — inviting two people in a row is a real
sequence, and losing it would cost a full reopen each time.

**Layout — post-C4 (the table lands above the invite action; the shell does not move):**
```text
|   USERS                                                                      |
|   ------------------------------------------------------------------        |
|   PERSON                  ROLE     STATUS                  LAST SEEN         |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   anna@acme.com (you)     Admin     Active                 2 hours ago       |
|   sam@acme.com          [Viewer v]  Active                 3 days ago [Remove]|
|   new@acme.com            Viewer    Invited — expires 2d   —          [Revoke]|
|                                                                              |
|   Dropdown only on other members' rows. Your own row and pending             |
|   invite rows render the role as plain text.                                 |
|                                                                              |
|                                            [ ▓  Invite a user  ]             |
```

**Open questions:**
1. ~~**C4** — no member/invite administration endpoints.~~ **✅ Resolved 2026-08-11** — the
   published contract and backend now provide the separate resources; the SPA screen remains.
2. ~~**C17** — no email delivery exists anywhere in the product.~~ **✅ Resolved in code** —
   Resend sends invite and reset links; production delivery still needs a verified sending domain
   with SPF/DKIM/DMARC.
3. ~~**C18** — re-inviting existing users or pending invitees is undefined.~~ **✅ Resolved** —
   an existing member returns `400 email_already_member`; a live pending invite returns
   `409 invite_already_pending`.
4. ~~Rename the nav item to "Invite" for v1?~~ **✅ Decided 2026-07-13 — no.** It stays **Users**,
   at `/users`, and grows more user-related surfaces inside it. Nav names domains, not the one
   action that happens to be buildable this month.

---

### SETTINGS

**Route:** `/settings` · **Shell:** inside · **Roles:** admin, viewer · **Flow:** B5

**Epicenter** — **who you are signed in as, and what you can do about it.** The screen opens on
your email and your role, read without interaction, and then offers the two things you can do to
that account: change its password, or leave the organization. *Who am I* comes before *change my
password*, always — a screen that opens with the cursor in a current-password field and never
names the account has asked for a secret before saying whose it is. *Amended 2026-08-18
(DMI-107); it previously read "change your own password".*

Changing the password is still the most common reason anyone comes here, and it is still the
**only** change-password screen in the product — there is no forced rotation and no 403-triggered
flow ([`ADR-016`](../adr/ADR-016-password-policy.md) — forced periodic rotation is rejected as
NIST-misaligned). It is now reached through a `[Change password]` trigger that opens a modal, so
the page's regular state is four short sections with air between them rather than three password
fields and a wall of labels.

**The details block is read-only** — email and role, no display name and no `[Save]`. Open
question **C3** stays open: there is no self-profile update operation, and an input the user can
type into but not submit is worse than text.

**Leaving the organization also lives here** ([`ADR-017`](../adr/ADR-017-account-removal.md), added
2026-08-08), for **both roles**. A viewer never sees the USERS screen, so this is the only place
they can remove their own account — and an account nobody can leave is the wrong default for a
product holding this data. It sits at the bottom, visually separated, and is the last thing on the
page: it is not what anyone came here to do.

The copy does **not** name the organization. A signed-in member cannot read it — `UserProfileResponse` carries `user_id`, `email` and `role` only, and `org_name` exists solely on the
pre-session invite lookup. The wording is org-neutral rather than adding a request to discover a name
the heading has already supplied (spec 033).

**Activity disclosure is built for both roles** (spec 030). The `Activity` heading sits on **its
own line**, and a disclosure row — a caret and the accent-coloured label `What's recorded?` —
sits beneath it; activating that row expands a persistent note and rotates the caret. It was
originally specced *beside* the heading, which made a section title and a control read as one
label and left the control with no affordance at all; that arrangement is withdrawn. The row is
the shared button primitive in its `link` variant and carries all five interactive states
(§Interaction states) — it is the worked example that section is written for. *Corrected
2026-08-18 (DMI-107).* It names last use and last sign-in, says org admins can see the activity
time, and states that no viewed/action detail is recorded. It is information, not a toggle, and
must work by keyboard and assistive technology.

**The scan target network is not here.** It is a property of the Pi, not of the user — one box
pointed at one network, identical for every admin in the org. It lives on AGENTS (B4).

**Data:**
- `POST /api/v1/auth/change-password` → **`204`**. Body: `{ current_password, new_password }`;
  `new_password` has `minLength: 12` in the contract. Errors: **`400`** for both a wrong current
  password (`wrong_current_password`) and a policy rejection (`password_policy_violation`); `401`
  on this route means the session itself failed, not the field. This split is deliberate — the
  SPA's refresh interceptor ([`ADR-008`](../adr/ADR-008-frontend-stack.md) §Auth Client) acts on
  every `401`, so returning one for a mistyped field would refresh-and-retry, then sign the user
  out over a typo. *Settled by contract ask C13.*
- Profile (display name, email) — **🔓 C3 update half.** `GET /users/me` exists, but there is no
  self-profile update operation and the model still has no display name.
- `DELETE /api/v1/users/me` → **`204`**. No body. Any role. **Hard delete** — the account and its
  sessions are gone, not disabled. One error worth designing for: **`409 last_admin`** when the
  caller is their org's only admin, because an org with no admins can invite nobody and manage
  nothing. The route does **not** clear the refresh cookie and does not need to: deleting the user
  cascades their refresh tokens, so the cookie is already inert.
- Activity disclosure — static product copy over the activity facts recorded by the backend; no
  request and no opt-out control.

**Password policy** ([`AUTH.md`](AUTH.md) → Passwords) — stated up front, not discovered by failing:
minimum 12 characters; no common or breached passwords; no obvious patterns (repeated characters,
simple suffixes); no names or birth dates.

**Three states:**
- **Regular:** the form. Both sections stacked in the 720px prose column.
- **Blank:** **not applicable, deliberately.** A settings form is never empty — it always has its
  own fields. Recording this so nobody invents an empty state to satisfy rule 1.
- **Error:** field-level inline errors (wrong current password, policy rejection). No toast for form
  validation — the error belongs next to the field that caused it.
- **Success:** inline confirmation, not a redirect. The user stays where they are.
- **Confirming removal:** a modal over the page. It states what is lost, and the confirm button is
  greyed out and disabled until the user has typed **their own email address**, enabling the
  instant it matches — deletion is irreversible and kills a live session, so a single click is not
  proportionate to it ([`ADR-017`](../adr/ADR-017-account-removal.md) §5, amended 2026-08-17). Same
  component as the USERS screen's Remove; two call sites is the bar §Shared components sets.
- **Removed:** not a state of this screen. The session is gone, so the SPA drops its in-memory token
  and redirects to LOGIN, which carries the confirmation line (see LOGIN copy).

**Copy:**
| Element | Copy |
| --- | --- |
| Page title | "Settings" |
| Section — password | "Change your password" |
| Policy hint | "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere." |
| Fields | "Current password" / "New password" / "Confirm new password" |
| Button | "Change password" |
| Success | "Password changed." |
| Error — wrong current | "That's not your current password." |
| Error — policy | "That password isn't strong enough. Try a longer one that isn't based on a name or a date." |
| Error — mismatch (client-side) | "Those two passwords don't match." |
| Section — activity | "Activity" |
| Activity control | "What's recorded?" |
| Activity disclosure | "Your organization's admins can see when you last used Dmitri and when you last signed in. We record only these times — not what you viewed or did." |
| Section — profile | "Your details" |
| Profile fields | "Display name" / "Email" |
| Profile button | "Save" |
| Section — leaving | "Leave this organization" |
| Leaving — body | "Your account is deleted and you lose access to this organization's scans, hosts and findings straight away. This can't be undone — an admin would have to invite you again." |
| Leaving — trigger | "Delete my account" |
| Confirm — heading | "Delete your account?" |
| Confirm — prompt | "Type **you@example.com** to confirm." |
| Confirm — button | "Delete my account" · in flight: "Deleting…" |
| Confirm — cancel | "Cancel" |
| Error — last admin (`409`) | "You're the only admin. Make someone else an admin first, then you can leave." |
| Error — server | "Couldn't delete your account." · [Try again] |

**Layout:**
```text
+------------------------------------------------------------------------------+
| DMITRI    Home  Scans  Hosts  Agents  Users  Settings          [Log out]     |
+==============================================================================+
|                                                                              |
|   SETTINGS                                                                   |
|   ------------------------------------------------------------------        |
|                                                                              |
|   CHANGE YOUR PASSWORD                                                       |
|   At least 12 characters. Avoid names, dates, and passwords you've           |
|   used elsewhere.                                               (muted)      |
|                                                                              |
|   Current password       [____________________________]                      |
|   New password           [____________________________]                      |
|   Confirm new password   [____________________________]                      |
|                                                                              |
|                          [ Change password ]                                 |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|   ACTIVITY                         [What's recorded?]                          |
|   (expanded) Your organization's admins can see when you last used Dmitri    |
|   and when you last signed in. We record only these times — not what you     |
|   viewed or did.                                                (muted)      |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|                                                                              |
|                                                                              |
|   YOUR DETAILS                                        ⚠️ blocked — C3         |
|   Display name           [____________________________]                      |
|   Email                  [____________________________]                      |
|                          [ Save ]                                            |
|                                                                              |
|   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -          |
|                                                                              |
|   LEAVE THIS ORGANIZATION                                                    |
|   Your account is deleted and you lose access to this organization's         |
|   scans, hosts and findings straight away. This can't be undone — an         |
|   admin would have to invite you again.                         (muted)      |
|                                                                              |
|   [ Delete my account ]                                                      |
+------------------------------------------------------------------------------+
```

Confirming — a modal over the page; the confirm button is greyed out and disabled until the
address matches, shown here with parentheses in place of brackets (the convention `DESIGN.md` §2.2
uses for a greyed, non-clickable button; a live button keeps square brackets):
```text
+--------------------------------------------------+
|  DELETE YOUR ACCOUNT?                            |
|                                                  |
|  Your account is deleted and you lose access     |
|  straight away. This can't be undone.            |
|                                                  |
|  Type you@example.com to confirm.                |
|  [__________________________________]            |
|                                                  |
|            [ Cancel ]  ( Delete my account )     |
+--------------------------------------------------+
```

**Open questions:**
1. **C3** — no user resource. The profile section cannot be built.
2. Password strength meter — parked ([`IDEAS.md`](IDEAS.md) → Auth & admin). The policy hint is
   stated up front instead.
