---
name: frontend-conventions
description: >-
  Binding code and styling conventions for Dmitri's React SPA under frontend/ — React 19,
  TypeScript 6, Vite 8, Tailwind v4, TanStack Query v5, React Router v7. Version traps that
  compile but misbehave, the API-type rule, the spacing scale and rhythm rules, and the
  absent-not-disabled rule. Load this before writing or editing any file under frontend/src/,
  and whenever reviewing or planning React/Vite/Tailwind/TanStack Query work.
---

# Frontend conventions (`frontend/`)

Binding. `docs/ui/FOUNDATIONS.md` and `docs/adr/ADR-008-frontend-stack.md` outrank this file;
where a feature's approved `ARCHITECTURE.md` / `DESIGN.md` is more specific, it wins.

Depth, with primary sources for every claim:

- `docs/research/frontend-react19-vite-typescript-conventions.md` — stack.
- `docs/research/frontend-testing-vitest-testing-library-msw.md` — tests.

## Version traps — each compiles and is still wrong

| Do not write | Why | Instead |
| --- | --- | --- |
| a fetch/refresh in `useEffect` | StrictMode double-invokes Effects in dev; with a rotating refresh token the second call consumes what the first rotated | TanStack Query, which deduplicates |
| `isLoading` from a query | v5 renamed it `isPending`; `isLoading` still exists with a **different** meaning | `isPending` |
| `onSuccess` / `onError` on `useQuery` | removed in v5 — **silently no-ops** | derive in render |
| `forwardRef` on a leaf component | React 19 passes `ref` as an ordinary prop | `function C({ ref, ...rest })` |
| `propTypes` / `defaultProps` | removed in React 19; `propTypes` is **silently ignored** | TS types + default params |
| `react-router-dom` | v7 merged it into `react-router` | `react-router` |
| `tailwind.config.js`, `darkMode: 'class'` | Tailwind v4 has no JS config | `@theme` in CSS |
| `baseUrl` in tsconfig | deprecated in TS 6, hard error in TS 7 — shadcn's own docs still tell you to add it | `paths` alone |
| `enum` | `erasableSyntaxOnly` is on; enums emit runtime code | `as const` object + union |
| `import { act } from 'react-dom/test-utils'` | `react-dom/test-utils` was removed in React 19 | `import { act } from 'react'` |
| a `placeholder` as the only label | fails WCAG 3.3.2 and vanishes on input | `<label htmlFor>` |
| a conditionally-mounted error region | a live region must pre-exist in the DOM to be announced | always render it, empty when clean |

## Data and types

- **Never hand-write an API type.** Every request/response shape comes from
  `src/types/openapi.d.ts` via `components['schemas'][...]`. Aliases stay inside `src/api/`.
- **Never edit `contracts/openapi/openapi.yaml` or the generated types by hand.**
  `npm run gen:types` must produce a clean diff.
- **One HTTP layer.** Reuse `apiClient` / `authClient` and the existing single-flight 401
  interceptor. No second client, no bespoke fetch wrapper, no parallel retry path.
- **Query keys are coarse→fine arrays**, so a prefix invalidates a family.
- Data fetching lives in TanStack Query, never in an Effect.

## Styling

Values live in `docs/ui/FOUNDATIONS.md` (binding, 2026-09-02). Until DMI-132 lands,
`frontend/src/index.css` and the local lint rules still carry the previous token values; do not
add new usages of retired tokens.

- **No magic numbers.** Every color, size, radius, border width and space is a token. A raw hex
  or pixel value in a component is a bug — including arbitrary-value utilities (`p-[13px]`,
  `text-[15px]`), which are the same bug in brackets.
- **The only layout widths are the named containers:** `max-w-frame` for both the top bar and
  every inside-shell page, and `max-w-form` for a standalone short form. `max-w-prose` is a
  reading measure, not a layout container. A card sizes to its content, never to its column.
- **The type scale is closed, and you pick from it by NAME**, never by pixel and never by a raw
  framework size. `text-xs`, `text-sm`, `text-base` and `text-lg` are not scale tokens even when
  their pixels match. The token names and their current values are in `FOUNDATIONS.md` §Type.
- **Spacing uses the nine permitted steps** on Tailwind's 4px base: `0 1 2 3 4 6 8 12 16 24`.
  No `p-5`, no `gap-7`. Do not invent a `--space-*` token layer; the stock utilities are the
  scale.
- **Components carry no outer margin.** A component renders flush to its own box; the parent
  supplies the gap via `gap-*` on a flex/grid container, never sibling margins. A `mb-4` baked
  into a shared component dictates its spacing at every future call site.
- **Section separation is decided once per screen.** The inter-section step is `6`, `8` or `12`,
  never an arbitrary value, and never smaller than the inter-group step.
- **Every interactive element specifies all five states:** rest, hover, focus-visible, active,
  and disabled — plus the cursor. Tailwind v4 preflight sets `cursor: default` on `<button>`, so
  a clickable control must add `cursor-pointer`; do not assume the browser supplies it. Hover and
  keyboard focus must both have visible affordances, and the focus ring is never removed.
- **Absent, not disabled.** Disabled is reserved for progress or incomplete-input states on an
  action the user is permitted to take.
- **Four local lint rules enforce these authored-style rules:** `local/no-arbitrary-utility`,
  `local/no-raw-type-size`, `local/spacing-scale`, and `local/no-bare-interactive`. Their only
  exemptions are vendored shadcn source (`src/components/ui/**`), test files
  (`src/**/*.test.{ts,tsx}`), and the test harness (`src/test/**`). Never widen an exemption to
  make the gate pass; fix the rule or the application code. The rules hard-code token names, so
  a token rename and its lint edit ship in the same commit.
- **No `dark:` utility, no `prefers-color-scheme`, no theme toggle.** One light theme ships,
  desktop only (1440 target, 1280 minimum).
- Components size to their container, never the viewport; `min-w-0` on flex children; long
  values wrap, truncate or scroll rather than widening the page. The body never scrolls
  horizontally.

## Product rules that show up as code

- **Only shared components may be interactive.** Application screens compose shared primitives;
  they do not hand-roll native controls or one-off click targets. Vendored shadcn primitives
  stay under `src/components/ui/`; Dmitri-owned shared components stay under `src/components/`.
  `Disclosure` is the shared component for expandable information and owns its cursor, hover,
  focus-visible, active, caret, and keyboard behavior.
- **Absent, not disabled.** An affordance a role cannot use is not rendered at all. Disabled is
  reserved for progress or incomplete-input states on an action the user is permitted to take;
  its opacity, pointer events, and tab-order treatment must be specified.
- **No control that navigates nowhere** — no `href`, `Link` or handler pointing at an unrouted
  path. If the destination is out of scope, the control is out of scope.
- **Roles come from the server** (`GET /users/me`), never decoded from a token. No `jwt-decode`
  or equivalent.
- Accessible names on every interactive element; a real `<label htmlFor>` on every input; the
  focus ring is never removed.

## Gate

From `frontend/`:

```
npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build
```

Plus `npm run gen:types` with a clean diff whenever the API layer moved.
