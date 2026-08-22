# ARCHITECTURE — Frontend Foundations guardrails and the UI defects they prevent

> Implements `TRUTH.md` (DMI-107, validated 2026-08-18, plus the folded-in backend item
> decided 2026-08-21). Nothing in TRUTH.md is re-decided here. Where TRUTH.md and this
> document disagree, TRUTH.md wins.
>
> **No `INTEGRATION.md`.** The backend item is a self-contained configuration default with
> no new cross-layer contract: no route, schema, or generated type changes. The frontend
> half never crosses a layer boundary at all.

---

## 1. System context

This feature does not touch the scan pipeline (discovery → port scan → NSE → `ScanPayload` →
TUI/persistence). It sits in two places, and they are independent of each other:

```
                    ┌─────────────────────────────────────────────────────┐
   authoring time   │  docs/ui/SCREENS.md §Foundations   (the written rule)│
                    │            ↓ inherited by                            │
                    │  .claude/skills/frontend-conventions/  (agent rule)  │
                    │  .claude/agents/frontend-design-agent.md             │
                    │  .claude/agents/frontend-code-reviewer.md            │
                    │  .claude/skills/remediate/            (feedback in)  │
                    └─────────────────────────────────────────────────────┘
                                         ↓ enforced by
                    ┌─────────────────────────────────────────────────────┐
     lint time      │  frontend/eslint.config.js                          │
                    │    → frontend/eslint-rules/*.js   (4 local rules)    │
                    └─────────────────────────────────────────────────────┘
                                         ↓ constrains
                    ┌─────────────────────────────────────────────────────┐
     run time       │  frontend/src/index.css        (the token set)      │
                    │  frontend/src/components/**    (shell + primitives) │
                    │  frontend/src/pages/**         (screens)            │
                    └─────────────────────────────────────────────────────┘

   ── unrelated to the above ──────────────────────────────────────────────
                    │  backend/src/api/core/config.py  (CORS default)     │
                    │    → api/middleware.py:build_cors_middleware_kwargs │
                    │    → api/main.py: NoContentCorsMiddleware           │
                    └─────────────────────────────────────────────────────┘
```

No new hardware, daemon, or external tooling. **No `HUMAN_INFRA_REQUIRED`.**
No new runtime or development dependency, per TRUTH rule 7 and Out-of-scope.

---

## 2. Decisions taken here (and what they rule out)

| # | Decision | Rejected alternative | Why |
|---|----------|---------------------|-----|
| D1 | Four **local ESLint rule modules** under `frontend/eslint-rules/`, registered as an inline plugin in `eslint.config.js` | `no-restricted-syntax` with esquery selectors | See §3.1 |
| D2 | The **three** new tokens go in the existing **`@theme inline`** block; **none** in `:root`. The 720px prose token is **not declared** | a `:root` declaration + `@theme` alias; a fourth `--container-prose` token | See §4, §4.1 |
| D3 | *Withdrawn 2026-08-22.* A dev-only `/styleguide` route was specified here and is no longer in scope (TRUTH rules 10–11) | — | See §6 |
| D4 | The activity disclosure becomes `frontend/src/components/Disclosure.tsx` — **not** `components/ui/` | `components/ui/disclosure.tsx` | See §7.5 |
| D5 | The password modal **consumes the existing `DialogShell`**; no shell is written or extracted | a new modal shell | See §7.6 |
| D6 | Backend CORS default becomes `""` (empty), not a required field | required field with no default | See §8 |

---

## 3. The ESLint rules (the core engineering problem)

### 3.1 Mechanism — local rule modules, not `no-restricted-syntax`

`no-restricted-syntax` was evaluated and **rejected**. It fails three of the four things the
acceptance criteria demand:

| Requirement | `no-restricted-syntax` | Local rule module |
|---|---|---|
| Message *names the token to use instead* (AC "Raw type size rejected") | Message is a fixed string per selector entry, so one entry per raw size × per context; the mapping cannot be computed | A lookup table in the rule; one message template |
| Scope by file path | ✅ (flat-config `files`/`ignores` on a config object) | ✅ (same mechanism) |
| Read `className` **and** `cn(...)`/`cva(...)` arguments **and** template literals | esquery has no bracket-aware tokenizer; a class string is one `Literal` whose *value* must be split on whitespace and on `:` at bracket depth 0 before any token can be judged. A regex over the whole literal cannot do this, which is exactly how `has-data-[state=open]` gets mistaken for an arbitrary value | ✅ — the rule tokenizes properly |
| No new dependency (TRUTH rule 7) | ✅ | ✅ — plain `.js` files in this repo, imported by `eslint.config.js`. ESLint flat config accepts an **inline plugin object**; nothing is installed |

A regex-only approach would also have to fire on every string literal in the file, which
means `data-testid="settings-activity-info"`, copy strings in `lib/copy.ts`, and
`aria-describedby` id lists all become candidates. The local rule restricts itself to
authored class strings (§3.2) and never sees them.

**Registration** in `frontend/eslint.config.js`:

```js
import local from './eslint-rules/index.js'      // { rules: { … } }

// … existing config object unchanged …
{
  files: ['src/**/*.{ts,tsx}'],
  ignores: [
    'src/components/ui/**',        // vendored shadcn source  (TRUTH rule 8)
    'src/**/*.test.{ts,tsx}',      // fixtures, not shipped controls (TRUTH rule 8)
    'src/test/**',                 // test harness: setup, MSW handlers, render helper
  ],
  plugins: { local },
  rules: {
    'local/no-arbitrary-utility': 'error',
    'local/no-raw-type-size': 'error',
    'local/spacing-scale': 'error',
    'local/no-bare-interactive': 'error',
  },
}
```

The exemption list is exactly TRUTH rule 8 and nothing more. `src/test/**` is a judgement
call recorded here: `setup.ts`, `mswHandlers.ts` and `renderWithProviders.tsx` are test-only
support code in the same class as a `*.test.tsx` file, and none of it ships.

`frontend/eslint-rules/` sits **outside** `src/`, so it is outside both `npm run lint`
(`eslint src`) and `npm run format:check` (`prettier --check src`). That is deliberate and
matches `eslint.config.js`, which is already outside both. Do not widen either script — a
wider `prettier --check` is a repo-wide formatter run by another name, which
`.claude/CLAUDE.md` forbids.

### 3.2 The shared tokenizer — `frontend/eslint-rules/class-strings.js`

All four style rules share one helper so the false-positive analysis is done once.

**A node is an authored class string if and only if** it is a `Literal` with a string value,
or a `TemplateElement`, and *some ancestor* is one of:

1. a `JSXAttribute` whose name is `className` (covers `className="…"` and
   `className={\`… ${x}\`}` — e.g. `DialogShell.tsx:70-72`), or
2. a `CallExpression` whose callee is an `Identifier` named `cn`, `clsx`, `twMerge` or `cva`
   (covers `TopBar.tsx:7-11`'s `navLinkClass`, and every `cva` variant map).

Everything else — `data-testid`, `aria-describedby`, `lib/copy.ts`, MSW URLs, `id` strings —
is invisible to these rules.

**Token extraction**, applied to each class string:

1. Split the value on whitespace.
2. Per token: strip a leading `!` (important) and a leading `-` (negative).
3. Split on `:` **only at bracket depth 0** (depth counts `[`/`]` and `(`/`)`).
   The **last** segment is the *utility*; every earlier segment is a *variant*.
4. Judge the **utility segment only**.

Step 3 is the whole false-positive defence. It is why
`has-data-[icon=inline-end]:pr-2`, `in-data-[slot=button-group]:rounded-lg`,
`not-aria-[haspopup]:translate-y-px`, `group-data-[state=open]:rotate-90` and
`[&_svg:not([class*='size-'])]:size-4` are **not** arbitrary-value utilities: their brackets
live in a variant segment. A variant prefix is not an arbitrary *value*.

### 3.3 `local/no-arbitrary-utility`

**Reports** a utility segment containing `[` … `]`.

Message:

> `{{token}}` is an arbitrary value. Use a named token: widths are `max-w-frame` or
> `max-w-form`, spacing is a scale step (`1 2 3 4 6 8 12 16 24`), type is a
> `text-title-*` / `text-body-*` / `text-caption-*` / `text-nav` token. Add the token to
> `frontend/src/index.css` if it does not exist yet.

**Clears 3 violations** — `components/AppShell.tsx:10`, `components/AuthShell.tsx:7`,
`components/TopBar.tsx:18`, all `max-w-[45rem]`.

The ~20 bracketed strings in `components/ui/**` (`rounded-[min(var(--radius-md),10px)]`,
`bg-[color-mix(…)]`, `text-[0.8rem]`, and the variant-prefix ones above) are out of scope by
the path exemption; the variant-prefix subset would pass the rule anyway.

### 3.4 `local/no-raw-type-size`

**Reports** a utility segment matching `^text-(xs|sm|base|lg|xl|[2-9]xl)$` after stripping a
`/…` line-height modifier.

Anchored alternation is what keeps `text-title-sm`, `text-body-md`, `text-caption-md`,
`text-nav`, and every colour utility (`text-muted-foreground`, `text-destructive`,
`text-accent`) passing. They are not `text-sm`.

Mapping table, used to build the message:

| Raw | px | Scale token | Note |
|---|---|---|---|
| `text-xs` | 12 | `text-caption-md` | exact |
| `text-sm` | 14 | `text-body-md` | exact — **the only mapping this feature exercises** |
| `text-base` | 16 | `text-title-xs` | exact px, but 16px non-title has no token; message says so |
| `text-lg` | 18 | — | no token; message says to name one or pick the nearest |
| `text-xl` | 20 | `text-title-sm` | exact |
| `text-2xl`+ | — | — | no token |

Message with a mapping:

> `text-sm` is a framework size, not a scale token. Use `text-body-md` (same 14px).

Message without one:

> `text-lg` is a framework size and no scale token matches 18px. Pick the nearest
> `text-title-*` / `text-body-*` / `text-caption-*` token, or add one to
> `frontend/src/index.css`.

**Clears 29 violations**, verified by grep, all of them `text-sm`:

| File | Count |
|---|---|
| `frontend/src/pages/AcceptInvite.tsx` | 10 |
| `frontend/src/pages/Settings.tsx` | 6 |
| `frontend/src/pages/ResetPassword.tsx` | 6 |
| `frontend/src/pages/ForgotPassword.tsx` | 4 |
| `frontend/src/pages/Login.tsx` | 3 |

All 29 become `text-body-md` = `0.875rem` = 14px. **Computed font size is unchanged**, which
is the AC "Type-token swap is invisible".

The 6 remaining raw sizes (`ui/button.tsx` ×2, `ui/input.tsx` ×3, `ui/label.tsx` ×1) are
exempt and stay as they are. 35 total − 29 = 6; this is the arithmetic that proves the
exemption scope is right rather than convenient.

### 3.5 `local/spacing-scale`

**Reports** a utility segment matching
`^(m|p)(t|r|b|l|x|y|s|e)?-(.+)$` or `^(gap|gap-x|gap-y|space-x|space-y)-(.+)$`
whose value is not one of `0 1 2 3 4 6 8 12 16 24 px auto`.

Tokens containing `[` are **skipped** — `local/no-arbitrary-utility` owns those, and one
violation should produce one error, not two.

Message:

> `{{token}}` is off the spacing scale. `SCREENS.md` §Spacing permits only
> `1 2 3 4 6 8 12 16 24` on Tailwind's 4px base.

**Clears 0 violations.** Verified by grep across `frontend/src` excluding
`components/ui/**`: the spacing scale is already obeyed 100%, exactly as TRUTH.md's narrative
states. The rule exists so the next drift is caught, and its AC ("Off-scale spacing rejected")
is satisfied by a fixture in the rule's own unit test, not by a source violation.

`ui/button.tsx`'s `gap-1.5`, `px-2.5`, `pr-1.5` are exempt by path.

### 3.6 `local/no-bare-interactive`

**Reports** a `JSXOpeningElement` whose name is the lowercase identifier `button`, `input`,
`select` or `textarea`.

**`<a>` is deliberately excluded.** React Router's `Link`/`NavLink` render the anchor, no
`components/ui/` primitive wraps one, and there is no bare `<a>` in app code today. Adding it
would be a rule with no violation to prevent and one plausible future false positive. If an
anchor primitive is ever written, add `a` then.

Message:

> `<{{name}}>` is a native control. Application screens compose the shared primitives —
> `Button` / `Input` / `Label` / `Select` from `@/components/ui/`, or a shared component
> under `@/components/` — so interactive state is specified in one place
> (`SCREENS.md` §Foundations, business rule 2).

**Clears 1 violation**: `frontend/src/pages/Settings.tsx:212`, the Activity disclosure —
exactly the control that feels broken. See §7.5 for how it is cleared.

The 14 bare `<button>`s in `*.test.tsx` fixtures are exempt by path. Without that exemption
the gate is unusable; TRUTH rule 8 says so and §3.1 encodes it.

### 3.7 False-positive risks — the full list

| Risk | Handled by |
|---|---|
| Variant-prefix brackets (`has-data-[…]`, `group-data-[…]`, `in-data-[…]`, `not-aria-[…]`, `[&_svg…]:`) mistaken for arbitrary values | Depth-0 `:` split; only the last segment is judged (§3.2 step 3) |
| `max-w-frame`, `max-w-frame`, `max-w-form` flagged as arbitrary | They contain no brackets; they are named tokens |
| `text-title-*` / `text-body-*` / `text-caption-*` / `text-nav` flagged as raw sizes | Anchored alternation in §3.4 |
| `text-muted-foreground` and other colour utilities flagged | Same anchor |
| `data-testid` / `aria-*` / `id` strings scanned at all | Class-string contexts only (§3.2) |
| Arbitrary values in non-class strings (MSW URLs, `lib/copy.ts`, regexes) | Same |
| Template-literal class strings missed (`DialogShell.tsx:70`) | `TemplateElement` is visited (§3.2) |
| `cva` variant maps missed (`ui/button.tsx`) | `cva` is a class-string callee (§3.2) — moot today via the path exemption, but correct for any future `cva` outside `ui/` |
| `mx-auto`, `p-px` flagged as off-scale | `auto` and `px` are in the allowed value set (§3.5) |
| Double-reporting `p-[13px]` | `spacing-scale` skips bracketed tokens (§3.5) |
| A `size-*` / `h-*` / `w-*` step off the scale | **Not covered.** These rules are the four TRUTH names them, no more. Simplicity first |

---

## 4. Token additions — `frontend/src/index.css`

**Three** tokens, all added to the **existing `@theme inline` block**, none to `:root`.

```css
@theme inline {
  /* … existing … */
  --container-frame: 70rem;   /* 1120px — the bar AND the page content */
  --container-form:  24rem;   /*  384px — a form / card column         */
  --text-nav:        0.6875rem; /* 11px — navigation only              */
}
```

> **Three, not four.** A 720px prose-column token was specified until the shell was resolved
> to **option C** on 2026-08-21 (`DESIGN.md` §4, §16 q0): the bar and the page content now
> share `--container-frame`, so nothing in the product is 720px and the token has no call
> site. §4.1 records why declaring it would have been a bug anyway.

**Why `@theme`, not `:root` — this is the Tailwind v4 trap.** A custom property declared in
`:root` alone is only a CSS variable; it registers in **no theme namespace**, so Tailwind
generates **no utility** for it. `max-w-frame` and `text-nav` would simply not exist and the
class would silently do nothing. Only variables declared inside `@theme` (or `@theme inline`)
register in a namespace: `--container-*` → `max-w-*` / `w-*` / `min-w-*` / `basis-*`, and
`--text-*` → `text-*`.

**Why `@theme inline` specifically:** `inline` only changes whether the generated utility
emits the literal value or a `var()` reference; both register the namespace. This file's
`:root` holds raw brand values that `@theme inline` then aliases (`--paper` → `--color-background`),
and its literal-valued tokens — `--text-title-lg: 2rem`, `--text-body-md: 0.875rem` — already
live directly inside `@theme inline`. These three are literal constants with nothing to alias,
so they join their neighbours. A `:root` indirection for a constant buys nothing.

### 4.1 Why the prose token is absent — the Tailwind v4 trap, measured

> **Measured by compiling Tailwind 4.3.3 against these exact tokens**, after two earlier
> drafts of the specs disagreed about what `--container-prose: 45rem` would do. An earlier
> draft of *this* document claimed it **overrides** the built-in `max-w-prose` and widens two
> Settings paragraphs. `DESIGN.md` §3 claimed it yields a **`max-w-prose-col`** utility. Both
> were plausible readings of the v4 namespace rules; **both are wrong.**

Tailwind v4 resolves `max-w-*` from **two** namespaces, and `--max-width-*` wins over
`--container-*` on a name collision. Tailwind ships `--max-width-prose: 65ch`
(`node_modules/tailwindcss/theme.css:509`) — note the namespace: it is **not**
`--container-prose`. Declaring our own `--container-prose: 45rem` would therefore override
nothing, and would emit no `max-w-` utility of its own.

Compiled output:

| Class | Emitted | Verdict |
|---|---|---|
| `.max-w-frame` | `max-width: 70rem` | ✅ shipped — no built-in named `frame` |
| `.max-w-form` | `max-width: 24rem` | ✅ shipped — no built-in named `form` |
| `.text-nav` | `font-size: 0.6875rem` | ✅ shipped |
| `.max-w-prose` | `max-width: 65ch` | the built-in, **unchanged by us** |
| `.max-w-prose-col` | *not generated* | `--container-prose` never produces this name |
| `.w-prose` / `.min-w-prose` | `45rem` | our value, but the wrong property |

**The trap this avoids:** an implementer writing `max-w-prose` on `AppShell`, expecting the
720px column, would silently have got **65ch ≈ 546px** — a ~24% narrowing inherited by every
screen, invisible without compiling.

**Option C removed the need for the token entirely**, and with it the naming decision that was
open at the approval gate. Two container tokens remain and neither collides with a built-in.

> **If a narrower content column ever returns**, the token comes back as **`--container-page`**
> (→ `max-w-page`, verified) or **`--max-width-prose-col`** (→ `max-w-prose-col`, verified) —
> **never** as `--container-prose`. Recorded so the trap is not re-entered.

**The nine existing `max-w-prose` call sites are untouched** by this feature — seven dialog
descriptions plus `pages/Settings.tsx:227,244`. They keep binding at 65ch, which is the
*reading measure* and a different job from a layout container. Nothing is deleted.

`--container-form: 24rem` is numerically identical to Tailwind's stock `--container-sm`
(24rem), so `max-w-form` and `max-w-sm` render the same. The auth card uses `max-w-form`
because **the name is the rule** (TRUTH business rule 3), not because the number differs.
`DialogShell`'s `max-w-sm` / `max-w-md` stay as they are — a dialog panel is not one of the
three named layout containers.

---

## 5. Clearing the 32 violations

Mechanical, and lands in the **same change as the rules** (TRUTH rule 9 — no commit is
knowingly red).

| Rule | Count | Change |
|---|---|---|
| `no-raw-type-size` | 29 | `text-sm` → `text-body-md` across 5 files in `pages/` (table in §3.4) |
| `no-arbitrary-utility` | 3 | `max-w-[45rem]` → **`max-w-frame`** in both `AppShell.tsx:10` and `TopBar.tsx:18` (option C makes them the same width); → `max-w-form` in `AuthShell.tsx:7` |
| `spacing-scale` | 0 | none |
| **Total** | **32** | the *mechanical* clearing. The AC "Tree is clean" counts **33** — the 33rd is `no-bare-interactive` at `Settings.tsx:212`, cleared in G5 (§5.1), not by a token swap. Lint exits zero only when all 33 are gone |

> Under option C both shell widths are `max-w-frame`, so there is no intermediate value to
> pass through. An earlier draft warned against landing a prose width first and widening it
> second, which would have been a temporary implementation —
> `.claude/CLAUDE.md` forbids. **Land `max-w-frame` directly** in the remediation change; the
> width change is the UI fix and it arrives with the guardrail. `AuthShell.tsx:7` likewise
> lands as `max-w-form` directly (§7.3).

### 5.1 The 33rd violation

`no-bare-interactive` finds `pages/Settings.tsx:212`. TRUTH counts 32 for the mechanical
clearing and describes this one separately, because clearing it is not a token swap — it
requires the `Disclosure` component to exist.

**Resolution, binding on the task breakdown:** `frontend/src/components/Disclosure.tsx` is a
**guardrail-phase artifact**, not a UI fix. It is built complete on first write — cursor,
hover, focus-visible, active, caret rotation, keyboard, `aria-expanded`/`aria-controls` — per
TRUTH business rule 1 and the no-temporary-code rule. `Settings.tsx` swaps its bare `<button>`
for it in the same change that enables `no-bare-interactive`. The UI-fix phase then only
*places* the Activity section (heading on its own line, section order); it does not build the
control.

---

## 6. The `/styleguide` route — withdrawn

> **Withdrawn 2026-08-22 at the refine gate** (TRUTH rules 10–11). This section specified a
> dev-only `/styleguide` page, an `import.meta.env.DEV` + `lazy()` route guard, and a
> `frontend/scripts/assert-no-styleguide.mjs` postbuild assertion that the guard held.
>
> DMI-107 asked for the page and the specs carried it faithfully. Guilherme withdrew it: the
> rendered preview the design agent now publishes (TRUTH rule 12) already serves the
> "judge the system in one look" need — it is what option C was selected from — and the human
> visual check (TRUTH rule 13) already covers drift across the five real screens. Three new
> files plus a build-script change were not worth their cost to the one person they served.
>
> **Nothing replaces it.** No `/styleguide` route, no `pages/Styleguide.tsx`, no
> `scripts/assert-no-styleguide.mjs`, no `DMITRI_STYLEGUIDE_SENTINEL`, and
> `frontend/package.json`'s `build` script is **not touched**. `frontend/src/App.tsx` is not
> touched either.
>
> The specification also carried an unresolved contradiction about this page — ARCHITECTURE
> put the route outside `RequireSession` with a no-session test, while `DESIGN.md` §9 drew the
> top bar on it and §16 q5 said it needed a session. Withdrawal dissolves that question; it is
> recorded so it is not re-opened by half.

---

## 7. UI component changes

`DESIGN.md` owns exact copy, mockups and `data-testid` values. This section owns structure,
file placement, and the contract each component exposes.

### 7.1 `frontend/src/components/TopBar.tsx`

> **Rewritten 2026-08-21 for option C** (`DESIGN.md` §4, §16 q0). An earlier draft specified a
> left-adjacent nav in a flex row with a 32px wordmark gap. Both are replaced: the nav is
> **centred**, permanently, and the 32px gap no longer exists as a measurement.

- Inner frame `max-w-[45rem]` → **`max-w-frame`** (70rem = 1120px). AC: "the wordmark sits at
  the frame's left edge".
- **The row becomes a three-column grid — `grid grid-cols-[1fr_auto_1fr]`** — with three direct
  children: the wordmark (`justify-self-start`), the `<nav>` (`justify-self-center`), and
  `Log out` (`justify-self-end`). The existing `bar-left` wrapper that grouped the wordmark
  with the nav is **removed**; they are now siblings in different columns.
- **Do not centre the nav with `justify-between` or `mx-auto` in a flex row.** Either centres
  it in the space the wordmark and button leave over, so it drifts whenever `Log out` changes
  width or `Users` appears for an admin and vanishes for a viewer. The `1fr auto 1fr` grid pins
  it to the frame's true centre. AC: "the navigation is centred on the bar"; AC: "a fourth
  destination … the navigation is still centred".
- The nav's own inter-item gap stays **`gap-4`** (16px).
- **No `gap-8` anywhere in this file.** The wordmark→nav distance is emergent, not specified.
  A test asserting a fixed value there asserts something the layout no longer promises.
- `navLinkClass`: `text-body-md` → **`text-nav`** (11px). AC: "nav items compute to 11px".
- Wordmark stays `font-title text-title-xs` (16px). AC: "the wordmark is 16px in the title
  face" — already true, do not touch it.
- Horizontal padding stays `px-4` so the wordmark sits at the frame's left inset, matching the
  content column's inset.

### 7.2 `frontend/src/components/AppShell.tsx`

`<main>`: `max-w-[45rem]` → **`max-w-frame`**. 720px → **1120px**. AC: "the page content
column is the same width as the bar's contents". This one *is* a resize, per option C.

### 7.3 `frontend/src/components/AuthShell.tsx`

The centred column `max-w-[45rem]` → **`max-w-form`** (24rem = 384px). The card keeps
`w-full`. AC: "the card is 384px wide and taller than it is wide" — the height follows
from the content, which is the point of TRUTH business rule 4 (a card sizes to its
content, never to its column).

> **Task 5 structural amendment — approved 2026-08-22.** Group the wordmark and
> `Ornament` in a `w-full px-6` flex column with `gap-2`. The existing outer
> `gap-4` separates that brand group from the card. This gives the mark the card's
> 336px content measure at desktop without an arbitrary width: the wrapper owns the
> inset and `Ornament` still fills whatever container it is given.
> `AuthShell.tsx` is part of Task 5's target-file fence.

### 7.4 `frontend/src/components/Ornament.tsx` — lozenge rule

The approved product invariant is unchanged: replace the Unicode `· · ❦ · ·` with a
filled vector lozenge centred between two hairline rule segments. **Three call sites
inherit the change with no edit of their own** — `AuthShell.tsx:9`,
`pages/Home.tsx:28`, `pages/home/HomeBlank.tsx:21`. The Home files remain outside the
Task 5 file fence.

> **Structural decision recorded 2026-08-22.** `DESIGN.md` §5.6 originally
> specified one no-viewBox SVG, an 11px lozenge and a paper-coloured knockout,
> while this section and Task 5 specified three SVGs, a tokenized 12px lozenge
> and real flex gaps. After the fourth review triggered `STRUCTURAL_REEVAL.md`,
> the human approved the three-SVG amendment. This section is authoritative.

The exact structure is one `data-testid="ornament"` and `aria-hidden` flex row
with `w-full items-center gap-2 text-muted-foreground`, containing:

1. a rule segment — `<svg className="h-px flex-1" viewBox="0 0 1 1"
   preserveAspectRatio="none" focusable="false">` with one `1 × 1`
   `fill="currentColor"` rectangle,
2. the lozenge — `<svg className="size-3 shrink-0" viewBox="0 0 12 12"
   focusable="false">` with one `fill="currentColor"` diamond path and **no**
   `preserveAspectRatio` override, so the default `xMidYMid meet` preserves it,
3. a second rule segment identical to (1).

No SVG has a title or role. `gap-2` supplies the real 8px break on each side, so there
is no paper-coloured knockout or paper-only constraint. The root owns the muted colour
because neither Home parent supplies it and both Home files must stay untouched.
`Ornament` has no props or outer margin. Its explicit `w-full` makes the flex
item consume the 336px auth brand wrapper and each Home parent's existing content
box instead of shrink-wrapping its children; only the rule segments change length.

The test uses the escaped literal `'\u2766'`, which Prettier preserves, to prove the
rendered DOM contains no ornament glyph without putting a literal `❦` in application
or test source. The stale `Ornament` row in `.claude/docs/frontend/screens.md` is part
of the Task 5 target fence and changes from glyph copy to a full-width vector-lozenge
description with no literal glyph. A literal repository search for `❦` must then
return no match outside `specs/`.


### 7.5 `frontend/src/components/Disclosure.tsx` (new) — D4

A shared, reusable disclosure. **Path decision:** `components/`, *not* `components/ui/`.

TRUTH rule 8 exempts `components/ui/**` because it is *vendored third-party source*. A
hand-written `Disclosure` is neither vendored nor third-party, and putting it behind the
exemption would mean our own new interactive component is the one piece of the product the
new rules never check. Placing it in `components/` keeps the exemption exactly as narrow as
TRUTH.md defines it.

This is only possible because the component is built on Radix's `Collapsible`
(`radix-ui`, already a dependency): `Collapsible.Trigger` is a **component**, so
`local/no-bare-interactive` — which reports lowercase JSX element names — passes it, and no
exemption is needed. The component also passes rules 1–3 on tokens alone. It is the proof
that the rule set is livable.

Props: `label: string`, `children: ReactNode`, `testId: string`, `defaultOpen?: boolean`.
Radix supplies `aria-expanded`, `aria-controls`, the id wiring, and keyboard activation.

Interactive state, declared in full per TRUTH business rule 1 — this is the defect being
fixed, so none of these is optional:

| State | Treatment |
|---|---|
| rest | `text-body-md text-muted-foreground`, caret at 0° |
| cursor | `cursor-pointer` — Tailwind v4's preflight sets `cursor: default` on `<button>`, which is exactly why the current control affords nothing (see the comment in `ui/button.tsx`) |
| hover | `hover:underline hover:text-foreground` — AC "the cursor is a pointer and the label is underlined" |
| focus-visible | `focus-visible:ring-3 focus-visible:ring-ring/50 outline-none`, matching `ui/button.tsx`; the ring is never removed and stays intact while expanded |
| active | `active:translate-y-px`, matching `ui/button.tsx` |
| expanded | caret rotates via `group-data-[state=open]:rotate-90` on a `lucide-react` `ChevronRight` |
| disabled | not applicable — a disclosure is never permission-gated (SCREENS.md "absent, not disabled") |

ACs covered: "Disclosure affords a click", "Disclosure works by keyboard", "Disclosure caret".

### 7.6 `frontend/src/pages/settings/PasswordDialog.tsx` (new) — D5

> **`DialogShell` already exists** at `frontend/src/components/DialogShell.tsx`. It is a
> Radix-based shell with `size` variants, `locked`, `initialFocusRef` and hand-rolled focus
> restoration, and `ConfirmByTyping` already consumes it. DMI-107's wording — "a shared modal
> shell extracted from `ConfirmByTyping`" — is **stale**; that extraction landed in earlier
> work. **Do not write a new shell and do not re-extract one.** The password modal consumes
> the existing `DialogShell` and nothing else.

- `<DialogShell size="sm" …>` — 24rem = 384px, the right measure for a three-field form.
- Moves the entire password form out of `Settings.tsx`: the three `Input`/`Label` pairs, the
  three field-level error regions, the form-level error region, the submit button, the
  success region, and `handleSubmit` with its `wrong_current_password` /
  `password_policy_violation` branches. Behaviour is preserved verbatim; only its container
  changes.
- Error regions stay **always rendered and empty when clean** — a conditionally-mounted live
  region is never announced (`frontend-conventions` version-trap table).
- `initialFocusRef` → the current-password input, so opening the modal focuses the first
  field.
- Focus restoration on close is `DialogShell`'s existing `onCloseAutoFocus` + captured
  opener. AC "Focus returns": focus returns to the change-password trigger. Nothing new is
  written for this.
- Precedent to mirror: `frontend/src/pages/users/InviteDialog.tsx`.

### 7.7 `frontend/src/pages/Settings.tsx` + `frontend/src/pages/settings/AccountDetails.tsx` (new)

`Settings.tsx` becomes a composer. Section order, per the AC:

1. **Your details** — `AccountDetails.tsx`, read-only, renders `user.email` and `user.role`
   from `useSession()`. Visible on load with no interaction; **no field has focus** —
   `autoFocus` is removed from what is now the modal's first field, and nothing replaces it.
   Read-only per TRUTH out-of-scope (no display-name editing; open question C3 stays open).
2. **Change your password** — a `Button` trigger that opens `PasswordDialog`.
3. **Activity** — heading on its own line above the disclosure row (AC "Activity heading"),
   then `<Disclosure label="What's recorded?">` with the existing note copy.
   The bare `<button>` at line 212 is gone (§5.1).
4. **Leave this organization** — unchanged, including its `ConfirmByTyping` (AC "Existing
   confirmation unchanged" — do not touch this section beyond its position in the list).

Also in this file: the 6 `text-sm` → `text-body-md` (§3.4). The two `max-w-prose` usages at
lines 227 and 244 are **kept exactly as they are** — they still bind at 65ch ≈ 546px and are
not dead code (§4.1).

### 7.8 `frontend/src/pages/Login.tsx` — the network-error string

> **Folded in 2026-08-22.** `DESIGN.md` §16 q4 raised `/login` copy drift as an open question and
> the specs fenced it out. At the refine gate the evidence closed half of it: this is a
> **violation**, not a contradiction, so no amendment is needed and the fix is two lines.

`frontend/src/lib/copy.ts:13` already exports

```ts
export const SERVICE_ERROR = "Couldn't reach Dmitri. Try again in a moment."
```

— the exact `SCREENS.md` §LOGIN string — and `Settings.tsx`, `AcceptInvite.tsx`,
`ResetPassword.tsx` and `ForgotPassword.tsx` all import it. `Login.tsx:58` is the only call site
that hardcodes a different string.

**The change:** add `SERVICE_ERROR` to the existing `@/lib/copy` import and use it at line 58.
**No new string is written and `lib/copy.ts` is not touched** — this is a call site joining the
four that were already right.

**`frontend/src/pages/Login.test.tsx:159` must change with it.** It currently asserts the
hardcoded literal, so the two-line source change alone turns the suite red. The test should assert
the imported `SERVICE_ERROR`, not a second copy of the string — a test that repeats the literal is
how the two drifted apart in the first place.

The title at `Login.tsx:86` is **not** touched. That half was a contradiction; the operator chose
`Sign in`, and `docs/ui/SCREENS.md` §LOGIN is amended instead (`DESIGN.md` §14.12).

---

## 8. Backend — CORS fails closed (D6)

### 8.1 The change

`backend/src/api/core/config.py:54-57`:

```python
    # Fails closed: an unset CORS_ALLOWED_ORIGINS yields an empty allowlist, so the API
    # permits no browser origin at all. The previous default trusted a developer
    # workstation and a placeholder domain nobody owns, which — with
    # allow_credentials=True — made a missing variable a silent exposure.
    cors_allowed_origins: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")
```

`backend/src/api/middleware.py:53-58` **needs no change**: `build_cors_middleware_kwargs`
already filters empty entries, so `""` yields `allow_origins: []`, and Starlette's
`CORSMiddleware` then emits no `access-control-allow-origin` header for any origin.

### 8.2 Why option 2 (`default=""`) and not option 1 (required field)

TRUTH rule 16 and the AC accept either — "it either refuses to start or permits no origin at
all". Option 2 is chosen because:

- It is already fail-closed. `allow_origins: []` permits nothing, and the SPA's every
  cross-origin call fails visibly — "misconfiguration looks like a broken product", which is
  the stated intent.
- CORS is a **browser** control. An empty allowlist leaves the Pi agent's WebSocket and every
  server-to-server caller working, which is correct; a hard refusal to start would take the
  whole API down over a browser-only setting.
- Option 1's blast radius is disproportionate. `Settings()` is constructed with only
  `DATABASE_URL` and `JWT_SIGNING_SECRET` in `backend/tests/conftest.py`; a required field
  makes every such construction raise `ValidationError`, and `backend/.env` /
  `backend/.env.example` / every deploy environment must be edited before the process can
  boot at all. That is a large change for no additional safety.

Option 1 is the better choice if a *silent* empty allowlist is ever observed to confuse an
operator. It is recorded here as the rejected alternative, not forbidden forever.

### 8.3 The test fixture that currently depends on the fail-open default

**This is the load-bearing detail.** `backend/tests/conftest.py` sets
`Settings.model_config["env_file"] = None` and never sets `CORS_ALLOWED_ORIGINS`. So
`api/main.py:55` builds its middleware from the **default**, and these assertions pass only
because the default trusts `http://localhost:5173`:

- `backend/tests/test_cors_headers.py` — `ALLOWED_ORIGIN = "http://localhost:5173"`, asserted
  in three tests
- `backend/tests/test_auth_wiring.py:44-55` — same origin asserted on the login preflight

Changing the default to `""` breaks all of them. The fix is **not** to weaken the default; it
is for the suite to configure the origin it asserts on, exactly as it already does for
`JWT_SIGNING_SECRET`. In `conftest.py`, beside the existing `os.environ.setdefault` calls and
**before** `from api.core.config import Settings`:

```python
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
```

This strengthens the tests: they now assert against an origin they set, rather than against a
production default that happened to include a laptop.

### 8.4 Scope fence — what is *not* changed

`https://app.vscanner.example.com` also appears in:

- `contracts/openapi/openapi.yaml:20,39,46,1394`
- `frontend/src/types/openapi.d.ts:1344` (generated)
- `docs/adr/ADR-005-security-model.md:150`
- `specs/014-frontend-scaffold/ARCHITECTURE.md:27`

**None of these are touched.** TRUTH out-of-scope forbids hand-edits to the API contract and
its generated types, and the AC is scoped to "the configuration source … no host the team
does not control appears in any **default**". A documented example server URL is not a default
that grants trust. The ADR and the old spec are historical records.

---

## 9. Agent and skill artifacts

| Artifact | Change |
|---|---|
| `.claude/agents/frontend-code-reviewer.md` | New **Foundations checklist** section under `## Frontend-specific rejections`: (a) the four `local/*` rules and their exemption globs, with the note that a reviewer never widens an exemption to make a gate pass; (b) reject any new file added under `src/components/ui/` that is not vendored shadcn source — our own primitives go in `src/components/`; (c) reject any interactive element whose cursor / hover / focus-visible / active / disabled states are not all specified; (d) reject any layout width that is not `max-w-frame` or `max-w-form`; (e) reject a card sized to its column rather than its content |
| `.claude/agents/frontend-design-agent.md` | New **rendered preview is mandatory** requirement in `## Output requirements`: `DESIGN.md` must link a rendered preview built from the real tokens (`frontend/src/index.css`) and the real typefaces (IM Fell English, IBM Plex Mono via Google Fonts), published as an Artifact. ASCII mockups stay, as structure notes, but no longer constitute an approvable design — they cannot express proportion, type size or affordance, which is how the letterbox login card was approved. Also state TRUTH rule 13: the visual check is performed by the human and closes every frontend feature; no agent signs off on how something looks |
| `.claude/skills/frontend-conventions/SKILL.md` | Under `## Styling`: the three named containers and `text-nav`; the type scale is a closed set and `text-sm` is not in it; the four lint rules by name with their exemptions; the interactive-state requirement (TRUTH business rule 1) and the `cursor-pointer` trap Tailwind v4 preflight creates. Under `## Product rules`: `Disclosure` joins the shared components, and "only shared components may be interactive" is stated |
| `.claude/skills/remediate/SKILL.md` | **New skill.** Turns free-text human feedback into pipeline work. Per item: classify as **violation** (the spec was right, the code broke it) → write a task directly; or **contradiction** (the spec itself must change) → write a proposed amendment against the feature's `TRUTH.md` / `DESIGN.md` and **stop at a human approval gate**; no task is written for a contradiction until the amendment is approved. Includes the classification test (does the spec already require this behaviour, or does it explicitly decide otherwise?), the amendment format, the gate wording, and one worked example of each class. Structure mirrors `.claude/skills/refine-specs/` — `SKILL.md` only, no `REFERENCE.md` |
| `docs/ui/SCREENS.md` §Foundations | The written gaps TRUTH.md names. **New `### Interactive state` subsection** (cursor, hover, focus-visible, active, disabled specified for every interactive element; only shared components are interactive) — `cursor` currently appears zero times in 1630 lines. **New `### Containers` subsection** naming `frame` / `prose` / `form` as the only layout widths, plus "a card sizes to its content, never to its column". **New type-scale table** under `### Typography` listing the named tokens and stating the raw framework sizes are not part of the scale. **`### Building rules`** gains a line pointing at the four lint rules as the enforcement |

`docs/ui/SCREENS.md` is referenced **by section and quoted phrase, never by line number**.
DMI-107's citations (`:1478`, `:1493`) are stale — the `### SETTINGS` heading is at line 1579,
the epicenter paragraph at ~1583-1588, the Activity "beside" paragraph at ~1601-1605.

---

## 10. Ordering constraint (for `TASKS.md`)

TRUTH.md: *"Every guardrail is complete before any UI fix starts."* Ordering is a rule, not a
preference — the UI fixes are built under the new rules and checked by the new gate, which is
why the two halves are one feature.

As a dependency statement the task breakdown can consume:

```
Phase G — guardrails (no UI fix may start until every G task is Done)
  G1  docs/ui/SCREENS.md §Foundations: interactive state, containers, type scale
  G2  index.css tokens                                       (depends: G1)
  G3  eslint-rules/ + eslint.config.js wiring + rule unit tests
  G4  clear the 32 violations, in the same change as G3      (depends: G2, G3)
  G5  components/Disclosure.tsx, built complete; Settings.tsx
      swaps its bare <button> for it                         (depends: G3)
  G6  .claude/ frontend artifacts: frontend-conventions/SKILL.md,
      frontend-code-reviewer.md, frontend-design-agent.md      (depends: G1)

Phase U — UI fixes (every U task depends on ALL of G1…G6)
  U1  TopBar frame / nav gap / text-nav
  U2  AppShell column rename
  U3  AuthShell card width
  U4  Ornament → lozenge rule + AuthShell brand wrapper
  U5  Settings reorder + AccountDetails + PasswordDialog
  U6  Login.tsx: import SERVICE_ERROR instead of hardcoding
      its own network-error string  (DESIGN §10, §14.12)

Phase R — .claude/skills/remediate/, independent of both phases, may run at any time
  R1  remediate SKILL.md: classification test, the two worked
      examples, the approval-gate wording                      (depends: none)

Phase B — backend, independent of both phases, may run at any time
  B1  CORS default "" + conftest fixture + tests + .env.example
```

**Why `remediate` is Phase R and not Phase G** — decided 2026-08-22 at the refine gate. The
ordering rule exists because *the UI fixes are built under the new rules and checked by the new
gate*. G1–G5 supply those rules, tokens and the gate; G6 teaches the agents that build the
fixes. `remediate` does none of that — it processes human feedback **after** work ships, and no
part of the top bar, auth card, Settings or the mark touches it. Blocking five visible fixes
behind it applies the rule where its reason does not reach. The rule itself is unchanged and
still absolute for G1–G6.

`G3` and `G4` are separate tasks but **must land in one commit** (TRUTH rule 9: no commit is
knowingly red). Same for `G5`, whose rule is enabled by `G3`.

---

## 11. New files and naming (mandatory)

| Layer | Path | New? | Purpose |
|---|---|---|---|
| Lint | `frontend/eslint-rules/index.js` | new | Inline plugin object: `{ rules: { … } }`, imported by `eslint.config.js` |
| Lint | `frontend/eslint-rules/class-strings.js` | new | Shared helper: class-string context detection + bracket-aware token/variant split (§3.2) |
| Lint | `frontend/eslint-rules/no-arbitrary-utility.js` | new | Rule §3.3 |
| Lint | `frontend/eslint-rules/no-raw-type-size.js` | new | Rule §3.4, incl. the raw→token mapping table |
| Lint | `frontend/eslint-rules/spacing-scale.js` | new | Rule §3.5 |
| Lint | `frontend/eslint-rules/no-bare-interactive.js` | new | Rule §3.6 |
| Lint | `frontend/eslint.config.js` | touch | Register the inline plugin + the exemption globs (§3.1) |
| Tokens | `frontend/src/index.css` | touch | `--container-frame`, `--container-form`, `--text-nav` in `@theme inline` — three tokens, no `--container-prose` (§4, §4.1) |
| Shell | `frontend/src/components/TopBar.tsx` | touch | `max-w-frame`, `grid grid-cols-[1fr_auto_1fr]`, `text-nav`. **No `gap-8`** (§7.1) |
| Shell | `frontend/src/components/AppShell.tsx` | touch | `max-w-frame` (§7.2) |
| Shell | `frontend/src/components/AuthShell.tsx` | touch | `max-w-form`; Task 5 tokenized brand wrapper (§7.3) |
| Component | `frontend/src/components/Ornament.tsx` | touch | Authoritative lozenge-rule inline SVG contract (§7.4) |
| Component | `frontend/src/components/Disclosure.tsx` | **new** | Shared disclosure primitive on Radix `Collapsible` (§7.5) |
| Component | `frontend/src/components/DialogShell.tsx` | **unchanged** | Already exists. Consumed, not modified, not re-extracted (§7.6) |
| Screen | `frontend/src/pages/Settings.tsx` | touch | Section reorder, composes the two new page components, `text-body-md` (§7.7). Its two `max-w-prose` usages are **kept** — see §4.1 |
| Screen | `frontend/src/pages/settings/AccountDetails.tsx` | **new** | Read-only signed-in email + role (§7.7) |
| Screen | `frontend/src/pages/settings/PasswordDialog.tsx` | **new** | The three password fields inside `DialogShell size="sm"` (§7.6) |
| Screen | `frontend/src/pages/Login.tsx` | touch | 3 × `text-sm` → `text-body-md`; **and** line 58 imports `SERVICE_ERROR` from `@/lib/copy` instead of hardcoding `Can't reach the server…` (§7.8). The title at line 86 stays `Sign in` — `SCREENS.md` moves to it, not the reverse |
| Screen | `frontend/src/pages/ForgotPassword.tsx` | touch | 4 × `text-sm` → `text-body-md` |
| Screen | `frontend/src/pages/ResetPassword.tsx` | touch | 6 × `text-sm` → `text-body-md` |
| Screen | `frontend/src/pages/AcceptInvite.tsx` | touch | 10 × `text-sm` → `text-body-md` |
| Build | `frontend/vitest.config.ts` | **unchanged** | Default `include` glob already covers `eslint-rules/*.test.js` (§12.1) |
| Tests | `frontend/eslint-rules/no-arbitrary-utility.test.js` | **new** | RuleTester cases (§12.1) |
| Tests | `frontend/eslint-rules/no-raw-type-size.test.js` | **new** | RuleTester cases |
| Tests | `frontend/eslint-rules/spacing-scale.test.js` | **new** | RuleTester cases — the only proof for the AC "Off-scale spacing rejected" |
| Tests | `frontend/eslint-rules/no-bare-interactive.test.js` | **new** | RuleTester cases |
| Tests | `frontend/src/pages/Login.test.tsx` | touch | Line 159 asserts the hardcoded `Can't reach the server…` string. It must assert `SERVICE_ERROR` instead, or U6 turns the suite red |
| Tests | `frontend/src/components/Disclosure.test.tsx` | **new** | Keyboard, `aria-expanded`, announced note |
| Tests | `frontend/src/components/TopBar.test.tsx` | touch | Nav class assertions |
| Tests | `frontend/src/components/Ornament.test.tsx` | **new** | SVG structure, semantics and escaped no-glyph assertion (§12.2) |
| Code map | `.claude/docs/frontend/screens.md` | touch | Replace the stale Unicode Ornament entry with full-width vector-lozenge text; no literal glyph (§7.4) |
| Tests | `frontend/src/pages/Settings.test.tsx` | touch | Order, identity-visible, modal open/focus-return, disclosure |
| Backend | `backend/src/api/core/config.py` | touch | `cors_allowed_origins` default `""` (§8.1) |
| Backend | `backend/src/api/middleware.py` | **unchanged** | Already filters empties. Do not modify `NoContentCorsMiddleware` |
| Backend | `backend/tests/conftest.py` | touch | `os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")` before the `api` imports (§8.3) |
| Backend | `backend/tests/test_settings.py` | touch | Line ~142: assert the default is `""` |
| Backend | `backend/tests/test_middleware.py` | touch | New case: empty setting → `allow_origins == []` |
| Backend | `backend/tests/test_cors_headers.py` | touch | New case: preflight from a foreign origin carries no allow-origin header. Existing 204 cases must not regress |
| Backend | `backend/tests/test_auth_wiring.py` | **unchanged** | Guarded by the `conftest.py` fixture; must keep passing |
| Backend | `backend/.env.example` | touch | Line 16 → `CORS_ALLOWED_ORIGINS=` with a fail-closed comment |
| Docs | `docs/ui/SCREENS.md` | touch | §Foundations: interactive state, containers, type scale, enforcement (§9). **Also §LOGIN**: the title row becomes `Sign in` (`DESIGN.md` §14.12) |
| Agents | `.claude/agents/frontend-code-reviewer.md` | touch | Foundations checklist (§9) |
| Agents | `.claude/agents/frontend-design-agent.md` | touch | Rendered-preview requirement (§9) |
| Skills | `.claude/skills/frontend-conventions/SKILL.md` | touch | Containers, type scale, four rules, interactive state (§9) |
| Skills | `.claude/skills/remediate/SKILL.md` | **new** | Violation vs contradiction classification + approval gate (§9) |

**Not in this feature, explicitly:** `frontend/src/App.tsx`, `frontend/package.json`,
`frontend/scripts/**` (all three withdrawn with §6), `contracts/openapi/openapi.yaml`,
`frontend/src/types/openapi.d.ts`, `docs/adr/ADR-005-security-model.md`,
`frontend/src/pages/Home.tsx`, `frontend/src/pages/home/**`,
`frontend/src/components/ConfirmByTyping.tsx`, `frontend/src/pages/users/**`,
`frontend/src/components/ui/**`.

---

## 12. Testing expectations

### 12.1 The lint rules

ESLint ships `RuleTester`; no dependency is added. One `*.test.js` per rule, run by Vitest
alongside the rest. **`frontend/vitest.config.ts` needs no change**: it sets no `include`, so
Vitest's default glob `**/*.{test,spec}.?(c|m)[jt]s?(x)` from the project root already picks
up `frontend/eslint-rules/*.test.js`. Its global `environment: 'jsdom'` is harmless for
`RuleTester`; do not add a projects/workspace split for four rule tests.

Each rule's test carries, at minimum:

| Rule | Must report | Must **not** report |
|---|---|---|
| `no-arbitrary-utility` | `className="max-w-[45rem]"`; `cn('p-[13px]')`; a template quasi | `has-data-[icon=inline-end]:pr-2`; `group-data-[state=open]:rotate-90`; `[&_svg]:size-4`; `max-w-prose`; `max-w-page`; `data-testid="a-[b]"`; a non-class string containing brackets |
| `no-raw-type-size` | `text-sm` → message names `text-body-md`; `text-xs`; `text-lg` → message says no token matches | `text-body-md`; `text-title-sm`; `text-caption-md`; `text-nav`; `text-muted-foreground`; `text-destructive` |
| `spacing-scale` | `p-5`; `gap-7`; `mt-2.5` | `p-6`; `gap-4`; `mx-auto`; `p-px`; `p-[13px]` (owned by `no-arbitrary-utility`) |
| `no-bare-interactive` | `<button>`; `<input>`; `<select>`; `<textarea>` | `<Button>`; `<Collapsible.Trigger>`; `<a href>`; `<div onClick>` (not covered — documented, not a gap) |

### 12.2 Frontend component tests

Mirror the nearest existing test in each case; assert user-visible behaviour, not classes,
except where the AC is literally about a class or a computed size.

| File | Asserts | Mirror |
|---|---|---|
| `Disclosure.test.tsx` | collapsed by default; click and `{Enter}`/`{Space}` flip `aria-expanded`; the note is `aria-controls`-linked and revealed; the trigger carries `cursor-pointer` and a `hover:underline` class | `ConfirmByTyping.test.tsx` |
| `Ornament.test.tsx` | root `data-testid="ornament"`, `aria-hidden` and `w-full` muted flex-row classes; exactly three direct vectors in rule/lozenge/rule order; both rules' class, view box, non-uniform aspect ratio, focusability and `1 × 1 currentColor` rectangle; the lozenge's fixed class, view box, default aspect ratio, focusability and `currentColor` path; no title or role; rendered text excludes the escaped literal `'\u2766'` | `Timestamp.test.tsx` |
| `Login.test.tsx` (touch) | the network-error case asserts `SERVICE_ERROR` imported from `@/lib/copy`, not a repeated literal — so the constant and the assertion cannot drift apart again | existing file, line 159 |
| `TopBar.test.tsx` (touch) | nav links carry `text-nav`; the frame carries `max-w-frame`; the wordmark keeps `text-title-xs` | existing file |
| `Settings.test.tsx` (touch) | on load, email and role are visible with no interaction and `document.activeElement` is `document.body`; sections appear in the order details → password → activity → leave; the change-password trigger opens a dialog containing all three fields; dismissing it returns focus to the trigger; the leave confirmation still behaves identically | existing file — keep every existing leave-organization case unchanged |

`jsdom` computes no layout, so the pixel ACs (1440px proportions, 384px card and the
approved 336px auth mark measure) are **not** asserted with a fake
`getBoundingClientRect` stub. The Task 5 test may assert classes because those tokens and
the SVG attributes are the approved structural contract. The reviewer still inspects
the real auth and Home surfaces for alignment, visible hairlines and an undistorted
lozenge (TRUTH rule 13). No screenshot or visual-regression test is added (TRUTH
out-of-scope).

### 12.3 Bundle assertion — none

Withdrawn with the `/styleguide` page (§6). `npm run build` is unchanged and
`frontend/package.json` is not touched.

### 12.4 Backend tests

| File | Case |
|---|---|
| `test_settings.py` | `Settings().cors_allowed_origins == ""` when the env var is unset — replaces the current line-142 assertion verbatim |
| `test_middleware.py` | `build_cors_middleware_kwargs(Settings(CORS_ALLOWED_ORIGINS=""))["allow_origins"] == []` — the fail-closed proof |
| `test_cors_headers.py` | new: preflight with `Origin: http://localhost:9999` returns **no** `access-control-allow-origin` header. Existing three cases keep asserting 204 with no body headers |
| `test_auth_wiring.py` | untouched; must keep passing on the `conftest.py` fixture |

### 12.5 The remediation skill

`.claude/skills/remediate/SKILL.md` is an agent workflow, not code, so no unit test asserts it.
That is not the same as nothing to prove. **Sharpened 2026-08-22** after the skill was
challenged at the refine gate and kept: an untestable deliverable inside a testable feature
must carry its own proof, or it gets waved through.

The proof is **two worked examples, both real and both drawn from this feature**, which the
skill carries in full and which a reviewer checks against a known answer:

| Feedback (verbatim input) | Cited authority | Correct class | Correct output |
|---|---|---|---|
| *"the activity disclosure does not look clickable"* | TRUTH business rule 1 — every interactive element declares cursor and hover | **violation** — the specification was already right | a task, written directly, no approval step |
| *"the navigation should be centred on the bar"* | `SCREENS.md` §App shell, which decided left-adjacent on 2026-08-07 | **contradiction** — the specification itself must change | a written amendment naming §App shell and what it would change, then **stop**; no task until a human approves |

The second example is not hypothetical: it is exactly what happened on 2026-08-21, and
`DESIGN.md` §14.9 is the amendment it should have produced. That is what makes it checkable.

**Task success criteria, binding:**

1. The skill states the classification test as a single question a reader can apply: *does the
   specification already require this behaviour, or does it explicitly decide otherwise?*
2. It carries both rows above, each showing input, cited section, class, and output.
3. It fixes the gate wording, and the wording names the target document and section and states
   what would change. An amendment nobody can review is not a gate (TRUTH rule 15).
4. A human walks both examples through the skill at review and confirms the classification.
   This walkthrough is the acceptance step; record its result in the task.

`SKILL.md` only, no `REFERENCE.md` — structure mirrors `.claude/skills/refine-specs/`.

---

## 13. Gates

Both layers are owed (TRUTH Scope note).

**Frontend**, from `frontend/`:

```
npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
```

`npm run build` is unchanged by this feature. `npm run gen:types` is **not** run — the
API contract does not move (§8.4).

**Backend** — `./database.sh` **first**, then from `backend/`:

```
uv run ruff check src tests
uv run pytest
```

Expect **665 passed / 0 skipped**. A non-zero database-test skip count means the database was
not up and the run proves nothing; re-run or say so. **Never `uv run ruff format`** — `ruff
check` is the backend's only Python gate (`.claude/CLAUDE.md`, decided 2026-07-30).

**No repo-wide formatter run**, in either layer.

---

## 14. Constraints

- **No new dependency**, runtime or development (TRUTH rule 7). The lint rules are repo
  source; `RuleTester` ships with ESLint; the
  `Disclosure` uses `radix-ui` and `lucide-react`, both already installed.
- **No new infrastructure.** No `HUMAN_INFRA_REQUIRED`.
- **No temporary code** (`.claude/CLAUDE.md`). `TopBar` and `AuthShell` land at their final
  widths in the remediation change; `Disclosure` is built complete on first write.
- **No exemption may be widened to make a gate pass.** The exemption list is TRUTH rule 8 and
  §3.1, and the 35 → 29 and 3 → 3 arithmetic is what proves it. If a rule fires somewhere
  unexpected, fix the rule's tokenizer or fix the code — never the glob.
- **Do not invent a parallel styling layer.** No `--space-*` tokens, no `tailwind.config.js`
  (Tailwind v4 has no JS config), no `dark:` variants.
- The CLAUDE.md orchestrator/`ScanRunner`/`ScanProgressScreen` threading rule does not apply:
  this feature adds no orchestrator or runner parameter and touches no
  `hardware-agent/src/agent/` module. Its analogue here is §7.4's call-site fence — all three
  `Ornament` call sites are accounted for and none needs an edit — and §8.3's, where every
  construction site of the changed `Settings` default was traced and the one that depended on
  it (`conftest.py`) is listed.
