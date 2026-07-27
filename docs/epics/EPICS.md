# Cloud & hosting — epics

> **NSPi target (September):** Supabase (Postgres) + Railway (API + worker). AWS staging runs in
> parallel — separate epic, not a blocker for September.
>
> **Context:** [`roadmap/BACKEND.md`](../roadmap/BACKEND.md) (B4/B5 phased plan).

Use **epics** (milestones) + small **issues** — one concern per issue, one deployable outcome each.

---

## Epic 1 — Cloud docs & decisions

- Create `docs/cloud/` structure (plan, decisions, env contract)
- Document NSPi target stack (Supabase + Railway)
- App requirements sheet for infra (env vars, processes, health checks)
- Weekly infra ↔ app review ritual (template)

## Epic 2 — ADR review & alignment

- Review ADR-007 (deployment) vs Supabase/Railway phased plan
- Review ADR-009 (database) vs Supabase for NSPi
- Review ADR-005 (security) for hosted URLs, secrets, CORS
- Record outcomes in `docs/cloud/` (update ADRs only when locked)

## Epic 3 — Supabase (database)

- Provision Supabase project (region, plan for September)
- Define connection strings (app vs migrations)
- Run Alembic migrations against Supabase
- Validate enrichment job queue on Supabase Postgres

## Epic 4 — Railway (compute)

- Dockerize API + worker (if not already deploy-ready)
- Railway: API service
- Railway: worker service (separate process)
- Wire `DATABASE_URL` + secrets on Railway
- Staging/prod environment split (or single NSPi env)

## Epic 5 — Backend cloud readiness

- Replace SQLite / `create_all` with Postgres + Alembic path
- Settings: load all secrets from env (JWT placeholder; device auth is Ed25519 — no shared secret to store)
- Health/readiness endpoints for deploy checks
- Smoke test: ingest → worker → read (against hosted stack)

## Epic 6 — Edge & clients (hosted URLs)

- Choose API + frontend public URLs / domains
- CORS config for dev + NSPi frontend origin
- Pi: `AGENT_BACKEND_BASE_URL` for NSPi environment
- Document operator runbook (deploy, rollback, logs)

## Epic 7 — NSPi cutover (September)

- End-to-end hosted demo checklist
- Supabase backup / no-pause plan before demo
- Go/no-go review (app + infra)

## Epic 8 — AWS staging (parallel backlog)

- Week 0 kickoff (region, diagram, `infra/aws/`)
- RDS + ECR
- ECS API + worker
- S3 + CloudFront frontend
- Staging smoke parity with Supabase/Railway
- Prod cutover plan (open only when staging passes)

---

## Labels

| Label | Use |
|-------|-----|
| `cloud` | All infra issues |
| `supabase` | Epic 3 |
| `railway` | Epic 4 |
| `aws` | Epic 8 |
| `docs` | Epic 1–2 |
| `adr` | Epic 2 |
| `blocked-app` | Infra waiting on app contract |
| `blocked-infra` | App waiting on hosted env |

---

## Sequencing

```
Epic 1 + 2  →  Epic 3 + 5  →  Epic 4  →  Epic 6  →  Epic 7
                              Epic 8 (parallel; not required for September)
```

Epic 3 and Epic 5 can run in parallel once the env contract from Epic 1 exists.
