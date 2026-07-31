---
type: Package Overview
title: frontend package overview
description: The React 19 + TypeScript SPA — contract-typed API access, the auth-client plumbing, the session layer, and the first real screens (login → Home).
resource: frontend/
tags: [frontend, spa, react, vite, auth, router]
timestamp: 2026-07-31T00:00:00Z
---

# frontend package overview

## Purpose

`frontend/` is a Vite + React 19 + TypeScript SPA that talks to the FastAPI backend **exclusively**
through the frozen OpenAPI contract at `contracts/openapi/openapi.yaml`. Spec 014 built the
foundation (contract-generated types, the two-Axios-instance auth client, the in-memory token
store) behind a throwaway stub UI. Spec 020 replaced the stubs with the first real vertical slice:
a router, a session provider and route guard, two shells, and the **LOGIN** and **HOME** screens.

The product frame is the verdict, not a dashboard: Home answers "does anything need me?" in one
sentence, backed by a pure derivation over four reads.

## Layout

| Area | What lives there | Doc |
|------|------------------|-----|
| `src/api/` | The typed API layer: the two bare Axios instances (`instances.ts`), the module that arms them with the Bearer + refresh interceptors (`client.ts`), the auth resource module (`auth.ts`), the in-memory token store (`tokenStore.ts`), the session-expiry event bus (`authEvents.ts`), and the read resource modules (`users`/`scans`/`findings`). | [api](./api.md) |
| `src/auth/` | The session layer: `SessionProvider` (boot refresh as a query, sign-in/sign-out), `useSession`, and the `RequireSession` route guard. | [auth](./auth.md) |
| `src/App.tsx`, `src/main.tsx` | The provider nest and the route table. | [app](./app.md) |
| `src/pages/`, `src/components/` | The screens (Login, Home, NotFound), the two shells, the top bar, and the shared presentation components. | [screens](./screens.md) |
| `src/lib/review.ts`, `src/hooks/useHomeReview.ts` | The pure verdict derivation and the hook that composes the four Home reads into one discriminated union. | [review](./review.md) |
| `src/types/openapi.d.ts` | Generated from the frozen contract by `npm run gen:types` (openapi-typescript). Committed; CI re-checks for drift. Sole source of request/response types. | — |
| `src/components/ui/` | shadcn/ui `button`, `input`, `label` only (Tailwind CSS v4, light-only foundation). | — |
| `src/test/`, `*.test.ts(x)` | Vitest + MSW harness (`mswHandlers.ts` fixtures, `renderWithProviders.tsx`); MSW intercepts at the network layer so the real client/interceptor run untouched. | [api](./api.md) |

## How it connects

- Consumes the backend contract [contracts](/contracts.md) via generated types — no hand-written
  request/response models are permitted (ADR-008 §Geração de Tipos).
- The `frontend` CI job in `.github/workflows/ci.yml` gates the layer: `npm ci` → `gen:types` →
  `git diff --exit-code -- src/types` (drift) → `lint` → `format:check` → `typecheck` → `test` →
  `build`.
- Visual foundations (colour, spacing, type scale, the absent-not-disabled rule) are governed by
  [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md), whose §Color table this feature filled in.

## Notes / gotchas

- **Light-only, deliberately.** `index.css` defines no dark theme. `@custom-variant dark` is
  redefined to an unreachable selector (`&:is(.dmitri-dark-unused *)`) rather than deleted —
  deleting it makes Tailwind v4 fall back to its default `prefers-color-scheme: dark` media query,
  which would activate the stray `dark:` classes still present in the untouched shadcn
  `button.tsx`/`input.tsx`.
- **`GET /agents/{agent_id}` is unimplemented backend-side** (DMI-78), so Home's Pi-status footer
  line is deliberately not built. No `VITE_AGENT_ID`, no hardcoded UUID. `src/api/agents.ts` and
  its MSW handler existed but were called by nothing; both were **deleted 2026-07-31** rather than
  left as speculative surface. They return with the feature that needs them.
- **Dev server must run on port `5173`** (Vite default, unoverridden) to match the backend's CORS
  allow-list; the refresh cookie flow depends on it.
- **`.npmrc` pins `legacy-peer-deps=true`** — `openapi-typescript` peers on TS `^5` while the app
  pins TS `~6.0.2`; the setting keeps a plain `npm ci` green in CI.
- **`src/types/` is prettier-ignored** (`frontend/.prettierignore`) so `format:check` passes on the
  unformatted generated file; the drift check (`git diff -- src/types`) is a separate guard.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/TRUTH.md](../../../specs/020-frontend-vertical-slice-login-home/TRUTH.md)
[2] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[3] [specs/014-frontend-scaffold/ARCHITECTURE.md](../../../specs/014-frontend-scaffold/ARCHITECTURE.md)
[4] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
