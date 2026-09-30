---
type: Module
title: partial scan coverage details
description: ScanPartialWarning shows an attention control beside scan duration and opens per-tool coverage details when a scan is partial.
resource: frontend/src/pages/scans/ScanPartialWarning.tsx
tags: [frontend, scans, coverage, i18n, accessibility]
timestamp: 2026-09-30T00:00:00Z
---

# Partial scan coverage details

## Purpose

`ScanPartialWarning` gives completed scans with incomplete targeted coverage a compact attention
control beside duration. Opening it shows planned, completed, failed, timed-out, and skipped work,
grouped by tool with available gap reasons. Complete scans render no control.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `ScanPartialWarning` | Reads `partial_result` and the scan's stored coverage metadata, then renders the attention trigger and accessible details dialog only for partial results. | `frontend/src/pages/scans/ScanPartialWarning.tsx:83` |
| `targetedCoverage()` | Parses the serialized per-tool coverage field into completed, failed, timed-out, skipped, and gap-reason values. | `frontend/src/pages/scans/ScanPartialWarning.tsx:44` |

## How it connects

- `ScanSummaryStrip` places the component next to duration on Scan Detail
  ([screens](./screens.md)).
- The component reads metadata already present in `ScanDetailResponse`; no extra API request is
  made.
- Text comes from the English, Brazilian Portuguese, and Russian message catalogs
  ([i18n](./i18n.md)).

## Notes / gotchas

- Partial status alone decides whether the trigger is rendered; a completed scan with empty coverage
  metadata does not show the dialog.
- Gap reason identifiers are translated for display while the stored metadata remains unchanged.
