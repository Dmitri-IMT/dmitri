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
| Postgres | Supabase |
| API + worker | Railway (2 services) |
| Frontend | Railway static (same project) |
| AWS | Staging parallel — see BACKEND B4/B5 schedule |
