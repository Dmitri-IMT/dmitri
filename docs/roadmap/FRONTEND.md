# Roadmap — Frontend (React SPA)

> **Status:** **first vertical slice shipped.** `frontend/` exists: the spec-014 scaffold plus the
> spec-020 login → Home slice (routing, session layer, Home verdict screen). The stack is already
> decided in [`ADR-008`](../adr/ADR-008-frontend-stack.md); this doc is about *what to build and in
> what order*, not re-deciding the stack.
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

- **Public auth:** login, accept invite, forgot/reset password, and voluntary change password.
- **Inside shell:** Home, Scans, Hosts, Agents, Users & invites (admin only), and **Settings**.
- **Settings** is in the MVP after all: a logged-in user has nowhere to change their own password
  (B1 covers only the invite/reset flows). Holds change-password
  and profile — **as built (spec 028) it holds change-password only**, since profile is still blocked
  on C3, and it is open to both roles. **It also gains self-service account removal**
  ([`ADR-017`](../adr/ADR-017-account-removal.md)) — for *both* roles, since a viewer never sees the
  Users screen and Settings is their only way out of the org. It does **not** hold the scan target network — that is a property of the Pi (below).
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
- **Host inventory:** discovered machines → **`/hosts`** (renamed from `/devices` in B7; the read model is `hosts[]` / `host_id` / `host_ip` throughout) — not the same as scanner **agents**.
- **Real-time:** poll `GET /commands/{id}` for `queued` → `delivered` → `running` → `uploading` → `done`.
- **UI status:** flows are drafted, **LOGIN and Home are built** (spec 020), and all other screen
  specs are pending. Shared visual foundations are **written** in
  [`ui/SCREENS.md` §Foundations](../ui/SCREENS.md#foundations) — app shell (top bar, no sidebar),
  light-only theme, typography (IM Fell English titles + IBM Plex Mono for everything else),
  viewport (desktop-only but fluid, 1440/1280), locked neutral palette, shared components, building
  rules, and consistency rules. **The deep purple and the severity hexes are now locked** — they
  were deferred to the build so the accent could be auditioned against real screens, and spec 020
  wrote them into [`ui/SCREENS.md` §Color](../ui/SCREENS.md#color) with measured contrast ratios.
  [`ui/SCREENS.md`](../ui/SCREENS.md) is the source of truth for the UI: where it disagrees with an
  ADR or a roadmap doc, those get reconciled to it (ADR-008's `AppShell` was narrowed to a top bar
  on 2026-07-13). The active UI documents replaced the removed March-era `ui/wireframes.md`.
- **Contract asks — 4 of the original 8 still open.** Raised 2026-07-13 against
  `contracts/openapi/openapi.yaml`; each blocks a flow and none are frontend-solvable — see
  [`ui/FLOWS.md` § Contract asks](../ui/FLOWS.md#contract-asks) and
  [`BACKEND.md` B11](BACKEND.md#b11--frontend-contract-asks-) for the full 18-row list.
  The heavy ones: **`/users` is still listing-less** (C3 ◐, C4) — spec 019 added `GET /users/me`, but
  only `POST /invites` exists beyond it, so listing users or invites, changing a role and revoking
  an invite still have no endpoints, leaving **Users & invites mostly unbuildable** as breadboarded.
  Then `GET /agents` (C1) and the Pi's target network (C2 ◐ — `AgentDetail.available_subnets`
  landed, but nothing persists the chosen `target_subnet`).
  **Closed since:** `HostSummary.first_seen_at` (C6) and `FindingRecord.cve_id` (C8) are both in the
  contract; invite-accept does auto-log-in (C7, returns a full `LoginResponse`). (C5
  forced-password-change is void — forced rotation dropped, [`ADR-016`](../adr/ADR-016-password-policy.md).)
- **Role comes from `GET /users/me`, not a JWT claim** (B11-C16, closed). Spec 020's session layer is
  its only reader and nothing in the SPA decodes a token. ⚠️ **REVALIDATE:**
  [`ADR-008`](../adr/ADR-008-frontend-stack.md) §Papéis still says the role rides in JWT claims and
  now contradicts the shipped code — it needs an amendment.
- **`GET /agents/{agent_id}` is in the contract but unimplemented backend-side** (DMI-78). Spec 020
  wrote `src/api/agents.ts` against it and left it **called by nothing**; Home's Pi-status footer
  line is deliberately not built rather than faked from a `VITE_AGENT_ID` or a scan.
- **Open design decisions (1):** the 409 busy-Pi copy. *(The stale-coverage threshold is decided —
  spec 020 locked it at **3 days**, owned by `STALE_COVERAGE_DAYS` in `frontend/src/lib/review.ts`.)*

## Milestones

1. ◐ Lock shared UI foundations (done — typography and the accent + severity hexes now locked) and
   the auth/Home/Agents flows; resolve the contract blockers needed by those screens. **Auth and
   Home cleared; Agents still blocked on C1** (no `GET /agents`, so no `agent_id` to read).
2. ✅ Scaffold `frontend/` (Vite + TS + Router + Query + shadcn) + Axios client + OpenAPI type-gen —
   spec 014.
3. ✅ First vertical slice: login → Home, including blank, regular, and error states with live data —
   spec 020.
4. ◐ Admin auth and user-management surfaces. ✅ **Invite acceptance, forgot/reset password and the
   voluntary change-password screen shipped 2026-08-07 (spec 028)** — `/invite` consumes spec 027's
   `POST /invites/lookup`, and `/settings` ships change-password only (profile still blocked on C3).
   The flows are built but not usable end to end until invite/reset **email delivery** exists (see
   the provider + SPF/DKIM/DMARC decision in [`ui/status.md`](../ui/status.md)). **Users & invites
   remains blocked on C3/C4** (no `/users` listing endpoints).
   **Widened 2026-08-08** ([`ADR-017`](../adr/ADR-017-account-removal.md)): Users ships **one**
   table — *Person · Role · Status · Last seen* — with pending invites as rows inside it (merged in
   the SPA from `GET /users` + `GET /invites`, which stay separate resources), plus a **Remove**
   action on other people's rows. **This milestone now also reopens Settings**, which shipped in
   spec 028 with change-password only: every role gets self-service account removal there. Both
   removal surfaces share one confirm-by-typing-the-email component — two call sites, so it clears
   the bar in [`ui/status.md`](../ui/status.md) for a shared component.
5. Scan list/detail; host inventory/detail; then Agents read state — no Pi pairing UI.
6. **"Scan now" trigger + status** — September (B10 Control); [`PI.md`](PI.md) installer-provisioned daemon.
7. LLM explainer panel only when it is explicitly brought into scope.

## Ripple

The frontend consumes the backend contract: changes here often start as a need in
[`BACKEND.md`](BACKEND.md) (new endpoint/DTO). Auth UX is bound to
[`SECURITY.md`](SECURITY.md); the trigger UX to [`PI.md`](PI.md); the explainer panel to
[`AI.md`](AI.md).
