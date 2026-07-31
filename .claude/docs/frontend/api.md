---
type: Module
title: frontend API layer
description: The two Axios instances, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, and the three read resource modules.
resource: frontend/src/api/client.ts
tags: [frontend, api, axios, auth, refresh]
timestamp: 2026-07-31T00:00:00Z
---

# frontend API layer

## Purpose

`src/api/` scopes the refresh cookie to auth requests structurally (two Axios instances), attaches
the Bearer token, and recovers an expired session with exactly one refresh — sharing that single
refresh across concurrent 401s. Credential scoping is achieved **solely** by the two-instance split;
no interceptor toggles `withCredentials` by inspecting the URL (approach B from the research doc is
deliberately rejected). On top of that sit the thin, contract-typed read modules the screens call.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `apiClient` | Business Axios instance, `baseURL = ${VITE_API_URL}/api/v1`, `withCredentials` left at the Axios default (`false`). Created bare; the interceptors are attached to it by `client.ts`. | `frontend/src/api/instances.ts:5` |
| `authClient` | Auth Axios instance, same baseURL, `withCredentials: true`. Carries **no** interceptors — so a refresh call's own 401 cannot recurse. | `frontend/src/api/instances.ts:7` |
| `client.ts` (side effects) | Attaches both interceptors to the shared `apiClient` **at import time**, then re-exports `apiClient`/`authClient`. Importing this module is what arms authentication — see the gotcha below. | `frontend/src/api/client.ts:24` |
| `performRefresh()` | Single-flight refresh: memoizes one in-flight `refresh()` in module-scoped `refreshPromise`; concurrent 401s await the same promise; `.finally` resets it. | `frontend/src/api/client.ts:13` |
| response interceptor | On a 401 for a not-yet-retried request: refresh once (guarded by per-request `_retry`), rewrite the header, retry via `apiClient(config)`; on refresh failure clear the token store and **`emitSessionExpired()`**, no second refresh. | `frontend/src/api/client.ts:44` |
| `onSessionExpired()` / `emitSessionExpired()` | Module-scoped handler `Set` — the seam that lets `client.ts` report an unrecoverable session without importing React or the router. | `frontend/src/api/authEvents.ts:5` |
| `login()` / `refresh()` / `logout()` | The **only** callers of `authClient`, hitting `/auth/login`, `/auth/refresh`, `/auth/logout`. `login`/`refresh` write the returned `access_token` to the store; `logout` clears it. | `frontend/src/api/auth.ts:8` |
| `getAccessToken()` / `setAccessToken()` / `clearAccessToken()` | The in-memory token store over a single module-scoped `let accessToken` — never `localStorage`/`sessionStorage`/cookies/React state. | `frontend/src/api/tokenStore.ts:3` |
| `getCurrentUser()` | `GET /users/me`. The **sole** source of identity and role — nothing decodes a JWT anywhere in the app. | `frontend/src/api/users.ts:6` |
| `getLatestScan()` / `getLatestSuccessfulScan()` | Two distinct reads (`LATEST_SCAN_QUERY`, and the same plus `status: 'completed'`), each `per_page: 1`. Return `null` on `{ data: [], total: 0 }`; a `404` is **not** treated as "no scans" and propagates as an error. | `frontend/src/api/scans.ts:25` |
| `listFindings({ scan_id, severity })` | One severity per call (never a list or comma-joined string), `per_page: 100`, returns the **whole envelope** so `total` survives alongside `data`. | `frontend/src/api/findings.ts:15` |
| `HOME_SEVERITIES` | `['critical','high'] as const satisfies readonly Severity[]`. Order is load-bearing — the deck shows critical before high — and `useHomeReview` maps it through `useQueries` rather than hand-writing one `useQuery` per severity. | `frontend/src/api/findings.ts:8` |

## How it connects

- **Import direction is asymmetric and load-bearing.** `instances.ts` is the leaf: it creates both
  Axios objects and imports nothing. `client.ts` imports the bare instances plus `refresh` from
  `auth.ts`, and arms the interceptors. The read modules (`users`, `scans`, `findings`) import
  `apiClient` **from `client.ts`**, never from `instances.ts`. `auth.ts` is the one exception — it
  imports `authClient` from `instances.ts`, because `client.ts` depends on it and the other
  direction would be a genuine cycle.
- `emitSessionExpired()` is consumed by [auth](./auth.md)'s `SessionProvider`, which clears the
  token + query cache and navigates to `/login`.
- The three read modules are consumed by [review](./review.md)'s `useHomeReview()`.
- Consumes the generated types from `src/types/openapi.d.ts` (see [overview](./overview.md)).
- Behavioral proof lives in `src/api/client.test.ts` (one-refresh-on-401, refresh-failure→event,
  concurrent single-flight, cookie scoping) — MSW intercepts at the network layer so these real
  instances run untouched — and in `src/api/authHeader.test.ts`, which proves each read module
  reaches the interceptors *on its own*.

## Notes / gotchas

- **A read module that imports `apiClient` from `instances.ts` silently loses authentication.**
  The interceptors are a side effect of evaluating `client.ts`; if nothing imports that module, no
  `Authorization` header is ever attached and the 401→refresh chain never runs. This shipped
  broken — `users`/`scans`/`findings` all imported `./instances`, and the only importer of
  `./client` was its own test, so the suite stayed green while every authenticated request in the
  browser 401'd. Fixed 2026-07-31; `authHeader.test.ts` guards it.
- **Testing that guard requires module isolation.** `apiClient` is one shared object, so importing
  `./client` anywhere in a test file's graph arms the interceptors for every other module in that
  file. `authHeader.test.ts` therefore calls `vi.resetModules()` and dynamically imports exactly
  one read module per test; a naive version of the same test passes even with the bug present.
- **No `window.location` anywhere in `src/api/`.** The hard `window.location.href = '/login'` that
  spec 014 used on refresh failure was replaced by the `authEvents` bus, so the redirect is a
  router navigation and the module stays free of React/router imports.
- **All three read modules are typed exclusively from `components['schemas'][...]`.** A hand-written
  request/response interface is an ADR-008 violation even when it is correct today.
- **Path tails are relative to the `/api/v1` baseURL** set in `instances.ts` — never repeat the prefix.
- The MSW `/scans` handler branches on `status` and `/findings` branches on `severity`, so the two
  scan reads return genuinely different fixture records (`src/test/mswHandlers.ts`).

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [docs/research/axios-withcredentials-auth-scoping.md](../../../docs/research/axios-withcredentials-auth-scoping.md)
[3] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
