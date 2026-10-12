---
type: Module
title: partial scan warning
description: ScanPartialWarning shows a plain attention line beside scan duration when a scan is partial.
resource: frontend/src/pages/scans/ScanPartialWarning.tsx
tags: [frontend, scans, coverage, i18n, accessibility]
timestamp: 2026-10-12T00:00:00Z
---

# Partial scan warning

## Purpose

`ScanPartialWarning` gives completed scans with incomplete coverage a plain attention line beside
duration: an amber warning icon and the "partial scan" label. It is static text with no dialog or
details. Complete scans render nothing.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ScanPartialWarning` | Reads `metadata.partial_result` and renders the `scan-partial-warning` line only when it is `true`. | `frontend/src/pages/scans/ScanPartialWarning.tsx:7` |

## How it connects

- `ScanSummaryStrip` places the component next to duration on Scan Detail
  ([screens](./screens.md)).
- The component reads `ScanDetailResponse`; no extra API request is made.
- The label comes from `scans.partialWarningTitle` in the English, Brazilian Portuguese, and Russian
  message catalogs ([i18n](./i18n.md)).

## Notes / gotchas

- Partial status alone decides whether the line renders.
- `ScanDetailResponse.targeted_coverage` and the `targeted_units_*` metadata counts are still
  returned by the API ([contracts](../contracts.md)), but no screen renders them since the details
  dialog was removed.
