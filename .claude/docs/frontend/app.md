---
type: Entry Point
title: frontend app root & routing
description: The React root's provider nest and App's route table — /login, the guarded shell branch, and a catch-all that renders rather than redirects.
resource: frontend/src/App.tsx
tags: [frontend, react, entrypoint, router]
timestamp: 2026-07-29T00:00:00Z
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
| `App` | The route table only: `/login` → `Login`; then a `RequireSession` branch wrapping an `AppShell` branch holding `/` → `Home` and `*` → `NotFound`. | `frontend/src/App.tsx:8` |

## How it connects

- Guarded by [auth](./auth.md)'s `RequireSession`; framed by [screens](./screens.md)'s `AppShell`.
- `Login` sits **outside** the guard and redirects to `/` itself when already authenticated.

## Notes / gotchas

- **The catch-all renders, it does not redirect.** `*` is nested *inside* the
  `RequireSession`/`AppShell` branch, so an unknown path is a not-found page inside the shell for a
  signed-in operator (URL preserved) and a redirect to `/login` for a signed-out one. There is no
  `Navigate` on the catch-all — rewriting the URL would hide the typo the operator needs to see.
- **Router package is `react-router` v7**, not `react-router-dom` — v7 merged them, and importing
  the old package name is a silent-drift trap.
- `App.test.tsx` supplies its own `MemoryRouter` (App mounts routes, not a router), and reads the
  live path through a `useLocation()` probe to prove the catch-all preserved it.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [specs/020-frontend-vertical-slice-login-home/DESIGN.md](../../../specs/020-frontend-vertical-slice-login-home/DESIGN.md)
