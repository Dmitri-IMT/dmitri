---
name: create-tasks
description: >-
  Phase 2 of the document-driven pipeline. Reads the human-approved flat Peirce specs
  in specs/NNN-feature-slug/ (TRUTH.md, ARCHITECTURE.md, DESIGN.md, optional
  INTEGRATION.md) and writes TASKS.md — small, testable tasks in the canonical
  orchestrator shape (Description / Dependencies / Target Files / Success Criteria /
  Status / Review Rejections), plus a dependency graph and status table. Use when the
  user says /create-tasks, "taskify this spec", "break this spec into tasks", or
  "write TASKS.md".
user-invocable: true
argument-hint: "Path to spec directory (e.g. specs/005-extensive-scan)"
---

# Create tasks from spec (`/create-tasks`)

Phase 2 of the Dmitri document-driven pipeline. You read the **human-approved flat
Peirce specs** and write **`TASKS.md` as a file** in the spec directory. You do **not**
implement application code and you do **not** create harness tasks — `TASKS.md` is the
ledger the **`feature-orchestrator`** drives.

## Pipeline position

```
/feature-planning  → flat specs written → [human approval gate]
/refine-specs      → optional grilling before approval
/create-tasks      → writes specs/NNN-…/TASKS.md   ← you are here
/feature-orchestrator → runs the per-task Coder → Tester → Reviewer loop on TASKS.md
```

`feature-orchestrator`'s Phase 2 expects a `TASKS.md` in the spec dir. This skill writes
it. (If `/create-tasks` is skipped, the orchestrator writes the same shape inline.)

## Inputs

The argument is a **path to a spec directory** (e.g. `specs/005-extensive-scan`). If
empty, pick the most recent `specs/NNN-…` by numeric prefix. If ambiguous, ask which
spec to taskify.

## Workflow

### 1. Read the approved specs (do all reads before analysis)

Read the flat docs in this order. Pass through whatever exists — `DESIGN.md` and
`INTEGRATION.md` are optional.

1. `TRUTH.md` — narrative, business rules, user stories, **verifiable acceptance
   criteria** (Given/When/Then), out-of-scope
2. `ARCHITECTURE.md` — pipeline fit, data/contract changes, and the **mandatory
   "New files and naming" table** (the source of every task's `Target Files`)
3. `DESIGN.md` — Textual screen flow, layout, key bindings, copy, widget ids (only when
   screens change)
4. `INTEGRATION.md` — only when a real cross-layer contract exists (rare here)
5. `decisions/DR-*.md` — accepted decisions; `open-questions/to-define.md` — unresolved
   gaps (both optional, present only when they have content)

Old folder-tree specs (`specs/000`–`004`) are not migrated; if you are handed one, fall
back to its `README.md` / `contracts/` / `architecture/README.md`, but still emit the
new `TASKS.md` file shape below.

### 2. Identify implementation atoms

Extract **implementation atoms** — the smallest units of work that:
- Produce a testable artifact (function, module, screen, behavior change)
- Have a clear "done" definition derivable from the acceptance criteria or the naming table
- Map to one or more rows in the `ARCHITECTURE.md` naming table (or `DESIGN.md` widgets)

Use the [decomposition guide](REFERENCE.md#decomposition-guide) to categorize atoms, and
cross-check that **every acceptance-criteria scenario in `TRUTH.md` maps to at least one
task**.

### 3. Order and group

Split scope finely, in this default order:

```
config/constants → discovery/pipeline → normalization (ScanPayload) → TUI screens → tests
```

- **Foundations first**: config constants, pure helpers, schema/`ScanPayload` changes
- **Core behavior next**: runners, two-pass scans, normalization
- **Integration / callers last**: wiring new modules into existing call sites
- **Group into parallel tracks** when atoms share no dependencies (e.g. "Config &
  Pipeline" vs "TUI Screens"), as in `specs/004-nspi-scan-mode/TASKS.md`

### 4. Write TASKS.md

Write **`specs/NNN-feature-slug/TASKS.md`** by copying `specs/_templates/TASKS.md` and
filling it in. Each task uses the canonical orchestrator shape:

```markdown
## Task N: {Task name}
- **Description**: {what to implement; reference the governing spec file}
- **Dependencies**: {task numbers, or —}
- **Target Files**: [{exact paths from the ARCHITECTURE.md naming table / DESIGN.md}]
- **Success Criteria**: {verifiable goals the reviewer can check}
- **Status**: PENDING
- **Review Rejections**: 0
```

Then add the **dependency graph** and the **status table** (see the template). Header
line: `{N} tasks. **Unblocked now: #…**`.

- Every `Target Files` path must come from the `ARCHITECTURE.md` naming table or
  `DESIGN.md` — do not invent paths.
- Every task starts `Status: PENDING` and `Review Rejections: 0` — the orchestrator owns
  these fields from here on; don't pre-fill statuses.

### 5. Honor the CLAUDE.md integration rule

When any task adds a parameter to `ScanOrchestrator` / `ScanRunner`, you **must** add
explicit task(s) (or `Target Files` entries) threading it through
`hardware-agent/src/agent/scanner/runner.py` (`ScanRunner`) **and**
`hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`). TUI scans
bypass `ScanOrchestrator.run()`, so a parameter that isn't threaded reaches no TUI scan.

### 6. Report

Print the path you wrote and a short summary: total task count, parallel tracks, and which
tasks are **unblocked now**. Then tell the operator the next step is **`/feature-orchestrator`**.

## Rules

- **Write a file, not harness tasks** — output is `TASKS.md`; do not call `TaskCreate` /
  `TaskUpdate`.
- **Reference spec files** in each `Description` (e.g. "per ARCHITECTURE.md naming table").
- **Verifiable `Success Criteria`** in every task — the reviewer gates on them.
- **One task per testable unit** — don't combine unrelated changes.
- **Never create tasks for out-of-scope items** marked "out of scope (v1)", "deferred", or
  "not v1" in `TRUTH.md` / `decisions/`, or anything in `open-questions/`.
- **Don't overwrite a TASKS.md the orchestrator is already driving** — if one exists with
  non-`PENDING` statuses or `Review Rejections > 0`, stop and confirm before regenerating.
- **Cap at ~15 tasks** — if decomposition yields more, merge related atoms.

## Depth

Decomposition categories, criteria→task mapping, dependency heuristics, and the task-body
template: [REFERENCE.md](REFERENCE.md). Canonical file shapes live in `specs/_templates/`.
