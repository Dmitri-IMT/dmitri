# Roadmap — Frontend (React SPA)

> **Status:** **greenfield.** No `frontend/` directory exists yet. The stack is already decided
> in [`ADR-008`](../adr/ADR-008-frontend-stack.md); this doc is about *what to build and in what
> order*, not re-deciding the stack.
>
> **Sources:** [`ADR-008`](../adr/ADR-008-frontend-stack.md), [`ADR-005`](../adr/ADR-005-security-model.md),
> [`ui/REFERENCE.md`](../ui/REFERENCE.md), [`ui/FLOWS.md`](../ui/FLOWS.md), [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml).
> **Neighbours:** [`BACKEND.md`](BACKEND.md), [`AUTH.md`](AUTH.md), [`AI.md`](AI.md), [`SECURITY.md`](SECURITY.md), [`PI.md`](PI.md).

## Decided stack (ADR-008)

React 19 + TypeScript + **Vite**, **React Router v7 (library mode)**, **TanStack Query v5**,
**shadcn/ui**, **Axios** (one centralized client in `src/api/client.ts`). Types generated from the
backend OpenAPI via **openapi-typescript** → the contract is compile-time enforced. September slice:
[`ADR-011`](../adr/ADR-011-pi-command-channel.md) + `contracts/openapi/openapi.yaml` (`/hosts`, agents, commands, auth).

**Recharts** remains the selected library should a scoped data visualization be needed later; it is
not part of the initial Home screen or frontend scaffold.

## Product UI (from `ui/`)

The UI is shaped in this order: [`ui/REFERENCE.md`](../ui/REFERENCE.md) (principles) →
[`ui/FLOWS.md`](../ui/FLOWS.md) (places and connections) →
[`ui/SCREENS.md`](../ui/SCREENS.md) (states, copy, layouts). Do not introduce a screen or
interaction in implementation before it has passed through that sequence.

- **Public auth:** login, accept invite, forgot/reset password, and forced password change.
- **Inside shell:** Home, Scans, Hosts, Agents, Users & invites (admin only), and **Settings**.
- **Settings** is in the MVP after all: a logged-in user has nowhere to change their own password
  ([`AUTH.md`](AUTH.md) mandates 90-day rotation; B1 covers only the *forced* flow). Holds change-password
  and profile. It does **not** hold the scan target network — that is a property of the Pi (below).
- **Home** is the root route (`/`). It is deliberately not a metrics wall:
  it gives a plain-language verdict, only shows actionable critical/high findings, failed scans,
  or stale coverage, and is intentionally sparse when all is clear. Charts and metric cards are
  not in the MVP.
- **Agents:** both roles can read agent state; only admins see **Scan now**. Users & invites is
  omitted for viewers rather than rendered disabled.
- **LLM explainer:** deferred, in-context on scan/finding detail when it is later scoped; no
  separate page.

## Direction & open decisions

- **Build order:** design/admin-first: lock the auth, invite, user-management, Home, and Agents
  flows before their screen specs. Implementation starts with a small vertical slice — login →
  Home with live data — then completes the admin and read surfaces. LLM remains deferred.
- **Auth UX:** per [`AUTH.md`](AUTH.md) Phase 1 ✅ — login, invite, password flows, **7-day re-login**, silent refresh, server logout.
- **Pi provisioning:** **not** in business admin UI for September — installer/vendor on-site ([`AUTH.md`](AUTH.md)). Admin UI shows agents (online, trigger scan) only after install.
- **Single agent.** The MVP has exactly one Pi. The frontend still cannot *discover* it — `agent_id`
  is the provisioning `X-Device-Id` and there is no `GET /agents` (**contract ask C1**).
- **The scan target network is chosen by a human, once, on Agents.** The Pi is deliberately
  dual-homed ([NSPi field test](../tests/nspi-september/plan.md)) — ethernet to the target subnet
  with no default gateway, wifi for internet — so it sees two networks and cannot guess which is the
  target. `POST /commands` requires a `subnet` CIDR that a non-technical admin does not know. The Pi
  reports `available_subnets`; the admin picks one; it persists on the agent as `target_subnet`
  (**contract ask C2**). It is an agent property, not a user preference, so it is not in Settings.
- **Scan mode is not a choice:** the product picks `quick` and does not surface the other four.
- **Trigger scan UX:** admin-only `POST …/agents/{agent_id}/commands`; display a status pill as
  `queued → delivered → running → uploading → done`, then offer **View scan**. On **`503`** +
  `device_offline` show *"Pi seems to be offline."*; on **`409`** + `device_busy`, adopt the Pi's
  running command via `AgentDetail.active_command_id` (copy still to be decided). Poll
  `GET /commands/{id}` every 5s and invalidate the scans, agents, and findings caches once done.
  **Read `active_command_id` on mount** so the pill survives navigation and reloads during a
  ~10-minute scan. See [`ui/FLOWS.md`](../ui/FLOWS.md#b4--scan-now-command-flow)
  and [`BACKEND.md` B6](BACKEND.md#b6--pi-command-channel-).
- **Host inventory:** discovered machines → **`/hosts`** (OpenAPI `/devices` rename per B7) — not the same as scanner **agents**.
- **Real-time:** poll `GET /commands/{id}` for `queued` → `delivered` → `running` → `uploading` → `done`.
- **UI status:** flows are drafted, the Home screen is drafted, and all other screen specs are
  pending. Shared visual foundations are **written** in
  [`ui/SCREENS.md` §Foundations](../ui/SCREENS.md#foundations) — app shell (top bar, no sidebar),
  light-only theme, typography (IM Fell English titles + IBM Plex Mono for everything else),
  viewport (desktop-only but fluid, 1440/1280), locked neutral palette, shared components, building
  rules, and consistency rules. **The deep purple and the severity hexes are deferred on purpose**
  to the build, so the accent can be auditioned against real screens; the rules constraining them
  are already locked and nothing else waits on them.
  [`ui/SCREENS.md`](../ui/SCREENS.md) is the source of truth for the UI: where it disagrees with an
  ADR or a roadmap doc, those get reconciled to it (ADR-008's `AppShell` was narrowed to a top bar
  on 2026-07-13). The active UI documents replaced the removed March-era `ui/wireframes.md`.
- **Contract asks (8).** Raised 2026-07-13 against `contracts/openapi/openapi.yaml`; each blocks a
  flow and none are frontend-solvable — see [`ui/FLOWS.md` § Contract asks](../ui/FLOWS.md#contract-asks).
  The heavy ones: **there is no `/users` path in the contract at all** (C3, C4), which leaves
  **Users & invites mostly unbuildable** as breadboarded — only `POST /invites` exists, so listing
  users or invites, changing a role and revoking an invite have no endpoints. Then `GET /agents`
  (C1) and the Pi's target network (C2). Also: forced-password-change credentials (C5),
  `HostSummary.first_seen_at` (C6), invite auto-login (C7), and whether `FindingRecord` carries a
  `cve_id` (C8).
- **Open design decisions (2):** the stale-coverage threshold (N days) and the 409 busy-Pi copy.

## Milestones

1. Lock shared UI foundations (written; typography + severity hexes open) and the auth/Home/Agents
   flows; resolve the contract blockers needed by those screens.
2. Scaffold `frontend/` (Vite + TS + Router + Query + shadcn) + Axios client + OpenAPI type-gen.
3. First vertical slice: login → Home, including blank, regular, and error states with live data.
4. Admin auth and user-management surfaces: invite acceptance, forgot/reset, forced rotation
   (after its contract gap is resolved), and Users & invites.
5. Scan list/detail; host inventory/detail; then Agents read state — no Pi pairing UI.
6. **"Scan now" trigger + status** — September (B10 Control); [`PI.md`](PI.md) installer-provisioned daemon.
7. LLM explainer panel only when it is explicitly brought into scope.

## Ripple

The frontend consumes the backend contract: changes here often start as a need in
[`BACKEND.md`](BACKEND.md) (new endpoint/DTO). Auth UX is bound to
[`SECURITY.md`](SECURITY.md); the trigger UX to [`PI.md`](PI.md); the explainer panel to
[`AI.md`](AI.md).
