# Dmitri code-map

An [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle mapping the Dmitri codebase — what each module does and how the pieces connect. This is a
**code map**; product decisions and target-state design live in the repo's [`docs/`](../../docs/README.md)
knowledge base. See [MAINTAINING.md](./MAINTAINING.md) for how this bundle is kept current, and
[log.md](./log.md) for its change history.

> Only the hardware-agent + TUI is in active development; the backend is coded but not yet wired.
> Start at [overview.md](./overview.md).

## Start here

* [overview](./overview.md) — What Dmitri is, its components, the end-to-end scan flow, and what is built vs planned.
* [glossary](./glossary.md) — The core domain terms — agent, host, scan_host, command, scan, org — and their code meanings.
* [contracts](./contracts.md) — The OpenAPI + example-JSON seam binding agent, backend, and frontend — now unified on host/scan_mode vocabulary.

## Hardware agent (active)

The Pi appliance: the Nmap scan pipeline, normalization, and the Textual TUI. Full listing in
[hardware-agent/index.md](./hardware-agent/index.md).

* [hardware-agent/overview](./hardware-agent/overview.md) — The package, its scan pipeline, and the three front doors that drive it.
* [hardware-agent/cli](./hardware-agent/cli.md) — The dmitri CLI dispatcher, the headless entrypoint, scan tuning, and persisted user prefs.
* [hardware-agent/discovery](./hardware-agent/discovery.md) — Thin per-stage Nmap-argument builders — host/port/service/NSE-vuln scanning.
* [hardware-agent/normalize](./hardware-agent/normalize.md) — The Pydantic wire contracts and the NSE-to-findings extractor (the shared on-disk payload).
* [hardware-agent/tui](./hardware-agent/tui.md) — The Textual application — app root, screens, and shared widgets.
* [hardware-agent/utils](./hardware-agent/utils.md) — Local-network detection/connectivity and the Nmap/NSE XML parsers.

### Scan engine — `scanner/`

Full listing in [hardware-agent/scanner/index.md](./hardware-agent/scanner/index.md).

* [scanner/runner](./hardware-agent/scanner/runner.md) — ScanRunner — worker thread, cancellation, deadline guards, and the `_run()` pipeline body.
* [scanner/stages](./hardware-agent/scanner/stages.md) — The threaded port and deep-inspection stages, with retry, circuit breaker, and payload builder.
* [scanner/nmap](./hardware-agent/scanner/nmap.md) — NmapRunner / LoggedNmapRunner — run Nmap, parse XML, classify failures, stream logs.
* [scanner/models](./hardware-agent/scanner/models.md) — The in-memory scan dataclasses that carry state across stages.
* [scanner/errors](./hardware-agent/scanner/errors.md) — The scan exception hierarchy that encodes the contingency policy.
* [scanner/progress](./hardware-agent/scanner/progress.md) — The ScanEvent stream, the ScanReporter protocol, and the progress mapper.
* [scanner/workspace](./hardware-agent/scanner/workspace.md) — The on-disk results/ + logs/ layout — serialization, per-run logging, pruning.

## Backend (read path wired, ingest not)

FastAPI API (read path + auth + invites wired) + the CVE-enrichment worker. Full listing in
[backend/index.md](./backend/index.md).

* [backend/overview](./backend/overview.md) — The FastAPI backend — its read path, auth, and invites are wired — and the CVE-enrichment worker.
* [backend/api](./backend/api.md) — The FastAPI app (health + the wired read path + auth), the worker process entry, settings, and the DB engine/session.
* [backend/routers](./backend/routers.md) — The three FastAPI routers that wire the read path — GET /hosts, /hosts/{id}, /scans/{id}, /findings — now behind require_user and scoped to the caller's org.
* [backend/auth](./backend/auth.md) — Login/refresh/logout + password change/reset, the invite flow, JWT access tokens with a role gate, rotating refresh-token families, the argon2 password policy, and the request-id/CORS middleware.
* [backend/device-auth](./backend/device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.
* [backend/management](./backend/management.md) — The two operator CLIs — backend-bootstrap-org (first org + its admin invite) and backend-provision-agent (register a device public key) — which print secrets to stdout and never to a log.
* [backend/models](./backend/models.md) — The SQLModel tables — scan persistence, host identity, enrichment/cache, risk snapshots, user identity, auth session tokens, and the command channel with its agent public keys and replay nonces.
* [backend/schemas](./backend/schemas.md) — The Pydantic ingest input (ScanResult), the legacy read/output projections (Persisted*), the read-path response schemas, and the auth and invite request/response models.
* [backend/services](./backend/services.md) — persist_scan, host-identity upsert, the org-scoped read-path queries, the worker loop, the NVD/KEV/EPSS clients, the explainable risk scorer, and the command lifecycle rulebook.
* [backend/migrations](./backend/migrations.md) — The Alembic env and eleven revisions that own the schema — baseline through the command channel, auth session tokens, agent nonces, global user-email uniqueness, and agent public keys — plus Supabase RLS hardening and the dmitri_runtime role.

## Frontend (first vertical slice)

The React 19 + TypeScript SPA. The scaffold plus the first real screens — routing, a session
layer, and login → Home. Full listing in [frontend/index.md](./frontend/index.md).

* [frontend/overview](./frontend/overview.md) — The React 19 + TypeScript SPA — contract-typed API access, the auth-client plumbing, the session layer, and the first real screens (login → Home).
* [frontend/api](./frontend/api.md) — The two Axios instances, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, and the read resource modules.
* [frontend/auth](./frontend/auth.md) — The SessionProvider (boot refresh modelled as a query), the useSession accessor, and the RequireSession route guard.
* [frontend/app](./frontend/app.md) — The React root's provider nest and App's route table — /login, the guarded shell branch, and a catch-all that renders rather than redirects.
* [frontend/review](./frontend/review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes the four reads into one discriminated union.
* [frontend/screens](./frontend/screens.md) — The LOGIN and HOME screens, the not-found page, the two shells and top bar, and the shared presentation components.

## Infrastructure

Full listing in [infra/index.md](./infra/index.md).

* [infra/supabase](./infra/supabase.md) — Supabase used purely as arms-length managed Postgres 17.
* [infra/deployment](./infra/deployment.md) — Dev-environment installers and the two-service Railway + Supabase topology.

## Meta

* [MAINTAINING](./MAINTAINING.md) — How agents write and keep this code-map current as the code changes.
* [pipeline](./pipeline.md) — (Not a code doc.) The team's document-driven feature pipeline.
