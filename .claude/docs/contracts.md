---
type: Data Contract
title: Shared contracts (OpenAPI + example)
description: The published OpenAPI + example-JSON seam binding agent, backend, and frontend, including the wired user/member, invite and agent administration surface.
resource: contracts/openapi/openapi.yaml
tags: [contracts, openapi, seam]
timestamp: 2026-10-13T00:00:00Z
---

# Shared contracts

`contracts/` is the **shared source of truth** binding the components. Today it is the *only* live
coupling between the [agent](/hardware-agent/overview.md) and the [backend](/backend/overview.md):
the agent writes payloads shaped by it, and the backend's schemas mirror it.

## Files

| File | What it is |
|------|-----------|
| `contracts/openapi/openapi.yaml` | The published OpenAPI 3.1 contract and system of record; FastAPI's generated schema endpoint is disabled. |
| `contracts/examples/scan_result.example.json` | A concrete `ScanIngestRequest` payload; the shared test fixture. |

## The ingest surface

- `POST /api/v1/scans` — agent ingest, **signed** (headers `X-Device-Id`, `X-Timestamp`,
  `X-Nonce`, `X-Body-SHA256`, `X-Signature`; returns `202 Accepted`). **Wired** (DMI-63), operation
  id `ingestScan`. `401` unauthenticated / nonce replay, `403` revoked device or a scan owned by
  another agent-or-org, `400` results after the command was written off, `422` payload shape.
- `GET /api/v1/scans`, `/scans/{id}`, `/hosts`, `/findings` — JWT-authed reads (a `pending` scan
  stub is returned before ingest completes). `GET /scans/{id}` (`ScanDetailResponse`) carries
  findings and hosts. `GET` and `POST /scans/{id}/analysis` (`getScanAIAnalysis` /
  `requestScanAIAnalysis`) are the on-demand AI envelope (`not_requested` until a member POSTs).
  Host and scan detail include `industrial_services` and `unreadable_fields`. Findings may include
  optional `error_code` (`ScanErrorCode | null`) since DMI-75; the list row (`ScanSummary`) does not.
  Findings may include `modbus_unit`. Process values are not on the contract.
- `POST /api/v1/agents/{agent_id}/commands` — admin-only "Scan now" trigger; `201` +
  `CommandSummary`, `409 device_busy`, `422 subnet_not_reported` (DMI-78, `ScanSubnetNotReported`),
  `503 device_offline`. **Wired** (DMI-64).
- `GET /api/v1/agents` (`listAgents`) and `GET /api/v1/agents/{agent_id}` — the fleet read surface;
  any authenticated caller, org-scoped. `AgentSummary` carries `online`/`last_seen_at`/
  required nullable `revoked_at`/`target_subnet`/`active_command_id`; `AgentDetail` adds the Pi's currently reported
  `available_subnets`. **Wired** (DMI-78) — the detail path was published earlier but unimplemented
  until then.
- `PATCH /api/v1/agents/{agent_id}` (`updateAgentTargetSubnet`) — admin-only choice of the network a
  Pi will scan; returns the full `AgentDetail`. `409 device_offline` (`AgentOfflineConflict`) when
  the Pi is reporting nothing, `422 subnet_not_reported` (`TargetSubnetNotReported`) for a network it
  did not report, `404` for an unknown or foreign agent. **Wired** (DMI-78).
- `POST /api/v1/agents/{agent_id}/revoke` (`revokeAgent`) and `/restore` (`restoreAgent`) are
  idempotent admin actions returning `AgentDetail`. Revoke commits before closing the socket;
  restore lets the Pi's next hourly attempt connect. **Wired** (DMI-155).
- `GET /api/v1/commands/{command_id}` — `CommandDetail`. **Wired** (DMI-64). `scan_id` is optional
  on both `CommandSummary` and `CommandDetail`: a `queued` or `expired` command has no linked scan.
  `error_code` is optional `ScanErrorCode | null` (DMI-75 / spec 032): eight published values;
  an off-contract stored string reads as `"unknown"`. `CommandStatus` includes `cancelled` (DMI-145).
- `POST /api/v1/commands/{command_id}/cancel` (`cancelCommand`) — admin stop. **Wired** (DMI-145).
  `202` when a cancel frame is sent; `200` when offline-retired or already terminal; `409`
  `command_not_cancellable` while `uploading`; `404` when missing/foreign.
- `GET /api/v1/agents/{agent_id}/commands` — **WebSocket** command channel (Ed25519; frames
  `hello`/`command`/`cancel`/`status`). Scan results never travel this socket. **Both ends wired** — the
  backend since DMI-64, the Pi client since DMI-66
  ([command-channel](/hardware-agent/command-channel.md)). `AvailableSubnet` gained a **required**
  `is_default_route` in DMI-66, so a hello that omits it is an invalid frame on every side:
  contract, backend Pydantic model, and generated frontend type.
  Private close codes and upgrade `403` now park the Pi for one hour instead of ending the daemon.
  DMI-145 adds outbound `cancel` and inbound status value `cancelled`.
- `GET /api/v1/users` (`listOrgUsers`) — admin-only member list, ordered by recent activity;
  `OrgMember` exposes `last_seen_at` but no login history or status.
- `PATCH /api/v1/users/{user_id}` (`updateUserRole`) — admin-only role change; `409 self_target`
  or `last_admin`, 404 for unknown/foreign members.
- `GET /api/v1/invites` (`listPendingInvites`) — admin-only live pending invitations, with no token
  material. `DELETE /api/v1/invites/{invite_id}` (`revokeInvite`) hard-deletes a pending invite.
- Account-removal routes remain `DELETE /api/v1/users/me` and
  `DELETE /api/v1/users/{user_id}`. CORS publication now includes PATCH:
  `GET, POST, PATCH, DELETE, OPTIONS`.
- `auth` login/session/password routes plus invite create/accept/lookup complete the identity surface.
- Admin data deletion (DMI-186, [ADR-022](../../docs/adr/ADR-022-scan-and-machine-deletion.md)):
  `DELETE /api/v1/scans` (`deleteAllScans` → `ScanDeletionResponse`), `DELETE /api/v1/scans/{scan_id}`
  (`deleteScan`, `204`, `409 ScanRunningConflict` with code `scan_running`),
  `DELETE /api/v1/hosts` (`deleteAllHosts` → `HostDeletionResponse`) and
  `DELETE /api/v1/hosts/{host_id}` (`deleteHost`, `204`). `UserProfileResponse` gained a required
  `org_name`, and `ActivityKind` gained `scans_deleted` / `machines_deleted`.

Security schemes: `AgentSignatureAuth` (ingest + WS), `FrontendBearerAuth` (short-lived JWT),
`RefreshCookieAuth` (httpOnly `dmitri_refresh` cookie). CORS restricted to the SPA origins.

> **Ingest is wired as of DMI-63** ([backend/routers](/backend/routers.md)), joining the read path,
> auth, the invite routes and the command channel. `POST /api/v1/scans` is mounted as `ingestScan`
> behind `require_agent` and returns the contract's `202`. **DMI-66 closed the device end**: the
> [daemon](/hardware-agent/daemon.md) dials the WS channel and posts results under the
> backend-supplied `scan_id`. What remains unexercised is a *real Pi* — the automated tests drive
> both ends with signed test requests and fake sockets.

## The payload shape

The agent emits a [`ScanPayload`](/hardware-agent/normalize.md); the backend validates a
`ScanIngestRequest` ([backend/schemas](/backend/schemas.md)) — since DMI-63 the Python class and the
contract component share the same name, as do `HostPayload`/`PortPayload`/`FindingPayload`. Both
carry a scan header (`scan_id`, `timestamp`, `subnet`, `scan_mode`), a list of **hosts**
(ip/mac/hostname/vendor + ports), a list of **findings** (cve_id, cvss, severity, confidence,
evidence), and metadata. Current scans also carry `assessment_policy_version`, one bounded
`device_profile` per host, and one `ExposurePayload` per open endpoint. The policy/version and
exposure collection are jointly optional only so legacy payloads remain valid.

Exposures are a separate attack-surface inventory. Their `attention` field is not vulnerability
severity and does not contribute to finding totals. Read contracts expose `assessment_status`, the
stored policy version, profiles, and `ExposureRead[]` on scan/host detail. Legacy records return
`unavailable` with an empty exposure list rather than reconstructed data.

**`PortPayload` is ingest-only (DMI-63).** The contract gained a *new* `PortPayload` component —
`Port` plus `cpes` — and `HostPayload.ports` was re-pointed at it. `Port` itself was deliberately
left byte-identical, because the read responses (`ScanHostView`, `HostDetailResponse`) still
fingerprint through it and `read.Port` has no `cpes`. Widening the shared component instead would
break both.

The OpenAPI `ScanIngestRequest` uses `HostPayload` (`hosts[]`); `ScanIngestAcceptedResponse` returns
`hosts_received` plus a `status` of `"accepted"` (ADR-013 retired
`Device`/`devices`/`devices_received` from the wire — ingest is
now `POST`ed as `hosts[]`, per contract asks C1–C5). Read responses add: `ScanHostView` — the
`HostPayload` shape plus a **required** `host_id` (C9, resolved host identity per host observation
in a scan); `HostSummary` / `HostDetailResponse` — list/detail rows with `machine_type` and
`vulnerability_count`; `HostListResponse.quiet_total`; `HostPort` (durable services, no `state`,
nullable `observed_in_latest_scan`); required `evidence_completeness` (`EvidenceCompleteness`:
`complete`/`partial`/`unknown`) on `ScanSummary` and `ScanDetailResponse`; `ScanDetailResponse.coverage`
(`CoverageUnitPayload[]`, also accepted on `ScanIngestRequest.coverage`);
`ScanDetailResponse.targeted_coverage` (`TargetedToolCoverage[]` with `TargetedCoverageGap[]`,
read-only, decoded from `metadata.targeted_coverage`);
`FindingRead.host_hostname` plus life timestamps. `GET /hosts` takes `group=active|quiet` (default
active). `HostSortBy` includes `vulnerability_count` and not `machine_type`.

**Nullability and `required`, tightened 2026-08-02.** `mac` is nullable on `ScanHostView`,
`HostSummary` and `HostDetailResponse` (a routed host has no MAC) but stays in each schema's
`required` list — always present on the wire, sometimes `null`. The collection fields
(`ScanHostView.ports`, `HostDetailResponse.ports`/`scan_history`, `ScanDetailResponse.hosts`/
`findings`) are likewise `required`: the backend always emits them, so publishing them as optional
would push needless `?.` into the generated frontend types. All address fields are `format: ipv4`,
which the Pydantic models now match exactly with `IPv4Address`.

`backend/tests/test_contract_fidelity.py` fingerprints mounted Pydantic schemas against this file.
Spec 030 added `OrgMember`, `OrgMemberListResponse`, `UpdateUserRoleRequest`, `PendingInvite`, and
`PendingInviteListResponse` to that coverage, and separately pins operation ids and response-code
sets for the four new admin operations. DMI-186 added `ScanDeletionResponse` and
`HostDeletionResponse` to the fingerprinted schemas and `ScanRunningConflict` to the error-code map. Query-parameter parity covers scans, findings and — since DMI-100 — hosts
(`OPERATION_PATHS`, `test_contract_fidelity.py:59`).

**The gate has one declared-but-unimplemented exemption.** `UNIMPLEMENTED_PARAMS =
{("/api/v1/hosts", "q")}` (`test_contract_fidelity.py:63`) is subtracted from the contract's
parameter set before the comparison. The contract declares a free-text `q` on `/api/v1/hosts`;
search is cut from v1, so the backend does not implement it and the contract keeps it anyway.
Without the exemption, adding `/api/v1/hosts` to `OPERATION_PATHS` would fail on `q` alone. This is
the intended final shape, not a stopgap — "the contract declares more of v1 than is built yet" is a
standing condition here. Do not resolve it by implementing `q` or by deleting it from the contract.
Drift on the other host params (`page`, `per_page`, `sort_by`, `sort_order`, `group`) is still caught.

Spec 032 added `ScanErrorCode` (eight-value string enum) and pointed both
`ScanDetailResponse.error_code` and `CommandDetail.error_code` at it as optional nullable `$ref`s.
`AgentStatusFrame.error_code` stays untyped `string | null` so a newer Pi is not silenced.
`ScanSummary` has no `error_code` — list rows are unchanged.

Spec 031 added `AgentSummary`, `AgentDetail`, `AgentListResponse` and
`UpdateAgentTargetSubnetRequest`, and pins `listAgents` and `updateAgentTargetSubnet` the same way.
`AgentDetail` gained `available_subnets` in `required` (after `last_seen_at`) plus an optional
`target_subnet`; `active_command_id` stays **out** of `required` — that is deliberate, not an
oversight to fix.

**Error responses are guarded too.** `ERROR_RESPONSE_ROUTES` now maps thirteen pinned components.
The `RoleChangeConflict` must match the role router's exact `409` codes (`self_target`,
`last_admin`), alongside the existing auth/invite and account-removal components. The gate
AST-extracts route literals and compares them with each contract enum — since spec 031 it matches
`ast.AsyncFunctionDef` as well as `ast.FunctionDef`, because `create_agent_command` is `async def`
and the scan would otherwise fail to find it.

**Three near-identical error components exist on purpose.** `AgentOfflineConflict` (409
`device_offline`), `TargetSubnetNotReported` (422 `subnet_not_reported`) and `ScanSubnetNotReported`
(422 `subnet_not_reported`) are not collapsible: `ERROR_RESPONSE_ROUTES` maps **one component to
exactly one handler**, so sharing one would leave an `ApiError` literal unverified. Nor does
`AgentOfflineConflict` merge into `DeviceOfflineError` — same machine code by decision, different
status and meaning. A separate test pins each path's `$ref`, because the operation-publication test
compares only status-code sets and would not notice a swap.

The example fixture (`scan_result.example.json`) now uses `scan_mode`, matching the OpenAPI schema
(previously it used `target_mode`/`scan_profile` — see "Resolved divergence" below); it is loaded by
`backend/tests/test_ingest_scan.py` to drive `ingest_scan`/`persist_scan` and the enrichment tests
offline. It carries no `artifacts` key — DMI-63 deleted the artifact concept end to end, so an
`artifacts` field in an ingest body is now a `422`.

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
[8] [specs/030-users-invites-admin-api](../../specs/030-users-invites-admin-api/TRUTH.md)
