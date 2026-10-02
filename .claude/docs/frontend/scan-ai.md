---
type: Module
title: frontend AI overview card
description: Scan Detail card that GETs analysis status in the UI language, offers Explain this scan once per language, polls only while pending or processing, and renders the Groq overview in collapsible sections when completed.
resource: frontend/src/pages/scans/ScanAIAnalysis.tsx
tags: [frontend, ai, scans, tanstack-query]
timestamp: 2026-10-02T00:00:00Z
---

# frontend AI overview card

## Purpose

`ScanAIAnalysis` sits on completed Scan Detail, above the findings groups — it is the first thing a
finished scan renders. `ScanReports` (the PDF-download control) is no longer a card in this stack at
all: since DMI-179 it lives in `ScanSummaryStrip`, the scan-details strip above everything here, as a
borderless purple ghost button labelled "Scan reports" that opens a menu ("Explained"/"Technical")
into the existing preview dialog. It uses its own query
(`queryKeys.scans.analysis(scanId, language)`), not the scan payload. `language` comes from
[`useI18n`](./i18n.md) and is sent as `?language=` on GET and POST, so switching language reads a
different analysis row (often `not_requested`). `unavailable` renders an informational card explaining that analysis is disabled or unavailable; it does not fabricate a summary.
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
| `ScanAIAnalysis` | Exhaustive `switch` on `status`; receives `findings` for title lookup. Takes a required `completeness` (`EvidenceCompleteness`). A ready analysis shows the `scan-ai-evidence-limit` line (`ai.evidenceLimit`, plus `ai.partialLimit` or `ai.unknownLimit` from `lib/evidenceCompleteness.evidenceLimitKey`). | `frontend/src/pages/scans/ScanAIAnalysis.tsx:25` |
| `handleRequest` | Disables the button, POSTs for the current language, writes that language's cache entry, 409 → refetch. | `frontend/src/pages/scans/ScanAIAnalysis.tsx:59` |
| `ScanDetail` | Mounts the card only on the completed branch. | `frontend/src/pages/ScanDetail.tsx:84` |
| `downloadScanReport` / `ScanReports` | PDF download with `params: { language }`, so the explained report matches the UI language. `ScanReports` renders inside [`ScanSummaryStrip`](./screens.md) (DMI-179), not as a section here or a card at the page's end — see Purpose. | `frontend/src/api/scans.ts:89` |

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
