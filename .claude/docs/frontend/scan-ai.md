---
type: Module
title: frontend AI overview card
description: Scan Detail card that GETs analysis status, offers Explain this scan once, polls only while pending or processing, and renders the Groq overview when completed.
resource: frontend/src/pages/scans/ScanAIAnalysis.tsx
tags: [frontend, ai, scans, tanstack-query]
timestamp: 2026-09-13T16:40:00Z
---

# frontend AI overview card

## Purpose

`ScanAIAnalysis` sits on completed Scan Detail, above findings. It uses its own query
(`queryKeys.scans.analysis(scanId)`), not the scan payload. `unavailable` renders nothing.
`not_requested` and `failed` show footer button `Explain this scan` (`scan-ai-request`).
`pending`/`processing` poll every 3s for at most 5 minutes (`aria-live="polite"`). `completed`
renders the English overview. A POST 409 refetches GET. POST errors use the existing error card
(`Reload overview`).

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `getScanAnalysis` / `requestScanAnalysis` | GET and POST `/scans/{id}/analysis`. | `frontend/src/api/scans.ts:63`, `:72` |
| `ScanAIAnalysis` | Exhaustive `switch` on `status`. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:29` |
| `handleRequest` | Disables the button, POSTs, writes the cache, 409 → refetch. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:62` |
| `ScanDetail` | Mounts the card only on the completed branch. | `frontend/src/pages/ScanDetail.tsx:74` |

## How it connects

- Backend: [AI scan analysis](/backend/ai.md).
- Scan findings stay visible regardless of AI status ([screens](./screens.md)).

## Notes / gotchas

- First GET `isPending` returns `null` (no skeleton). Analysis hanging must not block vulns/machines.
- No `dangerouslySetInnerHTML`. Overview text is plain React text.
- `FindingPanel` shows risk as `Math.round(risk_score)` plus ` of 100`, not `toFixed(2)`.
