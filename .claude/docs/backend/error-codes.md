---
type: Module
title: Scan failure-code vocabulary
description: The closed ScanErrorCode set and the two pure helpers every read path uses to normalise a stored command code onto the wire.
resource: backend/src/api/core/error_codes.py
tags: [backend, core, error-code, command-channel]
timestamp: 2026-08-13T00:00:00Z
---

# Scan failure-code vocabulary

## Purpose

A failed scan must carry a reason on the scan itself, in one request. The reason is a closed
machine code, not prose. This leaf module is the single vocabulary: nine published codes, plus
the two pure functions that map a stored `commands.error_code` (which may be NULL, off-contract,
or from a newer Pi) onto that set. It lives in `api/core/` for the same reason
[`Severity`](/backend/api.md) does — `schemas/read.py` and `schemas/commands.py` have no import
edge between them, and must not gain one.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ScanErrorCode` | `Literal` of the nine published codes: `device_offline`, `device_busy`, `agent_disconnected`, `scan_failed`, `scan_timeout`, `invalid_command`, `result_unavailable`, `ingest_failed`, `unknown`. | `backend/src/api/core/error_codes.py:5` |
| `SCAN_ERROR_CODES` | `frozenset` of those members, derived via `get_args` so the set cannot drift from the Literal. | `backend/src/api/core/error_codes.py:16` |
| `UNKNOWN` | The `"unknown"` member, used when a failed scan has no usable stored code. | `backend/src/api/core/error_codes.py:18` |
| `normalise_error_code(stored)` | `None` stays `None`; a published code round-trips; any other string becomes `"unknown"`. Used on `GET /commands/{id}`. | `backend/src/api/core/error_codes.py:21` |
| `scan_error_code(scan_status, stored)` | Non-`failed` scans always return `None` (no stale reason on a green scan). A `failed` scan never returns `None` — NULL / off-contract / missing command all become `"unknown"`. Used on `GET /scans/{id}`. | `backend/src/api/core/error_codes.py:33` |

## How it connects

- [schemas](/backend/schemas.md) import `ScanErrorCode` for `ScanDetailResponse.error_code` and
  `CommandDetail.error_code`.
- [services](/backend/services.md) `get_command_detail` wraps the stored value in
  `normalise_error_code`; `get_scan_detail` derives the field via `scan_error_code` after a
  `command_for_scan` join.
- Inbound `AgentStatusFrame.error_code` stays `str \| None` — a newer Pi is not silenced. The
  stored string is normalised only on read.
- The operator-facing sentence lives in the SPA copy deck
  ([scan-failure-reasons](/frontend/scan-failure-reasons.md)), not on the wire.

## Notes / gotchas

- **No column on `scans`.** The reason is derived from the command row at read time. No migration,
  no backfill.
- **An `expired` command has no `scan_id`** (ADR-011 CHECK). Both `queued → expired` writers —
  the sweep's `queued` branch and `_expire_queued_command` on the delivery path — record
  `device_offline`, and both are observable only on `GET /commands/{id}`, never on scan detail.
- **Only three codes have an emitter today**, all backend-side: `device_offline` (delivery +
  sweep), `agent_disconnected` (sweep, disconnect pass) and `scan_timeout` (sweep, duration pass —
  a connected Pi that ran past its per-mode budget). The other six are the vocabulary the Pi reports into —
  `hardware-agent` threads `error_code: str | None` up its whole status path but passes `None` on
  every branch. Publishing the closed set now is what lets the Pi name its failures later without
  a contract revision.
- Imports nothing from `api.schemas` or `api.services` — keep it a leaf.

# Citations

[1] [specs/032-failed-scan-error-code/TRUTH.md](../../../specs/032-failed-scan-error-code/TRUTH.md)
[2] [docs/adr/ADR-011-pi-command-channel.md](../../../docs/adr/ADR-011-pi-command-channel.md)
