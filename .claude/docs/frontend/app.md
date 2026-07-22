---
type: Entry Point
title: frontend app root & stub UI
description: The React root, the boot-time silent-refresh gate, and the throwaway login stub + signed-in placeholder.
resource: frontend/src/App.tsx
tags: [frontend, react, entrypoint, auth, stub]
timestamp: 2026-07-22T00:00:00Z
---

# frontend app root & stub UI

## Purpose

The thin visual surface and app-root wiring. On start the app attempts one silent refresh before
rendering protected content — the mechanism that survives a full page reload given the token lives
in memory only. The two "pages" are throwaway stubs that exist to prove the real client mechanics
and the real UI stack together; they are replaced wholesale by the first real-screens feature.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `App` | Tri-state (`loading`/`signedIn`/`signedOut`). A single `useEffect` fires one boot-time `refresh()`; success → `SignedInPlaceholder`, failure → `LoginStub`. App-root enforcement only — no per-route guard, no router. | `frontend/src/App.tsx:6` |
| `main.tsx` root | Mounts `App` inside `<StrictMode>` + `QueryClientProvider` (TanStack Query). No router, guards, or app shell. | `frontend/src/main.tsx:9` |
| `LoginStub` | Two shadcn `Input`s (email, password) + one `Button`; submit calls `auth.ts`'s `login()` through `authClient`; success calls `onSuccess()` to transition, failure shows one generic message. Only 200/401 handled — no forced-password-change flow (contract-ambiguous, out of scope). | `frontend/src/pages/LoginStub.tsx:6` |
| `SignedInPlaceholder` | Trivial one-line "Signed in" placeholder — no navigation, no real content. | `frontend/src/pages/SignedInPlaceholder.tsx:1` |

## How it connects

- Drives the [api](./api.md) layer: `App` calls `refresh()`, `LoginStub` calls `login()`; both
  populate the in-memory token store on success.
- shadcn `Button`/`Input` come from `src/components/ui/` (Tailwind v4, light-only).

## Notes / gotchas

- **StrictMode double-effect (dev only).** The boot `useEffect` has no double-invoke guard, so
  `refresh()` fires twice in dev; production fires once. Left unguarded deliberately on a throwaway
  stub.
- The stub's transition is proven by `src/pages/LoginStub.test.tsx` (real `authClient` round-trip →
  `SignedInPlaceholder`).

# Citations

[1] [specs/014-frontend-scaffold/ARCHITECTURE.md](../../../specs/014-frontend-scaffold/ARCHITECTURE.md)
[2] [specs/014-frontend-scaffold/TRUTH.md](../../../specs/014-frontend-scaffold/TRUTH.md)
