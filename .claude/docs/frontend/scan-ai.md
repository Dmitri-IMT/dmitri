---
type: Module
title: frontend AI overview card
description: Scan Detail card that GETs analysis status in the UI language, offers Explain this scan once per language, polls only while pending or processing, and renders the Groq overview in collapsible sections when completed.
resource: frontend/src/pages/scans/ScanAIAnalysis.tsx
tags: [frontend, ai, scans, tanstack-query]
timestamp: 2026-09-19T21:00:00Z
---

# frontend AI overview card

## Purpose

`ScanAIAnalysis` sits on completed Scan Detail, above reports and findings. It uses its own query
(`queryKeys.scans.analysis(scanId, language)`), not the scan payload. `language` comes from
[`useI18n`](./i18n.md) and is sent as `?language=` on GET and POST, so switching language reads a
different analysis row (often `not_requested`). `unavailable` renders nothing.
`not_requested` and `failed` show footer button `Explain this scan` (`scan-ai-request`).
`pending`/`processing` poll every 3s for at most 5 minutes (`aria-live="polite"`). `completed`
renders the executive summary, then `Disclosure` sections for the plain-language summary, priority
actions, per-finding explanations, and assessment details and uncertainties. A POST 409 refetches GET. Load failures use
`scan-ai-retry` (`Couldn't load the overview.`). Contextual Q&A is [context-ai](./context-ai.md), not
this card.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `getScanAnalysis` / `requestScanAnalysis` | GET and POST `/scans/{id}/analysis` with `params: { language }`. | `frontend/src/api/scans.ts:67`, `:78` |
| `ScanAIAnalysis` | Exhaustive `switch` on `status`; receives `findings` for title lookup. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:25` |
| `handleRequest` | Disables the button, POSTs for the current language, writes that language's cache entry, 409 → refetch. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:59` |
| `ScanDetail` | Mounts the card only on the completed branch. | `frontend/src/pages/ScanDetail.tsx:84` |
| `downloadScanReport` / `ScanReports` | PDF download with `params: { language }`, so the explained report matches the UI language. | `frontend/src/api/scans.ts:113` |

## How it connects

- Backend: [ai](/backend/ai.md).
- Home teaser: [home-ai-overview](./home-ai-overview.md).
- Scan findings stay visible regardless of AI status ([screens](./screens.md)).

## Notes / gotchas

- The automatic path on the backend creates only the `en` analysis. In `pt-BR` or `ru` the card
  shows `not_requested` until someone asks for that language.
- First GET `isPending` returns `null` (no skeleton). Analysis hanging must not block vulns/machines.
- No `dangerouslySetInnerHTML`. Overview text is plain React text.
- `FindingPanel` shows risk as `Math.round(risk_score)` plus ` of 100`, not `toFixed(2)`.
