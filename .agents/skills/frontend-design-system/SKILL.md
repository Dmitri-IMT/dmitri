---
name: frontend-design-system
description: >-
  Binding design-system tokens and styling rules for Dmitri's React SPA — the shipped values in
  frontend/src/index.css, docs/ui/FOUNDATIONS.md, the six local ESLint rules, spacing rhythm,
  interaction states, and the device/machine vocabulary. Load this when authoring Tailwind
  classes, touching index.css, or reviewing visual work under frontend/src/.
---

# Frontend design system (`frontend/`)

Binding. `docs/ui/FOUNDATIONS.md` (2026-09-02, DMI-131; implemented DMI-132) outranks this file.
Shipped values live in `frontend/src/index.css`; reasoning and retired decisions live in
`docs/ui/FOUNDATIONS-DECISIONS.md`.

Load `frontend-conventions` for stack version traps, API types, and
product rules that show up as code.

## Tokens (`index.css`)

`:root` holds semantic colours, radii and motion durations. `@theme inline` registers what
Tailwind v4 turns into utilities — fonts, colours, radii, type scale, containers, eases.

| Area | Shipped values | Notes |
| --- | --- | --- |
| Canvas / card | `--canvas` `#FCFCFC`, `--card` `#FFFFFF` | Light only; no `dark:` |
| Ink | `--ink` `#0F172A`, `--ink-muted` `#475569` | `#64748B` is the text floor |
| Lines | `--rule` `#E2E8F0` (decorative), `--edge` `#64748B` (controls) | See outline-button flag below |
| Accent | `--accent` `#4F46E5`, hover `#4338CA`, active `#3730A3` | One accent; never severity |
| Radius | `--radius` `0.75rem`, `--control-radius` `0.5rem` | shadcn preset `radix-maia` |
| Type | `text-title-lg` … `text-caption-md` (seven tokens) | Inter Variable sans; Geist Mono for IP/MAC/port/CVE/UUID only |
| Containers | `max-w-frame` (1120px), `max-w-form` (384px) | No other layout widths |
| Row height | `@utility h-row` → 56px | `DataTable` fixed row height |

**Duration gap:** `--duration-fast/base/slow` sit in `:root` but not in `@theme`, so utilities
like `duration-base` are not generated. Use the CSS variables directly or register them in
`@theme` before relying on Tailwind duration utilities. Ease tokens *are* in `@theme`.

**Outline button mismatch:** `ui/button` `outline` uses `border-border` (`--rule`, ~1.2:1) while
FOUNDATIONS assigns `--edge` to control boundaries (3:1 floor). Pre-existing; matters now that
outlined buttons sit in card footers.

## Authored-style rules

- **No magic numbers.** Every colour, size, radius, border width and space is a token. Arbitrary
  utilities (`p-[13px]`, `text-[15px]`) are the same bug in brackets.
- **Pick type by token name**, never by pixel or raw framework size (`text-sm` is not a scale
  token).
- **Spacing:** nine steps on Tailwind's 4px base — `0 1 2 3 4 6 8 12 16 24`. No `p-5`, no
  `gap-7`, no `--space-*` layer.
- **Parent owns space between children.** Components ship with no outer margin; use `gap-*` on
  the container.
- **Inter-section step** per screen is `6`, `8` or `12` only, never smaller than inter-group.
- **Five interaction states** on every control: rest, hover, focus-visible, active, disabled —
  plus explicit `cursor-pointer` on clickable elements (Tailwind v4 preflight sets
  `cursor: default` on `<button>`).
- **No `dark:`**, no theme toggle, desktop only (1440 target, 1280 minimum).
- **Severity has no hue.** `SeverityWord` renders a bold ink word; API `Severity` is four
  members: critical, high, medium, low.
- **Never add coloured tags.** No chip, pill, tag or badge (a tinted, rounded label) for any
  state: availability, status, counts, versions. Say the state as a plain word or sentence in
  `--ink` or `--ink-muted`.
- **Vocabulary:** a *device* is the Dmitri box (`/devices`); a *machine* is a host on the
  customer's network (`/network`). Do not swap them in copy.

## Six local lint rules

Registered at `error` in `frontend/eslint.config.js`:

| Rule | Enforces |
| --- | --- |
| `local/no-arbitrary-utility` | No bracket utilities where a token exists |
| `local/no-raw-type-size` | Closed type scale only |
| `local/spacing-scale` | Permitted spacing steps (`FOUNDATIONS.md` §Spacing) |
| `local/no-bare-interactive` | Five states on interactive elements (`FOUNDATIONS.md` §Interaction states) |
| `local/no-raw-hex` | No hex/rgb/hsl in authored class strings or JSX `style` |
| `local/no-dark-variant` | No `dark:` prefix in authored class strings |

Exemptions: vendored shadcn (`src/components/ui/**`), test files (`src/**/*.test.{ts,tsx}`),
test harness (`src/test/**`). Never widen an exemption to pass the gate; fix the code or the rule.
A token rename and its lint edit ship in the same commit.
