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
* [glossary](./glossary.md) — The core domain terms — agent, host, device, command, scan, org — and their code meanings.
* [contracts](./contracts.md) — The OpenAPI + example-JSON seam binding agent, backend, and frontend — and its known divergences.

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

## Backend (coded, not yet wired)

FastAPI ingest/persistence + the CVE-enrichment worker. Full listing in
[backend/index.md](./backend/index.md).

* [backend/overview](./backend/overview.md) — The ingest/persistence backend and the enrichment worker — working code that nothing calls yet.
* [backend/api](./backend/api.md) — The FastAPI app (health-only), the worker entry, settings, and the DB engine/session.
* [backend/models](./backend/models.md) — The SQLModel tables — scan persistence, enrichment/cache, risk snapshots, dormant identity.
* [backend/schemas](./backend/schemas.md) — The Pydantic ingest input (ScanResult) and the read/output projections.
* [backend/services](./backend/services.md) — persist_scan, the worker loop, the NVD/KEV/EPSS clients, and the explainable risk scorer.
* [backend/migrations](./backend/migrations.md) — The Alembic env and revisions that own the schema, plus Supabase RLS hardening.

## Infrastructure

Full listing in [infra/index.md](./infra/index.md).

* [infra/supabase](./infra/supabase.md) — Supabase used purely as arms-length managed Postgres 17.
* [infra/deployment](./infra/deployment.md) — Dev-environment installers and the two-service Railway + Supabase topology.

## Meta

* [MAINTAINING](./MAINTAINING.md) — How agents write and keep this code-map current as the code changes.
* [pipeline](./pipeline.md) — (Not a code doc.) The team's document-driven feature pipeline.
