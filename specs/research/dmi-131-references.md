# DMI-131 — UI revamp reference gathering

> **This file is an input, not the deliverable.** It is one of the two research halves of DMI-131,
> together with [`dmi-131-audit.md`](dmi-131-audit.md). Both are synthesised into
> [`docs/ui/DESIGN-SYSTEM-RESEARCH.md`](../../docs/ui/DESIGN-SYSTEM-RESEARCH.md), which is the
> note DMI-132 plans and implements from. Read the synthesis first; come here for the source URLs,
> the measured contrast tables and the full comparable teardowns.

Research date: **2026-09-02**. Audience for the target UI: a **non-technical business owner**.
Every claim below carries a URL. Where a named source did not exist, that is stated plainly.

**Two corrections up front:**

1. `builtifului.dev` does not resolve (DNS `ENOTFOUND`). The real site is
   **`beautifului.dev`** — see §3.
2. The project is on shadcn style **`radix-nova`**, which is the *compact/dense* preset.
   The owner's brief ("bubbly, soft, generous, cute") describes **`maia`**, not `nova`.
   See §4 and the Synthesis.

---

## 1. OpenAI Codex app — visual language

### What it is

- The Codex app for macOS launched **2 February 2026**; OpenAI positions it as a
  "command center for agents" for running multiple coding agents in parallel.
  <https://openai.com/index/introducing-the-codex-app/> (page returns 403 to
  automated fetch; content reported via)
  <https://venturebeat.com/orchestration/openai-launches-a-codex-desktop-app-for-macos-to-run-multiple-ai-coding>
- April 2026 added an in-app browser (built on Atlas), background computer use, and
  image generation — the app is drifting from "terminal replacement" toward a
  consumer-shaped desktop product.
  <https://9to5mac.com/2026/04/16/openais-codex-app-adds-three-key-features-for-expanding-beyond-agentic-coding/>

### Typography — the single most concrete finding

- The face is **OpenAI Sans**, a bespoke typeface by OpenAI with **ABC Dinamo**,
  introduced in the 2025 rebrand. It ships across "the interface and presentation of
  ChatGPT in all its forms, from browser to apps."
  <https://www.wallpaper.com/tech/openai-has-undergone-its-first-ever-rebrand-giving-fresh-life-to-chatgpt-interactions>
- Its described character is exactly the owner's brief: the designers "brought
  **circular forms** into the letters and punctuation, such as the round 'O'," giving
  "a **friendly and circular** appearance" — geometric precision with a rounded,
  approachable character. Five weights: Light, Regular, Medium, Semibold, Bold.
  <https://www.wallpaper.com/tech/openai-has-undergone-its-first-ever-rebrand-giving-fresh-life-to-chatgpt-interactions>
- **OpenAI Sans is proprietary and not licensable by third parties.** OpenAI's brand
  page (<https://openai.com/brand/>) is 403 to automated fetch, but the typeface is
  documented only as a bespoke commission for OpenAI's own identity — it is not on
  Google Fonts, npm, or Fontsource. **We cannot ship it.** §6 lists substitutes that
  carry the same rounded-geometric feel under OFL.

### Honest limitation

I could not obtain a first-party screenshot teardown giving exact hex values, radius
in px, or motion curves for the Codex desktop app. The press coverage above is
feature-led, not design-led. **The best available proxy is §2** — T3 Code is an
open-source desktop app built *on top of the Codex CLI* by a team explicitly chasing
that same surface, and its CSS is fully readable. Treat §2 as the measurable stand-in
for "Codex feel," and §1 as the stated intent (round, friendly, geometric, low-text).

### Adjacent, and useful for §9

- An open issue on the Codex repo argues Codex "needs its own frontend design system"
  — evidence that encoding a design system in a file is the current practice for
  agent-built UI. <https://github.com/openai/codex/issues/20878>
- Community guidance around Codex recommends encoding rules in an `AGENTS.md` or
  `DESIGN.md` the agent loads every run: "no hero cards, at most two typefaces, one
  accent color, brand-first hierarchy." <https://codex-design.ai/>

---

## 2. T3 Code — open source, and directly readable

**It is open source.** Repo: <https://github.com/pingdotgg/t3code> (org `pingdotgg`).
Announced by Theo as "fully open source. Built on top of the Codex CLI."
<https://x.com/theo/status/2030071716530245800> · download <https://t3.codes/> ·
overview <https://betterstack.com/community/guides/ai/t3-code/>

Monorepo: `apps/{desktop,web,mobile,server,marketing}`, `packages/*`. The web app is
the design source of truth.

### UI stack (verified from the repo)

`apps/web/components.json` — <https://github.com/pingdotgg/t3code/blob/main/apps/web/components.json>

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "base-mira",
  "tailwind": { "css": "src/index.css", "baseColor": "zinc", "cssVariables": true },
  "iconLibrary": "lucide",
  "aliases": { "ui": "~/components/ui", "utils": "~/lib/utils" }
}
```

- **shadcn**, style `base-mira` — Base UI primitives + the *Mira* (most compact) style.
  Note this is a dense-IDE choice, not a friendly-dashboard choice. See §4.
- **Icons: Lucide** (`lucide-react ^0.564.0`), same as Dmitri today.
- **Tailwind v4** (`tailwindcss ^4.0.0`, `@tailwindcss/vite ^4.0.0`), `cssVariables: true`.
- `@formkit/auto-animate ^0.9.0` for list/layout animation — no Framer Motion.
- Base colour ramp: **zinc**. <https://github.com/pingdotgg/t3code/blob/main/apps/web/package.json>

### Tokens — `apps/web/src/index.css` (2,010 lines, the file to read)

<https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css>

**Fonts — a system stack, no webfont at all:**

```css
@theme {
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas,
               "Liberation Mono", monospace;
}
```

**Radius — `--radius: 0.625rem` (10px)**, with the shadcn derived scale:

```css
--radius-sm: calc(var(--radius) - 4px);   /*  6px */
--radius-md: calc(var(--radius) - 2px);   /*  8px */
--radius-lg: var(--radius);               /* 10px */
--radius-xl: calc(var(--radius) + 4px);   /* 14px */
--radius-2xl: calc(var(--radius) + 8px);  /* 18px */
--radius-3xl: calc(var(--radius) + 12px); /* 22px */
```

A separate `--control-radius: 0.5rem` (8px) keeps sidebar/palette/tooltip/toolbar
controls from drifting apart — a good pattern to copy.

**Light theme — off-white canvas, pure-white cards.** This directly answers the
"grey canvas with white cards" question: the canvas is *near*-white, the cards are
*pure* white, and the sidebar is one step darker.

| Token | Value | Resolved |
|---|---|---|
| `--background` | `--color-zinc-25` = `oklch(99.2% 0 0)` | **`#FCFCFC`** |
| `--card`, `--popover` | `--color-white` | `#FFFFFF` |
| `--sidebar` | `--color-zinc-50` | `#FAFAFA` |
| `--foreground` | `--color-zinc-800` | `#27272A` |
| `--muted-foreground` | `--color-zinc-500` | `#71717A` |
| `--border` | `--color-zinc-200` | `#E4E4E7` |
| `--primary` (light) | `oklch(0.488 0.217 264)` | **`#1B4ED8`** (≈ Tailwind blue-700) |
| `--primary` (dark) | `oklch(0.571 0.21 264)` | `#346BF1` |

`zinc-25` is a custom step they had to invent (`--color-zinc-25: oklch(99.2% 0 0)`) —
Tailwind's ramp starts at `zinc-50`. The canvas/card delta is deliberately tiny.

**Status colours use a `500` fill + `700` text + ~8% tint split:**

```css
--error:   var(--color-red-500);     --error-foreground:   var(--color-red-700);
--warning: var(--color-amber-500);   --warning-foreground: var(--color-amber-700);
--success: var(--color-emerald-500); --success-foreground: var(--color-emerald-700);
--info:    var(--color-blue-500);    --info-foreground:    var(--color-blue-700);
--error-surface:   color-mix(in srgb, var(--error) 8%, transparent);
--warning-surface: color-mix(in srgb, var(--warning) 8%, transparent);
--update-surface:  color-mix(in srgb, var(--update) 12%, transparent);
```

That is the tinted-pill pattern of §8, derived from one hue via `color-mix` instead
of hand-picked pairs — fewer tokens for an agent to get wrong.

**Motion — short, and `ease-out`-family:**

```css
::view-transition-group(t3-mobile-composer) {
  animation-duration: 180ms;
  animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
::view-transition-old(t3-mobile-draft-headline) {
  animation: ... 130ms cubic-bezier(0.4, 0, 1, 1) both;   /* exit, faster */
}
--animate-status-pulse: status-pulse 2s infinite;
--animate-ghost-pulse:  ghost-pulse 2.4s infinite;
--animate-skeleton:     skeleton 2s infinite linear;
```

Two more patterns worth stealing: a `.no-transitions` class that sets
`transition-duration: 0s !important` on `*` during theme swaps, and a comment noting
the indicator animations are "duty-cycled … so the compositor updates discrete frames
instead of every vsync."

### Files an agent should read for inspiration

| Purpose | Path |
|---|---|
| All tokens, themes, motion | `apps/web/src/index.css` |
| shadcn config / style / icons | `apps/web/components.json` |
| shadcn primitives | `apps/web/src/components/ui/` |
| Deps and versions | `apps/web/package.json` |
| Runtime font override logic | `apps/web/src/appearanceFonts.ts` |
| Contrast-boost logic (a11y) | `apps/web/src/appearanceContrast.ts` (+ `.test.ts`) |
| Theme palette model | `apps/web/src/themePalette.ts` |
| Their own agent instructions | `AGENTS.md`, `CLAUDE.md`, `.agents/skills/` at repo root |

Note `appearanceContrast.ts` and `appearanceFonts.ts` both ship unit tests — they
treat contrast and font stacks as testable logic, not CSS trivia.

---

## 3. `builtifului.dev` → **Beautiful UI (`beautifului.dev`)**

`builtifului.dev` **does not exist** — DNS resolution fails. The intended site is
**<https://www.beautifului.dev/>**, "Beautiful UI — crafted primitives for AI-native
interfaces."

### What it is

A copy-paste component library of **20 numbered primitives** for AI/agent interfaces,
MIT licensed (<https://www.beautifului.dev/license>). Install is via the **shadcn
registry protocol**, which is the important part for us:

```bash
npx shadcn add https://www.beautifului.dev/r/approval-card.json
```

Registry index: <https://www.beautifului.dev/r/registry.json>

### Stated design tokens

Tokens live in `app/globals.css` as **Tailwind v4 `@theme` variables**, themed light
and dark, with "cool, blue-tinted neutrals, solid hairline borders, **one blue
accent**, and semantic colors used sparingly."
<https://www.beautifului.dev/>

That is nearly identical to T3 Code's choices (zinc neutrals, one blue primary,
status colours held back) — two independent sources converging.

### Components on offer (01–20)

Loading states · thinking/reasoning displays · streaming text with sources ·
**approval cards** · tool chips · **task rows** · chat composers · prompt bars ·
recommendation cards · context cards · diff tables · **records tables** ·
**filter tables** · **sidebar navigation** · search · flowcharts · **insight cards** ·
code blocks · fine-tune inspectors · selection action menus.

### Most useful for Dmitri

Dmitri is a scanner, not a chat app, so the chat primitives are noise. The directly
transferable ones are **records tables** and **filter tables** (the device/finding
lists), **task rows** (scan progress), **insight cards** (the "here's what we found"
summary), **approval cards** (confirm-a-risky-action), and **sidebar navigation**.

**Caveat:** the homepage carries a paid-design-services CTA ("Turbo"). The components
are MIT, but treat the site as a vendor showcase, not a neutral standard.

---

## 4. shadcn v4 — current state

### Adding components (CLI + registry)

- CLI docs: <https://ui.shadcn.com/docs/cli> · project scaffold `npx shadcn create`
  <https://ui.shadcn.com/docs/changelog/2025-12-shadcn-create>
- `components.json` reference: <https://ui.shadcn.com/docs/components-json>
- Registry docs: <https://ui.shadcn.com/docs/registry>. Official registry lives at
  `https://ui.shadcn.com/r`. Any URL serving a registry item JSON can be installed —
  `npx shadcn add <url>` — and named registries are declared in `components.json`:

```json
"registries": { "@acme": "https://registry.acme.com/{name}.json" }
```

  (T3 Code declares `@coss` and `@spell` this way.)

### Styles / presets — **the `radix-nova` finding**

Style is now `{library}-{style}`: library is `radix` (Radix UI) or `base` (Base UI),
style is one of five.
<https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira> ·
<https://www.shadcnblocks.com/docs/blocks/styles> ·
<https://shadcncraft.com/docs/changelog/2026-04-bases-styles-icon-libraries>

| Style | Character | Fit for a non-technical owner |
|---|---|---|
| **Vega** | Classic shadcn. Medium radius, balanced spacing. | Safe default |
| **Nova** | *"Tighter padding and reduced margins"*, for dashboards and information-dense UIs | **← Dmitri is here today. Wrong for the brief.** |
| **Maia** | *"Larger border radii — often fully rounded — with generous spacing"*, for **consumer products and softer aesthetics** | **← Matches the brief exactly** |
| **Lyra** | Zero radius, boxy, sharp; pairs with monospace, for dev tools | The "paper" look we are leaving |
| **Mira** | Most compact; spreadsheets and data tables | T3 Code's pick (it is an IDE) |

Set in `components.json` as `{ "style": "radix-nova" }` — so the migration is
`radix-nova` → `radix-maia`, one field plus a re-add of the primitives.

Base UI support for all five styles landed 5 Feb 2026.
<https://www.shadcnblocks.com/changelog/new-feature-component-styles> ·
background on Radix vs Base UI:
<https://certificates.dev/blog/starting-a-react-project-shadcnui-radix-and-base-ui-explained>

### Theming with CSS variables in Tailwind v4

<https://ui.shadcn.com/docs/theming> · <https://ui.shadcn.com/docs/tailwind-v4>

- Convention: a surface token pairs with a `-foreground` token for text/icons on it
  (`--primary` / `--primary-foreground`). The word "background" is dropped from the
  surface token's name.
- An `@theme inline` block maps the variables onto Tailwind utilities, so
  `--background` becomes `bg-background` and `--foreground` becomes `text-foreground`.
- Full token set: `background`, `card`, `popover`, `primary`, `secondary`, `muted`,
  `accent` (each with `-foreground`), plus `destructive`, `border`, `input`, `ring`,
  `chart-1..5`, and the `sidebar-*` family.
- Radius: **one `--radius`** with a derived scale — "smaller radii scale down from
  `--radius`, larger radii scale up." Documented multipliers: `sm` 0.6×, `md` 0.8×,
  `lg` 1×, `xl` 1.4×, `2xl` 1.8×, `3xl` 2.2×, `4xl` 2.6×.

  (T3 Code uses the older additive `calc(var(--radius) ± Npx)` form. Either works;
  pick one and state it, so agents do not mix them.)

### Official guidance for AI agents — the shadcn MCP server

<https://ui.shadcn.com/docs/mcp>

Claude Code setup, from the docs, into `.mcp.json`:

```json
{ "mcpServers": { "shadcn": { "command": "npx", "args": ["shadcn@latest", "mcp"] } } }
```

It lets an agent **browse** registries, **search** them in natural language, and
**install** components conversationally ("add the button, dialog and card components").
It works against any shadcn-compatible registry, public or private — which is how the
Beautiful UI registry in §3 becomes agent-reachable.

Measured benefit: "the gap between AI agents with and without access to live component
docs is huge — with the shadcn/ui MCP server, Claude Code delivered accurate, working
components aligned with the latest specs."
<https://blog.logrocket.com/ai-shadcn-components/>

**Not found:** there is no `ui.shadcn.com/docs/styles` page (404) and no
`ui.shadcn.com/docs/registry/registry-for-agents` page (404). The style list is only
documented by third parties (shadcnblocks, shadcncraft) and by the `components.json`
schema itself. The agent story is the MCP page above.

---

## 5. Friendly SaaS comparables

### Linear

<https://linear.app/blog/how-we-redesigned-the-linear-ui>

1. **Two cuts of one face.** "We started using **Inter Display** to add more
   expression to our headings while maintaining their readability and kept using
   regular **Inter** for the rest of the text elements." One family, two optical sizes
   — expressive headings without a second typeface.
2. **Contrast raised, not lowered.** They made "text and neutral icons **darker** in
   light mode and lighter in dark mode." Low-contrast grey text is a common
   "minimal" mistake; Linear went the other way.
3. **Perceptual colour space.** They moved to **LCH** so that "a red and a yellow
   color with lightness 50 will appear roughly equally light to the human eye" —
   which is exactly what a severity ramp needs.
4. **Neutral chrome.** They reduced "how much chrome (blue in our case) was used in
   the calculations" for a "more neutral and timeless appearance." The accent is used
   sparingly, not spread through the greys.
5. **Alignment is felt, not seen.** Effort went into "aligning labels, icons, and
   buttons, both vertically and horizontally in the sidebar and tabs" — polish that
   "isn't something you'll immediately see but rather something that you'll feel."

### Basecamp / 37signals

<https://www.designprinciplesftw.com/collections/37-signals-principles> ·
<https://signalvnoise.com/posts/3122-the-new-basecamp-interface-details-and-power-user-goodness> ·
<https://basecamp.com/guides/how-we-communicate>

1. **Vocabulary is a design surface.** In the newer Basecamp "the list of terms used
   shrunk dramatically and complexity vastly decreased" — the single highest-leverage
   move for a non-technical audience.
2. **One word per concept.** "The same language is spoken across the interface" —
   posting a comment on a to-do *starts a discussion*, and the same term covers
   to-do lists, events, and files.
3. **No jargon, ever.** "Buzzwords, lingo, and sensationalized sales-and-marketing-speak
   have no place in their products."
4. **Three priorities in the UI:** speed, big picture, focus.
5. **Respect the customer's time.** Great service, ease of use, honest pricing —
   ease of use is stated as a product value, not a design nicety.

### Stripe Dashboard

<https://www.925studios.co/blog/stripe-dashboard-design-breakdown> ·
<https://www.shadcn.io/design/stripe> · <https://www.designmd.co/d/stripe>

1. **Typographic restraint.** Two weights carry nearly everything — 300 for body and
   headings, 400 for UI and buttons — "confident restraint rather than corporate
   shouting."
2. **Density is zoned, not global.** "Financial data displays (tables, charts) are
   tightly packed, but the UI chrome around them is generously spaced" — a
   spreadsheet in a beautiful frame. **This is the resolution of nova-vs-maia:**
   dense tables inside a generous shell.
3. **Trust comes from hierarchy.** Key metrics surfaced rather than "buried in data."
4. **Navigate by job, not by system.** Navigation is "organized around user jobs
   rather than system architecture."
5. **Accent:** a single indigo, `#533AFD`. <https://www.shadcn.io/design/stripe>

### Notion

<https://raw.studio/blog/how-notion-ux-converts-100-million-users/> ·
<https://memorable.design/empty-state-design-examples/>

1. **Progressive disclosure.** "Users only explore advanced features when they are
   ready" — the balance between simplicity and flexibility is cited as a primary
   growth driver.
2. **Empty state = onboarding.** Notion "filled its empty state with educational
   content that doubles as both demo content and a type of onboarding checklist."
3. **Empty state shows the filled state.** The template picker gives "each template
   preview showing what a filled-out page looks like" — show the destination, not a
   shrug.
4. **Reassuring nulls.** With no notifications, users get "a short, unobtrusive
   message that confirms everything's up to date." For a security scanner, "nothing
   found" is the *good* result and must read that way.
5. **No-results is a suggestion, not a dead end** — Notion "gently suggests an
   alternative."

### Vercel / Geist

<https://vercel.com/geist/introduction> · <https://vercel.com/font>

1. Geist is "Vercel's design system for building consistent web experiences," covering
   colours, typography, materials, layout, and React components.
2. Foundations are split into **Colors, Typography, Materials, Grid** — where
   *Materials* explicitly bundles "radii, fills, strokes, shadows" as presets. Naming
   that group is a useful convention for an agent-readable doc.
3. Colour is described as a "high-contrast, accessible palette" — accessibility framed
   as a foundation, not a checklist item.
4. Components ship as `@vercel/geistcn`, and every doc page is available as Markdown
   by appending `.md` to the URL — i.e. the design system is machine-readable by design.
5. Typography is Geist Sans + Geist Mono, built on "simplicity, minimalism, and speed"
   with Swiss-design roots. <https://vercel.com/font>

---

## 6. Type candidates

### Sans

| Face | License | Google Fonts | Fontsource (npm) | Used by |
|---|---|---|---|---|
| **Inter** | **OFL 1.1** <https://rsms.me/inter/> | Yes | `@fontsource-variable/inter@5.3.0`, OFL-1.1 <https://www.npmjs.com/package/@fontsource-variable/inter> | **Linear** (Inter + Inter Display) <https://linear.app/blog/how-we-redesigned-the-linear-ui> |
| **Geist Sans** | **OFL** <https://vercel.com/font> | Yes (reduced glyph set) | `@fontsource/geist-sans@5.3.0`, OFL-1.1 — **no `@fontsource-variable/geist-sans`** | Vercel / Geist <https://vercel.com/geist/introduction> |
| **System stack** | n/a | n/a | n/a | **T3 Code** — `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif` <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css> |
| **OpenAI Sans** | **Proprietary — unavailable** | No | No | Codex / ChatGPT §1 |

Notes:

- **Inter** carries 2,000+ glyphs across 147 languages, weights 100–900, and ships two
  optical sizes: a *text* cut with a tall x-height for legibility and a *display* cut
  with "clean lines and smooth curves" for large sizes. Weights 100/400/900 are
  separately drawn masters. Available by direct download, Google Fonts, npm, and
  Fontsource. <https://rsms.me/inter/>
- **Vercel's own guidance** is that npm is the recommended channel for Geist because
  Google Fonts carries "limited glyph sets." <https://vercel.com/font>
- The **system stack costs zero bytes and never FOUTs**, and it is what the closest
  Codex-adjacent app actually ships. It is the lowest-risk option, but it will not
  deliver the *rounded, circular* character of §1 — it renders as SF on macOS and
  Segoe on Windows.
- If the round/bubbly character is the priority, two OFL geometric-humanist faces are
  on Fontsource with variable builds and are much closer to OpenAI Sans in feel:
  `@fontsource-variable/figtree@5.3.0` (OFL-1.1) and
  `@fontsource-variable/nunito@5.3.0` (OFL-1.1).
  <https://www.npmjs.com/package/@fontsource-variable/figtree> ·
  <https://www.npmjs.com/package/@fontsource-variable/nunito>

### Mono — for inline technical data only (IPs, MACs, ports, hashes)

| Face | License | Fontsource | Note |
|---|---|---|---|
| **Geist Mono** | OFL <https://vercel.com/font> | `@fontsource-variable/geist-mono@5.3.0`, OFL-1.1 | Designed first, "prioritized readability in coding environments"; pairs with Geist Sans |
| **JetBrains Mono** | OFL | `@fontsource-variable/jetbrains-mono@5.3.0`, OFL-1.1 | Variable build available |
| **IBM Plex Mono** | OFL | `@fontsource/ibm-plex-mono` only — **no `@fontsource-variable/` build** | Static weights only; heavier install |
| **System mono** | n/a | n/a | T3 Code: `ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace` |

Verified 2026-09-02 against the npm registry. `@fontsource-variable/geist-sans` and
`@fontsource-variable/ibm-plex-mono` return 404 — those two have no variable package.

---

## 7. Motion

### shadcn / Tailwind v4 baseline

- shadcn has **deprecated `tailwindcss-animate` in favour of `tw-animate-css`**, and
  new projects install it by default. It is pure CSS, no JS plugin.
  <https://ui.shadcn.com/docs/tailwind-v4> ·
  <https://github.com/Wombosvideo/tw-animate-css>
- `tw-animate-css` defaults: **duration 150ms**, easing **`ease`**.
  <https://www.npmjs.com/package/tw-animate-css>
- Accordion animations default to **200ms `ease-out`**, and depend on
  `--radix-accordion-content-height`.
  <https://github.com/Wombosvideo/tw-animate-css/blob/main/docs/animations/accordion.md>
- Presets shipped: `accordion-down`, `accordion-up`, `caret-blink`, plus enter/exit
  utilities; duration, delay and easing are tunable per-utility.
  <https://www.shadcndirectory.com/products/shadcn_directory_npmjs_tw_animate_css/>

### Measured from T3 Code

<https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css>

- Shared-element move: **180ms** `cubic-bezier(0.4, 0, 0.2, 1)` (ease-in-out / standard)
- Exit of a departing headline: **130ms** `cubic-bezier(0.4, 0, 1, 1)` (ease-in) — exits
  are shorter than entrances
- Ambient status indicators: 2s–2.4s infinite, deliberately "duty-cycled" to spare the
  compositor
- Theme changes suppress *all* transitions via a `.no-transitions` class

### Practitioner guidance (Emil Kowalski)

<https://emilkowal.ski/ui/7-practical-animation-tips>

- "UI animations should generally stay **under `300ms`**."
- **180ms** for a select "feels more responsive" than 400ms; ~300ms for dropdowns;
  **125ms** for tooltips.
- Use **`ease-out`** for elements entering or leaving — it "provides a feeling of
  responsiveness." **Avoid `ease-in` for UI**: it speeds up at the end, the opposite of
  what you want.
- **Never animate from `scale(0)`** — start at 0.9+, or "it looks like the element
  comes out of nowhere." Buttons scale to `0.97` on `:active`.
- **Remove animations users see hundreds of times a day** — repetition makes an
  interface feel slower. Directly relevant to a scan list that updates constantly.

### Motion for users who need less of it

- **WCAG 2.3.3 Animation from Interactions** (Level AAA): *"Motion animation triggered
  by interaction can be disabled, unless the animation is essential to the
  functionality or the information being conveyed."*
  <https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html>
- The audience is people with **vestibular disorders**, who can experience "nausea,
  migraine headaches, and potentially needing bed rest to recover" from unnecessary
  motion. Respect the **`prefers-reduced-motion`** media query; the recommended
  approaches are removing non-essential animation, offering a control, or honouring the
  OS preference. Same URL.
- A common heuristic: motion beyond roughly **200ms** reads as deliberate and needs a
  reduced-motion path. <https://www.ruixen.com/blog/motion-design-tokens>
- Motion belongs in tokens, not in ad-hoc classes: duration (fast 150 / medium 300 /
  slow 600) and easing (standard, emphasized, decelerate, accelerate) as first-class
  entries, so "retuning a theme retunes every animation in one place."
  <https://www.ruixen.com/blog/motion-design-tokens> · <https://helix-ui.com/docs/tokens/motion/>
- Material 3 publishes a full easing/duration token spec worth cribbing structure from:
  <https://m3.material.io/styles/motion/easing-and-duration/tokens-specs>

---

## 8. Severity / status colour for a lay audience

### The tinted-pill pattern: soft background + darker text

**GitHub Primer** formalises this as an **emphasis vs muted** pair per semantic family,
applied consistently to background, foreground and border tokens.
<https://primer.style/product/primitives/color/>

| Family | Emphasis (bold fill) | Muted (soft tint) |
|---|---|---|
| Success | `#1F883D` | `#DAFBE1` |
| Danger | `#CF222E` | `#FFEBE9` |
| Attention | `#9A6700` | `#FFF8C5` |
| Done | `#8250DF` | `#FBEFFF` |

Note Primer's *attention* emphasis is a dark yellow-brown (`#9A6700`), not a bright
yellow — bright yellow cannot reach AA on white.

**T3 Code** reaches the same result generatively: `500` for the fill, `700` for the
text, and `color-mix(in srgb, <hue> 8%, transparent)` for the surface. §2.

**shadcn Badge** ships `default | secondary | destructive | outline` variants and is
the component to extend with the severity set.
<https://ui.shadcn.com/docs/components/badge>

**Linear** solves the "is red as loud as yellow?" problem with LCH, so equal lightness
values read equally light across hues — the right model for an ordered severity ramp.
<https://linear.app/blog/how-we-redesigned-the-linear-ui>

### Contrast, computed 2026-09-02 (WCAG 2.x relative luminance)

Accent candidates as text/icons **on white**:

| Colour | vs `#FFFFFF` | vs `#FAFAFA` | AA normal (4.5) | AA large (3.0) |
|---|---|---|---|---|
| `#1D4ED8` blue-700 | **6.70** | 6.42 | PASS | PASS |
| `#1B4ED8` *T3 Code primary* | **6.66** | 6.38 | PASS | PASS |
| `#4F46E5` indigo-600 | **6.29** | 6.02 | PASS | PASS |
| `#533AFD` *Stripe indigo* | **6.19** | 5.93 | PASS | PASS |
| `#7C3AED` violet-600 | **5.70** | 5.46 | PASS | PASS |
| `#2563EB` blue-600 | **5.17** | 4.95 | PASS | PASS |
| `#0284C7` sky-600 | 4.10 | 3.92 | **fail** | PASS |
| `#059669` emerald-600 | 3.77 | 3.61 | **fail** | PASS |
| `#0D9488` teal-600 | 3.74 | 3.59 | **fail** | PASS |

Text and neutrals on white: `#0F172A` slate-900 = **17.85**, `#475569` slate-600 =
**7.58**, `#64748B` slate-500 = **4.76** (passes AA, but it is the floor — do not go
lighter for body text; cf. Linear darkening its greys).

Proposed severity pills, **`700`-weight text on a `100`-weight tint**, all AA at
normal size:

| Severity | Text | Tint | Ratio | Tint vs white |
|---|---|---|---|---|
| Critical / danger | `#991B1B` | `#FEE2E2` | **6.80** | 1.22 |
| Warning | `#854D0E` | `#FEF9C3` | **6.38** | 1.07 |
| Medium / notice | `#9A3412` | `#FFEDD5` | **6.38** | 1.15 |
| Info | `#1E40AF` | `#DBEAFE` | **7.15** | 1.22 |
| Safe / resolved | `#166534` | `#DCFCE7` | **6.49** | 1.10 |
| Neutral / unknown | `#334155` | `#F1F5F9` | **9.45** | 1.10 |

Every tint sits at 1.07–1.23 against white, so the pills stay soft and the *text*
carries the contrast. Two caveats for a lay audience:

- **Never encode severity in colour alone** — pair each pill with a Lucide icon and a
  plain-English word. Primer's emphasis/muted split assumes a label is present.
  <https://primer.style/product/primitives/color/>
- A tint at ~1.1:1 against white is invisible as a *shape*. Give pills a matching
  `border` at the `200` step, or they vanish on the `#FCFCFC` canvas.

---

## 9. Design systems written for LLM coding agents

1. **`google-labs-code/design.md`** — <https://github.com/google-labs-code/design.md>
   (27.6k stars). *"A format specification for describing a visual identity to coding
   agents."* YAML front matter holds machine-readable tokens (`colors`, `typography`,
   `rounded`, `spacing`, `components`); the Markdown body holds the rationale — "tokens
   give agents exact values, prose tells them *why*." Ships a linter,
   `npx @google/design.md lint DESIGN.md`, which emits structured JSON findings
   **including WCAG contrast checks**, plus `diff` for token-level regressions between
   versions. Spec at `docs/spec.md`; worked examples under `examples/`.
   **This is the closest thing to an off-the-shelf answer to the owner's request.**
2. **Vercel — "Teaching agents product design"** —
   <https://vercel.com/blog/teaching-agents-product-design-at-vercel>. `AGENTS.md`
   states *when* to load the skill and in what order; `SKILL.md` holds the workflow;
   reference files split into `product-judgment.md`, `interface-quality.md`,
   `resilience.md`, `copy.md`. Rules are observable and testable, not vague —
   *"Destructive CTAs follow Verb + Noun. Never use Confirm, OK, or a bare verb"*;
   *"Suggest Radio buttons when Select has 2–3 static options."* Deterministic checks
   (off-grid spacing, nested modals, missing accessible names) go to **linters**;
   judgment calls go to the skill. An `exemplars/` directory records decisions from
   shipped PRs and `coverage-gaps.md` lists what has no standard yet.
3. **shadcn MCP server** — <https://ui.shadcn.com/docs/mcp>. The delivery mechanism:
   agents browse, search and install from any shadcn-compatible registry
   conversationally, so the design system is *reachable* rather than merely written down.
4. **`vercel/ai` AGENTS.md** — <https://github.com/vercel/ai/blob/main/AGENTS.md>. A
   real, public example of the file format in a large repo.
5. **Codex issue #20878** — <https://github.com/openai/codex/issues/20878>. Argues
   Codex needs a frontend design system to produce consistent UI; useful as evidence
   of the failure mode we are trying to avoid, and mirrored by the community
   `AGENTS.md`/`DESIGN.md` convention at <https://codex-design.ai/>.
6. **Vercel Agent Skills** — <https://vercel.com/docs/agent-resources/skills> — the
   productised form of #2.

---

## Synthesis — proposed direction

Each bullet cites the reference that supports it. **No code, no decisions taken — this
is a proposal for the owner to accept, amend or reject.**

1. **Switch the shadcn style from `radix-nova` to `radix-maia`.** `nova` is defined as
   *"tighter padding and reduced margins"* for dense dashboards; `maia` is *"larger
   border radii — often fully rounded — with generous spacing"* for *"consumer products
   and softer aesthetics."* The current setting actively fights the brief.
   <https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira>

2. **Resolve bubbly-vs-data the way Stripe does: zone the density.** Keep tables of
   findings tight; make everything around them generous — *"financial data displays are
   tightly packed, but the UI chrome around them is generously spaced."* This is why
   `maia` globally does not mean unreadable tables.
   <https://www.925studios.co/blog/stripe-dashboard-design-breakdown>

3. **Face: Inter Variable via Fontsource** (`@fontsource-variable/inter@5.3.0`,
   OFL-1.1) as the default. It is the safest choice, is what Linear ships, and its
   tall-x-height text cut is built for UI legibility. <https://rsms.me/inter/> ·
   <https://linear.app/blog/how-we-redesigned-the-linear-ui>

4. **If "round and friendly" outranks "safe", the alternative is Figtree or Nunito
   Variable** (both OFL-1.1, both with variable Fontsource builds). OpenAI Sans — the
   actual Codex face, with its *"friendly and circular"* round `O` — is bespoke and
   cannot be licensed, so these are the closest legal approximations.
   <https://www.wallpaper.com/tech/openai-has-undergone-its-first-ever-rebrand-giving-fresh-life-to-chatgpt-interactions> ·
   <https://www.npmjs.com/package/@fontsource-variable/figtree>

5. **One family, two cuts — never two families.** Linear gets expression from *Inter
   Display* for headings and plain *Inter* for everything else. The community Codex
   rule is the same: "at most two typefaces, one accent color."
   <https://linear.app/blog/how-we-redesigned-the-linear-ui> · <https://codex-design.ai/>

6. **Mono is quarantined to inline technical data** — IPs, MACs, ports, hashes — never
   body copy, never headings. Geist Mono Variable (`@fontsource-variable/geist-mono`,
   OFL-1.1) or the zero-cost system stack T3 Code uses. Monospace + zero radius is the
   `lyra` "dev tool" look we are leaving. <https://vercel.com/font> ·
   <https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira>

7. **Raise contrast, do not lower it.** Linear explicitly made "text and neutral icons
   darker in light mode." Body text at `#0F172A` (17.85:1 on white); secondary at
   `#475569` (7.58:1); `#64748B` (4.76:1) is the hard floor. Pale-grey text is the most
   common way a "friendly minimal" UI becomes unusable.
   <https://linear.app/blog/how-we-redesigned-the-linear-ui> — ratios computed §8

8. **Canvas/card: near-white canvas, pure-white cards, one step darker for the
   sidebar** — not a grey canvas. T3 Code invents a `zinc-25` step
   (`oklch(99.2% 0 0)` = `#FCFCFC`) for the canvas, uses `#FFFFFF` for cards and
   popovers, and `#FAFAFA` (`zinc-50`) for the sidebar. The delta is deliberately tiny;
   `border` at `#E4E4E7` does the separating.
   <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css>

9. **Radius: `--radius: 0.75rem` (12px)**, one notch above T3 Code's measured
   `0.625rem` (10px) because we are choosing `maia` where they chose `mira`. Derive the
   scale with the documented shadcn multipliers (sm 0.6× · md 0.8× · lg 1× · xl 1.4× ·
   2xl 1.8×), and pick *one* derivation form — shadcn's multiplicative one, not
   T3 Code's additive `calc()` — so agents cannot mix them.
   <https://ui.shadcn.com/docs/theming> · T3 Code's `--radius` §2

10. **Add a separate `--control-radius`** for sidebar rows, toolbar buttons, tooltips
    and the command palette, exactly as T3 Code does, "so sidebar, palette, tooltip and
    toolbar controls cannot quietly drift apart" — small controls at the card radius
    look bloated. <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css>

11. **Accent: pick one blue and use it sparingly.** Three AA-passing candidates on
    white — **`#1D4ED8`** blue-700 (**6.70:1**, and effectively T3 Code's measured
    `#1B4ED8`), **`#4F46E5`** indigo-600 (**6.29:1**), **`#533AFD`** Stripe indigo
    (**6.19:1**). `#2563EB` blue-600 (5.17:1) also passes and reads friendlier/lighter.
    **Reject** `#0D9488` teal-600 (3.74) and `#059669` emerald-600 (3.77) — large-text
    only. Contrast computed §8; Stripe's indigo <https://www.shadcn.io/design/stripe>

12. **Keep the accent out of the greys.** Linear reduced "how much chrome (blue in our
    case) was used in the calculations" for a "more neutral and timeless appearance";
    Beautiful UI states the same shape — "cool, blue-tinted neutrals, solid hairline
    borders, **one blue accent**, and semantic colors used sparingly." Blue is for the
    primary action, not the furniture.
    <https://linear.app/blog/how-we-redesigned-the-linear-ui> · <https://www.beautifului.dev/>

13. **Severity as tinted pills: `700` text on a `100` tint, plus a `200` border, plus
    an icon, plus a plain-English word.** Danger `#991B1B`/`#FEE2E2` (6.80:1), warning
    `#854D0E`/`#FEF9C3` (6.38), medium `#9A3412`/`#FFEDD5` (6.38), info
    `#1E40AF`/`#DBEAFE` (7.15), safe `#166534`/`#DCFCE7` (6.49), neutral
    `#334155`/`#F1F5F9` (9.45) — all AA at normal size, all tints ≤1.23:1 on white so
    they need the border to be visible on a `#FCFCFC` canvas. Mirrors Primer's
    emphasis/muted split. <https://primer.style/product/primitives/color/> — ratios §8

14. **Generate the severity surfaces rather than hand-picking them.** T3 Code derives
    every status surface from one hue with
    `color-mix(in srgb, var(--warning) 8%, transparent)` and pairs a `500` fill with a
    `700` foreground. Fewer tokens is fewer things an agent can get wrong.
    <https://github.com/pingdotgg/t3code/blob/main/apps/web/src/index.css>

15. **Icons stay Lucide.** It is already the project's set, it is the `iconLibrary`
    T3 Code declares in `components.json`, and it is a first-class option in the shadcn
    config schema — no migration cost, and it is the outline style that reads friendly
    at 16–20px. <https://github.com/pingdotgg/t3code/blob/main/apps/web/components.json> ·
    <https://ui.shadcn.com/docs/components-json>

16. **Motion tokens, not ad-hoc classes.** Three durations — **125ms** (tooltips),
    **180ms** (most transitions, the value T3 Code ships and Emil Kowalski calls more
    responsive than 400ms), **300ms** (the ceiling: "UI animations should generally stay
    under 300ms"). Easing: `ease-out` for entrances, a faster `ease-in` for exits
    (T3 Code: 180ms in / 130ms out). Never `ease-in` for an entrance.
    <https://emilkowal.ski/ui/7-practical-animation-tips> · T3 Code §2 ·
    <https://www.ruixen.com/blog/motion-design-tokens>

17. **`prefers-reduced-motion` is mandatory, not a nice-to-have.** WCAG 2.3.3:
    *"Motion animation triggered by interaction can be disabled, unless the animation
    is essential."* Unnecessary motion can cause "nausea, migraine headaches, and
    potentially needing bed rest" for people with vestibular disorders. Also copy
    T3 Code's `.no-transitions` escape hatch for theme swaps.
    <https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html>

18. **Animate the rare, not the constant.** "Remove animations users see hundreds of
    times a day" — a live scan list must not animate every row. Reserve motion for scan
    start/finish and for state changes the owner needs to notice.
    <https://emilkowal.ski/ui/7-practical-animation-tips>

19. **Low text is a vocabulary problem before it is a layout problem.** Basecamp's
    single biggest simplification was that "the list of terms used shrunk dramatically";
    they use "the same language across the interface" and ban lingo outright. Decide the
    owner-facing word for *device*, *finding*, *scan*, *risk* — one word each — and put
    that glossary in the design doc. <https://basecamp.com/guides/how-we-communicate> ·
    <https://www.designprinciplesftw.com/collections/37-signals-principles>

20. **Empty states carry the onboarding, and "nothing found" must read as good news.**
    Notion's empty state doubles as "demo content and a type of onboarding checklist,"
    previews show "what a filled-out page looks like," and a clean notification state
    gets "a short, unobtrusive message that confirms everything's up to date." For a
    security scanner that last pattern is the whole product's happy path.
    <https://memorable.design/empty-state-design-examples/> ·
    <https://raw.studio/blog/how-notion-ux-converts-100-million-users/>

21. **Write the system as a `DESIGN.md` in the Google Labs format**, and run
    `npx @google/design.md lint DESIGN.md` in CI. YAML front matter for tokens, prose
    for rationale — "tokens give agents exact values, prose tells them *why*" — and the
    linter checks WCAG contrast and token references automatically, so bullets 7/11/13
    above stay true as the palette moves.
    <https://github.com/google-labs-code/design.md>

22. **Make the rules observable, and split them by enforcer.** Vercel sends
    deterministic checks (off-grid spacing, nested modals, missing accessible names) to
    linters and judgment calls to the agent skill, and writes rules as testable
    statements — *"Destructive CTAs follow Verb + Noun. Never use Confirm, OK, or a bare
    verb."* Add an `exemplars/` folder from shipped PRs and a `coverage-gaps.md`.
    <https://vercel.com/blog/teaching-agents-product-design-at-vercel>

23. **Wire the shadcn MCP server so agents can reach the registry.** A written system
    an agent cannot query is half a system; with the MCP server agents browse, search
    and install components conversationally, and it works against third-party registries
    such as Beautiful UI's (`https://www.beautifului.dev/r/registry.json`, MIT).
    <https://ui.shadcn.com/docs/mcp> · <https://www.beautifului.dev/>

24. **Steal four component shapes from Beautiful UI, ignore the chat ones**: records
    tables and filter tables (device/finding lists), task rows (scan progress), insight
    cards (the "here's what we found" summary), approval cards (confirm a risky action).
    Dmitri is not a chat app. <https://www.beautifului.dev/>

25. **Treat contrast and font stacks as tested code.** T3 Code ships
    `appearanceContrast.ts` and `appearanceFonts.ts` each with a unit-test twin — a
    precedent worth following, and consistent with Geist framing accessibility as a
    foundation rather than a checklist.
    <https://github.com/pingdotgg/t3code/tree/main/apps/web/src> ·
    <https://vercel.com/geist/introduction>

---

## Open questions for the owner

1. **`radix-maia` or stay on `radix-nova`?** Bullets 1–2. This is the single decision
   that most affects how "bubbly" the result feels.
2. **Inter (safe, Linear-proven) or Figtree/Nunito (rounder, closer to OpenAI Sans)?**
   Bullets 3–4.
3. **Which accent** — `#1D4ED8`, `#4F46E5`, `#533AFD`, or the friendlier `#2563EB`?
   Bullet 11.
4. **Does `DESIGN.md` become the authored artefact** for DMI-131, with the linter in
   CI? Bullet 21.
