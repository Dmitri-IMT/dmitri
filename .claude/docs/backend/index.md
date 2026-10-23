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
* [Backend routers — reads, identity admin, ingest and commands](./routers.md) — The FastAPI read, identity admin, device revoke/restore, scan/machine deletion, ingest and command-channel HTTP/WS routers with their auth gates.
* [Backend management commands](./management.md) — The two operator CLIs — backend-bootstrap-org (first org + admin invite) and backend-provision-agent (device public key + org OT digest key).

## Data model

* [Backend ORM models](./models.md) — The SQLModel tables for scan persistence and live progress, host identity, enrichment/risk, user identity and activity, auth sessions, and the command channel.
* [Backend wire schemas](./schemas.md) — The Pydantic ingest/read/command/agent schemas, including live progress snapshots, plus profile, organization-member, auth and invite models.
* [Scan failure-code vocabulary](./error-codes.md) — The closed ScanErrorCode set and the two pure helpers every read path uses to normalise a stored command code onto the wire.

## Services

* [Backend explained and technical scan reports](./reports.md) — Localized educational PDFs with clickable contents and page numbers, complete device inventories, evidence-aware explanations, charts, remediation checks and the full finding register.
* [Backend services — persistence, host identity, read, enrichment, risk](./services.md) — Backend business logic for ingest, guarded live progress, reads, enrichment, command delivery and cancel, presence, idempotent device revoke/restore, and admin scan/machine deletion.
* [Backend AI — OpenAI fix tasks, researched sources, cached explanations, web-assisted chat and usage metadata.

## Auth

* [Backend auth — sessions, tokens, passwords, routes](./auth.md) — The wired user auth/session/password system, activity stamping, invite creation/lookup/list/revoke, role gates, and request-id/CORS middleware.
* [Backend API error envelope](./errors.md) — ApiError with per-site code overrides and the global handlers that shape every HTTPException into the contract ErrorResponse.
* [Backend device auth — Ed25519 signatures, nonces, the agent gate](./device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.

## Migrations

* [Backend database migrations](./migrations.md) — The Alembic env and revisions through AI, attack-surface profiles, agent identity, scan_cancelled activity, scan evidence coverage, live progress, and scan/machine deletion. Head is `20261024_48`.
