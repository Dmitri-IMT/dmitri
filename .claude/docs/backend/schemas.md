---
type: Module
title: Backend wire schemas
description: The Pydantic ingest input (ScanResult) and the read/output projections (Persisted*).
resource: backend/src/api/schemas/scan.py
tags: [backend, schemas, pydantic, contract]
timestamp: 2026-07-21T00:00:00Z
---

# Backend wire schemas

## Purpose

`schemas/` holds the Pydantic v2 models at the HTTP boundary — separate from the
[ORM models](/backend/models.md). `scan.py` is the **ingestion input**: it validates the `ScanResult`
an agent submits. `persistence.py` is the **read/output side**: projections that shape persisted rows
for API responses. `schemas/__init__.py` re-exports the ingest input plus the main persisted
projections.

## Key classes / functions — `scan.py` (ingest input)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `SubnetCIDR` | Constrained str, CIDR regex `d.d.d.d/n`. | `backend/src/api/schemas/scan.py:9` |
| `ScanResult` | Top-level payload: `scan_id`, `timestamp`, `subnet`, `target_mode` (`single_host`/`subnet`/`multi_host`), `scan_profile` (`single-host`/`lab`/`lan`/`deep`), `devices`, `findings`, `artifacts`, `metadata`. | `backend/src/api/schemas/scan.py:61` |
| `Device` | `ip` (`IPvAnyAddress`), MAC regex, `hostname`, `vendor`, `ports`. | `backend/src/api/schemas/scan.py:36` |
| `Port` | `port` (1–65535), `protocol` tcp/udp, `state`, `service`, `cpes`. | `backend/src/api/schemas/scan.py:27` |
| `Finding` | Optional `ip`/`port`/`protocol`, `cve_id` regex `CVE-\d{4}-\d{4,}`, `cvss_score` (0–10), `severity` enum, title/description/recommendation/evidence, `references`. | `backend/src/api/schemas/scan.py:44` |
| `Artifact` | `kind` (`nmap_xml`/`nse_output`), `path`, `stage`, optional `host_ip`. | `backend/src/api/schemas/scan.py:20` |
| `ScanIngestResponse` | `message`, `scan_id`, `devices_received` — the `202` response body. | `backend/src/api/schemas/scan.py:73` |

## Key classes / functions — `persistence.py` (read projections)

| Name | What it projects | Ref |
|------|------------------|-----|
| `PersistedDevice` / `PersistedPort` / `PersistedService` | A stored host with nested ports and one service (incl. `cpes`). | `backend/src/api/schemas/persistence.py:22` |
| `PersistedFinding` | A stored finding with `confidence`, `source_labels`, and embedded `KevRecordView` / `EpssRecordView` / `RiskSnapshotView`. | `backend/src/api/schemas/persistence.py:31` |
| `KevRecordView` / `EpssRecordView` / `RiskSnapshotView` | Read views of the KEV/EPSS/risk rows. | `backend/src/api/schemas/persistence.py:55` |
| `PersistedArtifact` | Stored artifact projection. | `backend/src/api/schemas/persistence.py:76` |
| `EnrichmentJobView` | An `enrichment_jobs` row (status, attempts, timestamps). | `backend/src/api/schemas/persistence.py:83` |
| `PersistedScanSummary` | Scan header + `device_count` / `finding_count`. | `backend/src/api/schemas/persistence.py:98` |
| `PersistedScanDetail` | Full scan: metadata + devices + findings + artifacts + enrichment jobs. | `backend/src/api/schemas/persistence.py:108` |
| `PersistedScanRiskSummary` | Aggregates: totals, confirmed/KEV counts, average/max risk, `top_findings`. | `backend/src/api/schemas/persistence.py:121` |

## How it connects

- `ScanResult` is the argument to [`persist_scan`](/backend/services.md), which maps it onto the
  [ORM models](/backend/models.md); the enrichment services also build synthetic `Finding` objects
  to feed `upsert_finding`.
- The `Persisted*` projections would shape the read endpoints in [contracts](/contracts.md) — those
  routes are not wired, so today these are used mainly by tests.

## Notes / gotchas

- **Contract divergence.** `ScanResult` uses `target_mode` + `scan_profile`; the OpenAPI
  `ScanIngestRequest` uses `scan_mode`. The Pydantic model and the example JSON agree with each other;
  the OpenAPI schema is the one out of step. Reference [contracts](/contracts.md); do not reconcile.
- **`devices`, not hosts.** The ingest schema keeps the frozen word `Device`/`devices` (see
  [glossary](/glossary.md)); output projections keep it too (`PersistedDevice`).
- These are Pydantic models, wholly distinct from the same-named ORM classes in
  [models](/backend/models.md) (`Device` schema vs `DeviceRecord` table).

# Citations

[1] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
[2] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
