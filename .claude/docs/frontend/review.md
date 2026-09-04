---
type: Module
title: the verdict derivation and the Home read hook
description: deriveReview() — the pure rule table behind Home's one-sentence verdict — and useHomeReview(), which composes four reads into one discriminated union.
resource: frontend/src/lib/review.ts
tags: [frontend, domain, verdict, tanstack-query]
timestamp: 2026-09-04T00:00:00Z
---

# the verdict derivation and the Home read hook

## Purpose

Home's whole product claim — "does anything need me?" — is decided here, deliberately away from the
DOM. `deriveReview()` is pure and synchronous, so the entire rule table is testable without a
render; `useHomeReview()` is the thin shell that fetches, feeds it, and collapses loading/error into
one union the page can switch over.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `STALE_COVERAGE_DAYS` | `3`. Declared once and referenced by name everywhere, tests included — the only place the number appears. | `frontend/src/lib/review.ts:7` |
| `deriveReview({ latestScan, latestSuccessfulScan, criticalFindings, highFindings, now })` | Returns `{ reviewCount, deckFindings, scanItem, coverageItem }`. Pure: no React, no network, and `now` is injected rather than read from the wall clock. | `frontend/src/lib/review.ts:37` |
| `deckFindings` ordering | Critical → high, newest-first within each severity — imposed here, because the API guarantees no caller-chosen order. Consumed by [screens](./screens.md)'s `AttentionTable`, not a carousel. | `frontend/src/lib/review.ts:44` |
| `useHomeReview()` | Four TanStack Query reads → `deriveReview()` → one `HomeReview` union plus `retry()`. Keys come from [api](./api.md)'s `queryKeys` (`scans.latest`, `findings.list`). The two scan reads are plain `useQuery`; the two findings reads are one `useQueries` over `HOME_SEVERITIES`. | `frontend/src/hooks/useHomeReview.ts:30` |
| `HomeReview` | `{ state: 'loading' \| 'blank' \| 'clear' \| 'pending' \| 'error' }`; only `clear`/`pending` carry verdict data, so a partial render is unrepresentable. | `frontend/src/hooks/useHomeReview.ts:23` |

## How it connects

- Reads flow in from [api](./api.md)'s `scans.ts` and `findings.ts` — the
  **envelopes**, not their `data` arrays.
- The union is consumed by [screens](./screens.md)'s `Home`, which renders exactly one variant.

## Notes / gotchas

- **`reviewCount` comes from the envelopes' `total`, never `deckFindings.length`.** The attention
  table shows at most 100 rows; a scan with 37 criticals must say 37 even if fewer rows are held.
- **Two scan reads, not one.** Staleness is measured against `latestSuccessfulScan`, so a *recent
  failed* scan cannot mask stale coverage.
- **Blank is keyed off the unfiltered `latestScan` read** (`total === 0` on a `200`), never off a
  `404` — a 404 is an error, not an empty network.
- **Any** of the four reads failing yields `error`; there is no partial verdict.
- **The findings reads gate on `skipToken`, not `enabled`.**
- **`FindingDeck` and `ReviewItemCard` are gone** (spec 042). Pending state renders `AttentionTable`
  plus `AttentionNotices` for scan/coverage sentences.

# Citations

[1] [specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md](../../../specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md)
[2] [specs/042-design-system/TRUTH.md](../../../specs/042-design-system/TRUTH.md)
