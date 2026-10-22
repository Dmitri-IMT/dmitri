# UI Foundations

> **Binding. Source of truth for the UI look. Decided 2026-09-02 (DMI-131); implemented by
> DMI-132. History: [`FOUNDATIONS-DECISIONS.md`](FOUNDATIONS-DECISIONS.md).**
>
> [`docs/ui/mockups/dmi-131-mockups-v4.html`](mockups/dmi-131-mockups-v4.html) is the **visual
> exemplar** — build to it, and raise a question rather than deviate. Values only live here;
> reasoning lives in the decisions appendix and in
> [`DESIGN-SYSTEM-RESEARCH.md`](DESIGN-SYSTEM-RESEARCH.md).
>
> **Where this document disagrees with [`ADR-008`](../adr/ADR-008-frontend-stack.md) or
> [`SCREENS.md`](SCREENS.md), this document wins.** ADR-008 owns the stack; SCREENS.md owns the
> screens; this owns the look.

## Audience & principles

- The reader is a **non-technical business owner**, not an analyst and not an operator.
- The product **interprets**; it does not present raw data for triage.
- **Zone the density** — tight tables inside a generous shell, never a uniformly dense app.
- **One accent, used sparingly.** Colour is not the working language of this product.
- **Say it in a label**, not in a paragraph. One vocabulary word per concept.

## Theme

| Item | Value |
| --- | --- |
| Themes shipped | **Light and dark.** The user's choice persists locally and both themes use the same semantic colour tokens. |
| `dark:` variants | Use only when a semantic token cannot express the needed state. Theme values belong in `index.css`. |
| Viewport | **Desktop first, fluid within.** Target 1440px; preserve usable navigation and readable content from 1024px upward. |
| Horizontal scroll | The page body never scrolls sideways. Wide content scrolls inside its own `overflow-x: auto` container. |

## Type

**Inter Variable** (`@fontsource-variable/inter`) is the one family — `--font-sans`, applied on
`html`. **Geist Mono Variable** is `--font-mono` and is **data only**: IP, MAC, port, CVE, UUID.
Mono never sets prose, labels, buttons or headings. There is no `--font-title`.
**One family, two cuts, never two families.** Headings differentiate by weight and size.

| Token | Value | Line height | Weight | Used for |
| --- | --- | --- | --- | --- |
| `--text-title-lg` | 2rem (32px) | 1.2 | 600 | page titles |
| `--text-title-md` | 1.5rem (24px) | 1.25 | 600 | prominent titles, auth wordmark |
| `--text-title-sm` | 1.375rem (22px) | 1.3 | 600 | section and card titles |
| `--text-title-xs` | 1rem (16px) | 1.4 | 600 | smallest title, inside-shell wordmark |
| `--text-body-md` | 0.9375rem (15px) | 1.5 | 400 | default body, labels, values, controls, **nav** |
| `--text-body-sm` | 0.875rem (14px) | 1.5 | 400 | helper and error copy, dense table cells |
| `--text-caption-md` | 0.8125rem (13px) | 1.45 | 400 | captions, dense metadata |

**The scale is closed.** These seven tokens are the complete set. `--text-nav` is **dropped** —
nav is `text-body-md`. Raw framework sizes (`text-xs`, `text-sm`, `text-base`, `text-lg`, …) are
not scale tokens even when the pixels match.

## Color

| Token | Hex | Role | Contrast |
| --- | --- | --- | --- |
| `--canvas` | `#FCFCFC` | page surface | — |
| `--card` | `#FFFFFF` | cards, dialogs, table headers, popovers | 1.01 vs canvas — the border separates, not the tint |
| `--ink` | `#0F172A` | primary text | 17.85 on white |
| `--ink-muted` | `#475569` | secondary text, timestamps, helper copy, silent-machine rows | 7.58 on white |
| `--rule` | `#E2E8F0` | decorative separators, table row lines | non-text |
| `--edge` | `#64748B` | control boundaries: input, select, button outlines | 4.76 on white (3:1 floor) |
| `--accent` | `#600BB5` | primary button, active nav item, focus ring | 8.02 on white |
| `--accent-hover` | `#500997` | hover on accent controls | — |
| `--accent-active` | `#400779` | pressed accent controls | — |
| `--accent-foreground` | `#FFFFFF` | text on the accent | — |

- `#64748B` is the **hard floor for any text**. Nothing lighter.
- Keep the `--rule` / `--edge` split: an input outline owes 3:1 (WCAG 1.4.11); a row line owes
  nothing.
- The `outline` button variant uses `border-border` (`--rule`, `#E2E8F0`, ~1.2:1 against white)
  where §Color assigns `--edge` (`#64748B`) to control boundaries. That is a pre-existing mismatch
  that spreads once the outlined button becomes the card-footer control.
- **One accent, never severity.** Purple never carries severity, and severity never borrows it.
- **Severity has no hue.** `Critical` / `High` / `Medium` / `Low` are set as a **bold `--ink`
  word** — in a table cell and as a section heading alike. No chip, pill, tag, dot, badge,
  coloured text, coloured side bar or coloured card edge, anywhere. The API `Severity` union has
  four members — `critical`, `high`, `medium`, `low`.
- **Never add coloured tags.** No chip, pill, tag or badge — a tinted, rounded label — for any
  state: availability, status, counts, versions, anywhere in the app. State is a plain word or
  sentence in `--ink` or `--ink-muted`.

## Spacing

Nine steps on Tailwind's 4px base, and no others. No `--space-*` layer.

| Step | Value | Used for |
| --- | --- | --- |
| `0` | 0 | flush |
| `1` | 4px | icon-to-text |
| `2` | 8px | label-to-value, items inside one group |
| `3` | 12px | tight stack, table cell padding |
| `4` | 16px | default gap between related elements |
| `6` | 24px | card internal padding; minimum gap between a numeric and a code column |
| `8` | 32px | between cards in a list |
| `12` | 48px | between sections of a table-led screen; Home's gap to the Events/Activity row |
| `16` | 64px | around an epicenter |
| `24` | 96px | top offset for a vertically-centred, near-empty screen |

**Rhythm rules, binding:**

1. **The parent owns the space between children.** Components ship with **no outer margin**.
2. **Gap, not margins between siblings.** `gap-*` on the flex/grid container.
3. **Space groups; it does not decorate.** Related elements sit closer than unrelated ones.
4. **Vertical rhythm is consistent; horizontal is generous.** At most three vertical steps per
   screen (intra-group, inter-group, inter-section). Horizontal padding inside a content column
   never drops below step `6`.
5. **The inter-section step is chosen once per screen, from `6`, `8` or `12`** — and only those.
   It is never smaller than the inter-group step.
6. `p-5`, `gap-7` and `mt-[13px]` are all the same bug.

## Radius

```
--radius: 0.75rem;          /* 12px — cards, dialogs, panels */
--control-radius: 0.5rem;   /* 8px — buttons, inputs, select triggers, tooltips, pills */
```

Derive the `sm…4xl` ladder with **shadcn's multiplicative form only**: `sm` 0.6× · `md` 0.8× ·
`lg` 1× · `xl` 1.4× · `2xl` 1.8× · `3xl` 2.2× · `4xl` 2.6×. Never an additive `calc(± Npx)`
form. shadcn preset: **`radix-maia`**, on Radix primitives, Lucide icons.

## Containers

| Token | Value | Is the width of |
| --- | --- | --- |
| `--container-frame` | `70rem` (1120px) | the frame — top-bar contents and every inside-shell page |
| `--container-form` | `24rem` (384px) | a short form standing alone, above all the auth card |

Both are maxima and fluid below themselves. **Nothing else is a layout width** —
`max-w-[45rem]` is the same bug as `p-[13px]`. `max-w-prose` is a reading measure (~65
characters), not a container. A card sizes to its content, never to its column.

## Interaction states

**Every interactive element declares all five.** A control that looks identical under the
pointer is a defect, not a style preference.

| State | Owes |
| --- | --- |
| **Rest** | It looks like a control: the accent, a hairline `--edge` boundary, or a caret. |
| **Hover** | `cursor: pointer`, **always**, including text-shaped controls, plus one visible change — underline, background wash or colour shift. |
| **Focus-visible** | A visible ring at `--ring`. Never `outline: none`, never a ring you have to look for. A control that underlines on hover underlines on focus. |
| **Active** | A pressed acknowledgement — the button primitive's nudge, or `scale(0.97)`. |
| **Disabled** | Reduced opacity, `pointer-events: none`, out of the tab order. **Only for progress or not-yet-supplied input.** |

**Cursor rule:** Tailwind v4 preflight sets `cursor: default` on `<button>`. The pointer is
added explicitly, never inherited.

**Absent, not disabled.** An affordance a role cannot use is not rendered. The carve-out is an
action the person *is* permitted to take but has not yet supplied the input for.

**Only shared components may be interactive.** Screens compose primitives; they never hand-roll
a native control.

## Motion

```
--duration-fast: 125ms;   /* tooltips */
--duration-base: 180ms;   /* default: hover, open, expand */
--duration-slow: 300ms;   /* the ceiling */
--ease-out:      cubic-bezier(0, 0, 0.2, 1);    /* entrances */
--ease-in:       cubic-bezier(0.4, 0, 1, 1);    /* exits, shorter than the entrance */
--ease-standard: cubic-bezier(0.4, 0, 0.2, 1);  /* moves and resizes */
```

- `ease-out` for anything entering. **Never `ease-in` for an entrance.**
- Never animate from `scale(0)` — start at 0.95 or above.
- **Animate the rare, not the constant.** A live scan list does not animate every row; motion is
  reserved for scan start/finish and state changes the reader should notice.
- `prefers-reduced-motion: reduce` is **mandatory** — a global block dropping non-essential
  animation to `0.01ms` (WCAG 2.3.3).
- A duration written inline in a component is a bug, like a raw hex.
- **Duration tokens are not in `@theme`.** `--duration-fast`, `--duration-base` and
  `--duration-slow` live in `:root` (`index.css:36-38`) but are not registered in the
  `@theme inline` block, so Tailwind does not emit `duration-base` and this motion spec is
  unreachable from utility classes without an arbitrary value. The ease tokens *are* in `@theme`.

## Icons

| Rule | Value |
| --- | --- |
| Set | **Lucide** (`iconLibrary` in `components.json`). No other set. |
| Sizes | `size-4` (16px) beside body text and in table cells · `size-5` (20px) in headings, primary buttons and empty states. **Two sizes only.** |
| Stroke | `stroke-width: 1.75`, set once as the app default. |
| Colour | Inherits `currentColor`. An icon never has its own hex. |
| Accessible name | Decorative → `aria-hidden="true"`. Icon-only control → `aria-label` with the action in words. An icon beside a label needs neither. |
| Where | Section headings, empty states, table sort markers, buttons, status rows, the back link, pagination. Not decoration for its own sake. |
| Sort markers | Lucide chevron/arrow icons sized off the type scale — never `▲▼` glyphs. |

## Chrome & navigation

**Top bar, no sidebar.** One horizontal bar above every inside-shell screen: wordmark left, nav
centred on a `1fr auto 1fr` grid, user identity right. The bar's contents and
the page beneath it both hold `--container-frame`, so the wordmark and the page title start on
the same vertical; the bar's bottom hairline is full-bleed.

| Element | Rule |
| --- | --- |
| Nav items | **Home · Scans · Network · Devices · Users · Settings.** `Users` is absent for viewers, never disabled. |
| Nav type | `text-body-md`. |
| Nav active | **Bold, no underline.** Hover is **also bold** — the weight change is the whole affordance. No rule, no pill, no bottom border. |
| Wordmark | The word **"Dmitri"** only. No icon, no mark, no lockup. |
| User identity | **The user's email**, as the trigger of a menu. Truncated with an ellipsis when it
  would crowd the bar; full value in `title`. No avatar — the product has no profile pictures. |
| User menu | Opens under the identity. Holds **`Log out`** and nothing else today. |
| Back link | A Lucide **`arrow-left` + the word "Back"**, one text link **above the page title**. The gap to the title is a step from the spacing scale. |

The nav names domains, not actions, and items do not get renamed between releases.

## Tables

| Element | Rule |
| --- | --- |
| Row height | **Fixed and equal for every row — 56px.** Written into `DataTable`; rows never grow with their content. |
| Column gaps | From the **spacing scale and fixed column widths**, never from content or ad-hoc padding. A numeric column followed by a code column (`Port` then `CVE`) sits **no closer than step 6 (24px)**. |
| Whole rows are links | The entire row navigates. No trailing "View" column. |
| Alignment | Every column left-aligns; numbers keep tabular figures. **The first column always starts flush left** whatever it holds. A heading carries its column's alignment. **Follow-up restyle:** Scans; Scan detail findings; Scan detail hosts; Device detail scan history. |
| Severity column | **Reads down the right edge** — it closes the row, or is second to last where a `Last seen` column closes. The bold-word treatment applies (§Color). |
| Highest-severity column | Kept on list tables: a row summarising several vulnerabilities shows its worst one as a word. |
| IDs | Truncate to the first 8 characters; the full value is in the `title`. Never wrap a UUID. |
| Inline select in a cell | shadcn `Select` with a **ghost, borderless trigger** — the text plus a small chevron close to the text, **aligned with the column header**. |
| Silent machines | A machine unseen for weeks is **not removed and not flagged as an error**. Its row is set in `--ink-muted` with a second line reading **"Not seen for N weeks"**; no chip, no icon, no colour. Those rows also **collapse into one group row at the bottom of the table**, labelled **"Not seen recently (N)"**, which expands. The group row is always last, after the severity/name sort. This is a `DataTable` pattern. |
| Loading | `LoadingSkeleton` for the table body on first load only, never on background refetch. Its bars appear only after 250 ms, so a fast read never flashes them. |
| Empty | A table never renders bare with no rows. |

## Cards & sections

- A grouped section on a detail screen is a **white `Card` on the `#FCFCFC` canvas, with its
  heading inside the card**. On Scan detail each severity group is one such card.
- **A card never varies with severity.** No coloured outline, no ink eyebrow, no tinted header
  band, no coloured icon. A vulnerability card is a plain white card.
- **A button may live inside a card**, as a **small outlined button in the card footer** — never
  a filled primary, never a button floating in the card body.
- **A list screen's own action goes below the table, bottom-right**, sized ~5% taller than the
  default control. On a list screen **the table is the epicenter**; an action is a function of
  the screen, not its focus.
- **A panel carries no trailing empty row** — no bottom padding beyond its last item.
- **Summary strips align to their table's width**, same left and right edges, so the strip and
  the table read as one block.
- Controls are generous by default; density is zoned into tables, not applied app-wide.

## Pagination

The shadcn **`Pagination`** component — ghost buttons, page numbers, an ellipsis. Never
hand-rolled.

| Element | Value |
| --- | --- |
| Previous / next | **Icon-only**: a Lucide `chevron-left` / `chevron-right` ghost button. |
| Accessible names | **"Previous page"** / **"Next page"**. |
| Words | **No "Previous" / "Next" text.** |
| Nav name | The `nav` root is named for its surface — **`{Thing} pages`** (`Scan pages`, `Machine pages`). Two paginations on one screen never share a name. |

## Copy rules & vocabulary

| Rule | Shape |
| --- | --- |
| **Never certify safety** | Describe what needs attention; never claim the network is safe. **"Nothing needs your attention"**, not "Your network is safe". |
| Empty state | **One sentence + one button.** Nothing else. (Exception: the Home attention board renders **nothing at all** — see below.) |
| Helper text | On demand, not by default. If a field needs a paragraph, the label is wrong. |
| No product restatement | The reader is already inside the product. "Dmitri scans your network…" does not appear anywhere. |
| Labels over paragraphs | Say it in a label, a group heading or an icon before saying it in prose. |
| Explanatory copy under a control | **Deleted, not reworded.** |
| One word per concept | One owner-facing word per concept — *device* and *machine* are not interchangeable
  (see Vocabulary). |
| Buttons | Verb + noun (`Start scan`, `Remove device`). Never `Confirm`, `OK`, or a bare verb. |
| Good news reads as good news | Zero vulnerabilities is a reassuring sentence, not a blank panel. |
| Real content only | Real hostnames, real CVE ids, real IPs. No lorem ipsum, no `foo`. |
| Timestamps | Relative inside 7 days, absolute beyond it; the exact value on hover. One `Timestamp` component owns this. |

**Vocabulary:**

| Term | Value |
| --- | --- |
| *Finding* | **Retired.** The owner-facing word is **Vulnerability** — both the table column and the general word. The API taxonomy is untouched. |
| Roles | **Admin** and **Viewer**. Unchanged. |
| Nav names | **Network** (was Hosts) · **Devices** (was Agents). |
| *Device* | The Dmitri box that scans a network. Listed on **Devices**; configured on the box detail
  screen. |
| *Machine* | A host on the customer's network — what **Network** lists. Never called a *device* in
  owner-facing copy. |
| *Open ports* | Retired. The heading is a plain sentence-case phrase about the **services running on
  this machine**. **🔓 Exact wording open** (§4.11 of the research note). |
| *Seen in these scans* | **Rejected.** The scan-history heading on the detail screens needs a replacement. **🔓 Wording open** — the same open item. |
| Home's attention-board empty state | **Nothing is rendered at all** — no text, no empty card. The canvas shows through and the page title carries the message. |

## Scan settings pattern

A **shadcn `Tabs` segmented control**, one tab per scan type, with a **one-line plain
description beneath the tab strip** and a **secondary "Use this scan type" button**. It sits on
the **box detail screen** (`/devices/:agentId`) — scan type is per box, not on the Scans run log.
Radio cards and a selectable list with a description column are rejected.

| Tab | Description (ships verbatim) |
| --- | --- |
| **Quick** | Checks the 1000 most-used connection points on each device for known vulnerabilities. About 2–5 minutes. |
| **Standard** | Same 1000 connection points, and also inspects the common services — file sharing, remote login, web — for weak settings. About 5–10 minutes. |
| **Extensive** | Checks the 10,000 most-used connection points, adds certificate and encryption checks, and reports lower-severity problems as well. Duration depends on the services found and can exceed an hour. |
| **Max** | Checks every connection point on every device and reports everything it finds, however small. 45 minutes or more. |
| **NSPi** | For networks with industrial equipment: checks the control-system connection points (Modbus, OPC UA, EtherNet/IP) plus Windows remote-access ones. About 20–30 minutes. |

| Action | Result |
| --- | --- |
| Selecting a tab | **Preview only.** Nothing is saved; the description below changes. |
| **"Use this scan type"** | Sets the selected type as the **default for the daily scan**. **Confirmation required.** |
| **"Scan now"** | Runs a scan **immediately** with the **currently selected** type, and **does not change the default**. |
| Leaving the page | The selection **reverts to the default**. A preview never survives navigation. |

Confirm-dialog copy, verbatim shape — the named type plus the two durations compared:
*"Make Max your daily scan? Every morning's scan will take 45 minutes or more instead of about
8 minutes."*
