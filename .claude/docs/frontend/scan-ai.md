---
type: Module
title: frontend scan to-do list
description: Fix-task list with ready, waiting, failed, unavailable, not-requested and empty states, shared language-specific analysis caching, and scanner fallback advice.
resource: frontend/src/pages/scans/TodoList.tsx
tags: [frontend, ai, scans, tanstack-query]
timestamp: 2026-10-23T00:00:00Z
---

# frontend scan to-do list

## Purpose

`TodoList` consumes the version-11 fix-task analysis on Scan Detail. Task order, ranks,
highest risk and checked source links come from the backend. The first task starts open.
Counts describe covered finding IDs; uncovered problems remain in the table below.
`not_checked` appears after the tasks. A disabled AI service shows the three scanner
recommendations with the highest risk. Empty analyses retain the scan-limit warning.

## Key classes / functions

| Name | What it does |
|------|--------------|
| `TodoList` | Reads and requests analysis for the UI language; request conflicts refetch the existing job. |
| `AnalysisWaiting` | Renders real research/group/synthesis progress and elapsed time from the job creation time. |
| `TaskRow` | Shows steps, checked source links, fallback and machine links; each task has a stable `todo-task-N` anchor. |
| `useScanAnalysis` | Shares `queryKeys.scans.analysis(scanId, language)` with problem views, machine advice and explanation pointers; polls active jobs for at most 20 minutes. |
| `FixTaskSteps` | Shared task advice for the vulnerability view and machine's best fix. |

## How it connects

- [backend AI](/backend/ai.md) supplies task ordering and source links.
- [result components](./nonexpert-results.md) use per-finding notes and matching task ranks.
- [context AI](./context-ai.md) is the separate explanation and chat surface.
- `ScanReports` is the outline Download report menu in `ScanDetailHeader`.

## Notes / gotchas

- Analyses before prompt version 11 read as `not_requested`; stored rows remain intact.
- Analysis loading does not block scan evidence.
- Request/load failures use toasts. The failed-job state offers a retry.
- The organisation-language setting described in the PRD is not implemented by this change.
