# Backend

The cloud half of Dmitri — a FastAPI API and a CVE-enrichment worker over a Supabase-managed
Postgres. **Read path + auth + invites wired, ingest not:** `GET /api/v1/health`, the read routes
(`/hosts`, `/hosts/{host_id}`, `/scans/{scan_id}`, `/findings` — now behind `require_user` and
scoped to the caller's org), the auth routes (login/refresh/logout + password change/reset), and the
invite routes are served today; `POST /api/v1/scans` (ingest) is still contract-defined only, and
`persist_scan`/the worker are exercised directly by tests. The device-authentication gate is built
but mounted on no route, awaiting the command channel (DMI-62/63).

## Overview & entry points

* [Backend — API + enrichment worker](./overview.md) — The FastAPI backend (read path wired) and the CVE-enrichment worker.
* [Backend entry points & config](./api.md) — The FastAPI app (health + the wired read path), the worker process entry, settings, and the DB engine/session.
* [Backend routers](./routers.md) — The three FastAPI routers that wire the read path — GET /hosts, /hosts/{id}, /scans/{id}, /findings — now behind require_user and scoped to the caller's org.
* [Backend management commands](./management.md) — The two operator CLIs — backend-bootstrap-org (first org + its admin invite) and backend-provision-agent (register a device public key) — which print secrets to stdout and never to a log.

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables — scan persistence, host identity, enrichment/cache, risk snapshots, user identity, auth session tokens, and the command channel.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest input (ScanResult), the legacy read/output projections (Persisted*), the read-path response schemas, and the auth request/response models.

## Services

* [Backend services — persistence, host identity, read, enrichment, risk](./services.md) — persist_scan, host-identity upsert, the read-path queries, the worker loop, the NVD/KEV/EPSS clients, the explainable risk scorer, and the command lifecycle rulebook.

## Auth

* [Backend auth — sessions, tokens, passwords, routes](./auth.md) — Login/refresh/logout + password change/reset, the invite flow, JWT access tokens with a role gate, rotating refresh-token families, the argon2 password policy, and the request-id/CORS middleware.
* [Backend device auth — Ed25519 signatures, nonces, the agent gate](./device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and eleven revisions that own the schema — baseline through the command channel, auth session tokens, agent nonces, global user-email uniqueness, and agent public keys — plus Supabase RLS hardening and the dmitri_runtime role.
