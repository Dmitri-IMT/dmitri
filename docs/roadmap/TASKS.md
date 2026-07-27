# Roadmap — Tasks (no-Pi work)

> **What this is:** the actionable task list extracted from the per-layer roadmap docs,
> scoped to **work that does not require Raspberry Pi hardware**. No Pi is in possession;
> every Pi-gated step is parked at the bottom. Ordered so each tier unblocks the next.
>
> **Sources:** [`README.md`](README.md), [`BACKEND.md`](BACKEND.md), [`PI.md`](PI.md),
> [`AUTH.md`](AUTH.md), [`FRONTEND.md`](FRONTEND.md), [`SECURITY.md`](SECURITY.md), [`AI.md`](AI.md).

---

## Tier 1 — Decisions to lock (gate the code below)

- [x] **T1 · B8 — Reuse `backend/` code.** ✅ Resolved in [`BACKEND.md` Reuse](BACKEND.md#reuse-from-backend-code-):
  keep the `services/` enrichment + scoring engine; discard the app shell (`main.py`, `db/session.py`
  stack, `config.py`, routers placeholder); keep-with-changes for `persist_scan`, data model, worker,
  scan schemas. *No longer blocks backend work.*
- [x] **T3 · Reconcile ADR-005.** ✅ **Amended, not superseded:** ADR-005 stays the v1 security
  baseline; its §1 agent directionality is amended by [`ADR-011`](../adr/ADR-011-pi-command-channel.md)
  (agent channel now bidirectional; signature rules reused for the WS upgrade). Added the amendment +
  status note to ADR-005, cleared the ⚠️ REVALIDATE flag in [`PI.md`](PI.md), and replaced the stale
  "proposal" framing in [`SECURITY.md`](SECURITY.md) with an authority map.

## Tier 2 — Build / refactor (runs on dev machine, no Pi)

> **Build-time prerequisite (not a now-task): T2 · validate the OpenAPI contract into a baseline.**
> [`contracts/openapi/openapi.yaml`](../../contracts/openapi/openapi.yaml) already contains a
> September-slice **draft** written ahead of the code (`/hosts`, `/agents`, `/commands`, `/auth/*`,
> typed WS envelope, trigger codes `503 device_offline` / `409 device_busy`). It is a **draft to
> validate against the locked [B6](BACKEND.md#b6--pi-command-channel-)/[B7](BACKEND.md#b7--openapi-contract-)
> decisions + [`ADR-011`](../adr/ADR-011-pi-command-channel.md)** — correct the drift, don't ship it as-is.
> Do it *immediately before* T6/T7 (backend routes) and T9 (frontend type-gen), not now.
>
> **"Freeze" was retired 2026-07-13.** T2 was written on 2026-07-04, *before* the
> [B11 contract asks](BACKEND.md#b11--frontend-contract-asks-) were raised. Those asks are now an epic
> of their own, and **its sub-issues each amend this same file after T2 lands** — so a freeze at T2
> would be a freeze in name only. T2 produces a **baseline**: correct against every decision that
> exists on the day it lands, and the thing T6/T7/T9 build from. The B11 amendments follow.

- [ ] **T4.1 · Study and fix NSPi port stage.** Review why NSPi mode failed on the real NSPi LAN
  (field test [`../tests/nspi-september/results.md`](../tests/nspi-september/results.md): discovery
  OK, 0 ports, partial cancel during port stage while Quick succeeds on the same subnet). Investigate
  two-pass `-T2` batching, timeouts, progress UX, and log retention. **No field retest planned** —
  fix and validate in dev; pilot continues on **Quick scan** + dual-homed laptop per field-test close.
- [ ] **T4 · Split headless daemon from TUI.** Make the scan pipeline (`ScanRunner` / stages)
  callable headlessly, separate from the Textual TUI — a `dmitri agent` entrypoint that runs the
  **same** pipeline without a screen ([`PI.md` Pi runtime](PI.md#pi-runtime-september-control)).
  ⚠️ Honor the CLAUDE.md integration rule: trace every `ScanRunner` / `ScanProgressScreen` call site.
- [ ] **T5 · Pi HTTP ingest client + Ed25519 signing.** Build the `POST /api/v1/scans` client with
  per-device Ed25519 signatures ([`PI.md` milestone 0](PI.md#milestones)). Testable against a local backend.
- [ ] **T6 · Auth Phase 1 — identity schema + middleware.** Alembic migrations (`org_id`, users,
  invites, roles); JWT Bearer on business routes; Ed25519 signature verify on Pi routes; `/auth/login`,
  `/auth/refresh`, `/auth/logout`, `/auth/change-password`; invite flow; breach-screened password
  policy (no forced rotation, [`ADR-016`](../adr/ADR-016-password-policy.md)); 15-min access / 7-day refresh sessions. Fully specced in [`AUTH.md` Phase 1](AUTH.md#phase-1--nspi--september-).
- [ ] **T7 · Backend command-channel skeleton.** `agents` / `commands` / `hosts` / `scans` tables,
  lifecycle state machine (`queued`→`delivered`→`running`→`uploading`→`done`/`failed`/`expired`),
  WS endpoint + connection registry, `POST …/agents/{id}/commands` enqueue (stub scan row). Drive
  with a fake local WS agent — no Pi. Per [`BACKEND.md` B6](BACKEND.md#b6--pi-command-channel-).

## Tier 3 — Frontend (greenfield)

- [ ] **T8 · Lock frontend open decisions.** Confirm admin-first build order; design the
  mutation / cache-invalidation flows (TanStack Query); set real-time strategy (poll
  `GET /commands/{id}`); confirm no web wireframe exists (the current one is the TUI — ⚠️ REVALIDATE
  in [`FRONTEND.md`](FRONTEND.md)).
- [ ] **T9 · Scaffold `frontend/`.** Vite + TS + Router + Query + shadcn + Axios client +
  `openapi-typescript` type-gen against the T2 contract. *Depends on T2.*

---

## Parked — Pi-gated (cannot do without hardware)

- Procure Pi 4 BOM per [`ADR-001`](../adr/ADR-001-hardware-selection.md).
- Flash Raspberry Pi OS Lite; headless SSH; static IP / DHCP reservation.
- Install `nmap`, `uv`, agent; **verify scan on real hardware**.
- Installer secret handoff; write `/etc/dmitri/agent.env`; enable `dmitri-agent.service`; verify WSS + ingest.
- Scheduled reboot policy.

See [`PI.md` Hardware acquisition](PI.md#hardware-acquisition--installer-provisioning) for owners.

---

## Suggested start

**T1** (B8 reuse ✅) and **T3** (reconcile ADR-005 ✅) are done. Next dev-machine work with no Pi:
**T4.1** (NSPi port-stage fix — blocks the September pilot scan mode), then **T4** (headless daemon
split). **T2 (OpenAPI freeze) is deliberately deferred** to just before the build tasks that consume
it (T6/T7/T9) — see the Tier 2 note.

## Dependency notes

- T2 → T6, T7, T9 (contract freeze is a build-time prerequisite for routes + frontend types; do it just before them, not now).
- T1 → T6, T7 (reuse call precedes backend build).
- T4.1 is independent of T4; not gated on another NSPi visit (field test closed).
- T4 → T5 (headless pipeline precedes ingest client wiring).
- T6, T7 are independent of each other but both want T1/T2 settled first.
