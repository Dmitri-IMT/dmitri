# Dmitri code-map

An [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle mapping the Dmitri codebase — what each module does and how the pieces connect. This is a
**code map**; product decisions and target-state design live in the repo's [`docs/`](../../docs/README.md)
knowledge base. See [MAINTAINING.md](./MAINTAINING.md) for how this bundle is kept current, and
[log.md](./log.md) for its change history.

> The hardware-agent + TUI is the most active layer, but the backend read path, auth, ingest and
> command channel are all wired, and since DMI-66 so is the Pi-side daemon that drives them.
> Start at [overview.md](./overview.md).

## Start here

* [overview](./overview.md) — What Dmitri is, its components, the end-to-end scan flow, and what is built vs planned.
* [glossary](./glossary.md) — The core domain terms — agent, host, scan_host, command, scan, org — and their code meanings.
* [contracts](./contracts.md) — The published OpenAPI + example-JSON seam binding agent, backend, and frontend, including the wired user/member and invite administration surface.

## Hardware agent (active)

The Pi appliance: the Nmap scan pipeline, normalization, and the Textual TUI. Full listing in
[hardware-agent/index.md](./hardware-agent/index.md).

* [hardware-agent/overview](./hardware-agent/overview.md) — The package, its scan pipeline, and the front doors that drive it — TUI, headless CLI, and the remote command daemon.
* [hardware-agent/cli](./hardware-agent/cli.md) — The dmitri CLI dispatcher, the headless entrypoint, scan tuning, and persisted user prefs.
* [hardware-agent/discovery](./hardware-agent/discovery.md) — Thin per-stage Nmap-argument builders — host/port/service/NSE-vuln scanning.
* [hardware-agent/normalize](./hardware-agent/normalize.md) — The Pydantic scan payloads and NSE extractor, including port- and host-scoped SMB findings.
* [hardware-agent/tui](./hardware-agent/tui.md) — The Textual application — app root, screens, and shared widgets.
* [hardware-agent/utils](./hardware-agent/utils.md) — Local-network detection/connectivity and the Nmap/NSE XML parsers.
* [hardware-agent/daemon](./hardware-agent/daemon.md) — The long-lived device process that executes one remote scan at a time, uploads it, reports lifecycle status, and logs safe upload outcomes.
* [hardware-agent/command-channel](./hardware-agent/command-channel.md) — The signed device WebSocket: strict hello/command/status frames, visible connection loss/recovery, and the pinned reconnect ladder.
* [hardware-agent/transport](./hardware-agent/transport.md) — The device-side ingest client: environment-loaded config, the Ed25519 request envelope, bounded retries, and the typed submission outcome.

### Scan engine — `scanner/`

Full listing in [hardware-agent/scanner/index.md](./hardware-agent/scanner/index.md).

* [scanner/runner](./hardware-agent/scanner/runner.md) — ScanRunner — worker thread, cancellation, deadline guards, and the `_run()` pipeline body.
* [scanner/stages](./hardware-agent/scanner/stages.md) — The threaded port and deep-inspection stages, with retry, circuit breaker, and payload builder.
* [scanner/nmap](./hardware-agent/scanner/nmap.md) — NmapRunner / LoggedNmapRunner — execute Nmap, log argv and failed stderr, parse XML, and retain per-run artifacts.
* [scanner/models](./hardware-agent/scanner/models.md) — The in-memory scan dataclasses that carry state across stages.
* [scanner/errors](./hardware-agent/scanner/errors.md) — The scan exception hierarchy that encodes the contingency policy.
* [scanner/progress](./hardware-agent/scanner/progress.md) — The ScanEvent stream, the ScanReporter protocol, and the progress mapper.
* [scanner/workspace](./hardware-agent/scanner/workspace.md) — The on-disk results/ + logs/ layout — serialization, per-run logging, pruning.

## Backend (reads, identity admin, command channel and ingest wired)

FastAPI API plus CVE-enrichment worker. Full listing in [backend/index.md](./backend/index.md).

* [backend/overview](./backend/overview.md) — The FastAPI backend — read, auth, user/invite administration, command-channel and ingest routes wired — plus the CVE-enrichment worker.
* [backend/api](./backend/api.md) — The FastAPI app (health, read, auth, user/invite admin, command-channel HTTP/WS, global errors), the worker entry, settings, and DB sessions.
* [backend/routers](./backend/routers.md) — The FastAPI read, user/member admin, account-removal, scan-ingest and command-channel HTTP/WS routers with their user/device auth gates.
* [backend/auth](./backend/auth.md) — The wired user auth/session/password system, activity stamping, invite creation/lookup/list/revoke, role gates, and request-id/CORS middleware.
* [backend/device-auth](./backend/device-auth.md) — The per-device authentication gate — Ed25519 canonical-string signing, single-use nonce replay protection, and the transport-agnostic authenticate_agent core with its require_agent HTTP adapter.
* [backend/management](./backend/management.md) — The two operator CLIs — backend-bootstrap-org (first org + its admin invite) and backend-provision-agent (register a device public key) — which print secrets to stdout and never to a log.
* [backend/models](./backend/models.md) — The SQLModel tables for scan persistence, host identity, enrichment/risk, user identity and activity, auth sessions, and the command channel.
* [backend/schemas](./backend/schemas.md) — The Pydantic ingest/read/command schemas plus profile, organization-member, auth and invite request/response models.
* [backend/error-codes](./backend/error-codes.md) — The closed ScanErrorCode set and the two pure helpers every read path uses to normalise a stored command code onto the wire.
* [backend/services](./backend/services.md) — The backend business logic for ingest/persistence, member administration, account removal, org-scoped reads, enrichment/risk, and command lifecycle/delivery.
* [backend/migrations](./backend/migrations.md) — The Alembic env and sixteen revisions through user activity and invite revocation privileges, with Supabase RLS and dmitri_runtime hardening.

## Frontend (auth, Home, Settings, user administration, and scan/host reads)

The React 19 + TypeScript SPA. Full listing in [frontend/index.md](./frontend/index.md).

* [frontend/overview](./frontend/overview.md) — The React 19 + TypeScript SPA — contract-typed API access, auth/session plumbing, public and guarded screens, local UI-foundation lint rules, and Railway static deployment.
* [frontend/linting](./frontend/linting.md) — The local ESLint plugin that enforces named Tailwind width, type and spacing tokens and shared interactive primitives in authored application source.
* [frontend/api](./frontend/api.md) — The two Axios instances, required VITE_API_URL base-URL construction, the single-flight 401→refresh interceptor, the session-expiry event bus, the token store, prefix-shaped query keys, and the read resource modules.
* [frontend/auth](./frontend/auth.md) — The SessionProvider (boot refresh modelled as a query), the useSession accessor, and the RequireSession route guard.
* [frontend/app](./frontend/app.md) — The React root's provider nest and App's route table — public auth, the guarded shell (including scans/hosts/agents), nested admin Users, and a catch-all that renders rather than redirects.
* [frontend/review](./frontend/review.md) — deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes the four reads into one discriminated union.
* [frontend/scan-failure-reasons](./frontend/scan-failure-reasons.md) — SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
* [frontend/scan-status](./frontend/scan-status.md) — scanStatusPill maps every ScanStatus to tone and label; isUnfinished hides counts; bySeverityDesc is the only guaranteed worst-first order.
* [frontend/tables](./frontend/tables.md) — DataTable with a discriminated rowAction and an optional right-align per column, Pagination that greys edge controls, EmptyState with no CTA, outline StatusPill, and LoadingSkeleton bars on --border.
* [frontend/host-detail](./frontend/host-detail.md) — readDetailState turns one detail query into loading/error/notFound/ready, ReadDetailGate renders the three non-ready states, and the host's findings section owns its own.
* [frontend/screens](./frontend/screens.md) — The public and guarded screens, 70rem app frame, 24rem auth shell, centred navigation, details-first Settings surface, and shared presentation and interaction components.

## Infrastructure

Full listing in [infra/index.md](./infra/index.md).

* [infra/supabase](./infra/supabase.md) — Supabase used purely as arms-length managed Postgres 17.
* [infra/deployment](./infra/deployment.md) — Dev-environment installers, the local Pi simulator, and the three-service Railway + Supabase topology.
* [infra/pi-simulator](./infra/pi-simulator.md) — The ephemeral Docker harness that runs the real agent, backend, worker, Postgres, and a Samba scan target.

## Meta

* [MAINTAINING](./MAINTAINING.md) — How agents write and keep this code-map current as the code changes.
* [pipeline](./pipeline.md) — (Not a code doc.) The team's document-driven feature pipeline.
