---
type: Data Contract
title: Shared contracts (OpenAPI + example)
description: The OpenAPI + example-JSON seam binding agent, backend, and frontend — now unified on host/scan_mode vocabulary.
resource: contracts/openapi/openapi.yaml
tags: [contracts, openapi, seam]
timestamp: 2026-08-06T00:00:00Z
---

# Shared contracts

`contracts/` is the **shared source of truth** binding the components. Today it is the *only* live
coupling between the [agent](/hardware-agent/overview.md) and the [backend](/backend/overview.md):
the agent writes payloads shaped by it, and the backend's schemas mirror it.

## Files

| File | What it is |
|------|-----------|
| `contracts/openapi/openapi.yaml` | OpenAPI 3.1 REST/ingest contract — the full integration surface (much broader than what the backend shell implements today). |
| `contracts/examples/scan_result.example.json` | A concrete `ScanIngestRequest` payload; the shared test fixture. |

## The ingest surface

- `POST /api/v1/scans` — agent ingest, **signed** (headers `X-Device-Id`, `X-Timestamp`,
  `X-Nonce`, `X-Body-SHA256`, `X-Signature`; returns `202 Accepted`). **Wired** (DMI-63), operation
  id `ingestScan`. `401` unauthenticated / nonce replay, `403` revoked device or a scan owned by
  another agent-or-org, `400` results after the command was written off, `422` payload shape.
- `GET /api/v1/scans`, `/scans/{id}`, `/hosts`, `/findings` — JWT-authed reads (a `pending` scan
  stub is returned before ingest completes).
- `POST /api/v1/agents/{agent_id}/commands` — admin-only "Scan now" trigger; `201` +
  `CommandSummary`, `409 device_busy`, `503 device_offline`. **Wired** (DMI-64).
- `GET /api/v1/commands/{command_id}` — `CommandDetail`. **Wired** (DMI-64). `scan_id` is optional
  on both `CommandSummary` and `CommandDetail`: a `queued` or `expired` command has no linked scan.
- `GET /api/v1/agents/{agent_id}/commands` — **WebSocket** command channel (Ed25519; frames
  `hello`/`command`/`status`). Scan results never travel this socket. **Both ends wired** — the
  backend since DMI-64, the Pi client since DMI-66
  ([command-channel](/hardware-agent/command-channel.md)). `AvailableSubnet` gained a **required**
  `is_default_route` in DMI-66, so a hello that omits it is an invalid frame on every side:
  contract, backend Pydantic model, and generated frontend type.
- `auth` (`login`/`refresh`/`logout`/…) + `invites` — identity surface.

Security schemes: `AgentHmacAuth` (ingest + WS), `FrontendBearerAuth` (short-lived JWT),
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
evidence), and metadata.

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
covers the read responses and — since DMI-63 mounted the route — the five ingest components
(`ScanIngestRequest`, `ScanIngestAcceptedResponse`, `HostPayload`, `PortPayload`, `FindingPayload`);
a name can only be listed there once some mounted route makes it reachable from `app.openapi()`, or
`_app_schema()` raises `KeyError`. `_property_shape` normalises two spellings that mean the same
thing — `type: [X, "null"]` ≡ `anyOf: [X, {type: null}]`, and `const: v` ≡ `enum: [v]` (pydantic emits
`const` for a single-value `Literal`; the contract writes a one-item `enum`). It does **not** read
`minLength`/`maxLength`, so a changed `constr(min_length=…)` is not caught — a known blind spot.
`OPERATION_PATHS` covers query parameters on `/scans` and `/findings`
only — `/api/v1/hosts` is **not** guarded, because the contract declares `sort_by`/`sort_order`/`q`
there and the service implements none of them (DMI-100 closes the sort half and adds the path).

**Error responses are guarded too, since DMI-77.** `ERROR_RESPONSE_ROUTES` maps seven pinned
`components/responses` entries — `PasswordChangeRejected`, `ResetPasswordRejected`, `ResetTokenGone`,
`AcceptInviteRejected`, `AcceptInviteTokenGone`, `InviteCreateRejected`, `InviteAlreadyPending` — to
`(router file, route function, status)`, AST-extracts that function's `ApiError(status, …, code="…")`
literals, and asserts exact set equality with the response's pinned `error.code` `enum`. Before this,
nothing cross-checked router literals against contract enums and a typo shipped green. Each pinned
response follows one shape: `allOf` of `ErrorResponse` plus an `enum`-constrained `error.code`, with
one example per code.

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
