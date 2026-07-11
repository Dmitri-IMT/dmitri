# Roadmap — Frontend (React SPA)

> **Status:** **greenfield.** No `frontend/` directory exists yet. The stack is already decided
> in [`ADR-008`](../adr/ADR-008-frontend-stack.md); this doc is about *what to build and in what
> order*, not re-deciding the stack.
>
> **Sources:** [`ADR-008`](../adr/ADR-008-frontend-stack.md), [`ADR-005`](../adr/ADR-005-security-model.md),
> [`ui/REFERENCE.md`](../ui/REFERENCE.md), [`ui/FLOWS.md`](../ui/FLOWS.md), [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).
> **Neighbours:** [`BACKEND.md`](BACKEND.md), [`AUTH.md`](AUTH.md), [`AI.md`](AI.md), [`SECURITY.md`](SECURITY.md), [`PI.md`](PI.md).

## Decided stack (ADR-008)

React 19 + TypeScript + **Vite**, **React Router v6**, **TanStack Query v5**, **shadcn/ui**,
**Recharts**, **Axios** (one centralized client in `src/api/client.ts`). Types generated from the
backend OpenAPI via **openapi-typescript** → the contract is compile-time enforced. September slice:
[`ADR-011`](../adr/ADR-011-pi-command-channel.md) + `contracts/openapi/openapi.yaml` (`/hosts`, agents, commands, auth).

## Screens (from ADR-008 + wireframes)

- **Login** (outside the app shell).
- **Dashboard** — summary counts, severity distribution (pie/donut), findings-over-time (bar/line).
- **Scan list** + **Scan detail** (with risk summary).
- **Host inventory** + **Host detail** — discovered machines (`/hosts`; was `/devices` in OpenAPI).
- **Agents** — scanner Pis (`/agents`); online state + **trigger scan**.
- **LLM explainer surface** — see [`AI.md`](AI.md); likely an in-context panel on scan/finding detail, not a separate page.

## Direction & open decisions

- **Build order:** **Admin UI first** (login, invites, user management) before viewer-facing dashboards ([`AUTH.md`](AUTH.md)). Then read-only dashboards, **"scan now"**, LLM deferred.
- **Auth UX:** per [`AUTH.md`](AUTH.md) Phase 1 ✅ — login, invite, password flows, **7-day re-login**, silent refresh, server logout.
- **Pi provisioning:** **not** in business admin UI for September — installer/vendor on-site ([`AUTH.md`](AUTH.md)). Admin UI shows agents (online, trigger scan) only after install.
- **Trigger scan UX:** `POST …/agents/{agent_id}/commands` — on **`503`** + `device_offline` → toast *"Pi seems to be offline."*; on **`409`** + `device_busy` → scan in progress (copy TBD). Poll `GET /commands/{id}` then `GET /scans/{id}`. Agent **online** from `GET /agents/{id}`. See [`BACKEND.md` B6](BACKEND.md#b6--pi-command-channel-).
- **Host inventory:** discovered machines → **`/hosts`** (OpenAPI `/devices` rename per B7) — not the same as scanner **agents**.
- **Real-time:** poll `GET /commands/{id}` for `queued` → `delivered` → `running` → `uploading` → `done`.
- **Device registration/config:** ADR-008 calls this out as the reason TanStack Query (mutations + cache invalidation) was chosen — design the mutation/invalidation flows around it.
- **Wireframes (resolved 2026-07-10, DMI-54):** the March-era `ui/wireframes.md` was web-SPA
  wireframes (the old ⚠️ REVALIDATE note claiming it documented the TUI was wrong) but predated
  auth/agents/Control; it has been removed. Flows are breadboarded in
  [`ui/FLOWS.md`](../ui/FLOWS.md) per [`ui/REFERENCE.md`](../ui/REFERENCE.md); screen
  layouts/states/copy land in [`ui/SCREENS.md`](../ui/SCREENS.md) (template ready, no screen specced yet).

## Milestones

1. Scaffold `frontend/` (Vite + TS + Router + Query + shadcn) + Axios client + OpenAPI type-gen.
2. **Admin UI:** login + invite flow + user/role management + **invite accept** (set password) + forgot/reset + forced rotation screen.
3. Read-only Dashboard + Scan list/detail.
4. Host inventory/detail + agent list/detail (online, scan history) — no Pi pairing UI.
5. **"Scan now" trigger + status** — September (B10 Control); [`PI.md`](PI.md) installer-provisioned daemon.
6. LLM explainer panel (depends on [`AI.md`](AI.md)).

## Ripple

The frontend consumes the backend contract: changes here often start as a need in
[`BACKEND.md`](BACKEND.md) (new endpoint/DTO). Auth UX is bound to
[`SECURITY.md`](SECURITY.md); the trigger UX to [`PI.md`](PI.md); the explainer panel to
[`AI.md`](AI.md).
