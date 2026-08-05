# Backend

The cloud half of Dmitri — a FastAPI API and a CVE-enrichment worker over a Supabase-managed
Postgres. **Read path + auth + users/me + the command channel + ingest wired:** `GET /api/v1/health`, the
read routes (`/hosts`, `/hosts/{host_id}`, `/scans/{scan_id}`, `/findings` — behind `require_user`
and scoped to the caller's org), `GET /api/v1/users/me` (role from the DB row), the auth routes
(login/refresh/logout + password change/reset), the invite routes, the command channel —
`POST /api/v1/agents/{agent_id}/commands` (behind `require_admin`),
`GET /api/v1/commands/{command_id}`, and `WebSocket /api/v1/agents/{agent_id}/commands` (behind
`require_agent_ws`), which delivers commands outbound and applies the Pi's reported status
transitions — and, since DMI-63, `POST /api/v1/scans` (ingest, behind `require_agent`) are all served
today. No Pi client dials the WS channel or posts results yet (the daemon is DMI-66), so delivery is
exercised against fake sockets and ingest against signed test requests.

## Overview & entry points

* [Backend — API + enrichment worker](./overview.md) — The FastAPI backend (read path wired) and the CVE-enrichment worker.
* [Backend entry points & config](./api.md) — The FastAPI app (health + wired routes + global error envelope), the worker process entry, settings, and the DB engine/session.
* [Backend routers](./routers.md) — The read-path GET routers, GET /users/me, the signed scan-ingest route POST /api/v1/scans, plus the agent WebSocket command channel — behind require_user / require_agent / require_agent_ws respectively.
* [Backend management commands](./management.md) — The two operator CLIs — backend-bootstrap-org (first org + its admin invite) and backend-provision-agent (register a device public key) — which print secrets to stdout and never to a log.

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables — scan persistence, host identity, enrichment/cache, risk snapshots, user identity, auth session tokens, and the command channel.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest input (ScanIngestRequest), the legacy read/output projections (Persisted*), the read-path response schemas, UserProfileResponse, and the auth/invite request/response models.

## Services

* [Backend services — persistence, host identity, read, enrichment, risk](./services.md) — ingest_scan/persist_scan, host-identity upsert, the read-path queries, the worker loop, the NVD/KEV/EPSS clients, the explainable risk scorer, and the command lifecycle rulebook.

## Auth

* [Backend auth — sessions, tokens, passwords, routes](./auth.md) — Login/refresh/logout + password change/reset, the invite flow, JWT access tokens with a role gate, rotating refresh-token families, the argon2 password policy, and the request-id/CORS middleware.
* [Backend API error envelope](./errors.md) — ApiError with per-site code overrides and the global handlers that shape every HTTPException into the contract ErrorResponse.
* [Backend device auth — Ed25519 signatures, nonces, the agent gate](./device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and fourteen revisions that own the schema — baseline through the command channel, auth session tokens, agent nonces, global user-email uniqueness, agent public keys, the findings severity check, command delivery and the scan-ingest rework — plus Supabase RLS hardening and the dmitri_runtime role.
