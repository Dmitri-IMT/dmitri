---
type: Module
title: scan failure-reason copy deck
description: SCAN_FAILURE_REASONS maps each published ScanErrorCode to one operator sentence; scanFailureReason() falls back to the unknown sentence.
resource: frontend/src/lib/scanFailureReasons.ts
tags: [frontend, copy, scan, error-code]
timestamp: 2026-08-13T00:00:00Z
---

# scan failure-reason copy deck

## Purpose

The API carries a closed set of failure codes; the sentence an operator reads is client copy.
This module is that copy — keyed off the generated `ScanErrorCode` union so a new code without a
sentence fails `tsc`. It has **no caller yet**: DMI-88 builds the Scan Detail screen and will
import it. That is deliberate, not a stopgap.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `SCAN_FAILURE_REASONS` | `Record<ScanErrorCode, string>` — nine verbatim approved sentences. Each names the Pi, says what happened, and ends with the next action. | `frontend/src/lib/scanFailureReasons.ts:7` |
| `scanFailureReason(code)` | `string \| null \| undefined` in — `error_code` is an *optional* property on the generated types, so callers pass it straight through without a `?? null`. Looks up through a widened `Record<string, string \| undefined>` and `??` falls back to the `unknown` sentence. | `frontend/src/lib/scanFailureReasons.ts:27` |

## How it connects

- The union comes from generated [`openapi.d.ts`](/contracts.md) (`components['schemas']['ScanErrorCode']`),
  itself produced by `npm run gen:types` from `contracts/openapi/openapi.yaml`. Never hand-edit
  that file.
- No page, hook, or `src/api/` module imports this yet. [screens](/frontend/screens.md) will when
  Scan Detail ships (DMI-88).

## Notes / gotchas

- **Copy is frozen.** Do not reword, re-punctuate, or "fix" the em dashes. The test asserts the
  nine sentences verbatim and forbids code strings, `_`, `nmap`, and `Traceback`.
- `scanFailureReason('warp_core_breach')`, `scanFailureReason(null)` and
  `scanFailureReason(undefined)` all return the `unknown` sentence — same honesty as the backend's
  `scan_error_code`.
- Mirror of [review](/frontend/review.md): a pure lib module with a Vitest neighbour, no React.

# Citations

[1] [specs/032-failed-scan-error-code/TRUTH.md](../../../specs/032-failed-scan-error-code/TRUTH.md)
[2] [specs/032-failed-scan-error-code/ARCHITECTURE.md](../../../specs/032-failed-scan-error-code/ARCHITECTURE.md)
