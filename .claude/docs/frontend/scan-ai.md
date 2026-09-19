---
type: Module
title: frontend AI overview card
description: Scan Detail card that GETs analysis status, offers Explain this scan once, polls only while pending or processing, and renders the Groq overview when completed.
resource: frontend/src/pages/scans/ScanAIAnalysis.tsx
tags: [frontend, ai, scans, tanstack-query]
timestamp: 2026-09-19T18:25:00Z
---

# frontend AI overview card

## Purpose

`ScanAIAnalysis` sits on completed Scan Detail, above reports and findings. It uses its own query
(`queryKeys.scans.analysis(scanId)`), not the scan payload. `unavailable` renders nothing.
`not_requested` and `failed` show footer button `Explain this scan` (`scan-ai-request`).
`pending`/`processing` poll every 3s for at most 5 minutes (`aria-live="polite"`). `completed`
renders executive summary, plain-language summary, priority actions, per-finding explanations, and a
`Disclosure` for assessment details and uncertainties. A POST 409 refetches GET. Load failures use
`scan-ai-retry` (`Couldn't load the overview.`). Contextual Q&A is [context-ai](./context-ai.md), not
this card.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `getScanAnalysis` / `requestScanAnalysis` | GET and POST `/scans/{id}/analysis`. | `frontend/src/api/scans.ts:66`, `:75` |
| `ScanAIAnalysis` | Exhaustive `switch` on `status`; receives `findings` for title lookup. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:32` |
| `handleRequest` | Disables the button, POSTs, writes the cache, 409 → refetch. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:65` |
| `ScanDetail` | Mounts the card only on the completed branch. | `frontend/src/pages/ScanDetail.tsx:75` |

## How it connects

- Backend: [ai](/backend/ai.md).
- Home teaser: [home-ai-overview](./home-ai-overview.md).
- Scan findings stay visible regardless of AI status ([screens](./screens.md)).

## Notes / gotchas

- First GET `isPending` returns `null` (no skeleton). Analysis hanging must not block vulns/machines.
- No `dangerouslySetInnerHTML`. Overview text is plain React text.
- `FindingPanel` shows risk as `Math.round(risk_score)` plus ` of 100`, not `toFixed(2)`.
