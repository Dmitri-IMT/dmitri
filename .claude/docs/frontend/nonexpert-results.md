---
type: Module
title: frontend scan and machine result components
description: Story and meaning cards, shared risk-sorted expandable problems, click-open term hints, backend risk parts and one vulnerability view with AI/scanner/fixed states.
resource: frontend/src/components/VulnerabilityView.tsx
tags: [frontend, scans, hosts, ai, accessibility]
timestamp: 2026-10-23T00:00:00Z
---

# frontend scan and machine result components

## Purpose

Scan Detail interprets results before technical evidence: `StoryStrip`, `TodoList`,
`MeaningTable`, `ProblemsTable`, then `ItSections`. Machine Detail shows `MachineAbout`,
`MachineBestFix`, the same problems table without its Machine column, then IT sections.
Running, stopped and failed scan states still come from `scanDetailView`.

## Key classes / functions

| Name | What it does |
|------|--------------|
| `StoryStrip` | Code-owned network, machine-type counts, scan mode/duration and coverage; `terminated_by=completed` is a normal finish. |
| `coverageCounts` | Counts completed and incomplete coverage units and distinct affected machine addresses. |
| `MeaningTable` | Severity counts, monochrome bars and fixed timing copy; unknown or partial evidence never proves safety. |
| `ProblemsTable` | Risk sort, confirmed-evidence select, first five rows, Show more and deep-linked inline expansion. Machine labels have a 24-character cap including `...`, with full hover/accessibility text and cell-width clipping. |
| `VulnerabilityView` | AI title/cause/effect and one task, else scanner advice; waiting and fixed states; collapsed scores, provenance, observations and references. |
| `TermHint` | Click/keyboard Radix Popover with one open hint, Escape and outside dismissal; hover does not open it. |
| `RiskBreakdownHint` | Displays the four backend risk parts; it does not duplicate the risk formula. |
| `EvidenceDetails` / `evidencePresentation` | Recorded observations and localized method/confidence/status explanations, moved out of the removed finding panels. |
| `MachineBestFix` | Chooses the task covering the most of this machine's latest-scan findings; rank resolves ties. |
| `ScanDetailSection` | Counted IT disclosure; semantic hidden state while closed; `openToken` supports targeted deep links. |

## How it connects

- [scan AI](./scan-ai.md) and [context AI](./context-ai.md) supply advice and explanations.
- `DataTable` supports a final-column expansion trigger and visually hidden headers.
- Machine findings are filtered by both host ID and latest scan ID; all API pages are
  fetched before selecting the best task.

## Notes / gotchas

- EPSS 10% selects Likely; the hint bands are 50% very high, 10% high, otherwise low.
- pt-BR and ru hint copy still needs the owner's language review.
- Severity uses ink weight and lightness, without coloured tags.
