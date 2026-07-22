# Tasks — Frontend scaffold (DMI-20 / roadmap T9, spec 014)

8 tasks. **Unblocked now: #1.**

Order (adapted for the frontend layer, since the scanner pipeline order does not apply):
project/tooling baseline → contract type-gen → UI stack → client mechanics → stub UI → tests → CI.

Parallel tracks after #1: contract type-gen (#2), UI stack (#3), and the token store (#4) share
no dependencies. The client mechanics (#5) join #2+#4; the stub UI (#6) joins #5+#3; tests (#7)
gate #5+#6; the CI job (#8) closes over #2+#7.

## Tooling

- **Node 22 (LTS) + npm.** All scripts run from `frontend/` (`working-directory: frontend` in
  CI), mirroring the existing per-layer `backend` job in `.github/workflows/ci.yml`. Node is
  pinned in `frontend/.nvmrc`, `frontend/package.json` `engines.node`, and the CI
  `actions/setup-node` version — the three must agree.
- **Contract path.** `gen:types` reads the frozen `contracts/openapi/openapi.yaml` at the repo
  root (`../contracts/...` relative to `frontend/`); it is read-only and never modified here.
- **CI provisions its own Node** — no local toolchain assumptions beyond the pinned version.

---

## Task 1: Scaffold the Vite + React + TypeScript project and tooling baseline
- **Description**: Create the greenfield `frontend/` Vite + React 19 + TypeScript project and the CI-runnable tooling per `ARCHITECTURE.md` §§ System context, Config constants, and New files and naming (Root config + `package.json` scripts). Produce a minimal buildable app (placeholder `App`) so `build`, `typecheck`, `lint`, and `format:check` are real, non-interactive, non-zero-on-failure commands. Do not add the API client, type-gen, Tailwind, or tests here — those are dedicated tasks.
- **Dependencies**: —
- **Target Files**: [`frontend/package.json`, `frontend/.nvmrc`, `frontend/.env.example`, `frontend/.gitignore`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/eslint.config.js`, `frontend/.prettierrc`]
- **Success Criteria**:
  - `npm ci` installs from a committed lockfile; `npm run build`, `npm run typecheck`, `npm run lint`, and `npm run format:check` each run headless and exit non-zero on failure.
  - `package.json` declares scripts named exactly `dev`, `build`, `typecheck`, `lint`, `format:check` (the `gen:types` and `test` scripts are added by Tasks 2 and 7); `engines.node` pins Node `22`, and `frontend/.nvmrc` contains `22`.
  - `.env.example` contains `VITE_API_URL=http://localhost:8000` (bare origin, no `/api/v1`); `.env` is gitignored along with `node_modules` and `dist`.
  - The Vite dev server default port is `5173` (not overridden — required by the contract's CORS allow-list); `npm run dev` starts without error.
  - `App.tsx` is a trivial placeholder with no API, auth, or routing logic; `main.tsx` mounts it. No `react-router` routes and no route guards are introduced.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Generate and commit the OpenAPI types from the frozen contract
- **Description**: Wire `openapi-typescript` type generation against the frozen `contracts/openapi/openapi.yaml` and commit the output, per `ARCHITECTURE.md` §§ Contract source of truth, Types, and the `gen:types` script row. This is the artifact the CI drift check (Task 8) enforces.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/package.json`, `frontend/src/types/openapi.d.ts`]
- **Success Criteria**:
  - `package.json` adds `openapi-typescript` as a dev dependency and a `gen:types` script that reads `../contracts/openapi/openapi.yaml` and writes into `frontend/src/types/` (exact output filename per the tool's convention; keep it inside `src/types/`).
  - Running `npm run gen:types` produces the committed types file; running it a second time on the unchanged contract yields **no** `git diff` (idempotent output).
  - The generated file is committed and `npm run typecheck` passes with it present; no hand-written interface models any request/response body the contract already defines.
- **Status**: COMPLETED
- **Review Rejections**: 1

## Task 3: Initialize Tailwind CSS v4 and shadcn/ui with the two stub components
- **Description**: Configure Tailwind CSS v4 and initialize shadcn/ui, then add exactly the `button` and `input` components per `ARCHITECTURE.md` § UI components and locked decision 7 (light-only foundation, add components as used). No other shadcn components.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/components.json`, `frontend/src/index.css`, `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/package.json`, `frontend/vite.config.ts`]
- **Success Criteria**:
  - Tailwind CSS v4 is configured via its Vite-first integration (`@tailwindcss/vite` plugin or the equivalent the current Tailwind v4 docs prescribe); `src/index.css` is the Tailwind entry stylesheet.
  - `components.json` exists (shadcn init); exactly `button.tsx` and `input.tsx` are present under `src/components/ui/` and no other shadcn component is added.
  - The app still builds and type-checks (`npm run build`, `npm run typecheck`) with Tailwind active; a Tailwind-styled element renders.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 4: Implement the in-memory access-token store
- **Description**: Implement the module-level access-token store per `ARCHITECTURE.md` § In-memory token store contract and the `TRUTH.md` "access token lives in memory only" business rule. Foundation consumed by the client interceptors and the auth module.
- **Dependencies**: Task 1
- **Target Files**: [`frontend/src/api/tokenStore.ts`]
- **Success Criteria**:
  - Exposes `getAccessToken()`, `setAccessToken(token)`, and `clearAccessToken()` over module-scoped state.
  - The token is held in a module variable only — never written to `localStorage`, `sessionStorage`, cookies, or React state.
  - `npm run typecheck` and `npm run lint` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 5: Build the two Axios instances, auth resource module, and single-flight 401→refresh interceptor
- **Description**: Implement the core client mechanics per `ARCHITECTURE.md` §§ Two-Axios-instance contract, Single-flight 401→refresh interceptor contract, and Auth endpoints consumed. This is the real, tested plumbing that the whole feature exists to prove.
- **Dependencies**: Tasks 2, 4
- **Target Files**: [`frontend/src/api/client.ts`, `frontend/src/api/auth.ts`]
- **Success Criteria**:
  - `client.ts` exports two instances: `apiClient` (`baseURL = ${VITE_API_URL}/api/v1`, `withCredentials` left at the Axios default `false`) and `authClient` (same `baseURL`, `withCredentials: true`).
  - `apiClient` carries a request interceptor attaching `Authorization: Bearer <token>` from the token store, and a response interceptor implementing the single-flight refresh: the first 401 starts one `authClient.post('/auth/refresh')` stored in a module-scoped promise; concurrent 401s await that same promise; on success the token store is updated, the failed request's `Authorization` is rewritten, and it is retried once (guarded by a per-request `_retry` flag); on refresh failure the token store is cleared and the app redirects to the login route with no second refresh.
  - `authClient` carries **no** 401→refresh response interceptor (so a refresh call's own 401 cannot recurse).
  - `auth.ts` defines `login`, `refresh`, and `logout` as the **only** callers of `authClient`, using tails `/auth/login`, `/auth/refresh`, `/auth/logout`; request/response bodies use the generated types from Task 2.
  - No interceptor toggles `withCredentials` by inspecting the request URL/path; credential scoping is achieved solely by the two-instance split.
  - `npm run typecheck` and `npm run lint` pass. (Behavioral proof is Task 7.)
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 6: Wire boot-time silent refresh, the stub login form, and the signed-in placeholder
- **Description**: Build the thin visual surface and app-root wiring per `ARCHITECTURE.md` §§ Boot-time silent refresh, Pages (stub only), and New files (`main.tsx`, `App.tsx`). The login form must fire a **real** auth request through the client from Task 5 using the shadcn components from Task 3. No route guards, no `AppShell`.
- **Dependencies**: Tasks 3, 5
- **Target Files**: [`frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/pages/LoginStub.tsx`, `frontend/src/pages/SignedInPlaceholder.tsx`]
- **Success Criteria**:
  - On app start, `App` attempts one boot-time `refresh()` before rendering protected content; success populates the token store and renders `SignedInPlaceholder`, failure leaves the store empty and renders `LoginStub`. Enforcement is at the app-root level only (no per-route guard).
  - `LoginStub` renders two shadcn `Input`s (email, password) and one shadcn `Button`, and on submit calls `auth.ts`'s `login()` through `authClient`; a successful login transitions the app to `SignedInPlaceholder`.
  - `main.tsx` mounts `App` wrapped in `QueryClientProvider`; no `react-router` routes, guards, or `AppShell` top bar are added.
  - `npm run build` and `npm run typecheck` pass.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 7: Add the Vitest + MSW harness and the client/stub behavioral tests
- **Description**: Establish the Vitest + MSW test setup and write the tests that prove the auth mechanics per `ARCHITECTURE.md` § Testing expectations and the `TRUTH.md` acceptance rows. MSW intercepts at the network layer so the real `apiClient`/`authClient` and interceptor run untouched. Add the `test` script and test deps.
- **Dependencies**: Tasks 5, 6
- **Target Files**: [`frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/mswHandlers.ts`, `frontend/src/api/client.test.ts`, `frontend/src/pages/LoginStub.test.tsx`, `frontend/package.json`]
- **Success Criteria**:
  - `package.json` adds `vitest`, `msw`, and testing-library deps and a `test` script running `vitest run` (non-watch, headless, non-zero on failure); `vitest.config.ts` uses the jsdom environment and references `src/test/setup.ts`, which manages the MSW server lifecycle (`beforeAll`/`afterEach`/`afterAll`).
  - `mswHandlers.ts` defines shared handlers for `/api/v1/auth/login`, `/api/v1/auth/refresh`, and one business-endpoint stand-in, with per-test `server.use(...)` overrides for the failure variants.
  - `client.test.ts` proves, via MSW: **one refresh on 401** (exactly one `/auth/refresh` then the original request's retry succeeds); **refresh failure → login** (token store cleared, redirect invoked, no second refresh); **concurrent 401s single-flight** (multiple in-flight 401s trigger exactly one refresh total, all retried after it resolves); **cookie scoping** (a business request carries no credentials, an auth request does).
  - `LoginStub.test.tsx` proves the stub fires a real request through `authClient` on submit and transitions to `SignedInPlaceholder` on a mocked successful `LoginResponse`.
  - `npm run test` passes headlessly.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 8: Add the frontend CI job with the gen:types drift check
- **Description**: Add a `frontend` job to the existing `.github/workflows/ci.yml`, mirroring the `backend` job's per-layer shape, per `ARCHITECTURE.md` §§ Exit codes / CI gate and CI, and locked decision 5. This is the authoritative gate for the "contract drift caught" and "CI tooling gate" acceptance rows.
- **Dependencies**: Tasks 2, 7
- **Target Files**: [`.github/workflows/ci.yml`]
- **Success Criteria**:
  - A new `frontend` job runs on the same `push`/`pull_request` to `main` triggers, uses `actions/checkout` + `actions/setup-node` pinned to Node 22, and sets `working-directory: frontend`.
  - Steps run in order and the job fails if any fails: `npm ci` → `npm run gen:types` → `git diff --exit-code -- src/types` (drift check) → `npm run lint` → `npm run format:check` → `npm run typecheck` → `npm run test` → `npm run build`.
  - The existing `validate`, `lint`, `tests`, and `backend` jobs are unchanged; no deployment/hosting steps are added.
  - **[Tracked from Task 3 review]** `npm run format:check` must pass in CI — the generated `src/types/openapi.d.ts` is NOT prettier-formatted, so a committed `frontend/.prettierignore` covering `src/types/` (or equivalent) must exist so `format:check` exits 0. Resolve as part of this task.
- **Status**: COMPLETED
- **Review Rejections**: 0

---

## Dependency graph

```text
        ┌─→ #2 ──────────────┬───────────────→ #8
#1 ─────┼─→ #4 ──┐           │                  ↑
        │        ├─→ #5 ─┬─→ #6 ─┬─→ #7 ────────┘
        └─→ #3 ──────────┘       │
                 └───────────────┘
```

(#5 depends on #2 + #4; #6 depends on #5 + #3; #7 depends on #5 + #6; #8 depends on #2 + #7.)

## Acceptance-criteria coverage

| TRUTH.md scenario | Task(s) |
|---|---|
| Clean build | #1, #2 (verified end-to-end by #8) |
| One refresh on 401 | #5 (impl), #7 (test) |
| Refresh failure → login | #5, #7 |
| Concurrent 401s single-flight | #5, #7 |
| Cookie scoping | #5, #7 |
| Contract drift caught | #2 (artifact), #8 (gate) |
| CI tooling gate | #8 |
| Stub proves wiring | #6, #7 |

## Status

| # | Task | Status |
|---|------|--------|
| 1 | Scaffold the Vite + React + TypeScript project and tooling baseline | COMPLETED |
| 2 | Generate and commit the OpenAPI types from the frozen contract | COMPLETED |
| 3 | Initialize Tailwind CSS v4 and shadcn/ui with the two stub components | COMPLETED |
| 4 | Implement the in-memory access-token store | COMPLETED |
| 5 | Build the two Axios instances, auth resource module, and single-flight 401→refresh interceptor | COMPLETED |
| 6 | Wire boot-time silent refresh, the stub login form, and the signed-in placeholder | COMPLETED |
| 7 | Add the Vitest + MSW harness and the client/stub behavioral tests | COMPLETED |
| 8 | Add the frontend CI job with the gen:types drift check | COMPLETED |
