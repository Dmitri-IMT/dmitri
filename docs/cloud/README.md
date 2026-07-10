# Cloud — plan & operations

> **Status:** stub. Epic 1 fills this in ([`epics/EPICS.md`](../epics/EPICS.md)).
>
> **Decisions:** [`roadmap/BACKEND.md`](../roadmap/BACKEND.md) (B4, B5, B9, B10).
> **Issue breakdown:** [`epics/EPICS.md`](../epics/EPICS.md).

## Planned contents

| Doc | Purpose |
|-----|---------|
| `DECISIONS.md` | Locked hosting choices (mirror BACKEND decision log) |
| `ENV-CONTRACT.md` | Env vars, processes (API + worker), ports, health checks |
| `NSPI-STACK.md` | Supabase + Railway layout for September |
| `WEEKLY-REVIEW.md` | Infra ↔ app review agenda template |

## NSPi stack (summary)

| Piece | Provider |
|-------|----------|
| Postgres | Supabase — region `us-east-1` (N. Virginia) |
| API + worker | Railway (2 services) — region `us-east4` (Virginia) |
| Frontend | Railway static (same project) |
| AWS | Staging parallel — see BACKEND B4/B5 schedule |

Region: Supabase `us-east-1` and Railway `us-east4` are co-located in Virginia (Railway has no South America region; compute↔DB latency dominates, so both sit together). Setup: [`supabase/SETUP.md`](supabase/SETUP.md) · [`railway/SETUP.md`](railway/SETUP.md).
