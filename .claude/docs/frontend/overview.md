---
type: Package Overview
title: frontend package overview
description: The React 19 + TypeScript SPA — contract-typed API access, auth/session plumbing, public and guarded screens, local UI-foundation lint rules, and Railway static deployment.
resource: frontend/
tags: [frontend, spa, react, vite, auth, router]
timestamp: 2026-10-01T00:00:00Z
---

# frontend package overview

## Purpose

`frontend/` is a Vite + React 19 + TypeScript SPA that talks to the FastAPI backend **exclusively**
through the frozen OpenAPI contract at `contracts/openapi/openapi.yaml`. Spec 014 built the
foundation (contract-generated types, the two-Axios-instance auth client, the in-memory token
store) behind a throwaway stub UI. Spec 020 replaced the stubs with the first real vertical slice:
a router, a session provider and route guard, two shells, and the **LOGIN** and **HOME** screens.
Spec 028 completed the auth surface around it. Spec 035 added executable UI-foundation guardrails.
Spec 039 (DMI-88) added scan and host read surfaces. Spec 040 (DMI-89) shipped the scan trigger.
Spec 042 (DMI-131) restyled the SPA — design-system v2 tokens, `/network` and `/devices` IA,
`SeverityWord`, six ESLint rules, and the Home attention table.

The product frame is the verdict, not a dashboard: Home answers "does anything need me?" from
one `GET /home` snapshot (attention, notices, events, activity).

The browser bundle requires a public `VITE_API_URL` at build time. The API client and Vite config
both fail fast when it is absent, so hosted builds cannot silently target localhost.

## Layout

| Area | What lives there | Doc |
|------|------------------|-----|
| `src/api/` | The typed API layer: instances, client interceptors, auth, token store, query keys, and resource modules (`users`/`scans`/`hosts`/`findings`/`agents`/`commands`). | [api](./api.md) |
| `src/auth/` | The session layer: `SessionProvider`, `useSession`, and route guards. | [auth](./auth.md) |
| `src/App.tsx`, `src/main.tsx` | The provider nest and the route table. | [app](./app.md) |
| `eslint.config.js`, `eslint-rules/` | Six local authored-source rules for named tokens, spacing, interactive primitives, raw hex, and dark variants. | [linting](./linting.md) |
| `src/pages/`, `src/components/` | Screens (auth, Home, Scans, ScanDetail, Network, HostDetail, Devices, DeviceDetail, Settings, Users, NotFound), shells, top bar, `DataTable` and friends. | [screens](./screens.md), [tables](./tables.md) |
| `src/api/home.ts`, `src/hooks/useHome.ts` | `getHome` and the one-query Home snapshot hook. | [review](./review.md) |
| `src/lib/scanStatus.ts`, `src/lib/severity.ts` | Scan-status labels / count hiding, and the load-bearing `bySeverityDesc` comparator. | [scan-status](./scan-status.md) |
| `src/lib/commandStatus.ts` | Command lifecycle labels and the settled predicate for the device-detail poll. | [command-status](./command-status.md) |
| `src/lib/scanModes.ts`, `src/lib/hostLastSeen.ts` | Scan-mode labels/order/default; host last-seen quiet-row helpers. | [devices-screen](./devices-screen.md), [screens](./screens.md) |
| `src/hooks/useScanCommand.ts`, `src/pages/agents/`, `src/pages/Devices.tsx`, `src/pages/DeviceDetail.tsx` | Command follow/poll/trigger and device-detail sections. | [devices-screen](./devices-screen.md) |
| `src/lib/detailState.ts`, `src/pages/hosts/HostFindings.tsx` | The shared detail-route state reader, and the host's second read owning its own section states. | [host-detail](./host-detail.md) |
| `src/types/openapi.d.ts` | Generated from the frozen contract by `npm run gen:types`. Committed; CI re-checks for drift. | — |
| `src/components/ui/` | shadcn/ui primitives (`button`, `input`, `label`, `card`, `dialog`, `tabs`, `pagination`, `select`). | — |
| `src/test/`, `*.test.ts(x)` | Vitest + MSW harness. | [api](./api.md) |

## How it connects

- Consumes the backend contract [contracts](/contracts.md) via generated types — no hand-written
  request/response models are permitted (ADR-008 §Geração de Tipos).
- The `frontend` CI job in `.github/workflows/ci.yml` gates the layer: `npm ci` → `gen:types` →
  `git diff --exit-code -- src/types` (drift) → `lint` (including the six local UI-foundation
  rules) → `format:check` → `typecheck` → `test` → `build` with
  `VITE_API_URL=http://localhost:8000`.
- Visual foundations are governed by [docs/ui/FOUNDATIONS.md](../../../docs/ui/FOUNDATIONS.md).

## Notes / gotchas

- **Hosted static deployment.** Railway builds `frontend/Dockerfile` and serves the resulting
  `dist/` through `frontend/Caddyfile`.
- **No localhost fallback.** `VITE_API_URL` is required in both the Vite config and API client.
- **Light-only, deliberately.** `index.css` defines no dark theme; `no-dark-variant` ESLint blocks
  `dark:` in authored source. Vendored shadcn primitives keep dormant `dark:` classes under an
  unreachable `@custom-variant`.
- **`GET /agents` and the command channel are wired in the SPA** (DMI-89). Device list and detail
  consume them. Home does not fetch agents.
- **`format:check` currently fails repo-wide on a Windows working copy** — open item; CI on Linux
  is unaffected.
- **Dev server must run on port `5173`** (Vite default, unoverridden).
- **`.npmrc` pins `legacy-peer-deps=true`** — TS 6 vs openapi-typescript peer.
- **`src/types/` is prettier-ignored** so `format:check` passes on the generated file.

# Citations

[1] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
[2] [docs/adr/ADR-008-frontend-stack.md](../../../docs/adr/ADR-008-frontend-stack.md)
