---
type: Module
title: frontend API layer
description: The two Axios instances, the single-flight 401→refresh interceptor, the auth resource module, and the in-memory token store.
resource: frontend/src/api/client.ts
tags: [frontend, api, axios, auth, refresh]
timestamp: 2026-07-22T00:00:00Z
---

# frontend API layer

## Purpose

`src/api/` is the tested plumbing the whole feature exists to prove: it scopes the refresh cookie
to auth requests structurally (two Axios instances), attaches the Bearer token, and recovers an
expired session with exactly one refresh — sharing that single refresh across concurrent 401s.
Credential scoping is achieved **solely** by the two-instance split; no interceptor toggles
`withCredentials` by inspecting the URL (approach B from the research doc is deliberately rejected).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `apiClient` | Business Axios instance, `baseURL = ${VITE_API_URL}/api/v1`, `withCredentials` left at the Axios default (`false`). Carries the Bearer request interceptor and the 401→refresh response interceptor. | `frontend/src/api/client.ts:7` |
| `authClient` | Auth Axios instance, same baseURL, `withCredentials: true`. Carries **no** interceptors — so a refresh call's own 401 cannot recurse. | `frontend/src/api/client.ts:9` |
| `performRefresh()` | Single-flight refresh: memoizes one in-flight `refresh()` in module-scoped `refreshPromise`; concurrent 401s await the same promise; `.finally` resets it. | `frontend/src/api/client.ts:17` |
| request interceptor | Attaches `Authorization: Bearer <token>` from the token store when a token is present. | `frontend/src/api/client.ts:28` |
| response interceptor | On a 401 for a not-yet-retried request: refresh once (guarded by per-request `_retry`), rewrite the header, retry via `apiClient(config)`; on refresh failure clear the token store and `window.location.href = '/login'`, no second refresh. | `frontend/src/api/client.ts:36` |
| `login()` / `refresh()` / `logout()` | The **only** callers of `authClient`, hitting `/auth/login`, `/auth/refresh`, `/auth/logout`. `login`/`refresh` write the returned `access_token` to the store; `logout` clears it. Bodies use the generated `LoginRequest`/`LoginResponse` types. | `frontend/src/api/auth.ts:8` |
| `getAccessToken()` / `setAccessToken()` / `clearAccessToken()` | The in-memory token store over a single module-scoped `let accessToken` — never `localStorage`/`sessionStorage`/cookies/React state. | `frontend/src/api/tokenStore.ts:3` |

## How it connects

- `client.ts` imports `refresh` from `auth.ts`, and `auth.ts` imports `authClient` from `client.ts`
  — a deliberate lazy circular import (neither binding is touched at module-eval time) that keeps
  "`auth.ts` is the only `authClient` caller" literally true.
- Consumes the generated types from `src/types/openapi.d.ts` (see [overview](./overview.md)).
- Driven at app start and on login by [app](./app.md) (`App.tsx` boot refresh, `LoginStub` submit).
- Behavioral proof lives in `src/api/client.test.ts` (one-refresh-on-401, refresh-failure→login,
  concurrent single-flight, cookie scoping) — MSW intercepts at the network layer so these real
  instances run untouched.

## Notes / gotchas

- **Redirect is a hard `window.location.href = '/login'`** — jsdom can't spy on it, so the failure
  test overrides `window.location` for that one case (test-side seam, no app code changed).
- No business resource modules (`hosts.ts`, `scans.ts`, …) exist yet — nothing calls them until the
  real-screens feature.

# Citations

[1] [specs/014-frontend-scaffold/ARCHITECTURE.md](../../../specs/014-frontend-scaffold/ARCHITECTURE.md)
[2] [docs/research/axios-withcredentials-auth-scoping.md](../../../docs/research/axios-withcredentials-auth-scoping.md)
[3] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
