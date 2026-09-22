---
type: Module
title: frontend AI usage panel
description: Settings section that GETs org-wide Groq usage summaries and recent operations without exposing prompts or responses.
resource: frontend/src/pages/settings/AIUsagePanel.tsx
tags: [frontend, ai, settings]
timestamp: 2026-09-22T00:00:00Z
---

# frontend AI usage panel

## Purpose

`AIUsagePanel` is the third block on [Settings](./screens.md) (after account and before leave-org).
It loads `GET /api/v1/ai/usage` via `getAIUsage` with a fetch limit of 50, keyed with
`queryKeys.ai.usage(limit)`. The panel shows aggregate request/token/error counts and a table of
recent operations (model, latency, status), paginated client-side at 10 rows per page (DMI-179) with
the shared [`Pagination`](./tables.md) dot control. Copy states explicitly that prompts and responses
are not stored.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `getAIUsage` | `GET /ai/usage?limit=` (default 50, max 100). | `frontend/src/api/ai.ts:10` |
| `AIUsagePanel` | Pending, error-with-retry, and ready states; `data-testid="settings-ai-usage"`. Slices the fetched page into 10-row pages locally (`USAGE_PER_PAGE`) and pads the `<tbody>` with `aria-hidden` spacer rows on a short last page, so the table's height never changes between pages — without the padding, a shorter last page shrinks the document and flashes the window scrollbar. | `frontend/src/pages/settings/AIUsagePanel.tsx:18` |
| `Settings` | Renders `<AIUsagePanel />` below the account `<hr>`. | `frontend/src/pages/Settings.tsx:101` |

## How it connects

- Backend: [ai](/backend/ai.md) (`get_ai_usage`, `AIUsageRecord`).
- API layer: [api](./api.md) (`queryKeys.ai`).

## Notes / gotchas

- `retry: false` — a failed load does not spam the API; the user retries manually.
