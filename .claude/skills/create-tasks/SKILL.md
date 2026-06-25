---
name: create-tasks
description: >-
  Analyze a versioned feature spec directory (specs/NNN-feature-slug/) and break
  it into small, testable implementation tasks with dependency ordering. Creates
  tasks via TaskCreate and wires blockedBy via TaskUpdate, then displays a
  summary table of parallel tracks and unblocked work. Use when user says
  /create-tasks, "taskify this spec", "break this spec into tasks", or "create
  tasks from spec".
user-invocable: true
argument-hint: "Path to spec directory (e.g. specs/002-agent-logs)"
---

# Create tasks from spec (`/create-tasks`)

## Inputs

The argument is a **path to a spec directory** (e.g. `specs/002-agent-logs`). If empty, look for the most recent spec under `specs/` by numeric prefix. If ambiguous, ask which spec to taskify.

## Workflow

### 1. Read the spec (do all reads before analysis)

Read every file in the spec directory tree. Prioritize in this order:

1. `README.md` — feature overview, problem, folder map
2. `decisions/*.md` — accepted design decisions (skip `record-template.md`)
3. `contracts/*.md` — normative schemas, layouts, naming rules
4. `architecture/README.md` — pipeline integration, data flow
5. `checklists/requirements.md` — release-readiness checklist
6. `testing/README.md` — test scope and suggested targets
7. `tech-stack/README.md` — platform notes, encoding, limits
8. `ui/README.md` — UX behavior tied to the feature
9. `interaction/README.md` — operator workflows
10. `notes/open-questions.md` — resolved items and deferred watchlist
11. `plans/`, `bugs/` — if non-empty

### 2. Identify implementation atoms

From the spec, extract **implementation atoms** — the smallest units of work that:
- Produce a testable artifact (function, module, behavior change)
- Have a clear "done" definition derivable from contracts or checklists
- Can be verified with unit tests before moving on

Use the [decomposition guide](REFERENCE.md#decomposition-guide) to categorize atoms.

### 3. Order and group

- **Foundations first**: data models, helpers, pure functions (no I/O dependencies)
- **Infrastructure next**: modules that set up directories, configs, schemas
- **Integration last**: wiring pieces together, updating existing callers
- **Group into parallel tracks** when atoms share no dependencies (e.g. "workspace track" vs "runner track")

### 4. Create tasks

For each atom, call `TaskCreate` with:
- **subject**: imperative verb + what (e.g. "Build run folder basename generator")
- **description**: what to implement, which spec files govern it, what tests to write
- **activeForm**: present-continuous for spinner (e.g. "Building basename generator")

### 5. Wire dependencies

Call `TaskUpdate` with `addBlockedBy` for each task that depends on another. Dependency rules:
- Migration depends on layout module
- Pruning depends on layout module
- Argv builder depends on basename generator
- Streaming runner depends on argv builder + basename generator
- Integration task depends on all component tasks it wires together
- UI/TUI updates depend on the modules they call

### 6. Display summary

Print a **summary table** showing:
- Parallel tracks with task numbers
- Dependency chain per track
- Which tasks are **unblocked** (ready to start now)
- Total task count

Format (example):

```
## Task Breakdown (N tasks, M parallel tracks)

### Track A — Workspace & Results (#1 → #2 → #3 → #8)
| # | Task | Blocked by |
|---|------|-----------|
| 1 | Create workspace layout module | — |
| 2 | Add legacy migration | #1 |
...

**Unblocked now:** #1, #4
```

## Rules

- **Reference spec files** in task descriptions (e.g. "per contracts/layout.md")
- **Include test expectations** in every task description
- **One task per testable unit** — don't combine unrelated changes
- **Never create tasks for out-of-scope items** marked "not v1" or "deferred" in decisions
- **Check for existing tasks** via TaskList before creating duplicates
- **Cap at ~15 tasks** — if decomposition yields more, merge related atoms

## Depth

Decomposition categories and checklist mapping: [REFERENCE.md](REFERENCE.md).
