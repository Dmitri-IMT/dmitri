# ARCHITECTURE — Frontend scaffold (DMI-20 / roadmap T9)

> Frontend-layer feature. This is greenfield: no `frontend/` directory exists yet. Nothing
> under `hardware-agent/` or `backend/` changes, and the TUI/`ScanRunner`/`ScanProgressScreen`
> integration rule from the scanner layer does not apply — there is no orchestrator, no
> `ScanPayload`, no nmap flags here. The equivalent discipline for this layer: the stack,
> folder structure, and auth-client mechanics are **already locked** by
> [`ADR-008`](../../docs/adr/ADR-008-frontend-stack.md) and researched in
> [`docs/research/axios-withcredentials-auth-scoping.md`](../../docs/research/axios-withcredentials-auth-scoping.md).
> This document does not re-decide any of that — it turns those decisions into exact file paths.
> No `INTEGRATION.md` and no `DESIGN.md` accompany this spec: single layer, frozen contract,
> and the only visual surface is a throwaway stub (see `TRUTH.md`).

## System context

The frontend is a React 19 + TypeScript SPA (Vite) that talks to the FastAPI backend
**exclusively** through the frozen OpenAPI contract at
[`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml). It has no server of
its own and no direct database or Pi access. Position in the product:

```
Pi agent → backend ingest/API (frozen contract, /api/v1/...) → frontend SPA (this feature)
```

- **Backend origin:** `http://localhost:8000` in local dev (`VITE_API_URL`), routed under
  `/api/v1` for every business and auth path. Production origins
  (`https://api.vscanner.example.com` / `https://app.vscanner.example.com`) exist in the
  contract's `servers:` block but are **out of scope** here (no deploy/hosting work, per
  constraints below).
- **CORS is already fixed server-side:** the contract's description states browser CORS is
  restricted to `http://localhost:5173` (Vite dev) and the production app origin, with
  credentials allowed. This feature's Vite dev server must run on `5173` (Vite's default) for
  the auth cookie flow to work locally — no CORS config is owned by this feature.
  Verified in [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) line 19.
- **This feature builds:** the project scaffold, the typed API layer generated from the
  contract, the two-Axios-instance client with the single-flight 401→refresh interceptor, an
  in-memory token store, a boot-time silent-refresh attempt, one stub login form, one "signed
  in" placeholder, and the CI job that keeps all of it green.
- **This feature does not build:** any real page (Home, Scans, Hosts, Agents, Users & invites),
  route guards, the `AppShell`/top bar, or any auth screen beyond the login stub. Those are the
  first real-screens feature, per `TRUTH.md` out-of-scope and ADR-008's screen inventory.

## Data model / contracts

### Contract source of truth

All API types come from `contracts/openapi/openapi.yaml` via `openapi-typescript`
(ADR-008 "Geração de Tipos"). **No hand-written interface may model a request/response body
that the contract already defines.** The generated output is committed so contract drift shows
in `git diff` and is re-checked in CI (see Testing expectations).

### Auth endpoints consumed (from the contract, exact paths and shapes)

| Endpoint | Method | Auth | Request body | Response body | Notes |
|---|---|---|---|---|---|
| `/api/v1/auth/login` | POST | none (`security: []`) | `LoginRequest` `{ email, password }` | `LoginResponse` `{ access_token, token_type: "bearer", expires_in }` + `Set-Cookie` (refresh, httpOnly) | 401 on bad credentials; 403 if password rotation is due (forced-change flow — **not built here**, see Constraints) |
| `/api/v1/auth/refresh` | POST | `RefreshCookieAuth` (cookie only, no body, no Bearer) | none | `LoginResponse` (same shape) + rotated `Set-Cookie` | 401 if cookie missing/expired/revoked/reused → SPA redirects to login |
| `/api/v1/auth/logout` | POST | `RefreshCookieAuth` | none | `204`, `Set-Cookie` cleared | Server-side revoke; client must still clear in-memory state |

`LoginResponse` carries **only** the access token, `token_type`, and `expires_in` — the refresh
token never appears in a JSON body, only in the httpOnly cookie. The client must not attempt to
read or store a refresh token itself. Verified in
`contracts/openapi/openapi.yaml` lines 2034–2050 (`LoginResponse` schema) and lines 584–685
(`/auth/login`, `/auth/refresh`, `/auth/logout` operations).

### Config constants

| Constant | Value | Where defined |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` (bare origin, no `/api/v1` suffix) | `.env.example`, read via `import.meta.env.VITE_API_URL` |
| API prefix | `/api/v1`, appended once in the client, never repeated in resource modules | `frontend/src/api/client.ts` |
| Dev server port | `5173` (Vite default — required for the CORS allow-list to match) | `frontend/vite.config.ts` (default; not overridden) |
| Node version | `22` (LTS) | `frontend/.nvmrc`, `frontend/package.json` `engines.node`, CI `actions/setup-node` |

### Two-Axios-instance contract (locked decision 2, backed by the research doc)

- `apiClient` — `axios.create({ baseURL: `${VITE_API_URL}/api/v1}` })`. `withCredentials`
  is left at its Axios default (`false`). Used by **every** business resource module
  (`hosts.ts`, `scans.ts`, etc., as they're added in later features — none exist yet). Carries
  the request interceptor that attaches `Authorization: Bearer <token>` from the in-memory
  store, and the response interceptor that performs the single-flight 401→refresh dance.
- `authClient` — `axios.create({ baseURL: `${VITE_API_URL}/api/v1}`, withCredentials: true })`.
  Used **only** by `login`, `refresh`, `logout` in `frontend/src/api/auth.ts`. Never carries the
  401→refresh response interceptor (excluding it prevents the refresh call's own 401 from
  recursively triggering another refresh — pitfall #2 in the research doc).
- **No URL-matching interceptor toggles credentials by path.** This is a hard constraint from
  the research doc (approach B is explicitly rejected: it fails open/silently on an
  over-matching regex). The two-instance split is the only mechanism that scopes credentials.

### Single-flight 401→refresh interceptor contract

Attached only to `apiClient`'s response interceptors:

1. On a non-401 or a request already marked `_retry`, reject normally (no refresh).
2. On the first 401 for a given expiry window, start `authClient.post('/auth/refresh')`,
   store the pending promise in a module-scoped variable (`refreshPromise`, not React state).
3. Concurrent 401s arriving while `refreshPromise` is pending `await` the **same** promise —
   they do not each start their own refresh (single-flight, TRUTH.md acceptance row
   "Concurrent 401s single-flight").
4. On refresh success: update the in-memory token store, rewrite the failed request's
   `Authorization` header, retry it once via `apiClient(originalConfig)`.
5. On refresh failure: clear the in-memory token store and redirect to `/login`; the pending
   `refreshPromise` is reset (`.finally`) so the next 401 window starts a fresh refresh, but no
   second refresh is attempted for requests already in this failed batch.

### In-memory token store contract

A module-level store (not `localStorage`, not `sessionStorage`, not React context state that
could be duplicated across renders) holding the current `access_token` and its `expires_in`
metadata, with `getAccessToken()`, `setAccessToken(token)`, `clearAccessToken()`. Read by the
`apiClient` request interceptor; written by login, the refresh interceptor, and boot-time
silent refresh; cleared by logout and by refresh failure.

### Boot-time silent refresh

On app start, before rendering any protected content, the app calls `authClient.post('/auth/refresh')`
once. Success populates the in-memory store and the app proceeds; failure leaves the store
empty (app stays on/redirects to the login stub). This is the mechanism that survives a full
page reload per ADR-008's session-lifecycle step 5 and TRUTH.md's "Access token lives in memory
only" business rule. No route guard exists yet to enforce this at the routing layer (deferred
per TRUTH.md) — for this feature it is enforced at the app-root level only (a single check
before rendering the stub content), not per-route.

### Exit codes / CI gate

The `frontend` CI job (see New files table) fails non-zero if any of: `npm ci`, `npm run
gen:types` + `git diff --exit-code` on the generated types dir, `npm run lint`, `npm run
typecheck`, `npm run test`, `npm run build` fails. No new exit codes beyond each tool's own
standard non-zero-on-failure behavior — nothing custom to define.

## New files and naming (mandatory)

All paths are relative to the repo root. Everything under `frontend/` is new (greenfield).

### Root config

| Path | Purpose |
|---|---|
| `frontend/package.json` | npm project manifest; `engines.node: "22.x"`; scripts: `dev`, `build`, `gen:types`, `lint`, `format:check`, `typecheck`, `test` (exact names, see below) |
| `frontend/.nvmrc` | Pins Node `22` (LTS) for local `nvm use` |
| `frontend/.env.example` | Committed template: `VITE_API_URL=http://localhost:8000` |
| `frontend/.gitignore` | Standard Vite/Node ignores (`node_modules`, `dist`, `.env`) |
| `frontend/vite.config.ts` | Vite build/dev config; default port `5173` (not overridden, per CORS allow-list) |
| `frontend/tsconfig.json` (+ `tsconfig.app.json` / `tsconfig.node.json` if Vite's TS template splits them) | TypeScript project config |
| `frontend/tailwind.config.ts` (or `@tailwindcss/vite` plugin entry in `vite.config.ts`, per Tailwind v4's Vite-first setup) | Tailwind CSS v4 config |
| `frontend/postcss.config.js` | Only if Tailwind v4's chosen integration path requires it (may be unnecessary with the `@tailwindcss/vite` plugin — implementer confirms per Tailwind v4 docs at scaffold time) |
| `frontend/components.json` | shadcn/ui CLI config (created by `npx shadcn@latest init`) |
| `frontend/index.html` | Vite SPA entry HTML |
| `frontend/src/main.tsx` | React root; mounts `App`, wraps in `QueryClientProvider` (TanStack Query) — router/provider wiring beyond this minimal mount is not required since no real routes exist yet |
| `frontend/src/App.tsx` | Top-level component: runs boot-time silent refresh, then renders the login stub or the signed-in placeholder based on in-memory auth state |
| `frontend/src/index.css` | Tailwind entry stylesheet (`@import "tailwindcss";` for v4) |

### API layer (`frontend/src/api/`)

| Path | Purpose |
|---|---|
| `frontend/src/api/client.ts` | Defines and exports **both** Axios instances: `apiClient` (Bearer-only, business calls) and `authClient` (`withCredentials: true`, auth calls only). Owns the request interceptor (attach `Authorization`) and the response interceptor (single-flight 401→refresh) on `apiClient` only. |
| `frontend/src/api/auth.ts` | Resource module for `login`, `refresh`, `logout` — the only three functions permitted to call `authClient`. Tails: `/auth/login`, `/auth/refresh`, `/auth/logout`. |
| `frontend/src/api/tokenStore.ts` | In-memory access-token store: `getAccessToken`, `setAccessToken`, `clearAccessToken`. Imported by `client.ts`'s interceptors and by `auth.ts`. |

No other resource modules (`hosts.ts`, `scans.ts`, `agents.ts`, etc.) are created in this
feature — ADR-008 lists them as the folder's eventual contents, but nothing calls them yet
since there are no real pages.

### Types (`frontend/src/types/`)

| Path | Purpose |
|---|---|
| `frontend/src/types/openapi.d.ts` (or `.ts`, per `openapi-typescript`'s default output name — implementer confirms exact filename from the tool's own convention, keep it inside `frontend/src/types/`) | Generated output of `npm run gen:types`, committed. Sole source of API request/response types. |

### Pages (stub only, `frontend/src/pages/`)

| Path | Purpose |
|---|---|
| `frontend/src/pages/LoginStub.tsx` | Throwaway login form: two shadcn/ui `Input`s (email, password) + one `Button`, calls `auth.ts`'s `login()` on submit through `authClient`. Proves the real client mechanics and the real UI stack together. Not a designed screen — replaced wholesale by the first real-screens feature. |
| `frontend/src/pages/SignedInPlaceholder.tsx` | Trivial "signed in" placeholder rendered after a successful login/boot-refresh. No navigation, no real content. |

### UI components (`frontend/src/components/ui/`)

| Path | Purpose |
|---|---|
| `frontend/src/components/ui/button.tsx` | shadcn/ui `button` component, added via `npx shadcn@latest add button` |
| `frontend/src/components/ui/input.tsx` | shadcn/ui `input` component, added via `npx shadcn@latest add input` |

No other `components/`, `hooks/` files are created — both dirs stay empty (or absent) beyond
what ADR-008's folder structure names, since nothing in this feature needs a custom hook or a
non-shadcn component. If the implementer's tooling requires a placeholder file to keep an empty
dir in git, add nothing beyond that; do not pre-build hooks speculatively.

### Test setup

| Path | Purpose |
|---|---|
| `frontend/src/test/setup.ts` | Vitest setup file: MSW server lifecycle (`beforeAll`/`afterEach`/`afterAll`), any global test config (e.g. `@testing-library/jest-dom` matchers if used) |
| `frontend/src/test/mswHandlers.ts` | MSW request handlers for `/api/v1/auth/login`, `/api/v1/auth/refresh`, and one business endpoint stand-in (e.g. `/api/v1/hosts` or any contract path) used to simulate 401→refresh scenarios |
| `frontend/src/api/client.test.ts` | Tests the interceptor contract directly: one-refresh-on-401, refresh-failure-redirect, concurrent-401 single-flight, cookie scoping (see Testing expectations for exact scenarios) |
| `frontend/src/pages/LoginStub.test.tsx` | Tests the stub login form fires a real request through `authClient` and transitions to the signed-in placeholder on success |
| `frontend/vitest.config.ts` (or a `test` block inside `vite.config.ts`) | Vitest configuration: jsdom environment, setup file reference |

### CI

| Path | Purpose |
|---|---|
| `.github/workflows/ci.yml` | **Edit, not new file.** Add a `frontend` job mirroring the existing `backend` job's shape: `actions/checkout`, `actions/setup-node@v4` pinned to Node 22, `working-directory: frontend`, steps: `npm ci` → `npm run gen:types` → `git diff --exit-code -- src/types` (drift check) → `npm run lint` → `npm run format:check` → `npm run typecheck` → `npm run test` → `npm run build`. |

### `package.json` scripts (exact names, all must exist and exit non-zero on failure)

| Script | Purpose |
|---|---|
| `dev` | `vite` — local dev server on port 5173 |
| `build` | `tsc -b && vite build` (or Vite's standard TS+build chain) — production build |
| `gen:types` | `openapi-typescript ../contracts/openapi/openapi.yaml -o src/types/openapi.d.ts` (exact flags per `openapi-typescript`'s current CLI; output path must match the Types table above) |
| `lint` | ESLint over `src/` |
| `format:check` | Prettier (or chosen formatter) `--check` over `src/` |
| `typecheck` | `tsc --noEmit` |
| `test` | `vitest run` (non-watch, CI-safe) |

## Constraints

- **No backend or contract changes.** `contracts/openapi/openapi.yaml` is read-only from this
  feature's perspective; the generated types are the only thing derived from it.
- **No deployment/hosting/container config.** No Dockerfile, no Railway service definition, no
  `nginx`/static-hosting config — that is the ops feature's scope, not this one.
- **No hand-written API types.** Any interface describing a request/response body that the
  contract defines must come from the generated `frontend/src/types/openapi.d.ts` output, never
  hand-authored. This is the mechanism that makes contract drift a compile error.
- **Two known follow-ups from `TRUTH.md`, explicitly NOT solved here:**
  1. Backend confirmation that the refresh cookie is issued with `Path` scoped to the auth
     routes (e.g. `/api/v1/auth`) — the authoritative, browser-enforced guarantee per the
     research doc. This feature's two-instance `withCredentials` split is the client-side
     second barrier, not the first; it does not by itself fix a missing/wrong cookie `Path` if
     the backend has one.
  2. The forced-password-change contract ambiguity (`/auth/login` 403 with no token vs. a
     restricted-scope login) is unresolved (`ADR-008` flags it; `TRUTH.md` names it explicitly
     out of scope). No forced-change-password screen or handling is built in this feature —
     login only handles success (200) and bad-credentials (401) paths in the stub.
- **No new infrastructure.** Everything here is local tooling (npm, Vite, Vitest, MSW) running
  in CI containers already provisioned by the existing GitHub Actions workflow. No
  `HUMAN_INFRA_REQUIRED` items in this feature.

## Testing expectations

Vitest + MSW, per the locked decision. MSW intercepts at the network layer so the real
`apiClient`/`authClient` instances and the real interceptor run in every test — nothing about
the client is mocked directly. Tests live beside the module they exercise (`*.test.ts(x)` next
to the source file), following the convention set by `frontend/src/api/client.test.ts` and
`frontend/src/pages/LoginStub.test.tsx` above; there is no prior frontend test file to mirror
since this is the first frontend feature, so these two files establish the convention future
features should follow.

| TRUTH.md acceptance row | Test file | What it proves |
|---|---|---|
| One refresh on 401 | `frontend/src/api/client.test.ts` | MSW handler returns 401 once then 200 on a business-endpoint stand-in and 200 on `/auth/refresh`; assert exactly one refresh request fired and the original request's retry succeeded |
| Refresh failure → login | `frontend/src/api/client.test.ts` | MSW handler returns 401 on the business call and 401 on `/auth/refresh`; assert in-memory token store is cleared, redirect-to-login is invoked, and no second refresh request fires |
| Concurrent 401s single-flight | `frontend/src/api/client.test.ts` | Fire multiple `apiClient` calls concurrently, all 401; MSW's refresh handler counts invocations; assert exactly one refresh call total and every queued request is retried after it resolves |
| Cookie scoping via the two-instance split | `frontend/src/api/client.test.ts` | Inspect the request config (or MSW-captured request) for a business call vs. an auth call; assert the business call carries no `withCredentials`/cookie and the auth call does |
| Contract drift caught | Not a Vitest test — enforced by the CI job's `npm run gen:types` + `git diff --exit-code` step (see CI table). No frontend test file proves this; it is a CI-only gate. |
| CI tooling gate | Not a Vitest test — the `frontend` CI job itself (`.github/workflows/ci.yml`) is the artifact under test; verified by the job running green end-to-end (install → drift check → lint → typecheck → test → build) |
| Stub proves wiring | `frontend/src/pages/LoginStub.test.tsx` | Render `LoginStub`, fill in credentials, submit; MSW's `/auth/login` handler returns a valid `LoginResponse`; assert the request went through `authClient` (credentialed) and the app transitions to `SignedInPlaceholder` |

`frontend/src/test/mswHandlers.ts` must define the shared handlers these tests use
(`/api/v1/auth/login`, `/api/v1/auth/refresh`, and one business-endpoint stand-in), with
per-test overrides (`server.use(...)`) for the 401/failure variants rather than duplicating
handler definitions per test file.
