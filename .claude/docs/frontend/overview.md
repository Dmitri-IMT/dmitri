---
type: Package Overview
title: frontend package overview
description: The React 19 + TypeScript SPA scaffold — contract-typed API access and the auth-client plumbing, with only a throwaway stub UI.
resource: frontend/
tags: [frontend, spa, react, vite, auth]
timestamp: 2026-07-22T00:00:00Z
---

# frontend package overview

## Purpose

`frontend/` is a greenfield Vite + React 19 + TypeScript SPA that talks to the FastAPI backend
**exclusively** through the frozen OpenAPI contract at `contracts/openapi/openapi.yaml`. This
feature (spec 014 / roadmap T9) builds the *foundation only*: contract-generated API types, the
two-Axios-instance auth client with a single-flight 401→refresh interceptor, an in-memory token
store, a boot-time silent-refresh attempt, and exactly one throwaway login stub plus a "signed in"
placeholder. The governing scope rule: **if a test case touches it, it is built for real; if it is
a screen, it is a stub.**

## Layout

| Area | What lives there | Doc |
|------|------------------|-----|
| `src/api/` | The typed API layer: both Axios instances + the refresh interceptor (`client.ts`), the auth resource module (`auth.ts`), the in-memory token store (`tokenStore.ts`). | [api](./api.md) |
| `src/App.tsx`, `src/main.tsx`, `src/pages/` | App-root wiring: boot-time silent refresh, the login stub, the signed-in placeholder. | [app](./app.md) |
| `src/types/openapi.d.ts` | Generated from the frozen contract by `npm run gen:types` (openapi-typescript). Committed; CI re-checks for drift. Sole source of request/response types. | — |
| `src/components/ui/` | shadcn/ui `button` + `input` only (Tailwind CSS v4, light-only foundation). | — |
| `src/test/`, `*.test.ts(x)` | Vitest + MSW harness; MSW intercepts at the network layer so the real client/interceptor run untouched. | [api](./api.md) |

## How it connects

- Consumes the backend contract [contracts](/contracts.md) via generated types — no hand-written
  request/response models are permitted.
- The `frontend` CI job in `.github/workflows/ci.yml` gates the layer: `npm ci` → `gen:types` →
  `git diff --exit-code -- src/types` (drift) → `lint` → `format:check` → `typecheck` → `test` →
  `build`.

## Notes / gotchas

- **Stub-only UI.** No real pages, route guards, or app shell exist yet — those are the first
  real-screens feature. `App.tsx` enforces auth at the app-root level only (no per-route guard).
- **Dev server must run on port `5173`** (Vite default, unoverridden) to match the backend's CORS
  allow-list; the refresh cookie flow depends on it.
- **`.npmrc` pins `legacy-peer-deps=true`** — `openapi-typescript` peers on TS `^5` while the
  scaffold pins TS `~6.0.2`; the setting keeps a plain `npm ci` green in CI.
- **`src/types/` is prettier-ignored** (`frontend/.prettierignore`) so `format:check` passes on the
  unformatted generated file; the drift check (`git diff -- src/types`) is a separate, independent
  guard.

# Citations

[1] [specs/014-frontend-scaffold/TRUTH.md](../../../specs/014-frontend-scaffold/TRUTH.md)
[2] [specs/014-frontend-scaffold/ARCHITECTURE.md](../../../specs/014-frontend-scaffold/ARCHITECTURE.md)
[3] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
