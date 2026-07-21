---
type: Data Contract
title: Shared contracts (OpenAPI + example)
description: The OpenAPI + example-JSON seam binding agent, backend, and frontend — and its known divergences.
resource: contracts/openapi/openapi.yaml
tags: [contracts, openapi, seam]
timestamp: 2026-07-21T00:00:00Z
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
- `GET /api/v1/agents/{agent_id}/commands` — **WebSocket** command channel (HMAC; frames
  `hello`/`command`/`status`). Scan results never travel this socket.
- `auth` (`login`/`refresh`/`logout`/…) + `invites` — identity surface.

Security schemes: `AgentHmacAuth` (ingest + WS), `FrontendBearerAuth` (short-lived JWT),
`RefreshCookieAuth` (httpOnly `dmitri_refresh` cookie). CORS restricted to the SPA origins.

> **Only `GET /api/v1/health` is implemented** in the backend shell today
> ([backend/api](/backend/api.md)). The ingest and read routes above are contract-defined but not yet
> wired; `persist_scan` is exercised directly by tests, not over HTTP.

## The payload shape

The agent emits a [`ScanPayload`](/hardware-agent/normalize.md); the backend validates a `ScanResult`
([backend/schemas](/backend/schemas.md)). Both carry a scan header (`scan_id`, `timestamp`, `subnet`),
a list of **devices** (ip/mac/hostname/vendor + ports), a list of **findings** (cve_id, cvss,
severity, confidence, evidence), and metadata.

The example fixture (`scan_result.example.json`) is loaded by
`backend/tests/test_ingest_scan.py` to drive `persist_scan` and the enrichment tests offline.

## Known divergences (note, do not "fix")

- **`scan_mode` vs `target_mode`/`scan_profile`.** The OpenAPI `ScanIngestRequest` uses `scan_mode`
  (enum quick/standard/extensive/nspi/max), while the implemented `schemas/scan.py` and the example
  JSON use `target_mode` (single_host/subnet/multi_host) + `scan_profile` (single-host/lab/lan/deep).
  The Pydantic model and the example agree with each other; the OpenAPI `ScanIngestRequest` is the
  one out of step.
- **device → host** translation happens at this ingest boundary (see [glossary](/glossary.md)).

# Citations

[1] [contracts/openapi/openapi.yaml](../../contracts/openapi/openapi.yaml)
[2] [contracts/examples/scan_result.example.json](../../contracts/examples/scan_result.example.json)
[3] [docs/adr/ADR-011-pi-command-channel.md](../../docs/adr/ADR-011-pi-command-channel.md)
[4] [docs/adr/ADR-005-security-model.md](../../docs/adr/ADR-005-security-model.md)
