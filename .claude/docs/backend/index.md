# Backend

The cloud half of Dmitri — a FastAPI API and CVE-enrichment worker over Supabase Postgres.
Data reads, auth/session/password flows, self profile/removal, member and pending-invite
administration, the agent fleet read surface and target-network choice, command enqueue/read/WebSocket,
and signed scan ingest are all served today.
The Pi daemon also exists; the remaining end-to-end gap is physical provisioning and operations,
not a missing client or backend route.

## Overview & entry points

* [Backend — API + enrichment worker](./overview.md) — The FastAPI backend — read, auth, user/invite administration, command-channel and ingest routes wired — plus the CVE-enrichment worker and optional AI analysis loop.
* [Backend entry points & config](./api.md) — The FastAPI app (health, read, auth, user/invite admin, command-channel HTTP/WS, global errors), the worker entry, settings, and DB sessions.
* [Backend routers — reads, identity admin, ingest and commands](./routers.md) — The FastAPI read, user/member admin, agent read/target-subnet, account-removal, scan-ingest and command-channel HTTP/WS routers with their user/device auth gates.
* [Backend management commands](./management.md) — The two operator CLIs — backend-bootstrap-org (first org + admin invite) and backend-provision-agent (device public key + org OT digest key).

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables for scan persistence, host identity, enrichment/risk, user identity and activity, auth sessions, and the command channel.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest/read/command/agent schemas plus profile, organization-member, auth and invite request/response models.
* [Scan failure-code vocabulary](./error-codes.md) — The closed ScanErrorCode set and the two pure helpers every read path uses to normalise a stored command code onto the wire.

## Services

* [Backend services — persistence, host identity, read, enrichment, risk](./services.md) — The backend business logic for ingest/persistence, member administration, account removal, org-scoped reads, agent reads and target-subnet choice, enrichment/risk, command lifecycle/delivery, and agent revocation enforcement on live connections.
* [Backend AI — scan analysis, contextual chat, usage telemetry](./ai.md) — Groq scan overviews (on-demand or auto after enrichment), scoped Q&A, and org usage metadata without storing prompts in `ai_usage`.

## Auth

* [Backend auth — sessions, tokens, passwords, routes](./auth.md) — The wired user auth/session/password system, activity stamping, invite creation/lookup/list/revoke, role gates, and request-id/CORS middleware.
* [Backend API error envelope](./errors.md) — ApiError with per-site code overrides and the global handlers that shape every HTTPException into the contract ErrorResponse.
* [Backend device auth — Ed25519 signatures, nonces, the agent gate](./device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and revisions through AI chat, usage telemetry, and writing-skill versions. Head is `20260919_31`.
