---
type: Module
title: Backend wire schemas
description: The Pydantic ingest input (ScanIngestRequest), the legacy read/output projections (Persisted*), the read-path response schemas, the user profile schema, the command-channel wire frames and HTTP shapes, and the auth and invite request/response models.
resource: backend/src/api/schemas/scan.py
tags: [backend, schemas, pydantic, contract]
timestamp: 2026-08-06T00:00:00Z
---

# Backend wire schemas

## Purpose

`schemas/` holds the Pydantic v2 models at the HTTP boundary — separate from the
[ORM models](/backend/models.md). `scan.py` is the **ingestion input**: it validates the
`ScanIngestRequest` an agent submits to the wired `POST /api/v1/scans`. `persistence.py` is the
legacy read/output side: `Persisted*` projections used
mainly by tests. `read.py` is the **wired read path**: the eleven response models the
[hosts/scans/findings routers](/backend/routers.md) actually return (plus `ScanSortBy`/`SortOrder`
literal aliases used only on the scan-list route). `schemas/__init__.py` re-exports
the ingest input plus the main persisted projections.

## Key classes / functions — `scan.py` (ingest input)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `SubnetCIDR` | Constrained str, CIDR regex `d.d.d.d/n`. | `backend/src/api/schemas/scan.py:10` |
| `ScanMode` | `Literal["quick", "standard", "extensive", "nspi", "max"]`. | `backend/src/api/schemas/scan.py:16` |
| `PortPayload` | `port` (1–65535), `protocol` tcp/udp, `state`, `service`, `version`, `cpes`. | `backend/src/api/schemas/scan.py:19` |
| `HostPayload` | `ip` (`IPv4Address`), MAC regex (required-but-nullable), `hostname`, `vendor`, `ports` (required). | `backend/src/api/schemas/scan.py:30` |
| `FindingPayload` | Optional `ip` (`IPv4Address`)/`port`/`protocol`, `cve_id` regex `CVE-\d{4}-\d{4,}`, `cvss_score` (0–10), `severity` enum, title/description/recommendation/evidence, `references`. | `backend/src/api/schemas/scan.py:40` |
| `ScanIngestRequest` | Top-level payload: `scan_id`, `timestamp`, `subnet`, `scan_mode`, `hosts`, `findings`, `metadata`. `hosts`/`findings` are required (no defaults). | `backend/src/api/schemas/scan.py:59` |
| `ScanIngestAcceptedResponse` | `message`, `scan_id`, `hosts_received` (`ge=0`), `status` (`Literal["accepted"]`) — the `202` response body. | `backend/src/api/schemas/scan.py:71` |

**All five carry `model_config = ConfigDict(extra="forbid")`** — DMI-63 pushed it to *every* ingest
depth, not just the top level. Before that only `ScanResult` forbade extras, so `hosts[0].os = "linux"`
was silently dropped instead of refused. The names are the contract's own (`HostPayload`,
`PortPayload`, `FindingPayload`), which also removes the short-name collision with `read.Port` that
made FastAPI mangle a component to `api__schemas__scan__Port`.

## Key classes / functions — `read.py` (wired read responses)

| Name | What it shapes | Ref |
|------|-----------------|-----|
| `Severity` / `SEVERITY_ORDER` | **Moved out of this module 2026-07-31** to [`core/severity.py`](/backend/api.md); `read.py` now imports `Severity` from there. Dict `low→1 … critical→4`, derived from the `Severity` literal's declaration order — the single severity-domain definition. | `backend/src/api/core/severity.py:5` |
| `Port` | Read-side port view (`extra="forbid"`): port/protocol/state/service/version. | `backend/src/api/schemas/read.py:18` |
| `ScanHostView` | A host as observed in one scan; **`host_id` is required** (resolved identity, not nullable). `mac` and `ports` are required-but-nullable / required — no defaults. | `backend/src/api/schemas/read.py:28` |
| `FindingRead` | A finding row plus resolved `host_id`/`host_ip` and `detected_at`. | `backend/src/api/schemas/read.py:39` |
| `HostSummary` | List-view row for `GET /hosts`: identity + `first_seen_at`/`last_seen_at` + `open_ports_count`/`highest_severity`. `mac` is required and nullable. | `backend/src/api/schemas/read.py:62` |
| `HostScanHistoryEntry` | One scan's contribution to a host's history: `scan_id`, `timestamp`, `scan_mode`, `open_ports_count`, `highest_severity`. | `backend/src/api/schemas/read.py:76` |
| `HostDetailResponse` | `GET /hosts/{host_id}`: identity + latest `ports` + full `scan_history`; `ports`/`scan_history` are required (no `default_factory`). | `backend/src/api/schemas/read.py:86` |
| `ScanDetailResponse` | `GET /scans/{scan_id}`: scan header + `hosts` (`ScanHostView[]`) + `findings` + `status`/`command_id`/counts; `hosts`/`findings` are required. | `backend/src/api/schemas/read.py:102` |
| `ScanSummary` | One row in `GET /scans`: identity + counts + optional `highest_severity` (`subnet` is plain `str`, no CIDR pattern). | `backend/src/api/schemas/read.py:118` |
| `ScanListResponse` | `GET /scans`: paginated `data`/`total`/`page` (no `per_page` in envelope). | `backend/src/api/schemas/read.py:131` |
| `HostListResponse` | `GET /hosts`: paginated `data`/`total`/`page`. | `backend/src/api/schemas/read.py:139` |
| `FindingListResponse` | `GET /findings`: paginated `data`/`total`/`page`. | `backend/src/api/schemas/read.py:147` |

## Key classes / functions — `users.py` (self profile)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `UserProfileResponse` | `user_id` (`UUID`), `email` (`str`), `role` (`Literal["admin", "viewer"]`); `extra="forbid"`. No `password_expires_at` — ADR-016 removed forced rotation. | `backend/src/api/schemas/users.py` |

Consumed by [`routers/users.py`](/backend/routers.md) for `GET /api/v1/users/me`.

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
| `AcceptInviteRequest` | `token`, `email`, `password` with the minimum taken from `MIN_LENGTH` in `services/passwords.py` — imported, never a literal `12`, so the schema and the policy cannot drift. `token` moved here from the URL path in DMI-77 to keep a live credential out of access logs. | `backend/src/api/schemas/invites.py:25` |

`extra="forbid"` on all three is load-bearing, not stylistic: it is what turns an `org_id` smuggled
into the create-invite body into a **422** instead of a silently ignored field. The invited org
always comes from the caller's JWT.

## Key classes / functions — `agent_frames.py` (command-channel wire frames)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `AvailableSubnet` | `interface` (min length 1), `cidr` (`SubnetCIDR`), and — required since DMI-66 — `is_default_route`. A hello that omits it is rejected; the model stays in Pydantic's lax mode like its neighbours, so `1`/`"true"`/`"yes"` still coerce. | `backend/src/api/schemas/agent_frames.py` |
| `AgentHelloFrame` | `type: "hello"`, `agent_version`, `available_subnets`. | `backend/src/api/schemas/agent_frames.py` |
| `AgentStatusFrame` | `type: "status"`, `command_id`, `status` (`running`/`uploading`/`done`/`failed`), optional `error_code`. | `backend/src/api/schemas/agent_frames.py` |
| `AgentCommandFrame` | `type: "command"`, `command_id`, `scan_id`, `scan_mode`, `subnet` — the outbound frame `deliver()` pushes down the socket. | `backend/src/api/schemas/agent_frames.py` |
| `AgentErrorFrame` | `type: "error"`, `message` — graceful parse/validation failures on the WS channel. | `backend/src/api/schemas/agent_frames.py` |

All five use `extra="forbid"` and mirror `contracts/openapi/openapi.yaml` frame schemas. Consumed by
[`services/agent_ws.py`](/backend/services.md) for inbound dispatch and by
[`services/commands.py`](/backend/services.md) for outbound delivery.

## Key classes / functions — `commands.py` (command-channel HTTP shapes)

| Name | What it validates | Ref |
|------|-------------------|-----|
| `CreateCommandRequest` | `POST /agents/{agent_id}/commands` body — `scan_mode` (`ScanMode`) and `subnet` (`SubnetCIDR`). `extra="forbid"`. | `backend/src/api/schemas/commands.py:22` |
| `CommandSummary` | The `201` response: `command_id`, optional `scan_id`, `agent_id`, `status`. | `backend/src/api/schemas/commands.py:29` |
| `CommandDetail` | `GET /commands/{command_id}` — `CommandSummary`'s fields plus `scan_mode`, `subnet`, optional `error_code`, and the four lifecycle timestamps (`created_at` required; `delivered_at`/`started_at`/`completed_at` nullable). | `backend/src/api/schemas/commands.py:38` |

**`scan_id` is optional on both `CommandSummary` and `CommandDetail`** — a `queued` or `expired`
command has none. The published contract was amended to drop it from `required` on both schemas;
`tests/test_contract_fidelity.py` gates that the two agree.

## Key classes / functions — `persistence.py` (legacy read projections)

| Name | What it projects | Ref |
|------|------------------|-----|
| `PersistedDevice` / `PersistedPort` / `PersistedService` | A stored host with nested ports and one service (incl. `cpes`). | `backend/src/api/schemas/persistence.py:22` |
| `PersistedFinding` | A stored finding with `confidence`, `source_labels`, and embedded `KevRecordView` / `EpssRecordView` / `RiskSnapshotView`. | `backend/src/api/schemas/persistence.py:31` |
| `KevRecordView` / `EpssRecordView` / `RiskSnapshotView` | Read views of the KEV/EPSS/risk rows. | `backend/src/api/schemas/persistence.py:55` |
| `EnrichmentJobView` | An `enrichment_jobs` row (status, attempts, timestamps). | `backend/src/api/schemas/persistence.py:76` |
| `PersistedScanSummary` | Scan header (`scan_mode`) + `device_count` / `finding_count`. | `backend/src/api/schemas/persistence.py:91` |
| `PersistedScanDetail` | Full scan: `scan_mode`/`status` + metadata + devices + findings + enrichment jobs. | `backend/src/api/schemas/persistence.py:100` |
| `PersistedScanRiskSummary` | Aggregates: totals, confirmed/KEV counts, average/max risk, `top_findings`. | `backend/src/api/schemas/persistence.py:112` |

`PersistedArtifact` and `PersistedScanDetail.artifacts` were **removed in DMI-63** along with the
rest of the artifact concept — see the note below.

## How it connects

- `ScanIngestRequest` is the body of `POST /api/v1/scans` ([routers](/backend/routers.md)) and the
  argument to [`ingest_scan`/`persist_scan`](/backend/services.md), which map it onto the
  [ORM models](/backend/models.md); the enrichment services also build synthetic `FindingPayload`
  objects to feed `upsert_finding`.
- The `read.py` models are built by [`services/read.py`](/backend/services.md) and returned directly
  by the [routers](/backend/routers.md) — this is the one wired HTTP surface today.
- The `Persisted*` projections still exist and are used mainly by tests; they predate the read path
  and are not returned by any router.

## Notes / gotchas

- **IPv4 only.** Every address field in `scan.py` and `read.py` is `IPv4Address`, not
  `IPvAnyAddress` (changed 2026-08-02). This matches the contract, which has always said
  `format: ipv4`, and `SubnetCIDR`, whose regex is IPv4-only. Ingest now **rejects** an IPv6 host or
  finding address with a `422` instead of accepting it. `HostRecord.ip` is still an unconstrained
  `str` column, so a pre-existing IPv6 row would fail response validation on read — none exist.
- **Required vs nullable on the read models.** `mac` is `| None` with **no default** on
  `ScanHostView`/`HostSummary`/`HostDetailResponse`: always present on the wire, sometimes `null`
  (a routed host has no MAC). The list fields `ports`, `scan_history`, `hosts` and `findings`
  likewise dropped `Field(default_factory=list)` — the service always passes them, and a default
  would make FastAPI publish them as optional, weakening the generated frontend types. Keep them
  defaultless so the contract's `required` list stays honest.
- **`scan_mode`, resolved.** `ScanIngestRequest.scan_mode` and the OpenAPI
  `ScanIngestRequest.scan_mode` now agree — see [contracts](/contracts.md) for the ADR-013 resolution.
  DMI-63 also adopted the contract's component *names*, so the Python class and the published
  schema are now called the same thing.
- **`hosts`, not devices.** The ingest schema uses `HostPayload`/`hosts`/`hosts_received` (ADR-013
  retired `device` from the wire — see [glossary](/glossary.md)).
  `PersistedDevice`/`devices`/`device_count` in the legacy `persistence.py` projections were **not**
  renamed by this change.
- **Artifacts are gone (DMI-63).** `Artifact`, `ArtifactKind`, `ScanResult.artifacts`,
  `PersistedArtifact` and `PersistedScanDetail.artifacts` were all deleted, along with the
  `ArtifactRecord` table — the agent never populated them. An `artifacts` key in an ingest body is
  now a **422** (unknown field), not a silently ignored one.
- **No ingest-side `Port` any more.** `scan.py` deliberately defines *no* class named `Port`; the
  read path keeps its own at `read.py:18`. Do not re-add one — the collision is what DMI-63 removed.
  The contract likewise gained a separate `PortPayload` component (`Port` plus `cpes`) rather than
  widening the shared `Port`, which the read responses still fingerprint against.
- These are Pydantic models, wholly distinct from the same-named ORM classes in
  [models](/backend/models.md) (`HostPayload` schema vs `ScanHostRecord`/`HostRecord` tables).

# Citations

[1] [contracts/openapi/openapi.yaml](../../../contracts/openapi/openapi.yaml)
[2] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
[3] [docs/adr/ADR-013-ingest-host-vocabulary-unification.md](../../../docs/adr/ADR-013-ingest-host-vocabulary-unification.md)
[4] [specs/015-read-path](../../../specs/015-read-path/TRUTH.md)
[5] [specs/018-agent-ws-command-channel](../../../specs/018-agent-ws-command-channel/TRUTH.md)
[7] [specs/021-scan-list-and-finding-filters](../../../specs/021-scan-list-and-finding-filters/TRUTH.md)
[8] [specs/024-scan-ingest-endpoint](../../../specs/024-scan-ingest-endpoint/TRUTH.md)
