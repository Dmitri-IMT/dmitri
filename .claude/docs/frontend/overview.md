---
type: Package Overview
title: frontend package overview
description: The React 19 + TypeScript SPA — contract-typed API access, auth/session plumbing, public and guarded screens, local UI-foundation lint rules, and Railway static deployment.
resource: frontend/
tags: [frontend, spa, react, vite, auth, router]
timestamp: 2026-08-29T00:00:00Z
---

# frontend package overview

## Purpose

`frontend/` is a Vite + React 19 + TypeScript SPA that talks to the FastAPI backend **exclusively**
through the frozen OpenAPI contract at `contracts/openapi/openapi.yaml`. Spec 014 built the
foundation (contract-generated types, the two-Axios-instance auth client, the in-memory token
store) behind a throwaway stub UI. Spec 020 replaced the stubs with the first real vertical slice:
a router, a session provider and route guard, two shells, and the **LOGIN** and **HOME** screens.
Spec 028 completed the auth surface around it: **FORGOT PASSWORD**, **RESET PASSWORD**, **ACCEPT
INVITE** (all public) and **SETTINGS** (guarded), plus the second nav item that ended the top bar's
transitional one-item centring.
Spec 035 added executable UI-foundation guardrails and aligned the existing shells, navigation,
Settings surface and auth screens with the named width, type and spacing tokens.
Spec 039 (DMI-88) added SCAN LIST, SCAN DETAIL, HOST INVENTORY, HOST DETAIL, and a read-only Agents
page shell. Spec 040 (DMI-89) shipped the scan trigger: agent reads, subnet chooser, `[Scan now]`,
command poll, cache invalidation on completion, and `FirstScanCta` on Home/Scans/Hosts blanks.

The product frame is the verdict, not a dashboard: Home answers "does anything need me?" in one
sentence, backed by a pure derivation over four reads.

The browser bundle requires a public `VITE_API_URL` at build time. The API client and Vite config
both fail fast when it is absent, so hosted builds cannot silently target localhost.

## Layout

| Area | What lives there | Doc |
|------|------------------|-----|
| `src/api/` | The typed API layer: the two bare Axios instances (`instances.ts`), the module that arms them with the Bearer + refresh interceptors (`client.ts`), the auth resource module (`auth.ts`), the in-memory token store (`tokenStore.ts`), the session-expiry event bus (`authEvents.ts`), the change-password module (`passwords.ts`), prefix-shaped `queryKeys.ts`, and the resource modules (`users`/`scans`/`hosts`/`findings`/`agents`/`commands`). | [api](./api.md) |
| `src/auth/` | The session layer: `SessionProvider` (boot refresh as a query, sign-in/sign-out/invite acceptance), `useSession`, and the `RequireSession` route guard. | [auth](./auth.md) |
| `src/App.tsx`, `src/main.tsx` | The provider nest and the route table. | [app](./app.md) |
| `eslint.config.js`, `eslint-rules/` | The local authored-source rules for named Tailwind widths, type and spacing plus shared interactive primitives. | [linting](./linting.md) |
| `src/pages/`, `src/components/` | Screens (auth, Home, Scans, ScanDetail, Hosts, HostDetail, Agents, Settings, Users, NotFound), the two shells, the top bar, `DataTable` and friends, and shared presentation components. | [screens](./screens.md), [tables](./tables.md) |
| `src/lib/review.ts`, `src/hooks/useHomeReview.ts` | The pure verdict derivation and the hook that composes the four Home reads into one discriminated union. | [review](./review.md) |
| `src/lib/scanStatus.ts`, `src/lib/severity.ts` | Scan-status pills / unfinished predicate, and the load-bearing `bySeverityDesc` comparator. | [scan-status](./scan-status.md) |
| `src/lib/commandStatus.ts` | Command lifecycle pills and the terminal predicate for the Agents poll. | [command-status](./command-status.md) |
| `src/hooks/useAgentScreen.ts`, `src/hooks/useScanCommand.ts`, `src/pages/agents/` | The Agents screen read union, command follow/poll/trigger, and screen-specific sections. | [agents-screen](./agents-screen.md) |
| `src/lib/detailState.ts`, `src/pages/hosts/HostFindings.tsx` | The shared detail-route state reader, and the host's second read owning its own section states. | [host-detail](./host-detail.md) |
| `src/types/openapi.d.ts` | Generated from the frozen contract by `npm run gen:types` (openapi-typescript). Committed; CI re-checks for drift. Sole source of request/response types. | — |
| `vite.config.ts` | Loads Vite environment variables and rejects a missing `VITE_API_URL` before the production build starts. | — |
| `Dockerfile`, `Caddyfile` | Build the SPA with Node 22, serve `dist/` with Caddy on Railway's `$PORT`, and rewrite deep links to `index.html`. | — |
| `src/components/ui/` | shadcn/ui `button`, `input`, `label` only (Tailwind CSS v4, light-only foundation). | — |
| `src/test/`, `*.test.ts(x)` | Vitest + MSW harness (`mswHandlers.ts` fixtures, `renderWithProviders.tsx`); MSW intercepts at the network layer so the real client/interceptor run untouched. | [api](./api.md) |

## How it connects

- Consumes the backend contract [contracts](/contracts.md) via generated types — no hand-written
  request/response models are permitted (ADR-008 §Geração de Tipos).
- The `frontend` CI job in `.github/workflows/ci.yml` gates the layer: `npm ci` → `gen:types` →
  `git diff --exit-code -- src/types` (drift) → `lint` (including the four local UI-foundation
  rules) → `format:check` → `typecheck` → `test` → `build` with
  `VITE_API_URL=http://localhost:8000`.
- Visual foundations (colour, spacing, type scale, the absent-not-disabled rule) are governed by
  [docs/ui/SCREENS.md](../../../docs/ui/SCREENS.md), whose §Color table this feature filled in.

## Notes / gotchas

- **Hosted static deployment.** Railway builds `frontend/Dockerfile` and serves the resulting
  `dist/` through `frontend/Caddyfile`; Caddy listens on Railway's `$PORT`, serves `/health`, and
  rewrites unknown paths to `index.html` for React Router deep links.
- **No localhost fallback.** `VITE_API_URL` is required in both the Vite config and API client.
  Railway must provide the public API service URL as a Docker build argument; the deployed bundle
  carries that URL at build time.

- **Light-only, deliberately.** `index.css` defines no dark theme. `@custom-variant dark` is
  redefined to an unreachable selector (`&:is(.dmitri-dark-unused *)`) rather than deleted —
  deleting it makes Tailwind v4 fall back to its default `prefers-color-scheme: dark` media query,
  which would activate the stray `dark:` classes still present in the untouched shadcn
  `button.tsx`/`input.tsx`.
- **`GET /agents` and the command channel are wired in the SPA** (DMI-89). `src/api/agents.ts` and
  `src/api/commands.ts` serve the Agents screen. **Home's Pi-status footer line is still not
  built** — `HomeFooter` reads no agent data.
- **`format:check` currently fails repo-wide on a Windows working copy.** Roughly 50 files —
  including ones no feature has touched — report as unformatted because the checkout is CRLF and
  Prettier expects LF. It reproduces on a clean tree, so it is a line-ending condition, not a
  feature's doing. Fixing it means a `.gitattributes` / `core.autocrlf` decision, **not** running a
  repo-wide formatter (forbidden by `.claude/CLAUDE.md`). CI on Linux is unaffected. Open item.
- **The Vitest forks pool cannot spawn workers on that same machine** ("Timeout waiting for worker
  to respond", zero tests collected). Run `npx vitest run --pool=threads --maxWorkers=1
  --no-file-parallelism` there; the default configuration is fine in CI.
- **Dev server must run on port `5173`** (Vite default, unoverridden). Local development must set
  the backend's fail-closed `CORS_ALLOWED_ORIGINS` explicitly to `http://localhost:5173`; the
  refresh-cookie flow depends on that exact browser origin being allowed.
- **`.npmrc` pins `legacy-peer-deps=true`** — `openapi-typescript` peers on TS `^5` while the app
  pins TS `~6.0.2`; the setting keeps a plain `npm ci` green in CI.
- **`src/types/` is prettier-ignored** (`frontend/.prettierignore`) so `format:check` passes on the
  unformatted generated file; the drift check (`git diff -- src/types`) is a separate guard.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/TRUTH.md](../../../specs/020-frontend-vertical-slice-login-home/TRUTH.md)
[2] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[3] [specs/014-frontend-scaffold/ARCHITECTURE.md](../../../specs/014-frontend-scaffold/ARCHITECTURE.md)
[4] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
