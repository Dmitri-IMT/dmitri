---
type: Module
title: frontend screens, shells and shared components
description: The LOGIN and HOME screens, the not-found page, the two shells and top bar, and the shared presentation components.
resource: frontend/src/pages/
tags: [frontend, ui, screens, react, accessibility]
timestamp: 2026-07-31T00:00:00Z
---

# frontend screens, shells and shared components

## Purpose

The visible surface of the app: two frames (signed-out and signed-in), three routes, and the small
set of components they share. The governing principle throughout is **absent, not disabled** — an
operator never meets a control that looks live and isn't.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `AuthShell` | Outside-shell frame: wordmark + `Ornament` + one centred card in the 720px column. No top bar. | `frontend/src/components/AuthShell.tsx:4` |
| `AppShell` | Inside-shell frame: `<TopBar />` + `<Outlet />` in the fluid 720px-max prose column. **No sidebar.** | `frontend/src/components/AppShell.tsx:4` |
| `TopBar` | Wordmark, `Home` alone as the nav (other sections arrive with their screens), `[Log out]` calling `signOut`. Active item is a 2px `--accent` underline, not a filled pill. **Reads only `signOut` — no role branch at all.** Laid out as three grid tracks (`1fr auto 1fr`) so the lone nav item sits at the bar's true centre. | `frontend/src/components/TopBar.tsx:6` |
| `Login` | Real `<form>` in `AuthShell`; labelled email/password, email autofocused, Enter submits from either field. In-flight the button reads `Signing in…` and is `disabled` — the feature's **one** legitimate `disabled`. | `frontend/src/pages/Login.tsx:10` |
| `Home` | Switches over `useHomeReview()` and renders **exactly one** of loading / blank / clear / pending / error. Items-pending order: deck → failed-scan card → stale-coverage card. | `frontend/src/pages/Home.tsx:10` |
| `NotFound` | `That page doesn't exist.` plus a real `Go to Home` **link**, inside the shell. | `frontend/src/pages/NotFound.tsx:3` |
| `Verdict` | The verdict + context sentence, shared by all-clear (centred) and items-pending (left-aligned), including the `1 thing needs your review.` singular split. Context comes from the **latest successful** scan and its own `host_count`. | `frontend/src/pages/home/Verdict.tsx:12` |
| `ReviewItemCard` | Square-edged card: `FINDING`/`SCAN`/`COVERAGE` label (the only place `--accent` appears on Home), severity badge top-right for findings. **Takes no `href` and no `onAction`.** | `frontend/src/pages/home/ReviewItemCard.tsx:18` |
| `FindingDeck` | One finding at a time with `←`/`→` and a `{i} of {n}` line, over the already-fetched array. | `frontend/src/pages/home/FindingDeck.tsx:8` |
| `HomeBlank` / `HomeError` / `HomeFooter` | First-run copy (no CTA, does not import `useSession`); the error copy + `[Retry]`; the last-scan line via `Timestamp`. | `frontend/src/pages/home/HomeBlank.tsx:3` |
| `Timestamp` / `formatTimestamp` | Relative inside 7 days, absolute beyond, exact value in `title`. | `frontend/src/components/Timestamp.tsx:21` |
| `SeverityBadge` | Severity-coloured text on a 10% tint of the same hue with a 1px full-colour border — never white-on-solid. Severity type aliases the generated schema. | `frontend/src/components/SeverityBadge.tsx:20` |
| `Ornament` | The `· · ❦ · ·` engraving. | `frontend/src/components/Ornament.tsx:1` |

## How it connects

- `Home` consumes [review](./review.md)'s `useHomeReview()`; `Login` and `TopBar` consume
  [auth](./auth.md)'s `useSession()`.
- Both shells are mounted from [app](./app.md)'s route table.
- Visual tokens come from `src/index.css`, governed by
  [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md).

## Notes / gotchas

- **Loading renders nothing below the top bar** — no skeleton, no spinner, no placeholder sentence.
  Any placeholder in the verdict's position is read as a verdict.
- **Blank and all-clear are distinct states** and are never collapsed; the footer is omitted
  entirely in the blank state.
- **The centred nav is transitional.** `TopBar` centres its nav *only* because it holds one item;
  from the second item on it reverts to left-adjacent, and the feature adding that item owns the
  revert (drop the grid for `flex justify-between`, give the nav `flex-1`). The rule lives in
  [docs/ui/SCREENS.md §App shell](../../../docs/ui/SCREENS.md) rather than as a count-driven branch
  in the component. Decided 2026-07-31.
- **Buttons carry an explicit `cursor-pointer`.** Tailwind v4's preflight sets `cursor: default` on
  `<button>` (changed from v3), so without it every button in the app shows an arrow. The class is
  a local addition to the vendored shadcn `buttonVariants` base and would be lost if the shadcn CLI
  re-adds the component; a comment in `ui/button.tsx` records why it is there.
- **The deck steps without fetching.** It owns the index into the already-fetched array; no
  `useQuery` is keyed on the index. Keyboard handling is a single tab stop with `onKeyDown` on the
  deck's own root — **never a `document`-level listener** — so arrows act only while it holds focus.
  The card region is `aria-live="polite"`, and the index resets when the underlying data changes.
- **End-stop arrows are absent, not disabled.** At each end the unavailable arrow unmounts and an
  `aria-hidden` placeholder of the same size holds the slot, so the row does not reflow while
  stepping. Stopping never wraps.
- **The finding sentence renders `{cve_id ?? title} on {host_ip}.`** — `FindingRecord` carries no
  `hostname`, only `host_id` (a UUID, which the design forbids on screen) and `host_ip`.
- **Home's Pi-status footer line is not built** — `GET /agents/{agent_id}` is unimplemented
  (DMI-78). `HomeFooter` reads no agent data.
- **The error region on Login is rendered always, empty when clean.** An `aria-live`/`role="alert"`
  region must pre-exist in the DOM to be announced; a conditionally-mounted error is silent to a
  screen reader. The 401 and network messages are distinct and name neither field.
- The role-invariance sweep (`TopBar.test.tsx`, repeated across every Home state) asserts
  `queryAllByRole(...)` elements are `toBeEnabled()` with no `aria-disabled` — never a
  `container.querySelectorAll('[disabled]')` sweep, which misses `fieldset[disabled]` inheritance
  and `aria-disabled` and violates Testing Library's `no-container`/`no-node-access` rules.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/DESIGN.md](../../../specs/020-frontend-vertical-slice-login-home/DESIGN.md)
[2] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[3] [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md)
