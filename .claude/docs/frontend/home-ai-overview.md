---
type: Module
title: frontend Home AI overview teaser
description: Home card for the latest successful scan's analysis status — links to Scan Detail when overview is missing, pending, or ready.
resource: frontend/src/pages/home/HomeAIOverview.tsx
tags: [frontend, ai, home]
timestamp: 2026-10-02T00:00:00Z
---

# frontend Home AI overview teaser

## Purpose

When `GET /home` includes `latest_successful_scan`, `Home` mounts `HomeAIOverview` above the attention
column. The component reuses `getScanAnalysis` and `queryKeys.scans.analysis(scanId, language)`, so it reads
the analysis row for the current UI language. It renders
nothing while loading, on error, or when status is `unavailable`. Other statuses show a compact card
(`data-testid="home-ai-overview"`) with hard-coded Portuguese copy (not yet moved to [i18n](./i18n.md)) and a link to the scan — including a CTA when
analysis was never requested.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `HomeAIOverview` | Status-specific teaser; does not POST analysis from Home. Shows the `home-ai-evidence-limit` line, plus the `evidenceLimitKey(latest_successful_scan.evidence_completeness)` line (`ai.partialLimit` or `ai.unknownLimit`). | `frontend/src/pages/home/HomeAIOverview.tsx:9` |
| `Home` | Passes `snapshot.latest_successful_scan`. | `frontend/src/pages/Home.tsx:102` |

## How it connects

- Full overview UI: [scan-ai](./scan-ai.md).
- Backend analysis read: [ai](/backend/ai.md).

## Notes / gotchas

- Pending/processing on Home does not poll — the card is static until the user opens Scan Detail.
