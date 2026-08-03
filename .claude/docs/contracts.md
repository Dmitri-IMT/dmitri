---
type: Data Contract
title: Shared contracts (OpenAPI + example)
description: The OpenAPI + example-JSON seam binding agent, backend, and frontend — now unified on host/scan_mode vocabulary.
resource: contracts/openapi/openapi.yaml
tags: [contracts, openapi, seam]
timestamp: 2026-08-03T00:00:00Z
---

# Shared contracts

`contracts/` is the **shared source of truth** binding the components. Today it is the *only* live
coupling between the [agent](/hardware-agent/overview.md) and the [backend](/backend/overview.md):
the agent writes payloads shaped by it, and the backend's schemas mirror it.

## Files

| File | What it is |
|------|-----------|
| `contracts/openapi/openapi.yaml` | OpenAPI 3.1 REST/ingest contract — the full integration surface (much broader than what the backend shell implements today). |
| `contracts/examples/scan_result.example.json` | A concrete `ScanResult` payload; the shared test fixture. |

## The ingest surface

- `POST /api/v1/scans` — agent ingest, **HMAC-signed** (headers `X-Device-Id`, `X-Timestamp`,
  `X-Nonce`, `X-Body-SHA256`, `X-Signature`; returns `202 Accepted`).
- `GET /api/v1/scans`, `/scans/{id}`, `/hosts`, `/findings` — JWT-authed reads (a `pending` scan
  stub is returned before ingest completes).
- `POST /api/v1/agents/{agent_id}/commands` — admin-only "Scan now" trigger; `201` +
  `CommandSummary`, `409 device_busy`, `503 device_offline`. **Wired** (DMI-64).
- `GET /api/v1/commands/{command_id}` — `CommandDetail`. **Wired** (DMI-64). `scan_id` is optional
  on both `CommandSummary` and `CommandDetail`: a `queued` or `expired` command has no linked scan.
- `GET /api/v1/agents/{agent_id}/commands` — **WebSocket** command channel (Ed25519; frames
  `hello`/`command`/`status`). Scan results never travel this socket.
- `auth` (`login`/`refresh`/`logout`/…) + `invites` — identity surface.

Security schemes: `AgentHmacAuth` (ingest + WS), `FrontendBearerAuth` (short-lived JWT),
`RefreshCookieAuth` (httpOnly `dmitri_refresh` cookie). CORS restricted to the SPA origins.

> **The read path is wired** in the backend shell today ([backend/routers](/backend/routers.md)):
> `GET /api/v1/health`, `/hosts`, `/hosts/{host_id}`, `/scans/{scan_id}`, `/findings`. Ingest
> (`POST /api/v1/scans`) and auth above are still contract-defined but not yet wired; `persist_scan`
> is exercised directly by tests, not over HTTP.

## The payload shape

The agent emits a [`ScanPayload`](/hardware-agent/normalize.md); the backend validates a `ScanResult`
([backend/schemas](/backend/schemas.md)). Both carry a scan header (`scan_id`, `timestamp`, `subnet`,
`scan_mode`), a list of **hosts** (ip/mac/hostname/vendor + ports), a list of **findings** (cve_id,
cvss, severity, confidence, evidence), and metadata.

The OpenAPI `ScanIngestRequest` uses `HostPayload` (`hosts[]`); `ScanIngestResponse` returns
`hosts_received` (ADR-013 retired `Device`/`devices`/`devices_received` from the wire — ingest is
now `POST`ed as `hosts[]`, per contract asks C1–C5). Read responses add: `ScanHostView` — the
`HostPayload` shape plus a **required** `host_id` (C9, resolved host identity per host observation
in a scan); `HostSummary` — the `GET /hosts` list row, adding `first_seen_at`/`last_seen_at` (C6).

**Nullability and `required`, tightened 2026-08-02.** `mac` is nullable on `ScanHostView`,
`HostSummary` and `HostDetailResponse` (a routed host has no MAC) but stays in each schema's
`required` list — always present on the wire, sometimes `null`. The collection fields
(`ScanHostView.ports`, `HostDetailResponse.ports`/`scan_history`, `ScanDetailResponse.hosts`/
`findings`) are likewise `required`: the backend always emits them, so publishing them as optional
would push needless `?.` into the generated frontend types. All address fields are `format: ipv4`,
which the Pydantic models now match exactly with `IPv4Address`.

`backend/tests/test_contract_fidelity.py` gates this file against the app's generated OpenAPI by
fingerprinting `additionalProperties`, `required` and every property shape. Its `SCHEMA_NAMES`
covers the read responses; `OPERATION_PATHS` covers query parameters on `/scans` and `/findings`
only — `/api/v1/hosts` is **not** guarded, because the contract declares `sort_by`/`sort_order`/`q`
there and the service implements none of them (DMI-100 closes the sort half and adds the path).

The example fixture (`scan_result.example.json`) now uses `scan_mode`, matching the OpenAPI schema
(previously it used `target_mode`/`scan_profile` — see "Resolved divergence" below); it is loaded by
`backend/tests/test_ingest_scan.py` to drive `persist_scan` and the enrichment tests offline.

## Resolved divergence (was: "note, do not fix" — now reconciled)

- **`scan_mode`, unified.** The OpenAPI `ScanIngestRequest` and the implemented `schemas/scan.py` +
  example JSON both now use `scan_mode` (enum quick/standard/extensive/nspi/max). The prior
  `target_mode`/`scan_profile` fields on the Pydantic model and example are gone. Resolved by
  spec [015-read-path](../../specs/015-read-path/TRUTH.md) /
  [ADR-013](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md).
- **device → host, unified on the wire too.** ADR-013 retires `device`/`Device`/`DevicePayload` from
  the ingest boundary entirely: the wire vocabulary is now `hosts`/`HostPayload` end to end. See
  [glossary](/glossary.md).

# Citations

[1] [contracts/openapi/openapi.yaml](../../contracts/openapi/openapi.yaml)
[2] [contracts/examples/scan_result.example.json](../../contracts/examples/scan_result.example.json)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../docs/adr/ADR-011-pi-command-channel.md)
[4] [docs/adr/ADR-005-security-model.md](../../docs/adr/ADR-005-security-model.md)
[5] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[6] [docs/adr/ADR-014-host-identity-resolution.md](../../docs/adr/ADR-014-host-identity-resolution.md)
[7] [specs/015-read-path](../../specs/015-read-path/TRUTH.md)
