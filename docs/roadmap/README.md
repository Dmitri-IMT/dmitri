# Product Roadmap — Dmitri

> **What this folder is:** forward-looking, per-layer roadmaps for taking Dmitri from
> "working TUI + scanning backend" to the **final product** (remotely-commandable Pi,
> frontend-facing backend, web app, and an in-app LLM explainer).
>
> **What this folder is *not*:** current-state architecture (see
> [`../architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md)) or locked decisions
> (see [`../adr/`](../adr/)). Those documents hold real truth, but **they are not absolute** —
> several were written before the current code existed. Where a roadmap doc relies on an ADR
> claim that needs checking against reality, it is flagged **⚠️ REVALIDATE**.

## Documents

| Doc | Layer | Status today |
|-----|-------|--------------|
| [`PI.md`](PI.md) | Raspberry Pi agent | **Daemon and backend client built in software.** A **Pi 3** is in hand since 2026-08-21 — not the Pi 4 ADR-001 selected — but nothing is provisioned and the 1 GB fit is unproven. |
| [`BACKEND.md`](BACKEND.md) | FastAPI — decisions | B4/B5 ✅ · B10 Control ✅ · B6/B7/B8 ✅ · C4 admin identity API ✅ |
| [`AUTH.md`](AUTH.md) | Identity & authorization | Phase 1 software controls built, including account removal, member/invite administration, activity stamps, and signed command/ingest transports. Operational Pi provisioning remains |
| [`FRONTEND.md`](FRONTEND.md) | React SPA | Scaffold, login → Home, public auth, Settings, Users & Invites, DMI-88 scan/host reads, and DMI-89 Agents scan trigger built. Next: LLM explainer |
| [`AI.md`](AI.md) | In-app LLM explainer | **In progress.** Grounded context, strict schemas, analysis persistence, and a read-only status/result endpoint are implemented on the feature branch. |
| [`SECURITY.md`](SECURITY.md) | Cross-cutting security | Cross-cutting posture; auth phases in [`AUTH.md`](AUTH.md) |
| [`TASKS.md`](TASKS.md) | Actionable task list | Tier 1 ✅ · Tier 2 in progress · NSPi port-stage fix (T4.1) open |

## Reference

| Doc | What |
|-----|------|
| [`../CLI.md`](../CLI.md) | Full `dmitri` CLI — `start` (TUI), `agent` (headless), scan modes, exit codes |

## Field tests

| Folder | What |
|--------|------|
| [`../tests/nspi-september/`](../tests/nspi-september/) | September NSPi pilot — dual-home plan + 2026-07-03 field results. **Closed** (no retest); pilot = Quick scan on dual-homed laptop. NSPi mode fix in T4.1 is dev-only. |

## Where each layer stands (one paragraph)

The scan pipeline, headless command daemon, and signed ingest client run in software; no physical Pi
is provisioned yet. The FastAPI backend serves data reads, auth, identity administration, the
command channel, and ingest. The web app has login → Home, public auth, Settings, Users & Invites, and the DMI-88 scan/host
read surfaces plus the Agents scan trigger (DMI-89). Still missing are physical Pi operations
and the LLM explainer. Invite/reset email now sends and delivers from the verified
`mail.peirce.dev`; what remains there is sender reputation, not code.

## Cross-layer milestone sequencing

These layers are coupled; build in roughly this order so each layer has something real to talk to:

1. **Pi hardware** (PI): board acquired 2026-08-21, but a **Pi 3**, which ADR-001 rejected for 1 GB RAM and USB 2.0. Base configure + **prove the pipeline fits in 1 GB** — still the top Pi-side risk
2. **Hosted stack** (BACKEND B4/B5): Supabase + Railway for NSPi — [`epics/EPICS.md`](../epics/EPICS.md)
3. **Auth Phase 1** — implement [`AUTH.md`](AUTH.md) (roadmap ✅)
4. **ADR-011 + OpenAPI** — ✅ [`ADR-011`](../adr/ADR-011-pi-command-channel.md); implement `contracts/openapi/` in backend/Pi
5. **Agent transport + command channel** (PI + BACKEND B6): daemon, **WebSocket**, Postgres command rows, ingest
6. **Frontend MVP** (FRONTEND): read UI + **"Scan now"** (B10 Control ✅)
7. **Auth Phase 2** (EOY): product-ready identity — [`AUTH.md`](AUTH.md)
8. **LLM explainer** (AI + BACKEND)
9. **Auth Phase 3 + enterprise** (deal-driven)

## Keeping these docs in sync

These docs share contracts (API shapes, auth, the Pi command channel). **Changing one usually
ripples to its neighbours.** The dependency map and the review rule live in the
**`roadmap-sync`** skill (`.claude/skills/roadmap-sync/`). After editing any file here, run it —
it tells you which sibling docs and the status table above to re-check.

## Conventions

- **⚠️ REVALIDATE** — a claim inherited from an ADR/ARCHITECTURE that must be checked against
  the code before it is trusted.
- **🔓 OPEN** — a decision not yet made; the doc lists options and a recommendation.
- Keep these short. Link to ADRs/ARCHITECTURE for detail instead of restating them.
- New cross-layer decisions get a real ADR under [`../adr/`](../adr/) once settled here.
