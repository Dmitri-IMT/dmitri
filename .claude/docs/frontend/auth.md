---
type: Module
title: frontend session layer
description: The SessionProvider (boot refresh modelled as a query), the useSession accessor, and the RequireSession route guard.
resource: frontend/src/auth/SessionProvider.tsx
tags: [frontend, auth, session, react, router]
timestamp: 2026-07-29T00:00:00Z
---

# frontend session layer

## Purpose

`src/auth/` owns "who is signed in" for the whole app. It performs one silent refresh at boot — the
mechanism that survives a full page reload given the token lives in memory only — then reads the
profile from `GET /users/me`. It is the single place identity, role, sign-in and sign-out live, and
the only place the session-expiry event is turned into a navigation.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `SessionProvider` | Owns the `['session']` query (boot `refresh()` when no token is held, then `getCurrentUser()`), the `enabled` gate, and the `signIn`/`signOut` actions. Registers the `onSessionExpired` handler. | `frontend/src/auth/SessionProvider.tsx:31` |
| `clearSession()` | Shared teardown: clears the token store and flips `enabled` to `false`. | `frontend/src/auth/SessionProvider.tsx:43` |
| `signIn(credentials)` | `login()` → re-enable → invalidate `['session']` → `navigate('/', { replace: true })`. | `frontend/src/auth/SessionProvider.tsx:63` |
| `signOut()` | `logout()`, then `clearSession()` + `navigate('/login', { replace: true })` — **whether or not the logout call succeeded**. | `frontend/src/auth/SessionProvider.tsx:70` |
| `status` | Derived three-way `'booting' \| 'authenticated' \| 'anonymous'`; checks `!enabled` first so a signed-out user reads `anonymous` immediately rather than falling back to `booting`. | `frontend/src/auth/SessionProvider.tsx:81` |
| `useSession()` | Throws outside the provider. **The only** way any component reads identity or role. | `frontend/src/auth/useSession.ts:4` |
| `RequireSession` | Route guard: `booting` → renders neither protected content **nor** a redirect; `anonymous` → `<Navigate to="/login" replace />`; `authenticated` → `<Outlet />`. | `frontend/src/auth/RequireSession.tsx:4` |

## How it connects

- Consumes [api](./api.md): `refresh()`, `login()`, `logout()`, `getCurrentUser()`, the token store,
  and `onSessionExpired`.
- Mounted by [app](./app.md)'s provider nest in `main.tsx`; `RequireSession` wraps the protected
  branch of `App`'s route table.
- Read by [screens](./screens.md): `Login` (status + `signIn`), `TopBar` (`signOut` only).

## Notes / gotchas

- **The boot refresh must not live in a `useEffect`.** StrictMode double-invokes Effects (React 19
  softened that for `useMemo`/`useCallback`, **not** for Effects), so an Effect fires two
  `POST /auth/refresh` calls; because ADR-008 specifies a **rotating** refresh token, the second
  consumes what the first just rotated, presenting as a phantom dev-only logout that looks like a
  backend fault. Modelling it as `useQuery({ queryKey: ['session'], retry: false })` deduplicates.
  `SessionProvider.test.tsx` asserts exactly one refresh with the provider mounted under
  `<StrictMode>` — the only configuration that catches the double-invoke.
- **Sign-out cannot use a bare `queryClient.clear()`.** The provider's own `['session']` observer
  stays mounted across sign-out, and TanStack Query v5 treats an active observer that loses its
  cached entry as needing to refetch — which silently re-authenticated the user who had just signed
  out. The fix is the `enabled` gate plus a post-commit `removeQueries({ queryKey: ['session'] })`
  (`SessionProvider.tsx:50`); `useBaseQuery` calls `queryCache.build()` on every render regardless
  of `enabled`, so a single synchronous removal inside the handler gets undone by the next render.
- **Nothing decodes a token.** The role is whatever `GET /users/me` returned; a token payload
  claiming a different role does not change it, and no `jwt-decode`-style dependency exists.
- `renderWithProviders.tsx` constructs its `QueryClient` **inside** the function (module scope would
  share a cache across a file) with `retry: false` — without it, error-path tests blow past
  `findBy`'s 1000 ms window on Query's three-retry backoff. Consequently no `useQuery` in
  `src/hooks/` may set its own `retry`, since defaults are only a fallback.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [docs/research/frontend-react19-vite-typescript-conventions.md](../../../docs/research/frontend-react19-vite-typescript-conventions.md)
[3] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
