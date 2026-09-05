---
type: Module
title: the Home snapshot hook
description: useHome() loads GET /home as one query and maps the snapshot to loading, error, blank, clear, or pending.
resource: frontend/src/hooks/useHome.ts
tags: [frontend, domain, verdict, tanstack-query, home]
timestamp: 2026-09-05T00:00:00Z
---

# the Home snapshot hook

## Purpose

Home answers "does anything need me?" from one snapshot. The server owns attention order, notices,
`review_count`, derived events, and activity sentences. `useHome()` is a single TanStack Query over
`getHome` and a five-state union the page can switch on.

## Key classes / functions

| Name | What it does | Ref |
|------|--------------|-----|
| `getHome(pages)` | `GET /home` with `attention_page`, `events_page`, `activity_page`. No `per_page` query param. | `frontend/src/api/home.ts:16` |
| `HOME_ATTENTION_PER_PAGE` / `HOME_EVENTS_PER_PAGE` / `HOME_ACTIVITY_PER_PAGE` | `8` / `5` / `8`. Mirror server constants; the client cannot override them. | `frontend/src/api/home.ts:12` |
| `queryKeys.home.snapshot(pages)` | Key includes the three page integers independently so one panel can page without resetting the others. | `frontend/src/api/queryKeys.ts` |
| `useHome(pages)` | One `useQuery` with `placeholderData: keepPreviousData`. After the first load, a page change never returns `loading`. | `frontend/src/hooks/useHome.ts:14` |
| `HomeView` | `loading` / `error` carry `retry`. `blank` / `clear` / `pending` carry `snapshot` plus `retry`. | `frontend/src/hooks/useHome.ts:5` |

## How it connects

- The wire type is `components['schemas']['HomeSnapshot']` from [api](./api.md).
- [screens](./screens.md)'s `Home` holds three `useState(1)` page integers and switches on `state`.
- `lib/review.ts` and `useHomeReview` are gone. Attention order and notices live in
  [`backend/src/api/services/home.py`](../backend/services.md).

## Notes / gotchas

- **`review_count` is the snapshot field**, not `attention.data.length`. Notices count toward it.
- **First load** renders `home-loading`. A later page change keeps the previous snapshot on screen.
- **One HTTP error** replaces the whole page. There is no per-panel error envelope.
- Home must not call `GET /scans` or `GET /findings`.

# Citations

[1] [specs/044-home-feed-and-attention-pagination/ARCHITECTURE.md](../../../specs/044-home-feed-and-attention-pagination/ARCHITECTURE.md)
[2] [specs/044-home-feed-and-attention-pagination/TRUTH.md](../../../specs/044-home-feed-and-attention-pagination/TRUTH.md)
