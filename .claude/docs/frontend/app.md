---
type: Entry Point
title: frontend app root & routing
description: The React root's provider nest and App's route table — the four public auth routes, the guarded shell branch with its nested admin-only segment, and a catch-all that renders rather than redirects.
resource: frontend/src/App.tsx
tags: [frontend, react, entrypoint, router]
timestamp: 2026-08-07T00:00:00Z
---

# frontend app root & routing

## Purpose

The app root is two small files: `main.tsx` builds the provider nest, and `App.tsx` is nothing but
the route table. Session state and the boot refresh live in [auth](./auth.md), not here — `App.tsx`
contains no `useEffect`, no refresh call and no session state at all.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `main.tsx` root | Mounts `<StrictMode>` → `BrowserRouter` → `QueryClientProvider` → `SessionProvider` → `App`. The router must sit outside the session provider, which navigates. | `frontend/src/main.tsx:11` |
| `App` | The route table only: four public routes — `/login` → `Login`, `/forgot-password` → `ForgotPassword`, `/reset-password` → `ResetPassword`, `/invite` → `AcceptInvite`; then a `RequireSession` branch wrapping an `AppShell` branch holding `/` → `Home`, `/settings` → `Settings`, a nested `RequireAdmin` segment holding `/users` → `Users`, and `*` → `NotFound`. | `frontend/src/App.tsx:15` |

## How it connects

- Guarded by [auth](./auth.md)'s `RequireSession`; framed by [screens](./screens.md)'s `AppShell`.
- `Login` sits **outside** the guard and redirects to `/` itself when already authenticated. The
  three other public routes sit outside it too: password recovery and invite acceptance must work
  with no session at all. `AcceptInvite` guards itself in the opposite direction — an
  *authenticated* visitor gets a sign-out block rather than the form.

## Notes / gotchas

- **The catch-all renders, it does not redirect.** `*` is nested *inside* the
  `RequireSession`/`AppShell` branch, so an unknown path is a not-found page inside the shell for a
  signed-in operator (URL preserved) and a redirect to `/login` for a signed-out one. There is no
  `Navigate` on the catch-all — rewriting the URL would hide the typo the operator needs to see.
- **Router package is `react-router` v7**, not `react-router-dom` — v7 merged them, and importing
  the old package name is a silent-drift trap.
- **Two screens sit inside the session guard**: `/settings` directly, and `/users` behind a second,
  nested [`RequireAdmin`](./auth.md) element route. Both must stay above the `*` catch-all.
- **The admin segment nests inside `AppShell`, not beside it**, so a gated route keeps the top bar
  and a refused viewer sees `NotFound` inside the normal frame rather than a bare page.
- `App.test.tsx` supplies its own `MemoryRouter` (App mounts routes, not a router), and reads the
  live path through a `useLocation()` probe to prove the catch-all preserved it.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [specs/020-frontend-vertical-slice-login-home/DESIGN.md](../../../specs/020-frontend-vertical-slice-login-home/DESIGN.md)
