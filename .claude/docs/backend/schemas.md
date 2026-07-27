---
type: Module
title: Backend wire schemas
description: The Pydantic ingest input (ScanResult), the legacy read/output projections (Persisted*), the read-path response schemas, and the auth and invite request/response models.
resource: backend/src/api/schemas/scan.py
tags: [backend, schemas, pydantic, contract]
timestamp: 2026-07-27T00:00:00Z
---

# Backend wire schemas

## Purpose

`schemas/` holds the Pydantic v2 models at the HTTP boundary — separate from the
[ORM models](/backend/models.md). `scan.py` is the **ingestion input**: it validates the `ScanResult`
an agent submits. `persistence.py` is the legacy read/output side: `Persisted*` projections used
mainly by tests. `read.py` is the **wired read path**: the nine response models the
[hosts/scans/findings routers](/backend/routers.md) actually return. `schemas/__init__.py` re-exports
the ingest input plus the main persisted projections.

## Key classes / functions — `scan.py` (ingest input)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `SubnetCIDR` | Constrained str, CIDR regex `d.d.d.d/n`. | `backend/src/api/schemas/scan.py:9` |
| `ScanResult` | Top-level payload (`extra="forbid"`): `scan_id`, `timestamp`, `subnet`, `scan_mode` (`quick`/`standard`/`extensive`/`nspi`/`max`), `hosts`, `findings`, `artifacts`, `metadata`. | `backend/src/api/schemas/scan.py:60` |
| `Host` | `ip` (`IPvAnyAddress`), MAC regex, `hostname`, `vendor`, `ports`. | `backend/src/api/schemas/scan.py:35` |
| `Port` | `port` (1–65535), `protocol` tcp/udp, `state`, `service`, `cpes`. | `backend/src/api/schemas/scan.py:26` |
| `Finding` | Optional `ip`/`port`/`protocol`, `cve_id` regex `CVE-\d{4}-\d{4,}`, `cvss_score` (0–10), `severity` enum, title/description/recommendation/evidence, `references`. | `backend/src/api/schemas/scan.py:43` |
| `Artifact` | `kind` (`nmap_xml`/`nse_output`), `path`, `stage`, optional `host_ip`. | `backend/src/api/schemas/scan.py:19` |
| `ScanIngestResponse` | `message`, `scan_id`, `hosts_received` — the `202` response body. | `backend/src/api/schemas/scan.py:73` |

## Key classes / functions — `read.py` (wired read responses)

| Name | What it shapes | Ref |
|------|-----------------|-----|
| `Port` | Read-side port view (`extra="forbid"`): port/protocol/state/service/version. | `backend/src/api/schemas/read.py:14` |
| `ScanHostView` | A host as observed in one scan; **`host_id` is required** (resolved identity, not nullable). | `backend/src/api/schemas/read.py:24` |
| `FindingRead` | A finding row plus resolved `host_id`/`host_ip` and `detected_at`. | `backend/src/api/schemas/read.py:35` |
| `HostSummary` | List-view row for `GET /hosts`: identity + `first_seen_at`/`last_seen_at` + `open_ports_count`/`highest_severity`. | `backend/src/api/schemas/read.py:58` |
| `HostScanHistoryEntry` | One scan's contribution to a host's history: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`, `highest_severity`. | `backend/src/api/schemas/read.py:72` |
| `HostDetailResponse` | `GET /hosts/{host_id}`: identity + latest `ports` + full `scan_history`. | `backend/src/api/schemas/read.py:82` |
| `ScanDetailResponse` | `GET /scans/{scan_id}`: scan header + `hosts` (`ScanHostView[]`) + `findings` + `status`/`command_id`/counts. | `backend/src/api/schemas/read.py:98` |
| `HostListResponse` | `GET /hosts`: paginated `data`/`total`/`page`. | `backend/src/api/schemas/read.py:114` |
| `FindingListResponse` | `GET /findings`: paginated `data`/`total`/`page`. | `backend/src/api/schemas/read.py:122` |

## Key classes / functions — `auth.py` (auth request/response)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `LoginRequest` | `email`, `password` (min length 1); `extra="forbid"`. | `backend/src/api/schemas/auth.py:8` |
| `LoginResponse` | `access_token`, `token_type` (`Literal["bearer"]`), `expires_in`. | `backend/src/api/schemas/auth.py:15` |
| `ChangePasswordRequest` | `current_password`, `new_password` (min length 12). | `backend/src/api/schemas/auth.py:23` |
| `ForgotPasswordRequest` | `email`. | `backend/src/api/schemas/auth.py:30` |
| `ResetPasswordRequest` | `token`, `new_password` (min length 12). | `backend/src/api/schemas/auth.py:36` |

These match the frozen `openapi.yaml` `auth` tag exactly and are consumed by the
[auth router](/backend/auth.md). `email` is plain `str` (no `EmailStr` — `email-validator` isn't a
dependency); the contract's `format: email` is advisory.

## Key classes / functions — `invites.py` (invite request/response)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `CreateInviteRequest` | `email`, `role` (`Literal["admin", "viewer"]`); `extra="forbid"`. | `backend/src/api/schemas/invites.py:11` |
| `InviteCreatedResponse` | `invite_token`, `expires_at`. | `backend/src/api/schemas/invites.py:18` |
| `AcceptInviteRequest` | `email`, `password` with the minimum taken from `MIN_LENGTH` in `services/passwords.py` — imported, never a literal `12`, so the schema and the policy cannot drift. | `backend/src/api/schemas/invites.py:25` |

`extra="forbid"` on all three is load-bearing, not stylistic: it is what turns an `org_id` smuggled
into the create-invite body into a **422** instead of a silently ignored field. The invited org
always comes from the caller's JWT.

## Key classes / functions — `persistence.py` (legacy read projections)

| Name | What it projects | Ref |
|------|------------------|-----|
| `PersistedDevice` / `PersistedPort` / `PersistedService` | A stored host with nested ports and one service (incl. `cpes`). | `backend/src/api/schemas/persistence.py:22` |
| `PersistedFinding` | A stored finding with `confidence`, `source_labels`, and embedded `KevRecordView` / `EpssRecordView` / `RiskSnapshotView`. | `backend/src/api/schemas/persistence.py:31` |
| `KevRecordView` / `EpssRecordView` / `RiskSnapshotView` | Read views of the KEV/EPSS/risk rows. | `backend/src/api/schemas/persistence.py:55` |
| `PersistedArtifact` | Stored artifact projection. | `backend/src/api/schemas/persistence.py:76` |
| `EnrichmentJobView` | An `enrichment_jobs` row (status, attempts, timestamps). | `backend/src/api/schemas/persistence.py:83` |
| `PersistedScanSummary` | Scan header (`scan_mode`) + `device_count` / `finding_count`. | `backend/src/api/schemas/persistence.py:98` |
| `PersistedScanDetail` | Full scan: `scan_mode`/`status` + metadata + devices + findings + artifacts + enrichment jobs. | `backend/src/api/schemas/persistence.py:107` |
| `PersistedScanRiskSummary` | Aggregates: totals, confirmed/KEV counts, average/max risk, `top_findings`. | `backend/src/api/schemas/persistence.py:120` |

## How it connects

- `ScanResult` is the argument to [`persist_scan`](/backend/services.md), which maps it onto the
  [ORM models](/backend/models.md); the enrichment services also build synthetic `Finding` objects
  to feed `upsert_finding`.
- The `read.py` models are built by [`services/read.py`](/backend/services.md) and returned directly
  by the [routers](/backend/routers.md) — this is the one wired HTTP surface today.
- The `Persisted*` projections still exist and are used mainly by tests; they predate the read path
  and are not returned by any router.

## Notes / gotchas

- **`scan_mode`, resolved.** `ScanResult.scan_mode` and the OpenAPI `ScanIngestRequest.scan_mode` now
  agree — see [contracts](/contracts.md) for the ADR-013 resolution.
- **`hosts`, not devices.** The ingest schema uses `Host`/`hosts`/`hosts_received` (ADR-013 retired
  `device` from the wire — see [glossary](/glossary.md)). `PersistedDevice`/`devices`/`device_count`
  in the legacy `persistence.py` projections were **not** renamed by this change.
- These are Pydantic models, wholly distinct from the same-named ORM classes in
  [models](/backend/models.md) (`Host` schema vs `ScanHostRecord`/`HostRecord` tables).

# Citations

[1] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
[2] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[3] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[4] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
