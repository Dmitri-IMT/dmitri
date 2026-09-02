# DMI-131 — Design-system audit (revamp: paper/serif → friendly white sans)

> **This file is an input, not the deliverable.** It is one of the two research halves of DMI-131,
> together with [`dmi-131-references.md`](dmi-131-references.md). Both are synthesised into
> [`docs/ui/DESIGN-SYSTEM-RESEARCH.md`](../../docs/ui/DESIGN-SYSTEM-RESEARCH.md), which is the
> note DMI-132 plans and implements from. Read the synthesis first; come here for the underlying
> inventory, line references and cost counts.

Audit half of the research note. **What exists, what to keep, what to throw out.** No values are
picked here; a separate agent researches references.

Sources read: `docs/ui/SCREENS.md`, `docs/ui/REFERENCE.md`, `docs/ui/FLOWS.md`, `docs/ui/IDEAS.md`,
`frontend/src/index.css`, `frontend/components.json`, `frontend/package.json`, every file in
`frontend/src/components/` and `frontend/src/components/ui/`, the page files in
`frontend/src/pages/`, `.claude/skills/frontend-conventions/SKILL.md`,
`frontend/eslint.config.js` + `frontend/eslint-rules/*`, `docs/adr/ADR-008-frontend-stack.md`.

---

## 1. Inventory

### 1.1 Tokens — all of them live in `frontend/src/index.css`

| Group | Tokens | Where | Note |
| --- | --- | --- | --- |
| Type scale (closed) | `--text-title-lg 2rem`, `title-md 1.5rem`, `title-sm 1.25rem`, `title-xs 1rem`, `--text-body-md .875rem`, `body-sm .8125rem`, `--text-caption-md .75rem`, `--text-nav .6875rem` | `index.css:84-91` | 8 sizes, no line-height or weight tokens at all |
| Fonts | `--font-title: 'IM Fell English', serif`; `--font-mono: 'IBM Plex Mono', monospace` | `index.css:44-45` | `html { @apply font-mono }` (`index.css:103`) makes mono the body default; **no `--font-sans`** |
| Neutrals | `--paper #FAF8F4`, `--card #fff`, `--ink #1A1917`, `--ink-muted #6B6862`, `--rule #E5E0D8`, `--edge #8C8880` | `index.css:13-18` | warm paper palette; `--rule` decorative vs `--edge` control-boundary split |
| Accent | `--accent #7C3AED` | `index.css:19` | maps to `--primary` |
| Severity | `--sev-critical #B91C1C`, `high #C2410C`, `medium #A16207`, `low #1D4ED8` | `index.css:20-23` | semantic, AA-validated on paper |
| shadcn alias layer | `--background/--foreground/--card/--popover/--primary/--secondary/--muted/--accent/--destructive/--border/--input/--ring` | `index.css:24-38` | all aliases of the six neutrals + accent — the indirection the revamp needs |
| Radius | `--radius: 0` → `--radius-sm..4xl` derived by multiplier | `index.css:39`, `70-76` | **one number drives every corner in the app** |
| Containers | `--container-frame 70rem`, `--container-form 24rem` | `index.css:80-81` | only two layout widths |
| Spacing | *none* — Tailwind's 4px base, restricted to the steps `1 2 3 4 6 8 12 16 24` by lint | `SCREENS.md:225-247`, `eslint-rules/spacing-scale.js:3-16` | deliberately no `--space-*` layer |
| Motion | *none* — no duration/easing token. Spec: "motion is a transform, and it is small" (`SCREENS.md:212-213`); in code only `transition-transform` on carets and `active:translate-y-px` on buttons | `ui/button.tsx:11`, `Disclosure.tsx:41` | |
| Custom utility | `grid-cols-bar` = `1fr auto 1fr` | `index.css:94-96` | the centred-nav grid |
| Dark | `@custom-variant dark (&:is(.dmitri-dark-unused *))` | `index.css:2-4` | deliberately dead selector; neutralises the `dark:` classes shadcn shipped |

### 1.2 Fonts and dependencies

`@fontsource/im-fell-english` + `@fontsource/ibm-plex-mono` (`package.json:13-14`), imported at
`index.css:6-8`. Runtime deps otherwise: `radix-ui` (single package), `lucide-react`,
`class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `shadcn` (for
`shadcn/tailwind.css`, imported at `index.css:5`), `tailwindcss` 4.3, `@tailwindcss/vite`.
`components.json:3` pins `"style": "radix-nova"`, `baseColor: neutral`, `iconLibrary: lucide`.

### 1.3 Components — vendored shadcn vs hand-built

Vendored primitives (lint-exempt) in `frontend/src/components/ui/`; Dmitri-owned shared components
in `frontend/src/components/`.

| Component | File | What it does | shadcn equivalent | Verdict |
| --- | --- | --- | --- | --- |
| `Button` | `ui/button.tsx` (70) | cva with 6 variants × 8 sizes; `cursor-pointer`, `active:translate-y-px`, focus ring | shadcn `button` | **keep, re-token** — variants stay; `rounded-lg` already resolves through `--radius`, so radius is free. Carries dead `dark:` classes (`:11,17,21,23`) |
| `Input` | `ui/input.tsx` (19) | `h-8`, `border-input`, focus ring | shadcn `input` | **keep, re-token** — `h-8`/`text-base`+`md:text-sm` are pre-token leftovers |
| `Label` | `ui/label.tsx` (22) | Radix Label wrapper | shadcn `label` | **keep** |
| `Select` | `ui/select.tsx` (75) | Trigger/Content/Item, trimmed (no groups, no check icon) | shadcn `select` | **keep, re-token** |
| `TopBar` | `TopBar.tsx` (70) | wordmark / centred nav / log out on `grid-cols-bar`; `text-nav` 11px links, accent underline for active | none | **keep structure, restyle** — 11px nav and the border-bottom-2 active marker go |
| `PageHeader` | `PageHeader.tsx` (23) | `font-title` h1 + optional subtitle + `<hr>` | none | **keep, restyle** |
| `DataTable` | `DataTable.tsx` (296) | generic table: colgroup widths, sortable headers, whole-row link *or* expand row, skeleton, empty slot | shadcn `table`/`data-table` (heavier, TanStack Table) | **keep** — the most valuable asset in the repo; restyle only (`border-dashed` header `:174`, `h-8` rows, ▲▼ glyph sort markers `:215`) |
| `ListSurface` | `ListSurface.tsx` (96) | query→(error \| pending \| blank \| table+pagination) switch | none | **keep as-is** — pure logic, no look |
| `Pagination` | `Pagination.tsx` (65) | range text + Previous/Next | shadcn `pagination` | **keep, restyle** |
| `LoadingSkeleton` | `LoadingSkeleton.tsx` (31) | `<tbody>` of grey bars | shadcn `skeleton` | **wrap/replace** — swap for a rounded, optionally-pulsing skeleton; it is 31 lines, cheap either way |
| `EmptyState` | `EmptyState.tsx` (31) | heading + body + action + note + `Ornament` | shadcn `empty` | **keep, restyle** — drop the Ornament slot (`:24-26`) |
| `ErrorRetry` | `ErrorRetry.tsx` (27) | serif message + `[Retry]` | none | **keep, restyle** |
| `NotFoundNotice` | `NotFoundNotice.tsx` (34) | serif message + back link | none | **keep, restyle** |
| `ReadDetailGate` | `ReadDetailGate.tsx` (56) | detail-state switch (ready/notFound/error) | none | **keep as-is** — logic only |
| `DialogShell` | `DialogShell.tsx` (77) | Radix Dialog + overlay + focus restore + `locked` | shadcn `dialog` | **keep, restyle** — `sm`/`md` widths use `max-w-sm`/`max-w-md`, which are *not* named containers (`:4`) |
| `ConfirmByTyping` | `ConfirmByTyping.tsx` (144) | type-the-address destructive confirm | none | **keep** — behaviour, not look |
| `Disclosure` | `Disclosure.tsx` (53) | Collapsible + caret, owns its five states | shadcn `collapsible`/`accordion` | **keep, restyle** |
| `Toast` (provider) | `Toast.tsx` (52) | Radix Toast, one at a time, bottom-right | shadcn `sonner`/`toast` | **keep, restyle** |
| `SeverityBadge` | `SeverityBadge.tsx` (33) | 4 severity tones, `border + bg/10 + text` | shadcn `badge` | **keep, re-token** — square today, rounds for free |
| `StatusPill` | `StatusPill.tsx` (29) | 3 tones, shared `h-8` | shadcn `badge` | **keep, re-token** — "pill" that is currently a rectangle |
| `Timestamp` | `Timestamp.tsx` (53) | relative <7d, absolute beyond, exact on hover | none | **keep as-is** — no styling at all |
| `AdminOnly` | `AdminOnly.tsx` (14) | renders children only for admin | none | **keep as-is** — the absent-not-disabled enforcer |
| `FirstScanCta` / `FirstScanNote` | `FirstScanCta.tsx` (31) | admin CTA / viewer note | none | **keep, restyle** |
| `AppShell` | `AppShell.tsx` (18) | ToastProvider + TopBar + `max-w-frame` main | none | **keep** |
| `AuthShell` | `AuthShell.tsx` (20) | centred `max-w-form` card, serif wordmark + `Ornament` | none | **keep, restyle** — Ornament out (`:10`) |
| `EmptyMark` | `EmptyMark.tsx` (6) | the "—" for an unobserved value | none | **keep as-is** |
| `Ornament` | `Ornament.tsx` (31) | inline-SVG engraving: hairline–lozenge–hairline | none | **delete** — it is the single most "paper-press" element; used in 5 places (`AuthShell:10`, `EmptyState:25`, `Home.tsx:28`, `Agents.tsx:80`, `home/HomeBlank.tsx:19`) plus `Ornament.test.tsx` (68 lines) |

**Missing primitives the new look will want:** `card`, `separator`, `alert`, `tooltip`, `badge`,
`avatar`, `switch`/`checkbox`. Today "a card" is an ad-hoc `border border-rule bg-card p-6`
(e.g. `AuthShell.tsx:12`, `DialogShell.tsx:68`, `Toast.tsx:33`) — there is no `Card` component.

### 1.4 Icon usage

Three imports, total: `ChevronRight` (`DataTable.tsx:10`, `Disclosure.tsx:2`) and `ChevronDown`
(`ui/select.tsx:2`). Nothing else in the product uses an icon — no status icons, no severity
icons, no nav icons. Sort direction is drawn with the text glyphs `▲▼` (`DataTable.tsx:215`).
Lucide is installed and barely used; a friendlier UI will lean on it far more.

### 1.5 Lint rules (`frontend/eslint.config.js:28-43`, `frontend/eslint-rules/`)

| Rule | File | Enforces | Keys off |
| --- | --- | --- | --- |
| `local/no-arbitrary-utility` | `no-arbitrary-utility.js` | no `p-[13px]` / `text-[15px]` / `max-w-[45rem]` in authored class strings | the `[...]` bracket syntax; error text names `max-w-frame`/`max-w-form` and the type-token prefixes |
| `local/no-raw-type-size` | `no-raw-type-size.js:3-20` | no `text-xs…text-9xl`; maps each to its px and suggests the named token | a **hard-coded map** of token names → px (`text-sm → text-body-md`, …) |
| `local/spacing-scale` | `spacing-scale.js:3-16` | `m*/p*/gap*/space*` only at `0 1 2 3 4 6 8 12 16 24 px auto` | literal step values |
| `local/no-bare-interactive` | `no-bare-interactive.js:1` | no bare `<button> <input> <select> <textarea>` in screens | JSX element names |

Exemptions, and only these: `src/components/ui/**`, `src/**/*.test.{ts,tsx}`, `src/test/**`
(`eslint.config.js:30-34`).

---

## 2. Keep — the rules, regardless of look

| Rule | Where | Why it survives a revamp |
| --- | --- | --- |
| Closed type scale (8 named tokens, raw sizes banned) | `index.css:84-91`, `SCREENS.md:120-131` | The scale is a decision mechanism; only the *values* and the faces are era-specific. |
| Nine spacing steps on a 4px base, no `--space-*` layer | `SCREENS.md:225-247` | Rhythm is what makes a UI feel deliberate; friendly designs need it more, not less. |
| Named containers only (`frame`, `form`) | `index.css:80-81`, `SCREENS.md:308-336` | Stops the "720px letterbox around 336px of form" class of bug the doc records. |
| Five interaction states declared per control | `SCREENS.md:190-205` | A non-technical owner learns controls by their affordance; this rule is *why* a friendly UI feels clickable. |
| No outer margin — the parent owns the gap | `SCREENS.md:250-256` | The one rule that keeps components recomposable while every screen is restyled. |
| Absent, not disabled (with the input-not-yet-supplied carve-out) | `SCREENS.md:391-399`, `AdminOnly.tsx` | Permission model, not aesthetics. |
| Lint enforcement of the mechanical rules | `eslint.config.js:38-42` | Without it the new tokens rot within a sprint, exactly as arbitrary values did before. |
| Light-only, no `dark:`, no toggle | `SCREENS.md:66-84`, `index.css:2-4` | A white, friendly product wants one validated surface; dark stays a separate later pass. |
| Desktop-only, fluid within (1440 target, 1280 min) | `SCREENS.md:284-306` | Users are at a desk; the revamp must not smuggle a mobile programme in. |
| Top bar, no sidebar, nav centred on a `1fr auto 1fr` grid | `SCREENS.md:19-64`, `TopBar.tsx:18` | Decided, reverted, re-decided; re-litigating it is the documented failure mode. |
| Whole rows are links; severity reads down the right edge; IDs truncate; one `Timestamp` | `SCREENS.md:381-421` | Cross-screen consistency rules that a restyle does not touch. |
| Three states per screen (regular / blank / error), errors have a next step | `SCREENS.md:383-390`, `ListSurface.tsx` | Already implemented as shared code; keep both the rule and the component. |

---

## 3. Throw out — the values and elements

| Out | Where it lives | Why it goes | What replaces it *in spirit* |
| --- | --- | --- | --- |
| **IM Fell English** for every title | `index.css:7,44`; 35 `font-title` uses across `src/` | A 17th-century press face reads as "artefact", not "app"; it forces a 16px floor and blocks small headings | One friendly sans family, weight-differentiated headings (a `--font-sans` replacing both `--font-title` and `--font-mono` for prose) |
| **IBM Plex Mono as body copy** | `index.css:103` (`html { font-mono }`) | Mono body says "terminal output" to a non-technical owner; it is the single biggest cold-signal | Sans for all prose and UI; mono kept **only** as a data face for IP/MAC/CVE/UUID/port |
| **`--radius: 0`** | `index.css:39` | Square corners read industrial; every shadcn primitive already asks `--radius` for its corners | A positive base radius, with the existing derived ladder (`sm…4xl`) unchanged |
| **Warm paper palette** (`--paper #FAF8F4`, `--card #fff` at 1.06 separation) | `index.css:13-14` | Warm off-white + a card that differs only by warmth gives no real surface hierarchy | A true white/near-white page, surfaces separated by a soft tint or shadow rather than by warmth |
| **`--rule` / `--edge` beige borders as the main structure** | `index.css:17-18`; used on nearly every container | Hairline boxes everywhere is engraving logic; the whole UI is drawn with lines | Fewer lines: grouping by surface, spacing and soft elevation; keep the decoration-vs-control-boundary *distinction*, restate its values |
| **`Ornament`** (hairline–lozenge–hairline) | `Ornament.tsx`, 5 call sites + a 68-line test | Pure period decoration with no job | Nothing, or an illustrative/iconic empty-state mark |
| **Dashed rules** | `DataTable.tsx:174,280`, `Settings.tsx:42,65,93`, `agents/SubnetChooser.tsx:36` | Dashed = ledger paper; also the noisiest separator available | Solid hairline, or no line at all where spacing separates |
| **`text-nav` 11px** | `index.css:91`, `TopBar.tsx:24…` | 11px letterspaced nav is a print/marketing tic and hurts a non-technical reader | Nav at normal body size, weight/colour marking the active item |
| **`▲▼` glyph sort indicators** | `DataTable.tsx:215` | Text glyphs are misaligned, unstyleable and read as ASCII art | Lucide chevron/arrow icons, sized off the type scale |
| **`h-8` everywhere as the universal control height** | `ui/button.tsx:28`, `ui/input.tsx:11`, `ui/select.tsx:19`, `StatusPill.tsx:20`, `DataTable.tsx:62` | 32px controls + 32px table rows is a dense-tooling density | A more generous default control height; dense rows only where the table demands |
| **`bg-*/10` tinted, hard-bordered badges** | `SeverityBadge.tsx:14-17`, `StatusPill.tsx:6-8` | Bordered rectangles read as warning boxes | Rounded, filled, softer badges — same four semantic hues, restated for a white surface |
| **Deep purple `#7C3AED` as the only accent** | `index.css:19` | Keep the *rule* (one accent, never severity); the value is inherited from the paper direction and must be re-validated on true white | One accent, re-picked for a white surface, plus at least a hover/active step of it |
| **Prose-heavy explanation blocks** | see §4 | The screens explain the product where a friendlier layout could show it | Shorter copy plus visual affordance |

---

## 4. Copy bloat

Counted as rendered explanatory strings of ≥5 words in non-test `.tsx` under `frontend/src/pages/`
(labels, buttons and table headers excluded).

| Screen | Sentences ≈ | Words ≈ | Worst offender |
| --- | --- | --- | --- |
| **Users & invites** | **9** | **75** | `users/InviteDialog.tsx` — 6 strings, incl. a two-sentence role explainer (`:` role copy) and a two-sentence "only time you'll see this link" |
| **Settings** | 4 | 58 | `Settings.tsx:11` (only-admin block), the activity disclosure body, the delete-account body |
| **Agents** | 4+3 | ~63 | `Agents.tsx` footer note ("The Dmitri box is installed and configured on site…"), `agents/SubnetChooser.tsx` two-sentence network explainer, `agents/AgentsBlank.tsx` (3-clause blank state), `agents/CommandStatus.tsx` |
| **Accept invite** | 3 | 28 | `AcceptInvite.tsx` expired-link paragraph |
| **Scans** | 2 | 16 | `Scans.tsx` subtitle + blank body, both restating what Dmitri is |
| **Hosts** | 2 | 22 | subtitle + blank body, same duplication |
| **Home** | 2 | ~21 | `home/HomeBlank.tsx` (1 long sentence), `home/HomeError.tsx` |
| **Scan detail** | 2 | 10 | `scans/ScanUnfinishedNotice.tsx` ("doesn't update on its own") |
| **Login / Forgot / Reset** | 1–3 | 8–14 | thin already |
| **Host detail** | ~3 | ~13 | empty-state lines only |

**Verdict:** the app is *not* drowning in prose — the total across every screen is under ~400
words. The bloat is concentrated in **Users & invites, Settings and Agents**, and its shape is
*explaining the product mid-screen* (three screens each carry a "Dmitri scans your network…"
restatement: `Scans.tsx`, `Hosts.tsx`, `home/HomeBlank.tsx`). The heaviness the owner is reacting
to is therefore mostly **typographic and chromatic, not verbal** — a finding that should steer the
revamp toward tokens and primitives rather than a copy rewrite.

### SCREENS.md as a document

`SCREENS.md` is 1893 lines; **§Foundations is lines 14-421 (408 lines)** and it interleaves binding
rules with the decision history that produced them. 17 lines carry an explicit history marker
(*"Decided 2026-08-21"*, *"reverted"*, *"previously"*, *"was briefly considered and rejected"*,
*"Consequence, recorded"*), and each anchors a paragraph or more of narrative — e.g. the centred-nav
story (`:24-40`, ~17 lines for a one-line rule), the `--rule`-vs-whitespace argument (`:262-271`),
the inter-section-step trade (`:274-282`), the "only unfilled values" note (`:188`).

Rough split of §Foundations: **≈60% rule (tables, bold binding statements, the token lists) /
≈40% history-and-rationale (~160 lines)** — the reasons a value was chosen, the reversals, and the
references that justified the paper direction. Most of that 40% argues for values the revamp
discards, so it becomes actively misleading rather than merely long. Recommendation for the
follow-on work: split §Foundations into a short binding token spec and a `DECISIONS`/appendix
carrying the history, rather than editing values in place inside the narrative.

---

## 5. Constraints and migration risks

| Constraint | Detail | Risk |
| --- | --- | --- |
| **Tailwind v4 has no JS config** | Everything is `@theme inline` in `index.css`; `tailwind.config.js` / `darkMode:'class'` are traps (`SKILL.md` version-trap table) | Any revamp that reaches for a config file is wrong by construction. Good news: **the entire token surface is one 105-line file.** |
| **shadcn `radix-nova` style** | `components.json:3`; primitives read `--radius`, `--primary`, `--border`… | Changing `--radius` and the neutrals restyles all four primitives with **zero component edits** — the cheapest possible lever. But re-running `npx shadcn add` for new primitives pulls `radix-nova` markup that may not match a friendlier direction; expect hand-trimming (the existing `select.tsx` was already trimmed). |
| **`shadcn/tailwind.css` is imported** | `index.css:5` | It ships defaults the token block overrides; a token rename can silently fall through to it. |
| **`dark:` variant is neutralised, not removed** | `index.css:2-4`; dead `dark:` classes survive in `ui/button.tsx:11,17,21,23` and `ui/input.tsx:11` | If anyone "fixes" the custom-variant line, a half-built dark mode switches on. Leave the neutraliser; do not add `dark:` classes. |
| **Lint keys off token *names*** | `no-raw-type-size.js:5-19` hard-codes `text-sm → text-body-md` etc.; `no-arbitrary-utility.js:4-8` names `max-w-frame`/`max-w-form` | **Renaming a token breaks the lint rule silently** (the rule keeps suggesting a token that no longer exists). If the type scale grows a `text-body-lg` or drops `text-nav`, `no-raw-type-size.js` and both error messages must be updated in the same commit. |
| **Spacing rule is a literal allowlist** | `spacing-scale.js:3-16` | Any new step (e.g. `5`, `10`, `20`) must be added there *and* in `SCREENS.md` §Spacing *and* in `SKILL.md`; three places, no single source. |
| **`no-bare-interactive`** | `no-bare-interactive.js:1` | A restyle that inlines a `<button>` anywhere outside `ui/` fails the gate. New primitives must land in `src/components/ui/` or `src/components/`. |
| **`ui/**` is lint-exempt** | `eslint.config.js:30-34` | Vendored primitives can and do carry raw sizes (`text-base`, `text-xs`, `h-8`, `rounded-[min(...)]`, `text-[0.8rem]` at `ui/button.tsx:29-36`). These are invisible to the gate and must be audited by hand during the restyle. |
| **Tests assert class names** | 41 `toHaveClass` assertions; `TopBar.test.tsx:81-199` asserts `max-w-frame`, `grid-cols-bar`, `text-nav`, `border-accent`; `Ornament.test.tsx` asserts `h-px`, `size-3`; `Disclosure.test.tsx:78-109` asserts `text-body-md` and the caret rotation | Dropping `text-nav`, the ornament or the accent underline **breaks tests that assert styling, not behaviour**. Budget test edits into the same commits; `Ornament.test.tsx` (68 lines) is deleted outright. |
| **Tests key off `data-testid` and exact copy** | 494 `getByTestId` + 259 `findByTestId` + 171 `queryByTestId`, 42 `getByText`, 86 `getByRole` across 37 test files | Restyling is safe as long as **testids and copy are left alone**. Any copy trim (§4) is a test-touching change; keep it in a separate commit from the restyle. |
| **`max-w-sm` / `max-w-md` used as layout widths** | `DialogShell.tsx:4`, `Toast.tsx:44` | These are framework widths, not named containers, and they pass lint only because they are not bracketed. If dialogs are re-proportioned, do it by adding a named container token, not by picking another framework size. |
| **Prettier + `format:check` in the gate** | `package.json:19`, `SKILL.md` §Gate | Full gate is `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build`. Long cva class strings reflow; run prettier on the touched files only. |
| **ADR-008 owns the stack, SCREENS.md owns the look** | `ADR-008:7`, `SCREENS.md:5-8` | The revamp changes *values in SCREENS.md*; ADR-008's shadcn/Tailwind/Recharts decisions stay untouched. Only the ADR-008 note pointing at SCREENS.md needs no edit. |
| **Type generation** | `npm run gen:types` must diff clean | Unaffected by a restyle, but the gate still runs it if the API layer moves. |

---

## 6. Migration order

**Principle: change values before components, components before screens.** The token indirection in
`index.css:24-38` means most of the visual change lands in step 1.

1. **Tokens (`index.css`, ~105 lines).** New `--font-sans` (+ mono demoted to a data face), new
   neutrals, new accent, non-zero `--radius`, re-validated severity hues, re-check the type scale
   values, `html { font-mono }` → sans. *Verify:* `npm run build` and a visual pass; expect
   `TopBar.test.tsx`, `Disclosure.test.tsx` class assertions to flag.
2. **Lint + doc alignment, same PR as step 1.** `no-raw-type-size.js` map, both rule messages,
   `spacing-scale.js` allowlist if steps change, `SCREENS.md` §Foundations token tables,
   `SKILL.md` §Styling. *Verify:* `node --test frontend/eslint-rules/*.test.js`, `npm run lint`.
3. **Vendored primitives (`ui/button|input|label|select`).** The lint-exempt raw sizes
   (`text-base`, `text-xs`, `text-[0.8rem]`, `h-8`, `rounded-[min(...)]`) audited by hand; strip
   the dead `dark:` classes; add the primitives the new look needs (`card`, `separator`, `badge`,
   `tooltip`) — hand-trimmed like `select.tsx` was.
4. **Shared components (`src/components/`).** Delete `Ornament` + its test and its 5 call sites;
   restyle `DataTable` (dashed rules, `▲▼` → Lucide, row height), `EmptyState`, `ErrorRetry`,
   `NotFoundNotice`, `PageHeader`, `TopBar` (drop `text-nav`), `Pagination`, `Toast`,
   `SeverityBadge`, `StatusPill`, `LoadingSkeleton`, `DialogShell`. `ListSurface`,
   `ReadDetailGate`, `Timestamp`, `AdminOnly`, `EmptyMark`, `ConfirmByTyping` need **no change**.
5. **Screens**, cheapest first.

**Cost per screen** (all counts from non-test files):

| Screen | Files / lines | Own styling | Cost |
| --- | --- | --- | --- |
| Scans, Hosts | `Scans.tsx` 51, `Hosts.tsx` 80 + column files | almost none — pure `ListSurface` | **cheapest** |
| Host detail, Scan detail | `HostDetail.tsx` 54, `ScanDetail.tsx` 82 + `hosts/`, `scans/` fragments | `ReadDetailGate` + tables | cheap |
| NotFound, Login, Forgot, Reset | 20–174 lines each, `AuthShell` | one card each; `AuthShell` carries the ornament and serif wordmark | cheap once `AuthShell` is done |
| Home | `Home.tsx` 62 + `home/` (6 files, ~250) | the epicenter: verdict, finding deck, review card, footer, ornament | medium — highest *design* stakes, low code volume |
| Settings | `Settings.tsx` 151 + `settings/` (2 files, ~240) | 3 dashed section rules, disclosure, 2 dialogs, confirm-by-typing | medium |
| Accept invite | `AcceptInvite.tsx` 299 | the longest single page file; own form + expired/signed-in branches | dear |
| Agents | `Agents.tsx` 88 + `agents/` (7 files, ~400) | subnet chooser, scan control, command status, agent cards, ornament, own dashed rule | **dearest** |
| Users & invites | `Users.tsx` 165 + `users/` (5 files, ~680) + 6 test files (~1100) | invite dialog, directory table (**not** on `DataTable`), 3 more dialogs; heaviest copy | **dearest** — and the one place a `DataTable` retrofit is still outstanding (`SCREENS.md:363`) |

**Sequencing note:** do Scans/Hosts first as the proof that steps 1–4 landed (they are almost pure
composition, so anything that looks wrong there is a token or component bug, not a screen bug), then
Home for the design decision, then the dear screens last.
